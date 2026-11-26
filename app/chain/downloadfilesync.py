import time
from pathlib import Path
from typing import List, Optional

from app.chain import ChainBase
from app.db.downloadhistory_oper import DownloadHistoryOper
from app.helper.builtinconf import download_file_sync_conf
from app.helper.service import ServiceConfigHelper
from app.log import logger
from app.schemas.types import SystemConfigKey


class DownloadFileSyncChain(ChainBase):
    # 上次按需同步时间，用于节流：目录监控可能瞬时触发多次
    _last_trigger_at: float = 0.0
    # 种子内容/保存路径 -> (种子Hash, 下载器)
    _path_index: dict = {}
    # 索引构建时间戳，用于过期重建
    _index_built_at: float = 0.0
    # 索引有效期（秒）：目录监控是高频路径，过期后按需重建而非每次查询
    _INDEX_TTL: float = 300.0
    # 新鲜索引未命中后的主动刷新节流（秒），避免手工文件批量事件反复全量查询
    _MISS_REFRESH_TTL: float = 30.0
    # 上次未命中触发索引刷新的时间
    _miss_refresh_at: float = 0.0
    """
    下载文件同步链

    定时读取下载器中处于「可转移」状态的种子文件列表，落库为下载文件记录，
    供整理链判断种子是否完成、以及媒体同步删除时反查种子来源使用。
    原为独立插件能力，本分支内置为定时任务。

    除定时轮询外，目录监控发现新媒体文件时也会触发一次按需同步：
    这样刚入库就删除的场景不会因为等不到下一个同步周期而丢失对应记录。
    """

    def _sync_torrent_files(self, torrent_hash: str, downloader: Optional[str]) -> int:
        """
        同步单个种子的文件列表。

        :param torrent_hash: 种子 Hash
        :param downloader: 下载器名称
        :return: 新增的文件记录数
        """
        files = self.torrent_files(tid=torrent_hash, downloader=downloader)
        if not files:
            return 0

        downloadhis = DownloadHistoryOper()
        history = downloadhis.get_by_hash(download_hash=torrent_hash)
        # 优先问下载器：种子可能由外部添加，此时不存在下载历史；
        # 下载历史里的 path 还可能因移动任务而过时
        save_path = self._resolve_save_path(torrent_hash, downloader)
        if not save_path and history and history.path:
            save_path = str(history.path)
        if save_path:
            # 顺带修复历史遗留的相对路径记录：早期同步拿不到保存目录，
            # 只写入了相对路径，回填后才能按绝对路径精确反查
            backfilled = downloadhis.backfill_savepath(torrent_hash, save_path)
            if backfilled:
                logger.debug(
                    f"下载文件同步：种子 {torrent_hash} 回填保存目录 {save_path}，"
                    f"修正 {backfilled} 条记录"
                )

        existing = {
            item.fullpath
            for item in downloadhis.get_files_by_hash(torrent_hash, state=1)
        }
        file_items: List[dict] = []
        for file in files:
            # qBittorrent 返回 name 为相对路径，拼接种子保存目录得到完整路径
            name = str(getattr(file, "name", "") or "")
            if not name:
                continue
            fullpath = (
                str(Path(save_path) / name).replace("\\", "/")
                if save_path
                else str(Path(name).as_posix())
            )
            if fullpath in existing:
                continue
            file_items.append(
                {
                    "downloader": downloader,
                    "download_hash": torrent_hash,
                    "fullpath": fullpath,
                    "savepath": save_path,
                    "filepath": name,
                    "torrentname": history.torrent_name if history else "",
                    "state": 1,
                }
            )

        if file_items:
            downloadhis.add_files(file_items)
            logger.info(
                f"下载文件同步：种子 {torrent_hash} 新增 {len(file_items)} 条文件记录"
            )
        return len(file_items)

    def _resolve_save_path(self, torrent_hash: str, downloader: Optional[str]) -> str:
        """
        从下载器查询种子的保存根目录。

        下载历史可能缺失（历史数据迁移、手动添加种子），此时不能拿不到路径
        就退化成相对路径：文件记录的 fullpath 是媒体库删除时反查种子的唯一键，
        落成相对路径会让这条种子永远无法被判定为已清空。

        :param torrent_hash: 种子 Hash
        :param downloader: 下载器名称
        :return: 保存根目录，查询不到时返回空字符串
        """
        try:
            torrents = self.list_torrents(
                hashs=torrent_hash,
                downloader=downloader,
                include_all_tags=True,
            )
        except Exception as err:  # pylint: disable=broad-except
            logger.debug(f"查询种子 {torrent_hash} 保存路径失败：{err}")
            return ""
        target = str(torrent_hash).lower()
        for torrent in torrents or []:
            if str(getattr(torrent, "hash", "") or "").lower() != target:
                continue
            # save_path 是保存根目录；content_path 是任务内容路径，
            # 单文件种子下它已含文件名，直接当根目录会拼出重复文件名，
            # 因此优先 save_path，缺失时再从 content_path 反推
            save_path = getattr(torrent, "save_path", None)
            if save_path:
                return str(save_path).replace("\\", "/").rstrip("/")
            content_path = getattr(torrent, "content_path", None)
            if content_path:
                content = Path(str(content_path).replace("\\", "/"))
                # 单文件种子的 content_path 即文件本身，根目录是它的父级
                return (content.parent if content.suffix else content).as_posix()
            return ""
        return ""

    def _build_path_index(self) -> None:
        """
        构建「保存路径 -> 种子」索引。

        一次列出下载器中全部种子的保存路径与内容路径，供事件按路径快速反查。
        相比每次事件全量同步下载器，这里只在索引缺失或过期时执行一次。

        注意 save_path 的语义是「保存根目录」而非任务内容目录：
        qBittorrent 对多文件种子返回的分类根目录（如 Downloads/Anime），
        若直接入索引会把同分类下所有文件都错误归到该种子。
        因此 save_path 只在「不是其它键的祖先目录」时才保留作兜底。
        """
        index: dict = {}
        fallbacks: list = []
        try:
            torrents = self.list_torrents() or []
        except Exception as err:  # pylint: disable=broad-except
            logger.debug(f"构建下载器路径索引失败：{err}")
            return
        for torrent in torrents:
            torrent_hash = getattr(torrent, "hash", None)
            if not torrent_hash:
                continue
            entry = (torrent_hash, getattr(torrent, "downloader", None))
            for attr in ("path", "content_path"):
                value = getattr(torrent, attr, None)
                if not value:
                    continue
                # 统一成无尾斜杠的字符串，便于前缀匹配
                key = str(value).replace("\\", "/").rstrip("/")
                if key:
                    index.setdefault(key, entry)
            save_path = getattr(torrent, "save_path", None)
            if save_path:
                key = str(save_path).replace("\\", "/").rstrip("/")
                if key:
                    fallbacks.append((key, entry))
        # save_path 兜底键：若它已是其它键的祖先目录（说明精确键已覆盖该任务），
        # 保留会把同分类下无关文件全部吞掉，必须丢弃
        for key, entry in fallbacks:
            if not any(other.startswith(f"{key}/") for other in index if other != key):
                index.setdefault(key, entry)
        type(self)._path_index = index
        type(self)._index_built_at = time.monotonic()
        logger.debug(f"下载器路径索引已更新，共 {len(index)} 条")

    def resolve_torrent_by_path(self, file_path: str):
        """
        按文件路径解析所属种子，不写库。

        供目录监控在整理时携带种子信息，使整理记录能关联到种子，
        从而支持后续按种子反查与联动删除。

        :param file_path: 文件路径
        :return: (种子Hash, 下载器)，未匹配返回 (None, None)
        """
        if not file_path:
            return None, None
        target = str(file_path).replace("\\", "/")
        now = time.monotonic()
        stale = (now - self._index_built_at) > self._INDEX_TTL
        if stale:
            self._build_path_index()
        matched = self._match_index(target)
        if (
                not matched
                and not stale
                and now - self._miss_refresh_at >= self._MISS_REFRESH_TTL
        ):
            # 索引可能早于本种子建立，刷新一次以覆盖新下载内容；
            # 节流避免批量手工文件事件把该兜底变成持续全量扫描。
            type(self)._miss_refresh_at = now
            self._build_path_index()
            matched = self._match_index(target)
        if not matched:
            return None, None
        return matched

    # 需要保留源文件的下载器类型：BT 客户端靠源文件继续做种，
    # Usenet 客户端下载的是可重新抓取的发布，不涉及做种
    _SEEDING_DOWNLOADER_TYPES = frozenset({"qbittorrent", "transmission", "rtorrent"})

    def resolve_seeding_torrent_by_path(self, file_path: str):
        """
        判断文件是否属于需要保种的 BT 任务。

        与 resolve_torrent_by_path 的区别：只匹配 BT 类下载器，
        避免把 Usenet 客户端的文件误判为「需要保种」而保留。

        :param file_path: 文件路径
        :return: (种子Hash, 下载器)，不属于 BT 任务时返回 (None, None)
        """
        download_hash, downloader = self.resolve_torrent_by_path(file_path)
        if not download_hash or not downloader:
            return None, None
        try:
            configs = ServiceConfigHelper.get_downloader_configs()
        except Exception:  # pylint: disable=broad-except
            return download_hash, downloader
        for conf in configs:
            if conf.name == downloader:
                if str(conf.type or "").lower() in self._SEEDING_DOWNLOADER_TYPES:
                    return download_hash, downloader
                return None, None
        return download_hash, downloader

    def resolve_and_sync_torrent_by_path(self, file_path: str):
        """
        按文件路径解析所属种子，并在命中时复用该结果执行精准同步。

        目录监控即使未启用精准同步也必须返回种子信息给整理链，
        因此解析不受功能开关控制；只有落库同步受配置和节流约束。

        :param file_path: 发生变化的文件路径
        :return: (种子Hash, 下载器)，未匹配返回 (None, None)
        """
        torrent_hash, downloader = self.resolve_torrent_by_path(file_path)
        if torrent_hash:
            self._sync_resolved_torrent(file_path, torrent_hash, downloader)
        return torrent_hash, downloader

    def _sync_resolved_torrent(self, file_path: str, torrent_hash: str, downloader: Optional[str]) -> int:
        """
        对已解析出的种子执行节流精准同步。
        """
        conf = download_file_sync_conf()
        if not conf.enabled or not file_path:
            return 0

        # 节流：瞬时大量文件事件只处理第一个，其余由索引复用
        throttle = max(0, int(conf.trigger_throttle_seconds or 0))
        now = time.monotonic()
        if throttle and now - self._last_trigger_at < throttle:
            logger.debug(f"目录监控触发过于频繁，跳过精准同步：{file_path}")
            return 0

        type(self)._last_trigger_at = now
        added = self._sync_torrent_files(torrent_hash, downloader)
        if added:
            logger.info(
                f"目录监控精准同步：{Path(file_path).name} -> 种子 {torrent_hash[:12]}，新增 {added} 条"
            )
        return added

    def _match_index(self, target: str):
        """
        在路径索引中找出文件所属的种子。

        取最长匹配的路径前缀，确保多级目录下命中最近的种子保存目录。

        :param target: 文件全路径
        :return: (种子Hash, 下载器)，未命中返回 None
        """
        best_key = ""
        best_value = None
        for key, value in self._path_index.items():
            if target == key or target.startswith(f"{key}/"):
                if len(key) > len(best_key):
                    best_key, best_value = key, value
        return best_value

    def trigger_sync(self, reason: str = "") -> None:
        """
        目录监控发现新内容时按需触发一次同步。

        与定时任务的差别：带节流，避免一次批量入库触发几十次同步；
        未启用时直接返回，不产生额外开销。

        :param reason: 触发原因，仅用于日志
        """
        conf = download_file_sync_conf()
        if not conf.enabled:
            return
        # 节流窗口：同一窗口内只同步一次
        throttle = max(0, int(conf.trigger_throttle_seconds or 0))
        now = time.monotonic()
        if throttle and now - self._last_trigger_at < throttle:
            logger.debug(f"下载文件同步按需触发过于频繁，跳过（{reason}）")
            return
        type(self)._last_trigger_at = now
        logger.info(f"目录监控发现新内容，立即同步下载器（{reason}）")
        self.process()

    def process(self) -> None:
        """
        同步下载器中全部种子的文件列表。

        不能只同步「可转移」状态的种子：该状态表示「已完成且未整理」，
        种子一旦整理入库就会被打上已整理标签而脱离这个范围。同步的目的是
        记录每个种子包含哪些文件，供后续判断种子是否已清空，整理过的种子
        同样需要，否则媒体库删除时查不到清单，只能保守暂停。
        """
        conf = download_file_sync_conf()
        if not conf.enabled:
            logger.debug("下载文件同步未启用，跳过本次同步")
            return

        downloaders = ServiceConfigHelper.get_downloader_configs()
        if not downloaders:
            logger.debug("未配置下载器，跳过下载文件同步")
            return

        # 按配置筛选下载器
        selected = {name for name in (conf.downloaders or []) if name}
        total = 0
        synced = 0
        limit_reached = False
        for downloader_conf in downloaders:
            if limit_reached:
                break
            downloader_name = downloader_conf.name
            if selected and downloader_name not in selected:
                continue
            # 取全部状态：只同步待整理种子会让已入库的种子永远没有文件清单
            torrents = self.list_torrents(
                downloader=downloader_name,
                include_all_tags=True,
            )
            if not torrents:
                continue
            for torrent in torrents:
                if not torrent.hash:
                    continue
                # 限制单次同步数量，避免首次运行长时间占用
                if conf.max_torrents and synced >= conf.max_torrents:
                    logger.info(
                        f"下载文件同步已达到单次上限 {conf.max_torrents} 个种子，本轮结束"
                    )
                    limit_reached = True
                    break
                synced += 1
                try:
                    total += self._sync_torrent_files(
                        torrent_hash=torrent.hash,
                        downloader=downloader_name,
                    )
                except Exception as err:
                    logger.error(
                        f"下载文件同步失败：{downloader_name} - {torrent.hash} - {err}"
                    )
        logger.info(
            f"下载文件同步完成，本次处理 {synced} 个种子、新增 {total} 条文件记录"
        )
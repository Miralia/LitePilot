import time
from pathlib import Path
from typing import List, Optional

from app.chain import ChainBase
from app.db.downloadhistory_oper import DownloadHistoryOper
from app.helper.builtinconf import download_file_sync_conf
from app.helper.service import ServiceConfigHelper
from app.log import logger
from app.schemas.types import SystemConfigKey, TorrentStatus


class DownloadFileSyncChain(ChainBase):
    # 上次按需同步时间，用于节流：目录监控可能瞬时触发多次
    _last_trigger_at: float = 0.0
    # 种子内容路径(精确) -> (种子Hash, 下载器)
    _content_index: dict = {}
    # 种子保存目录(兜底) -> (种子Hash, 下载器)
    _path_index: dict = {}
    # 索引构建时间戳，用于过期重建
    _index_built_at: float = 0.0
    # 索引有效期（秒）：目录监控是高频路径，过期后按需重建而非每次查询
    _INDEX_TTL: float = 300.0
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
        save_path = str(history.path) if history and history.path else ""

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
                    "torrentname": history.torrent if history else "",
                    "state": 1,
                }
            )

        if file_items:
            downloadhis.add_files(file_items)
            logger.info(
                f"下载文件同步：种子 {torrent_hash} 新增 {len(file_items)} 条文件记录"
            )
        return len(file_items)

    def _build_path_index(self) -> None:
        """
        构建「保存路径 -> 种子」索引。

        一次列出下载器中全部种子的保存路径与内容路径，供事件按路径快速反查。
        相比每次事件全量同步下载器，这里只在索引缺失或过期时执行一次。
        """
        index: dict = {}
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
            for attr in ("path", "save_path", "content_path"):
                value = getattr(torrent, attr, None)
                if not value:
                    continue
                # 统一成无尾斜杠的字符串，便于前缀匹配
                key = str(value).replace("\\", "/").rstrip("/")
                if key:
                    index[key] = entry
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
        stale = (
                not self._content_index
                or (now - self._index_built_at) > self._INDEX_TTL
        )
        if stale:
            self._build_path_index()
        matched = self._match_index(target)
        if not matched and not stale:
            # 索引可能早于本种子建立，重建一次以覆盖新下载内容
            self._build_path_index()
            matched = self._match_index(target)
        if not matched:
            return None, None
        return matched

    def sync_torrent_by_path(self, file_path: str) -> int:
        """
        按文件路径定位所属种子，仅同步该种子的文件记录。

        目录监控发现新文件时调用：优先查内存索引（零额外请求），
        未命中时重建索引再匹配；命中后只拉取单个种子的文件列表，
        避免全量同步带来的性能压力。

        :param file_path: 发生变化的文件路径
        :return: 新增的文件记录数，未匹配到种子时返回 0
        """
        conf = download_file_sync_conf()
        if not conf.enabled or not file_path:
            return 0

        target = str(file_path).replace("\\", "/")
        # 节流：瞬时大量文件事件只处理第一个，其余由索引复用
        throttle = max(0, int(conf.trigger_throttle_seconds or 0))
        now = time.monotonic()
        if throttle and now - self._last_trigger_at < throttle:
            logger.debug(f"目录监控触发过于频繁，跳过精准同步：{file_path}")
            return 0

        torrent_hash, downloader = self.resolve_torrent_by_path(file_path)
        if not torrent_hash:
            logger.debug(f"路径未匹配到下载器种子，跳过精准同步：{file_path}")
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
        for index in (self._content_index, self._path_index):
            best_key = ""
            best_value = None
            for key, value in index.items():
                if target == key or target.startswith(f"{key}/"):
                    if len(key) > len(best_key):
                        best_key, best_value = key, value
            if best_value:
                return best_value
        return None

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
        同步所有处于可转移状态的种子的文件列表。
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
            torrents = self.list_torrents(
                status=TorrentStatus.TRANSFER,
                downloader=downloader_name,
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
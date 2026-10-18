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
from pathlib import Path
from typing import List, Optional

from app.chain import ChainBase
from app.db.downloadhistory_oper import DownloadHistoryOper
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.service import ServiceConfigHelper
from app.log import logger
from app.schemas.types import SystemConfigKey, TorrentStatus


class DownloadFileSyncChain(ChainBase):
    """
    下载文件同步链

    定时读取下载器中处于「可转移」状态的种子文件列表，落库为下载文件记录，
    供整理链判断种子是否完成、以及媒体同步删除时反查种子来源使用。
    原为独立插件能力，本分支内置为定时任务。
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

    def process(self) -> None:
        """
        同步所有处于可转移状态的种子的文件列表。
        """
        # 同步历史记录开关：关闭时不做任何落库
        if not SystemConfigOper().get(SystemConfigKey.DownloadFileSync):
            logger.debug("下载文件同步未启用，跳过本次同步")
            return

        downloaders = ServiceConfigHelper.get_downloader_configs()
        if not downloaders:
            logger.debug("未配置下载器，跳过下载文件同步")
            return

        total = 0
        for downloader_conf in downloaders:
            downloader_name = downloader_conf.name
            torrents = self.list_torrents(
                status=TorrentStatus.TRANSFER,
                downloader=downloader_name,
            )
            if not torrents:
                continue
            for torrent in torrents:
                if not torrent.hash:
                    continue
                try:
                    total += self._sync_torrent_files(
                        torrent_hash=torrent.hash,
                        downloader=downloader_name,
                    )
                except Exception as err:
                    logger.error(
                        f"下载文件同步失败：{downloader_name} - {torrent.hash} - {err}"
                    )
        logger.info(f"下载文件同步完成，本次新增 {total} 条文件记录")
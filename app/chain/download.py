from typing import List, Optional, Union

from app import schemas
from app.chain import ChainBase
from app.core.event import Event, eventmanager
from app.log import logger
from app.schemas import Notification
from app.schemas.types import EventType, MessageChannel, NotificationType, TorrentStatus
from app.utils.string import StringUtils


class DownloadChain(ChainBase):
    """
    下载器状态处理链
    """

    def remote_downloading(self, channel: MessageChannel, userid: Union[str, int] = None, source: Optional[str] = None):
        """
        查询正在下载的任务，并发送消息
        """
        torrents = self.list_torrents(status=TorrentStatus.DOWNLOADING)
        if not torrents:
            self.post_message(Notification(
                channel=channel,
                source=source,
                mtype=NotificationType.Download,
                title="没有正在下载的任务！",
                userid=userid,
                save_history=False,
            ))
            return
        # 发送消息
        title = f"共 {len(torrents)} 个任务正在下载："
        messages = []
        index = 1
        for torrent in torrents:
            messages.append(f"{index}. {torrent.title} "
                            f"{StringUtils.str_filesize(torrent.size)} "
                            f"{round(torrent.progress, 1)}%")
            index += 1
        self.post_message(Notification(
            channel=channel,
            source=source,
            mtype=NotificationType.Download,
            title=title,
            text="\n".join(messages),
            userid=userid,
            save_history=False,
        ))

    def remove_downloading(self, hash_str: str, name: Optional[str] = None) -> bool:
        """
        删除下载任务
        """
        return self.remove_torrents(hashs=[hash_str], downloader=name)

    @eventmanager.register(EventType.DownloadFileDeleted)
    def download_file_deleted(self, event: Event):
        """
        下载文件删除时，同步删除下载任务
        """
        if not event:
            return
        hash_str = event.event_data.get("hash")
        if not hash_str:
            return
        logger.warn(f"检测到下载源文件被删除，删除下载任务（不含文件）：{hash_str}")
        # 先查询种子
        torrents: List[schemas.DownloaderTorrent] = self.list_torrents(hashs=[hash_str])
        if torrents:
            self.remove_torrents(hashs=[hash_str], delete_file=False)
        else:
            logger.info(f"没有在下载器中查询到 {hash_str} 对应的下载任务")

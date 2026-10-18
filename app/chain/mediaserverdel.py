import time
from pathlib import Path
from typing import List, Optional, Tuple

from app.chain import ChainBase
from app.chain.download import DownloadChain
from app.chain.storage import StorageChain
from app.core.config import settings
from app.core.event import eventmanager
from app.db.downloadhistory_oper import DownloadHistoryOper
from app.db.transferhistory_oper import TransferHistoryOper
from app.helper.builtinconf import sync_del_by_media_server_conf
from app.log import logger
from app.schemas import FileItem
from app.schemas.message import Notification
from app.schemas.types import EventType, MediaImageType, MediaType, NotificationType

# 各媒体服务器 / 插件上报的删除事件名
DELETE_EVENTS = frozenset({"deep.delete", "media_del"})


class MediaServerDelChain(ChainBase):
    """
    媒体服务器删除同步链

    监听媒体服务器（Emby）的媒体删除事件，反查本地整理历史并同步清理：
    删除整理记录、删除媒体库中的残留文件、按需删除下载器任务与源文件。
    原为独立插件能力，本分支内置为事件处理器，只处理本地存储。
    """

    def __init__(self):
        """
        初始化删除同步链。
        """
        super().__init__()
        self.transferhis = TransferHistoryOper()
        self.downloadhis = DownloadHistoryOper()

    @staticmethod
    def _remove_empty_parents(path: Path, stop_at: Optional[Path] = None) -> None:
        """
        自下而上删除空目录，遇到非空目录或指定边界即停止。

        :param path: 起始路径（文件或目录）
        :param stop_at: 停止删除的上级目录边界
        """
        current = path if path.is_dir() else path.parent
        while current and current != current.parent:
            if stop_at and current == stop_at:
                return
            try:
                if any(current.iterdir()):
                    return
                current.rmdir()
                logger.info(f"已删除空目录：{current}")
            except OSError:
                return
            current = current.parent

    def _query_history(
            self,
            media_type: str,
            media_name: str,
            media_path: str,
            tmdb_id: int,
            season_num: Optional[str],
            episode_num: Optional[str],
    ) -> Tuple[str, List]:
        """
        按删除事件的粒度反查整理历史。

        :param media_type: 媒体类型（Movie/TV）
        :param media_name: 媒体名称
        :param media_path: 媒体路径
        :param tmdb_id: TMDB ID
        :param season_num: 季号
        :param episode_num: 集号
        :return: 描述文本与整理历史列表
        """
        season = str(season_num).rjust(2, "0") if season_num and str(season_num).isdigit() else None
        episode = str(episode_num).rjust(2, "0") if episode_num and str(episode_num).isdigit() else None
        mtype = MediaType.MOVIE if media_type in ("Movie", "MOV") else MediaType.TV

        if mtype == MediaType.MOVIE:
            return (
                f"电影 {media_name} {tmdb_id}",
                self.transferhis.get_by(tmdbid=tmdb_id, mtype=mtype.value, dest=media_path),
            )
        if not season:
            return (
                f"剧集 {media_name} {tmdb_id}",
                self.transferhis.get_by(tmdbid=tmdb_id, mtype=mtype.value),
            )
        if not episode:
            return (
                f"剧集 {media_name} S{season} {tmdb_id}",
                self.transferhis.get_by(
                    tmdbid=tmdb_id, mtype=mtype.value, season=f"S{season}"
                ),
            )
        return (
            f"剧集 {media_name} S{season}E{episode} {tmdb_id}",
            self.transferhis.get_by(
                tmdbid=tmdb_id,
                mtype=mtype.value,
                season=f"S{season}",
                episode=f"E{episode}",
                dest=media_path,
            ),
        )

    def _delete_source(self, history, conf=None) -> Tuple[str, Optional[str]]:
        """
        删除整理记录的源文件与媒体库文件，并按需处理下载任务。

        :param history: 整理历史记录
        :param conf: 联动删除配置，为空时读取当前配置
        :return: (种子处理结果, 种子hash)。结果为 deleted/paused/kept/none/error
        """
        conf = conf or sync_del_by_media_server_conf()
        storagechain = StorageChain()

        # 媒体库文件（硬链接或移动后的目标文件）
        if history.dest and Path(history.dest).exists():
            storagechain.delete_media_file(
                FileItem(storage=history.dest_storage or "local", path=history.dest)
            )

        # 下载源文件：仅本地源、且整理方式不是移动时删除；可由配置关闭
        src_path = Path(history.src) if history.src else None
        if (
            conf.delete_source_file
            and src_path
            and src_path.suffix in settings.RMT_MEDIAEXT
            and (history.src_storage or "local") == "local"
            and history.mode != "move"
            and src_path.exists()
        ):
            logger.info(f"正在删除下载源文件：{history.src}")
            if storagechain.delete_file(
                FileItem(storage=history.src_storage or "local", path=history.src)
            ) and conf.remove_empty_dirs:
                self._remove_empty_parents(src_path)

        # 源文件已全部删除时，删除下载器任务；可由配置关闭
        torrent_hash = history.download_hash
        if not (conf.delete_torrent and torrent_hash):
            return "none", torrent_hash
        # 用户可能已在联动删除之前手动删掉种子任务。
        # 这种情况下没有种子可处理，整理记录照常删除即可，不应报错。
        if not self._torrent_exists(torrent_hash, history.downloader):
            logger.info(f"种子 {torrent_hash} 已不存在于下载器，仅删除整理记录")
            return "gone", torrent_hash
        self.downloadhis.delete_file_by_fullpath(fullpath=history.src)
        remain = self.downloadhis.get_files_by_hash(download_hash=torrent_hash, state=1)
        if remain:
            # 种子还有内容没被删除：暂停而不是删除，等后续事件把剩余内容删完再移除任务
            logger.info(
                f"种子 {torrent_hash} 仍有 {len(remain)} 个文件未删除，暂停下载任务"
            )
            try:
                self.stop_torrents(hashs=torrent_hash)
            except Exception as err:  # pylint: disable=broad-except
                logger.error(f"暂停种子 {torrent_hash} 失败：{err}")
                return "error", torrent_hash
            return "paused", torrent_hash
        logger.info(f"种子 {torrent_hash} 文件已全部删除，删除下载任务")
        if DownloadChain().remove_downloading(hash_str=torrent_hash):
            self.eventmanager.send_event(
                EventType.DownloadDeleted,
                {"hash": torrent_hash},
            )
            return "deleted", torrent_hash
        return "error", torrent_hash

    def _torrent_exists(self, torrent_hash: str, downloader: Optional[str] = None) -> bool:
        """
        检查种子是否仍存在于下载器。

        :param torrent_hash: 种子哈希
        :param downloader: 下载器名称
        :return: 存在时返回 True；查询失败按存在处理，避免误跳过
        """
        if not torrent_hash:
            return False
        try:
            # 需要包含未打标签的任务，否则用户手动添加的种子会被误判为不存在
            torrents = self.list_torrents(
                hashs=torrent_hash,
                downloader=downloader,
                include_all_tags=True,
            )
        except Exception as err:  # pylint: disable=broad-except
            logger.debug(f"查询种子 {torrent_hash} 状态失败，按存在处理：{err}")
            return True
        if torrents is None:
            # 查询不可用时保守处理，交给后续逻辑判断
            return True
        return bool(torrents)

    def sync_del(
            self,
            media_type: str,
            media_name: str,
            media_path: str,
            tmdb_id: int,
            season_num: Optional[str] = None,
            episode_num: Optional[str] = None,
    ) -> None:
        """
        同步删除媒体服务器中已删除的媒体对应的本地记录与文件。

        :param media_type: 媒体类型（Movie/TV）
        :param media_name: 媒体名称
        :param media_path: 媒体路径
        :param tmdb_id: TMDB ID
        :param season_num: 季号
        :param episode_num: 集号
        """
        if not media_path:
            return
        # 媒体服务器已删除，但文件仍在（如重新整理），不做处理
        if Path(media_path).exists():
            logger.warn(f"路径 {media_path} 仍然存在，跳过同步删除")
            return

        msg, histories = self._query_history(
            media_type=media_type,
            media_name=media_name,
            media_path=media_path,
            tmdb_id=tmdb_id,
            season_num=season_num,
            episode_num=episode_num,
        )
        if not histories:
            logger.warn(f"{msg} 未查询到可删除的整理记录，跳过同步删除")
            return

        conf = sync_del_by_media_server_conf()
        # 媒体服务器上报的删除粒度未必等于实际删除的文件范围：
        # 批量删除时 Emby 只发一条 Series 级事件，不带具体集数。
        # 因此以「媒体库文件是否真的不存在」为准，只清理确实已被移除的记录；
        # 文件仍存在的记录保留，等后续事件再处理，避免把未删内容一并清掉。
        pending = []
        for history in histories:
            if history.dest and Path(history.dest).exists():
                logger.info(f"整理记录 {history.id} 的目标文件仍存在，保留待后续同步：{history.dest}")
                continue
            pending.append(history)
        histories = pending
        if not histories:
            logger.info(f"{msg} 没有已被移除的文件，跳过同步删除")
            return
        logger.info(f"正在同步删除{msg}，共 {len(histories)} 条整理记录")
        deleted = 0
        failed = 0
        dry_run_items: List[str] = []
        torrent_stats = {"deleted": 0, "paused": 0, "gone": 0, "error": 0}
        for history in histories:
            # 记录由 tmdbid + 季 + 集精确定位，直接遵循媒体服务器的删除意图，
            # 不再用标题做二次校验（译名写法差异会造成误跳过）
            if conf.dry_run:
                dry_run_items.append(f"{history.title}（{history.dest}）")
                logger.info(
                    f"[试运行] 将删除整理记录 {history.id}（{history.title}）、"
                    f"目标 {history.dest}、源 {history.src}"
                )
                continue
            try:
                self.transferhis.delete(history.id)
                state, _hash = self._delete_source(history, conf=conf)
                if state in torrent_stats:
                    torrent_stats[state] += 1
                deleted += 1
            except Exception as err:
                failed += 1
                logger.error(f"同步删除整理记录 {history.id} 失败：{err}")

        self._notify_result(
            msg=msg,
            conf=conf,
            deleted=deleted,
            failed=failed,
            dry_run_items=dry_run_items,
            torrent_stats=torrent_stats,
            tmdb_id=tmdb_id,
            media_type=media_type,
            season_num=season_num,
            episode_num=episode_num,
        )

    def _notify_result(
            self,
            msg: str,
            conf,
            deleted: int,
            failed: int,
            dry_run_items: List[str],
            torrent_stats: Optional[dict] = None,
            tmdb_id: Optional[int] = None,
            media_type: Optional[str] = None,
            season_num: Optional[str] = None,
            episode_num: Optional[str] = None,
    ) -> None:
        """
        把本次联动删除的结果发送到通知渠道。

        通知内容对齐原插件：附带封面图，并说明种子是删除、暂停还是保留。

        :param msg: 删除对象的描述
        :param conf: 联动删除配置
        :param deleted: 成功删除的记录数
        :param failed: 删除失败的记录数
        :param dry_run_items: 试运行模式下待删除项
        :param torrent_stats: 种子处理统计
        :param tmdb_id: TMDB ID，用于取图
        :param media_type: 媒体类型
        :param season_num: 季号
        :param episode_num: 集号
        """
        try:
            stats = torrent_stats or {}
            if conf.dry_run:
                if not dry_run_items:
                    return
                title = "媒体库同步删除（试运行）"
                lines = [msg, f"待删除记录 {len(dry_run_items)} 个"]
                lines.extend(f"· {item}" for item in dry_run_items[:10])
                if len(dry_run_items) > 10:
                    lines.append(f"… 另有 {len(dry_run_items) - 10} 条")
                image = None
            else:
                if not (deleted or failed):
                    return
                title = "媒体库同步删除任务完成"
                lines = [msg, f"删除记录 {deleted} 个"]
                if stats.get("deleted"):
                    lines.append(f"删除种子 {stats['deleted']} 个")
                if stats.get("paused"):
                    lines.append(f"暂停种子 {stats['paused']} 个（仍有未删除文件）")
                if stats.get("gone"):
                    lines.append(f"种子已手动删除 {stats['gone']} 个")
                if stats.get("error"):
                    lines.append(f"删种失败 {stats['error']} 个")
                if failed:
                    lines.append(f"删除记录失败 {failed} 个")
                image = self._obtain_notify_image(
                    tmdb_id=tmdb_id,
                    media_type=media_type,
                    season_num=season_num,
                    episode_num=episode_num,
                )
            lines.append(f"时间 {time.strftime('%Y-%m-%d %H:%M:%S')}")
            self.post_message(
                Notification(
                    mtype=NotificationType.Manual,
                    title=title,
                    text="\n".join(lines),
                    image=image,
                )
            )
        except Exception as err:  # pylint: disable=broad-except
            logger.error(f"发送联动删除通知失败：{err}")

    def _obtain_notify_image(
            self,
            tmdb_id: Optional[int],
            media_type: Optional[str],
            season_num: Optional[str] = None,
            episode_num: Optional[str] = None,
    ) -> str:
        """
        取通知用剧照，取不到时退回默认图标。

        :param tmdb_id: TMDB ID
        :param media_type: 媒体类型
        :param season_num: 季号
        :param episode_num: 集号
        :return: 图片地址
        """
        default_icon = "https://emby.media/notificationicon.png"
        if not tmdb_id:
            return default_icon
        mtype = MediaType.MOVIE if media_type in ("Movie", "MOV") else MediaType.TV
        try:
            image = self.obtain_specific_image(
                mediaid=tmdb_id,
                mtype=mtype,
                image_type=MediaImageType.Backdrop,
                season=int(season_num) if str(season_num or "").isdigit() else None,
                episode=int(episode_num) if str(episode_num or "").isdigit() else None,
            )
            return image or default_icon
        except Exception as err:  # pylint: disable=broad-except
            logger.debug(f"获取通知图片失败，使用默认图标：{err}")
            return default_icon

    def _resolve_tmdb_id(event_data, server_name: Optional[str]) -> Optional[int]:
        """
        单集或单季事件缺少 TMDB ID 时，从媒体服务器补齐。

        :param event_data: 媒体服务器事件信息
        :param server_name: 媒体服务器名称
        :return: TMDB ID，无法获取时返回 None
        """
        series_id = (event_data.json_object or {}).get("Item", {}).get("SeriesId")
        if not series_id:
            return None
        try:
            from app.helper.mediaserver import MediaServerHelper  # pylint: disable=import-outside-toplevel

            server = MediaServerHelper().get_service(server_name)
            if not server:
                return None
            item = server.instance.get_iteminfo(series_id)
            return int(item.tmdb_id) if item and item.tmdb_id else None
        except Exception as err:
            logger.error(f"获取剧集 TMDB ID 失败：{err}")
            return None

    @eventmanager.register(EventType.WebhookMessage)
    def sync_del_by_media_server(self, event) -> None:
        """
        监听媒体服务器删除事件并同步清理本地记录与文件。
        """
        if not event or not event.event_data:
            return
        conf = sync_del_by_media_server_conf()
        if not conf.enabled:
            return

        event_data = event.event_data
        event_type = getattr(event_data, "event", None)
        # 只处理删除类事件：Emby 官方 Webhooks 发 deep.delete，
        # EmbyScripterX 发 media_del，两者语义一致
        if not event_type or str(event_type) not in DELETE_EVENTS:
            return

        # 按配置限定媒体服务器
        allowed = {str(name) for name in (conf.servers or []) if name}
        if allowed and str(getattr(event_data, "server_name", "") or "") not in allowed:
            logger.debug(
                f"媒体服务器 {getattr(event_data, 'server_name', None)} 不在联动删除范围内，跳过"
            )
            return

        media_name = event_data.item_name
        media_path = event_data.item_path
        if not media_path:
            return

        media_type = event_data.item_type
        season_num = event_data.season_id
        episode_num = event_data.episode_id
        # 兼容 Emby 新版本 API 的整季删除
        if (event_data.json_object or {}).get("Item", {}).get("Type") == "Season":
            if not season_num and episode_num:
                season_num, episode_num = episode_num, None

        tmdb_id = event_data.tmdb_id
        if (season_num or episode_num) and not (tmdb_id and str(tmdb_id).isdigit()):
            tmdb_id = self._resolve_tmdb_id(event_data, event_data.server_name)
        if not tmdb_id or not str(tmdb_id).isdigit():
            logger.error(f"{media_name} 同步删除失败：未获取到 TMDB ID")
            return

        self.sync_del(
            media_type=media_type,
            media_name=media_name,
            media_path=media_path,
            tmdb_id=int(tmdb_id),
            season_num=season_num,
            episode_num=episode_num,
        )
from typing import Dict, List, Optional, Tuple, Union

from app import schemas
from app.chain import ChainBase
from app.core.context import MediaInfo
from app.core.event import Event, eventmanager
from app.core.meta import MetaBase
from app.db.mediaserver_oper import MediaServerOper
from app.log import logger
from app.schemas import ExistMediaInfo, NotExistMediaInfo, Notification
from app.schemas.types import EventType, MediaType, MessageChannel, NotificationType, TorrentStatus
from app.utils.media import build_media_key, resolve_media_identity
from app.utils.string import StringUtils


class DownloadChain(ChainBase):
    """
    下载器状态处理链
    """

    def get_no_exists_info(self, meta: MetaBase,
                           mediainfo: MediaInfo,
                           no_exists: Dict[int, Dict[int, NotExistMediaInfo]] = None,
                           totals: Dict[int, int] = None
                           ) -> Tuple[bool, Dict[Union[int, str], Dict[int, NotExistMediaInfo]]]:
        """
        检查媒体库，查询是否存在，对于剧集同时返回不存在的季集信息
        :param meta: 元数据
        :param mediainfo: 已识别的媒体信息
        :param no_exists: 在调用该方法前已经存储的不存在的季集信息，有传入时该函数搜索的内容将会叠加后输出
        :param totals: 电视剧每季的总集数
        :return: 当前媒体是否缺失，各标题总的季集和缺失的季集
        """
        media_source, media_id = resolve_media_identity(media=mediainfo)

        def __append_no_exists(_season: int, _episodes: list, _total: int, _start: int):
            """
            添加不存在的季集信息
            {tmdbid: [
                "season": int,
                "episodes": list,
                "total_episode": int,
                "start_episode": int
            ]}
            """
            mediakey = build_media_key(media_source, media_id)
            if not no_exists.get(mediakey):
                no_exists[mediakey] = {
                    _season: NotExistMediaInfo(
                        season=_season,
                        episodes=_episodes,
                        total_episode=_total,
                        start_episode=_start
                    )
                }
            else:
                no_exists[mediakey][_season] = NotExistMediaInfo(
                    season=_season,
                    episodes=_episodes,
                    total_episode=_total,
                    start_episode=_start
                )

        if not no_exists:
            no_exists = {}

        if not totals:
            totals = {}

        mediaserver = MediaServerOper()
        if mediainfo.type == MediaType.MOVIE:
            # 电影
            itemid = mediaserver.get_item_id(mtype=mediainfo.type.value,
                                             title=mediainfo.title,
                                             tmdbid=mediainfo.tmdb_id)
            exists_movies: Optional[ExistMediaInfo] = self.media_exists(mediainfo=mediainfo, itemid=itemid)
            if exists_movies:
                logger.info(f"媒体库中已存在电影：{mediainfo.title_year}")
                return True, {}
            return False, {}
        else:
            if not mediainfo.seasons:
                # 补充媒体信息
                mediainfo: MediaInfo = self.recognize_media(mtype=mediainfo.type,
                                                            tmdbid=mediainfo.tmdb_id,
                                                            doubanid=mediainfo.douban_id,
                                                            bangumiid=mediainfo.bangumi_id,
                                                            source=media_source,
                                                            mediaid=media_id,
                                                            episode_group=mediainfo.episode_group)
                if not mediainfo:
                    logger.error(f"媒体信息识别失败！")
                    return False, {}
                if not mediainfo.seasons:
                    logger.error(f"媒体信息中没有季集信息：{mediainfo.title_year}")
                    return False, {}
            # 电视剧
            itemid = mediaserver.get_item_id(mtype=mediainfo.type.value,
                                             title=mediainfo.title,
                                             tmdbid=mediainfo.tmdb_id,
                                             season=mediainfo.season)
            # 媒体库已存在的剧集
            exists_tvs: Optional[ExistMediaInfo] = self.media_exists(mediainfo=mediainfo, itemid=itemid)
            if not exists_tvs:
                # 所有季集均缺失
                for season, episodes in mediainfo.seasons.items():
                    if not episodes:
                        continue
                    # 全季不存在
                    if meta.sea \
                            and season not in meta.season_list:
                        continue
                    # 总集数
                    total_ep = totals.get(season) or len(episodes)
                    __append_no_exists(_season=season, _episodes=[],
                                       _total=total_ep, _start=min(episodes))
                return False, no_exists
            else:
                # 存在一些，检查每季缺失的季集
                for season, episodes in mediainfo.seasons.items():
                    if meta.sea \
                            and season not in meta.season_list:
                        continue
                    if not episodes:
                        continue
                    # 该季总集数
                    season_total = totals.get(season) or len(episodes)
                    # 该季已存在的集
                    exist_episodes = exists_tvs.seasons.get(season)
                    if exist_episodes:
                        # 已存在取差集
                        if totals.get(season):
                            # 按总集数计算缺失集（开始集为TMDB中的最小集）
                            lack_episodes = list(set(range(min(episodes),
                                                           season_total + min(episodes))
                                                     ).difference(set(exist_episodes)))
                        else:
                            # 按TMDB集数计算缺失集
                            lack_episodes = list(set(episodes).difference(set(exist_episodes)))
                        if not lack_episodes:
                            # 全部集存在
                            continue
                        # 添加不存在的季集信息
                        __append_no_exists(_season=season, _episodes=lack_episodes,
                                           _total=season_total, _start=min(lack_episodes))
                    else:
                        # 全季不存在
                        __append_no_exists(_season=season, _episodes=[],
                                           _total=season_total, _start=min(episodes))
            # 存在不完整的剧集
            if no_exists:
                logger.debug(f"媒体库中已存在部分剧集，缺失：{no_exists}")
                return False, no_exists
            # 全部存在
            return True, no_exists

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

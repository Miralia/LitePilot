import random
from typing import Optional, List

from app import schemas
from app.chain import ChainBase
from app.core.context import MediaInfo
from app.schemas import MediaType


class TmdbChain(ChainBase):
    """
    TheMovieDB处理链，单例运行
    """




    def tmdb_seasons(self, tmdbid: int) -> List[schemas.TmdbSeason]:
        """
        根据TMDBID查询themoviedb所有季信息
        :param tmdbid:  TMDBID
        """
        return self.run_module("tmdb_seasons", tmdbid=tmdbid)

    def tmdb_group_seasons(self, group_id: str) -> List[schemas.TmdbSeason]:
        """
        根据剧集组ID查询themoviedb所有季集信息
        :param group_id: 剧集组ID
        """
        return self.run_module("tmdb_group_seasons", group_id=group_id)

    def tmdb_episodes(self, tmdbid: int, season: int, episode_group: Optional[str] = None) -> List[schemas.TmdbEpisode]:
        """
        根据TMDBID查询某季的所有信信息
        :param tmdbid:  TMDBID
        :param season:  季
        :param episode_group:  剧集组
        """
        return self.run_module("tmdb_episodes", tmdbid=tmdbid, season=season, episode_group=episode_group)





    def movie_credits(self, tmdbid: int, page: Optional[int] = 1) -> Optional[List[schemas.MediaPerson]]:
        """
        根据TMDBID查询电影演职人员
        :param tmdbid:  TMDBID
        :param page:  页码
        """
        return self.run_module("tmdb_movie_credits", tmdbid=tmdbid, page=page)

    def tv_credits(self, tmdbid: int, page: Optional[int] = 1) -> Optional[List[schemas.MediaPerson]]:
        """
        根据TMDBID查询电视剧演职人员
        :param tmdbid:  TMDBID
        :param page:  页码
        """
        return self.run_module("tmdb_tv_credits", tmdbid=tmdbid, page=page)

    def tmdb_trending(self, page: Optional[int] = 1) -> Optional[List[MediaInfo]]:
        """
        TMDB流行趋势（登录页壁纸来源）
        :param page: 第几页
        :return: TMDB信息列表
        """
        return self.run_module("tmdb_trending", page=page)

    def person_detail(self, person_id: int) -> Optional[schemas.MediaPerson]:
        """
        根据TMDBID查询演职员详情
        :param person_id:  人物ID
        """
        return self.run_module("tmdb_person_detail", person_id=person_id)

    def person_credits(self, person_id: int, page: Optional[int] = 1) -> Optional[List[MediaInfo]]:
        """
        根据人物ID查询人物参演作品
        :param person_id:  人物ID
        :param page:  页码
        """
        return self.run_module("tmdb_person_credits", person_id=person_id, page=page)

    def get_random_wallpager(self) -> Optional[str]:
        """
        获取随机壁纸，缓存1个小时
        """
        infos = self.tmdb_trending()
        if infos:
            # 随机一个电影
            while True:
                info = random.choice(infos)
                if info and info.backdrop_path:
                    return info.backdrop_path
        return None

    def get_trending_wallpapers(self, num: Optional[int] = 10) -> List[str]:
        """
        获取所有流行壁纸
        """
        infos = self.tmdb_trending()
        if infos:
            return [info.backdrop_path for info in infos if info and info.backdrop_path][:num]
        return []




    async def async_tmdb_seasons(self, tmdbid: int) -> List[schemas.TmdbSeason]:
        """
        根据TMDBID查询themoviedb所有季信息（异步版本）
        :param tmdbid:  TMDBID
        """
        return await self.async_run_module("async_tmdb_seasons", tmdbid=tmdbid)

    async def async_tmdb_group_seasons(self, group_id: str) -> List[schemas.TmdbSeason]:
        """
        根据剧集组ID查询themoviedb所有季集信息（异步版本）
        :param group_id: 剧集组ID
        """
        return await self.async_run_module("async_tmdb_group_seasons", group_id=group_id)

    async def async_tmdb_episodes(self, tmdbid: int, season: int,
                                  episode_group: Optional[str] = None) -> List[schemas.TmdbEpisode]:
        """
        根据TMDBID查询某季的所有信信息（异步版本）
        :param tmdbid:  TMDBID
        :param season:  季
        :param episode_group:  剧集组
        """
        return await self.async_run_module("async_tmdb_episodes", tmdbid=tmdbid, season=season,
                                           episode_group=episode_group)





    async def async_movie_credits(self, tmdbid: int, page: Optional[int] = 1) -> Optional[List[schemas.MediaPerson]]:
        """
        根据TMDBID查询电影演职人员（异步版本）
        :param tmdbid:  TMDBID
        :param page:  页码
        """
        return await self.async_run_module("async_tmdb_movie_credits", tmdbid=tmdbid, page=page)

    async def async_tv_credits(self, tmdbid: int, page: Optional[int] = 1) -> Optional[List[schemas.MediaPerson]]:
        """
        根据TMDBID查询电视剧演职人员（异步版本）
        :param tmdbid:  TMDBID
        :param page:  页码
        """
        return await self.async_run_module("async_tmdb_tv_credits", tmdbid=tmdbid, page=page)

    async def async_person_detail(self, person_id: int) -> Optional[schemas.MediaPerson]:
        """
        根据TMDBID查询演职员详情（异步版本）
        :param person_id:  人物ID
        """
        return await self.async_run_module("async_tmdb_person_detail", person_id=person_id)

    async def async_person_credits(self, person_id: int, page: Optional[int] = 1) -> Optional[List[MediaInfo]]:
        """
        根据人物ID查询人物参演作品（异步版本）
        :param person_id:  人物ID
        :param page:  页码
        """
        return await self.async_run_module("async_tmdb_person_credits", person_id=person_id, page=page)


    async def async_tmdb_trending(self, page: Optional[int] = 1) -> Optional[List[MediaInfo]]:
        """
        TMDB流行趋势（异步版本，登录页壁纸来源）
        :param page: 第几页
        :return: TMDB信息列表
        """
        return await self.async_run_module("async_tmdb_trending", page=page)

    async def async_get_trending_wallpapers(self, num: Optional[int] = 10) -> List[str]:
        """
        获取所有流行壁纸（异步版本）
        """
        infos = await self.async_tmdb_trending()
        if infos:
            return [info.backdrop_path for info in infos if info and info.backdrop_path][:num]
        return []

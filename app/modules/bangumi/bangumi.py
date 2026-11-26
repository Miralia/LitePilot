import traceback
from datetime import datetime
from typing import Optional
from urllib.parse import quote

import requests

from app.core.cache import cached
from app.core.config import settings
from app.log import logger
from app.utils.http import RequestUtils, AsyncRequestUtils


class BangumiApi(object):
    """
    Bangumi API客户端。

    接口文档：https://bangumi.github.io/api/
    """

    _urls = {
        "search": "search/subject/%s",
        "detail": "v0/subjects/%s",
        "characters": "v0/subjects/%s/characters",
    }
    _base_url = "https://api.bgm.tv/"

    def __init__(self):
        self._session = requests.Session()
        self._req = RequestUtils(
            ua=settings.NORMAL_USER_AGENT,
            proxies=settings.PROXY,
            session=self._session,
        )
        self._async_req = AsyncRequestUtils(
            ua=settings.NORMAL_USER_AGENT,
            proxies=settings.PROXY,
        )

    @cached(maxsize=settings.CONF.bangumi, ttl=settings.CONF.meta, shared_key="get")
    def __invoke(self, url, key: Optional[str] = None, **kwargs):
        req_url = self._base_url + url
        params = {}
        if kwargs:
            params.update(kwargs)
        resp = self._req.get_res(url=req_url, params=params)
        try:
            if resp is None or resp.status_code != 200:
                return None
            result = resp.json()
            return result.get(key) if key else result
        except Exception as e:
            logger.error(f"Bangumi请求解析失败：{str(e)} - {traceback.format_exc()}")
            return None

    @cached(maxsize=settings.CONF.bangumi, ttl=settings.CONF.meta, shared_key="get")
    async def __async_invoke(self, url, key: Optional[str] = None, **kwargs):
        req_url = self._base_url + url
        params = {}
        if kwargs:
            params.update(kwargs)
        resp = await self._async_req.get_res(url=req_url, params=params)
        try:
            if resp is None or resp.status_code != 200:
                return None
            result = resp.json()
            return result.get(key) if key else result
        except Exception as e:
            logger.error(f"Bangumi请求解析失败：{str(e)} - {traceback.format_exc()}")
            return None

    def search(self, name):
        """
        搜索媒体信息
        """
        result = self.__invoke(self._urls["search"] % quote(name, safe=""), type=2)
        if result:
            return result.get("list")
        return []

    async def async_search(self, name):
        """
        搜索媒体信息（异步版本）
        """
        result = await self.__async_invoke(self._urls["search"] % quote(name, safe=""), type=2)
        if result:
            return result.get("list")
        return []

    def detail(self, bid: int):
        """
        获取番剧详情
        """
        return self.__invoke(self._urls["detail"] % bid, _ts=datetime.strftime(datetime.now(), '%Y%m%d'))

    async def async_detail(self, bid: int):
        """
        获取番剧详情（异步版本）
        """
        return await self.__async_invoke(self._urls["detail"] % bid, _ts=datetime.strftime(datetime.now(), '%Y%m%d'))

    def credits(self, bid: int):
        """
        获取番剧人物
        """
        ret_list = []
        result = self.__invoke(self._urls["characters"] % bid, _ts=datetime.strftime(datetime.now(), '%Y%m%d'))
        if result:
            for item in result:
                character_id = item.get("id")
                actors = item.get("actors")
                if character_id and actors and actors[0]:
                    actor_info = actors[0]
                    actor_info.update({'career': [item.get('name')]})
                    ret_list.append(actor_info)
        return ret_list

    async def async_credits(self, bid: int):
        """
        获取番剧人物（异步版本）
        """
        ret_list = []
        result = await self.__async_invoke(self._urls["characters"] % bid,
                                           _ts=datetime.strftime(datetime.now(), '%Y%m%d'))
        if result:
            for item in result:
                character_id = item.get("id")
                actors = item.get("actors")
                if character_id and actors and actors[0]:
                    actor_info = actors[0]
                    actor_info.update({'career': [item.get('name')]})
                    ret_list.append(actor_info)
        return ret_list

    def clear_cache(self):
        """
        清除缓存
        """
        self.__invoke.cache_clear()

    def close(self) -> None:
        """
        关闭Bangumi会话
        """
        if self._session:
            self._session.close()

from ..tmdb import TMDb


class Trending(TMDb):
    _urls = {"trending": "/trending/%s/%s"}

    def _trending(self, media_type="all", time_window="day", page=1):
        """
        Get trending, TTLCache 12 hours
        """
        return self._request_obj(
            self._urls["trending"] % (media_type, time_window),
            params="page=%s" % page,
            key="results",
            call_cached=False
        )

    def all_week(self, page=1):
        """
        Get all weekly trending
        :param page: int
        :return:
        """
        return self._trending(media_type="all", time_window="week", page=page)

    # 异步版本方法
    async def _async_trending(self, media_type="all", time_window="day", page=1):
        """
        Get trending, TTLCache 12 hours（异步版本）
        """
        return await self._async_request_obj(
            self._urls["trending"] % (media_type, time_window),
            params="page=%s" % page,
            key="results",
            call_cached=False
        )

    async def async_all_week(self, page=1):
        """
        Get all weekly trending（异步版本）
        :param page: int
        :return:
        """
        return await self._async_trending(media_type="all", time_window="week", page=page)

from ..tmdb import TMDb

try:
    from urllib import quote
except ImportError:
    from urllib.parse import quote


class Search(TMDb):
    _urls = {
        "movies": "/search/movie",
        "multi": "/search/multi",
        "tv_shows": "/search/tv",
    }

    def movies(self, term, adult=None, region=None, year=None, release_year=None, page=1):
        """
        Search for movies.
        :param term: str
        :param adult: bool
        :param region: str
        :param year: int
        :param release_year: int
        :param page: int
        :return:
        """
        params = "query=%s&page=%s" % (quote(term), page)
        if adult is not None:
            params += "&include_adult=%s" % "true" if adult else "false"
        if region is not None:
            params += "&region=%s" % quote(region)
        if year is not None:
            params += "&year=%s" % year
        if release_year is not None:
            params += "&primary_release_year=%s" % release_year
        return self._request_obj(
            self._urls["movies"],
            params=params,
            key="results"
        )

    def multi(self, term, adult=None, region=None, page=1):
        """
        Search multiple models in a single request.
        Multi search currently supports searching for movies, tv shows and people in a single request.
        :param term: str
        :param adult: bool
        :param region: str
        :param page: int
        :return:
        """
        params = "query=%s&page=%s" % (quote(term), page)
        if adult is not None:
            params += "&include_adult=%s" % "true" if adult else "false"
        if region is not None:
            params += "&region=%s" % quote(region)
        return self._request_obj(
            self._urls["multi"],
            params=params,
            key="results"
        )

    def tv_shows(self, term, adult=None, release_year=None, page=1):
        """
        Search for a TV show.
        :param term: str
        :param adult: bool
        :param release_year: int
        :param page: int
        :return:
        """
        params = "query=%s&page=%s" % (quote(term), page)
        if adult is not None:
            params += "&include_adult=%s" % "true" if adult else "false"
        if release_year is not None:
            params += "&first_air_date_year=%s" % release_year
        return self._request_obj(
            self._urls["tv_shows"],
            params=params,
            key="results"
        )

    # 异步版本方法

    async def async_multi(self, term, adult=None, region=None, page=1):
        """
        Search multiple models in a single request.（异步版本）
        Multi search currently supports searching for movies, tv shows and people in a single request.
        :param term: str
        :param adult: bool
        :param region: str
        :param page: int
        :return:
        """
        params = "query=%s&page=%s" % (quote(term), page)
        if adult is not None:
            params += "&include_adult=%s" % "true" if adult else "false"
        if region is not None:
            params += "&region=%s" % quote(region)
        return await self._async_request_obj(
            self._urls["multi"],
            params=params,
            key="results"
        )

    async def async_movies(self, term, adult=None, region=None, year=None, release_year=None, page=1):
        """
        Search for movies.（异步版本）
        :param term: str
        :param adult: bool
        :param region: str
        :param year: int
        :param release_year: int
        :param page: int
        :return:
        """
        params = "query=%s&page=%s" % (quote(term), page)
        if adult is not None:
            params += "&include_adult=%s" % "true" if adult else "false"
        if region is not None:
            params += "&region=%s" % quote(region)
        if year is not None:
            params += "&year=%s" % year
        if release_year is not None:
            params += "&primary_release_year=%s" % release_year

        return await self._async_request_obj(
            self._urls["movies"],
            params=params,
            key="results"
        )

    async def async_tv_shows(self, term, adult=None, release_year=None, page=1):
        """
        Search for a TV show.（异步版本）
        :param term: str
        :param adult: bool
        :param release_year: int
        :param page: int
        :return:
        """
        params = "query=%s&page=%s" % (quote(term), page)
        if adult is not None:
            params += "&include_adult=%s" % "true" if adult else "false"
        if release_year is not None:
            params += "&first_air_date_year=%s" % release_year
        return await self._async_request_obj(
            self._urls["tv_shows"],
            params=params,
            key="results"
        )

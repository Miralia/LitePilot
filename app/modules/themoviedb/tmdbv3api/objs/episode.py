from ..tmdb import TMDb


class Episode(TMDb):
    _urls = {
        "details": "/tv/%s/season/%s/episode/%s",
    }

    def details(self, tv_id, season_num, episode_num, append_to_response="trailers,images,casts,translations"):
        """
        Get the TV episode details by id.
        :param tv_id: int
        :param season_num: int
        :param episode_num: int
        :param append_to_response: str
        :return:
        """
        return self._request_obj(
            self._urls["details"] % (tv_id, season_num, episode_num),
            params="append_to_response=%s" % append_to_response
        )

    # 异步版本方法
    async def async_details(self, tv_id, season_num, episode_num,
                            append_to_response="trailers,images,casts,translations"):
        """
        Get the TV episode details by id.（异步版本）
        :param tv_id: int
        :param season_num: int
        :param episode_num: int
        :param append_to_response: str
        :return:
        """
        return await self._async_request_obj(
            self._urls["details"] % (tv_id, season_num, episode_num),
            params="append_to_response=%s" % append_to_response
        )

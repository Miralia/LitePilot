from ..tmdb import TMDb


class TV(TMDb):
    _urls = {
        "details": "/tv/%s",
        "images": "/tv/%s/images",
        "group_episodes": "/tv/episode_group/%s",
    }

    def details(self, tv_id, append_to_response="videos,trailers,images,credits,translations"):
        """
        Get the primary TV show details by id.
        :param tv_id: int
        :param append_to_response: str
        :return:
        """
        return self._request_obj(
            self._urls["details"] % tv_id,
            params="append_to_response=%s" % append_to_response,
        )

    def group_episodes(self, group_id):
        """
        查询剧集组所有剧集
        :param group_id: int
        :return:
        """
        return self._request_obj(
            self._urls["group_episodes"] % group_id,
            key="groups"
        )

    def images(self, tv_id, include_image_language=None):
        """
        Get the images that belong to a TV show.
        Querying images with a language parameter will filter the results.
        If you want to include a fallback language (especially useful for backdrops)
        you can use the include_image_language parameter.
        This should be a comma separated value like so: include_image_language=en,null.
        :param tv_id: int
        :param include_image_language: str
        :return:
        """
        return self._request_obj(
            self._urls["images"] % tv_id,
            params="include_image_language=%s" % include_image_language if include_image_language else ""
        )

    # 异步版本方法
    async def async_details(self, tv_id, append_to_response="videos,trailers,images,credits,translations"):
        """
        Get the primary TV show details by id.（异步版本）
        :param tv_id: int
        :param append_to_response: str
        :return:
        """
        return await self._async_request_obj(
            self._urls["details"] % tv_id,
            params="append_to_response=%s" % append_to_response,
        )

    async def async_group_episodes(self, group_id):
        """
        查询剧集组所有剧集（异步版本）
        :param group_id: int
        :return:
        """
        return await self._async_request_obj(
            self._urls["group_episodes"] % group_id,
            key="groups"
        )

    async def async_images(self, tv_id, include_image_language=None):
        """
        Get the images that belong to a TV show.
        Querying images with a language parameter will filter the results.
        If you want to include a fallback language (especially useful for backdrops)
        you can use the include_image_language parameter.
        This should be a comma separated value like so: include_image_language=en,null.（异步版本）
        :param tv_id: int
        :param include_image_language: str
        :return:
        """
        return await self._async_request_obj(
            self._urls["images"] % tv_id,
            params="include_image_language=%s" % include_image_language if include_image_language else ""
        )

from ..tmdb import TMDb


class Movie(TMDb):
    _urls = {
        "details": "/movie/%s",
        "images": "/movie/%s/images",
    }

    def details(self, movie_id, append_to_response="videos,trailers,images,casts,translations,keywords,release_dates"):
        """
        Get the primary information about a movie.
        :param movie_id: int
        :param append_to_response: str
        :return:
        """
        return self._request_obj(
            self._urls["details"] % movie_id,
            params="append_to_response=%s" % append_to_response
        )

    def images(self, movie_id, include_image_language=None):
        """
        Get the images that belong to a movie.
        Querying images with a language parameter will filter the results.
        If you want to include a fallback language (especially useful for backdrops)
        you can use the include_image_language parameter.
        This should be a comma separated value like so: include_image_language=en,null.
        :param movie_id: int
        :param include_image_language: str
        :return:
        """
        return self._request_obj(
            self._urls["images"] % movie_id,
            params="include_image_language=%s" % include_image_language if include_image_language else ""
        )

    # 异步版本方法
    async def async_details(self, movie_id,
                            append_to_response="videos,trailers,images,casts,translations,keywords,release_dates"):
        """
        Get the primary information about a movie.（异步版本）
        :param movie_id: int
        :param append_to_response: str
        :return:
        """
        return await self._async_request_obj(
            self._urls["details"] % movie_id,
            params="append_to_response=%s" % append_to_response
        )

    async def async_images(self, movie_id, include_image_language=None):
        """
        Get the images that belong to a movie.
        Querying images with a language parameter will filter the results.
        If you want to include a fallback language (especially useful for backdrops)
        you can use the include_image_language parameter.
        This should be a comma separated value like so: include_image_language=en,null.（异步版本）
        :param movie_id: int
        :param include_image_language: str
        :return:
        """
        return await self._async_request_obj(
            self._urls["images"] % movie_id,
            params="include_image_language=%s" % include_image_language if include_image_language else ""
        )

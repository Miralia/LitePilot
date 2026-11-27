"""媒体服务器删除通知图片边界测试。"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.chain.mediaserverdel import MediaServerDelChain
from app.modules.themoviedb import TheMovieDbModule
from app.schemas.types import MediaImageType, MediaType


def test_season_delete_notification_uses_season_poster() -> None:
    """TMDB 季详情没有 backdrop_path，整季删除通知应请求季海报。"""
    chain = object.__new__(MediaServerDelChain)
    chain.obtain_specific_image = MagicMock(return_value="https://image.tmdb.org/season.jpg")

    result = chain._obtain_notify_image(295071, "Series", season_num="1")

    assert result == "https://image.tmdb.org/season.jpg"
    assert chain.obtain_specific_image.call_args.kwargs["image_type"] is MediaImageType.Poster


def test_series_delete_notification_still_uses_series_backdrop() -> None:
    """未定位到具体季时仍使用剧集 backdrop，保持通知横幅语义。"""
    chain = object.__new__(MediaServerDelChain)
    chain.obtain_specific_image = MagicMock(return_value="https://image.tmdb.org/backdrop.jpg")

    result = chain._obtain_notify_image(295071, "Series")

    assert result == "https://image.tmdb.org/backdrop.jpg"
    assert chain.obtain_specific_image.call_args.kwargs["image_type"] is MediaImageType.Backdrop


def test_tmdb_season_detail_poster_is_returned() -> None:
    """季详情仅返回 poster_path 时，指定 Poster 类型可以生成完整图片 URL。"""
    module = object.__new__(TheMovieDbModule)
    module.tmdb = SimpleNamespace(
        get_tv_season_detail=lambda tmdbid, season: {"poster_path": "/season.jpg"}
    )

    result = module.obtain_specific_image(
        mediaid=295071,
        mtype=MediaType.TV,
        image_type=MediaImageType.Poster,
        season=1,
    )

    assert result is not None
    assert result.endswith("/season.jpg")


def test_tmdb_episode_zero_uses_episode_still() -> None:
    """episode_number 为 0 的特别篇也是有效集，不应被真值判断降级为季图。"""
    module = object.__new__(TheMovieDbModule)
    module.tmdb = SimpleNamespace(
        get_tv_episode_detail=lambda tmdbid, season, episode: {"still_path": "/episode0.jpg"},
        get_tv_season_detail=lambda tmdbid, season: {"poster_path": "/season0.jpg"},
    )

    result = module.obtain_specific_image(
        mediaid=295071,
        mtype=MediaType.TV,
        image_type=MediaImageType.Backdrop,
        season=0,
        episode=0,
    )

    assert result is not None
    assert result.endswith("/episode0.jpg")


def test_notify_image_preserves_numeric_episode_zero() -> None:
    """原生 webhook 的 int 0 季集号在通知图片路径中也不能被当成缺失。"""
    chain = object.__new__(MediaServerDelChain)
    chain.obtain_specific_image = MagicMock(return_value="https://image.tmdb.org/episode0.jpg")

    result = chain._obtain_notify_image(295071, "Episode", season_num=0, episode_num=0)

    assert result == "https://image.tmdb.org/episode0.jpg"
    assert chain.obtain_specific_image.call_args.kwargs["season"] == 0
    assert chain.obtain_specific_image.call_args.kwargs["episode"] == 0

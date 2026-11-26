"""媒体数据源能力边界回归测试。"""

import asyncio
import inspect

import pytest
from fastapi import HTTPException

from app.chain import ChainBase
from app.chain.media import MediaChain
from app.core.context import MediaInfo
from app.modules.bangumi import BangumiModule
from app.modules.themoviedb import TheMovieDbModule
import app.schemas.context as context_schemas
from app.api.endpoints.media import search as search_media_endpoint
from app.utils.media import resolve_media_identity


def test_douban_integration_interfaces_are_removed() -> None:
    """项目没有豆瓣模块，不应保留豆瓣查询或跨源转换入口。"""
    for chain_method in (
        "match_doubaninfo",
        "async_match_doubaninfo",
        "douban_info",
        "async_douban_info",
    ):
        assert not hasattr(ChainBase, chain_method)

    for media_method in (
        "get_tmdbinfo_by_doubanid",
        "async_get_tmdbinfo_by_doubanid",
        "get_doubaninfo_by_tmdbid",
        "async_get_doubaninfo_by_tmdbid",
        "get_doubaninfo_by_bangumiid",
        "async_get_doubaninfo_by_bangumiid",
    ):
        assert not hasattr(MediaChain, media_method)

    assert "douban_info" not in MediaInfo.__dataclass_fields__
    assert not hasattr(MediaInfo, "set_douban_info")
    assert not hasattr(context_schemas, "MediaPerson")


def test_legacy_douban_identity_fields_remain_available() -> None:
    """历史数据中的豆瓣ID仍可作为兼容身份保留和展示。"""
    media_info = MediaInfo(douban_id="35209731")

    assert media_info.douban_id == "35209731"
    assert media_info.detail_link == "https://movie.douban.com/subject/35209731"
    assert media_info.to_dict()["douban_id"] == "35209731"


def test_ambiguous_identity_prefers_active_bangumi_over_legacy_douban() -> None:
    """同时存在Bangumi与历史豆瓣ID时，兼容身份应优先选择仍可用的Bangumi。"""
    media_info = MediaInfo(douban_id="35209731", bangumi_id=400602)

    assert resolve_media_identity(media=media_info) == ("bangumi", "400602")
    serialized = media_info.to_dict()
    assert serialized["source"] == "bangumi"
    assert serialized["media_id"] == "400602"


def test_douban_only_identity_remains_readable_as_legacy_fallback() -> None:
    """只有历史豆瓣ID的旧数据仍应解析为豆瓣身份，避免丢失既有记录。"""
    media_info = MediaInfo(douban_id="35209731")

    assert resolve_media_identity(media=media_info) == ("douban", "35209731")
    serialized = media_info.to_dict()
    assert serialized["source"] == "douban"
    assert serialized["media_id"] == "35209731"


def test_shared_recognition_residue_is_removed() -> None:
    """共享识别链路已经移除，不应保留无效的共享元数据参数。"""
    assert "share_meta" not in inspect.signature(ChainBase.recognize_media).parameters
    assert "share_meta" not in inspect.signature(ChainBase.async_recognize_media).parameters


def test_removed_metadata_browse_interfaces_stay_removed() -> None:
    """TMDB/Bangumi 只服务识别与刮削，不保留无入口的浏览、推荐、人物详情接口。"""
    for method in (
        "tmdb_collection",
        "async_tmdb_collection",
        "tmdb_discover",
        "async_tmdb_discover",
        "tmdb_movie_similar",
        "async_tmdb_movie_similar",
        "tmdb_tv_similar",
        "async_tmdb_tv_similar",
        "tmdb_movie_recommend",
        "async_tmdb_movie_recommend",
        "tmdb_tv_recommend",
        "async_tmdb_tv_recommend",
        "tmdb_movie_credits",
        "async_tmdb_movie_credits",
        "tmdb_tv_credits",
        "async_tmdb_tv_credits",
        "tmdb_person_detail",
        "async_tmdb_person_detail",
        "tmdb_person_credits",
        "async_tmdb_person_credits",
        "search_persons",
        "async_search_persons",
        "search_collections",
        "async_search_collections",
    ):
        assert not hasattr(TheMovieDbModule, method)

    for method in (
        "bangumi_calendar",
        "async_bangumi_calendar",
        "bangumi_credits",
        "async_bangumi_credits",
        "bangumi_recommend",
        "async_bangumi_recommend",
        "bangumi_person_detail",
        "async_bangumi_person_detail",
        "bangumi_person_credits",
        "async_bangumi_person_credits",
        "bangumi_discover",
        "async_bangumi_discover",
    ):
        assert not hasattr(BangumiModule, method)


def test_active_metadata_recognition_interfaces_remain_available() -> None:
    """识别、详情、季集和刮削接口属于保留链路，不应被误删。"""
    for method in (
        "recognize_media",
        "async_recognize_media",
        "tmdb_info",
        "async_tmdb_info",
        "tmdb_seasons",
        "async_tmdb_seasons",
        "tmdb_episodes",
        "async_tmdb_episodes",
        "metadata_nfo",
        "metadata_img",
    ):
        assert hasattr(TheMovieDbModule, method)

    for method in (
        "recognize_media",
        "async_recognize_media",
        "bangumi_info",
        "async_bangumi_info",
        "metadata_nfo",
        "metadata_img",
    ):
        assert hasattr(BangumiModule, method)


def test_low_level_tmdb_browse_client_surface_is_removed() -> None:
    """内部TMDB客户端只保留识别、详情、图片、季集和趋势能力。"""
    import app.modules.themoviedb.tmdbv3api as tmdbv3api
    from app.modules.themoviedb.tmdbv3api import Movie, Search, TV, Trending

    for symbol in ("Account", "Authentication", "Collection", "Discover", "Person"):
        assert not hasattr(tmdbv3api, symbol)

    for method in ("companies", "collections", "keywords", "people"):
        assert not hasattr(Search, method)
        assert not hasattr(Search, f"async_{method}")

    for client in (Movie, TV):
        for method in ("credits", "recommendations", "similar", "videos", "watch_providers"):
            assert not hasattr(client, method)
            assert not hasattr(client, f"async_{method}")

    for method in ("movie_day", "movie_week", "tv_day", "tv_week", "person_day", "person_week"):
        assert not hasattr(Trending, method)
        assert not hasattr(Trending, f"async_{method}")


def test_non_media_search_types_are_rejected() -> None:
    """媒体搜索只服务入库识别，不再暴露人物或合集浏览搜索类型。"""
    for search_type in ("person", "collection", "unknown"):
        with pytest.raises(HTTPException, match="仅支持媒体搜索"):
            asyncio.run(search_media_endpoint(title="测试", type=search_type, _=None))


def test_non_media_search_chain_interfaces_are_removed() -> None:
    """人物与合集搜索没有产品入口，不应保留链层调度接口。"""
    for method in (
        "search_persons",
        "async_search_persons",
        "search_collections",
        "async_search_collections",
    ):
        assert not hasattr(ChainBase, method)

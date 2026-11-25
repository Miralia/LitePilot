"""媒体数据源能力边界回归测试。"""

from app.chain import ChainBase
from app.chain.media import MediaChain
from app.core.context import MediaInfo
from app.schemas.context import MediaPerson
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
    for person_field in ("roles", "title", "url", "avatar", "latin_name"):
        assert person_field not in MediaPerson.model_fields


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

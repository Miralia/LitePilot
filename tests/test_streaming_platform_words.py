# -*- coding: utf-8 -*-
"""流媒体平台词表与输出形态用例。

覆盖用户词表解析、与内置表的合并优先级，以及全称/简称两种输出形态。
"""
import pytest

from app.core.meta.streamingplatform import (
    DISPLAY_FULL,
    DISPLAY_SHORT,
    StreamingPlatforms,
)


@pytest.fixture()
def platforms():
    """每个用例都用独立实例，避免单例状态相互影响。"""

    class _Isolated(StreamingPlatforms):
        """绕开单例、每例新建的测试替身。"""

    instance = _Isolated.__new__(_Isolated)
    instance._lookup_cache = {}
    instance._short_lookup = {}
    instance._display_mode = DISPLAY_FULL
    instance._loaded_words = None
    instance._loaded_mode = None
    instance._build_cache()
    return instance


def test_parse_custom_words_supports_short_and_full():
    """`简称 = 全称` 应被正确拆开。"""
    parsed = StreamingPlatforms.parse_custom_words(["MYS = My Stream", "ONLYNAME"])

    assert parsed == [("MYS", "My Stream"), ("ONLYNAME", "ONLYNAME")]


def test_parse_custom_words_ignores_comments_and_blanks():
    """注释行与空行应被忽略。"""
    parsed = StreamingPlatforms.parse_custom_words(["# 这是注释", "", "  ", "A = B"])

    assert parsed == [("A", "B")]


def test_custom_word_is_recognized(platforms):
    """用户新增的平台应能被识别。"""
    platforms.apply_custom(words=["MYS = My Stream"])

    assert platforms.is_streaming_platform("MYS")
    assert platforms.is_streaming_platform("My Stream")
    assert platforms.get_streaming_platform_name("mys") == "My Stream"


def test_custom_word_overrides_builtin(platforms):
    """同名时用户词表应覆盖内置表。"""
    platforms.apply_custom(words=["NF = 奈飞"])

    assert platforms.get_streaming_platform_name("NF") == "奈飞"


def test_builtin_platforms_survive_custom_words(platforms):
    """未冲突的内置平台在合并后仍可识别。"""
    platforms.apply_custom(words=["MYS = My Stream"])

    assert platforms.is_streaming_platform("AMZN")
    assert platforms.get_streaming_platform_name("AMZN") == "Amazon"


def test_display_full_is_default(platforms):
    """默认输出全称，保持既有整理结果不变。"""
    platforms.apply_custom(words=[])

    assert platforms.get_streaming_platform_name("NF") == "Netflix"


def test_display_short_outputs_abbreviation(platforms):
    """输出形态为简称时应返回简称。"""
    platforms.apply_custom(words=[], display_mode=DISPLAY_SHORT)

    assert platforms.get_streaming_platform_name("NF") == "NF"
    assert platforms.get_streaming_platform_name("Netflix") == "NF"


def test_display_short_keeps_unknown_untouched(platforms):
    """未知平台不应被简称模式影响。"""
    platforms.apply_custom(words=[], display_mode=DISPLAY_SHORT)

    assert platforms.get_streaming_platform_name("UNKNOWN_PLATFORM") is None


def test_invalid_display_mode_falls_back_to_full(platforms):
    """非法输出形态应退回全称。"""
    platforms.apply_custom(words=[], display_mode="nonsense")

    assert platforms.get_streaming_platform_name("NF") == "Netflix"


def test_display_short_with_custom_word(platforms):
    """简称模式下自定义平台也输出简称。"""
    platforms.apply_custom(words=["MYS = My Stream"], display_mode=DISPLAY_SHORT)

    assert platforms.get_streaming_platform_name("My Stream") == "MYS"

def _reload_streaming_platforms(mode: str):
    """按指定输出形态重新加载平台表。"""
    from app.core.meta import streamingplatform

    streamingplatform.StreamingPlatforms().ensure_loaded()

    from app.db.systemconfig_oper import SystemConfigOper
    from app.schemas.types import SystemConfigKey

    SystemConfigOper().set(SystemConfigKey.StreamingPlatformDisplay, mode)
    streamingplatform.StreamingPlatforms().ensure_loaded()


@pytest.mark.parametrize(
    ("title", "short", "full"),
    [
        ("Show.2024.1080p.NF.WEB-DL.x264-GRP.mkv", "NF", "Netflix"),
        ("Show.2024.1080p.Netflix.WEB-DL.x264-GRP.mkv", "NF", "Netflix"),
        ("Show.2024.1080p.AMZN.WEB-DL.x264-GRP.mkv", "AMZN", "Amazon"),
        ("Show.2024.1080p.CR.WEB-DL.x264-GRP.mkv", "CR", "Crunchyroll"),
    ],
)
def test_rust_path_respects_display_mode(title, short, full):
    """Rust 识别路径也要遵守简写/全称开关，不能固定输出全称。"""
    from app.core.metainfo import MetaInfo

    _reload_streaming_platforms("short")
    assert MetaInfo(title).web_source == short

    _reload_streaming_platforms("full")
    assert MetaInfo(title).web_source == full

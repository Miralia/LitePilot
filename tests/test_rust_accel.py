import os
import time
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from types import SimpleNamespace

import pytest

from app.helper import rss as rss_module
from app.helper.rss import RssHelper
from app.core import metainfo as metainfo_module
from app.core.config import settings
from app.core.meta.customization import CustomizationMatcher
from app.core.meta.releasegroup import ReleaseGroupsMatcher
from app.core.meta.streamingplatform import StreamingPlatforms
from app.db.systemconfig_oper import SystemConfigOper
from app.schemas.types import MediaType, SystemConfigKey
from app.utils import rust_accel
from app.utils.http import RequestUtils


pytestmark = pytest.mark.skipif(
    not rust_accel.is_available(),
    reason="moviepilot_rust 扩展未安装",
)


def _require_rust_package_version(min_version: str) -> None:
    """
    跳过依赖尚未发布到 PyPI 的 Rust 扩展新行为用例。
    """
    try:
        installed_version = version("moviepilot-rust")
    except PackageNotFoundError:
        pytest.skip("moviepilot-rust 包版本不可用")
    installed_parts = tuple(
        int(part) for part in installed_version.split("+", 1)[0].split(".")[:3]
    )
    required_parts = tuple(int(part) for part in min_version.split(".")[:3])
    if installed_parts < required_parts:
        pytest.skip(f"需要 moviepilot-rust>={min_version}，当前为 {installed_version}")


def test_rust_filter_rule_parser_matches_boolean_semantics():
    """
    Rust 过滤规则解析应保持 pyparsing 的布尔表达式结构。
    """
    result = rust_accel.parse_filter_rule("HDR & !BLU")

    assert result == [["HDR", "and", ["not", "BLU"]]]


def test_rust_filter_rule_parser_handles_parentheses_and_or():
    """
    Rust 过滤规则解析应保持括号、与、或的优先级语义。
    """
    result = rust_accel.parse_filter_rule("CNSUB & (4K | 1080P) & !BLU")

    assert result == [[["CNSUB", "and", ["4K", "or", "1080P"]], "and", ["not", "BLU"]]]


def test_rust_rss_parser_extracts_rss_and_atom_items():
    """
    Rust RSS解析应覆盖 RSS item、Atom entry、命名空间和日期字段。
    """
    xml = """
    <root xmlns:dc="http://purl.org/dc/elements/1.1/">
      <rss>
        <channel>
          <item>
            <title>Movie &amp; Show</title>
            <description><![CDATA[Desc <b>bold</b>]]></description>
            <link>https://example.com/details/1</link>
            <enclosure url="https://example.com/download/1.torrent" length="123456" />
            <pubDate>Tue, 19 May 2026 08:30:00 GMT</pubDate>
            <dc:creator>豆瓣用户</dc:creator>
          </item>
        </channel>
      </rss>
      <feed>
        <entry>
          <title>Atom Title</title>
          <summary>Atom Summary</summary>
          <link href="https://example.com/atom/2" />
          <updated>2026-05-19T09:30:00Z</updated>
        </entry>
      </feed>
    </root>
    """

    result = rust_accel.parse_rss_items(xml, max_items=100)

    assert len(result) == 2
    assert result[0]["title"] == "Movie & Show"
    assert result[0]["description"] == "Desc <b>bold</b>"
    assert result[0]["link"] == "https://example.com/details/1"
    assert result[0]["enclosure"] == "https://example.com/download/1.torrent"
    assert result[0]["size"] == 123456
    assert result[0]["nickname"] == "豆瓣用户"
    assert int(result[0]["pubdate"].timestamp()) == int(datetime(2026, 5, 19, 8, 30, tzinfo=timezone.utc).timestamp())
    assert result[1]["title"] == "Atom Title"
    assert result[1]["description"] == "Atom Summary"
    assert result[1]["link"] == "https://example.com/atom/2"
    assert result[1]["enclosure"] == "https://example.com/atom/2"
    assert int(result[1]["pubdate"].timestamp()) == int(datetime(2026, 5, 19, 9, 30, tzinfo=timezone.utc).timestamp())


def test_rust_rss_parser_skips_incomplete_items():
    """
    Rust RSS解析应保持原逻辑，跳过无标题或无链接的条目。
    """
    xml = """
    <rss>
      <channel>
        <item><title></title><link>https://example.com/a</link></item>
        <item><title>No Link</title></item>
        <item><title>OK</title><link>https://example.com/ok</link></item>
      </channel>
    </rss>
    """

    result = rust_accel.parse_rss_items(xml, max_items=100)

    assert result == [{
        "title": "OK",
        "enclosure": "https://example.com/ok",
        "size": 0,
        "description": "",
        "link": "https://example.com/ok",
        "pubdate": "",
    }]


def test_rss_helper_parse_uses_rust_parser(monkeypatch):
    """
    RssHelper.parse 应在请求和编码处理后直接使用 Rust 解析结果。
    """
    xml = """
    <rss>
      <channel>
        <item>
          <title>Helper Title</title>
          <description>Helper Description</description>
          <link>https://example.com/details/3</link>
          <pubDate>2026-05-19T10:30:00Z</pubDate>
        </item>
      </channel>
    </rss>
    """

    class FakeRequestUtils:
        """
        测试用 RequestUtils，避免真实网络请求。
        """

        get_decoded_xml_content = staticmethod(RequestUtils.get_decoded_xml_content)

        def __init__(self, **_kwargs):
            """
            保存构造参数占位，兼容 RssHelper 的调用方式。
            """

        def get_res(self, _url):
            """
            返回带 content/text/status_code 的最小响应对象。
            """
            return SimpleNamespace(
                status_code=200,
                content=xml.encode("utf-8"),
                text=xml,
                apparent_encoding="utf-8",
                encoding="utf-8",
            )

    monkeypatch.setattr(rss_module, "RequestUtils", FakeRequestUtils)

    result = RssHelper().parse("https://example.com/rss")

    assert len(result) == 1
    assert result[0]["title"] == "Helper Title"
    assert result[0]["enclosure"] == "https://example.com/details/3"
    assert int(result[0]["pubdate"].timestamp()) == int(datetime(2026, 5, 19, 10, 30, tzinfo=timezone.utc).timestamp())


def _metainfo_options(custom_words=None):
    """
    构造 Rust MetaInfo 测试所需的配置，保持和生产入口一致。
    """
    systemconfig = SystemConfigOper()
    release_groups = ReleaseGroupsMatcher().get_release_groups()
    customization = CustomizationMatcher.normalize_customization(
        systemconfig.get(SystemConfigKey.Customization)
    )
    return {
        "custom_words": custom_words or [],
        "media_exts": settings.RMT_MEDIAEXT + settings.RMT_SUBEXT + settings.RMT_AUDIOEXT,
        "release_groups": release_groups,
        "customization": customization,
        "streaming_platforms": StreamingPlatforms().get_lookup_cache(),
    }


def test_rust_metainfo_parser_handles_video_from_entry():
    """
    Rust MetaInfo 入口应完整识别普通影视标题。
    """
    result = rust_accel.parse_metainfo(
        "The Long Season 2017 2160p WEB-DL H265 120FPS AAC-XXX",
        options=_metainfo_options(),
    )

    assert result["kind"] == "video"
    assert result["type"] == "未知"
    assert result["en_name"] == "The Long Season"
    assert result["year"] == "2017"
    assert result["resource_type"] == "WEB-DL"
    assert result["resource_pix"] == "2160p"
    assert result["video_encode"] == "H265"
    assert result["audio_encode"] == "AAC"
    assert result["fps"] == 120


def test_rust_metainfo_parser_handles_anime_from_entry():
    """
    Rust MetaInfo 入口应完整识别 Anime 标题。
    """
    result = rust_accel.parse_metainfo(
        "[ANi] OVERLORD 第四季 - 04 [1080P][Baha][WEB-DL][AAC AVC][CHT].mp4",
        options=_metainfo_options(),
    )

    assert result["kind"] == "anime"
    assert result["type"] == "电视剧"
    assert result["en_name"] == "Overlord"
    assert result["begin_season"] == 4
    assert result["begin_episode"] == 4
    assert result["resource_pix"] == "1080p"
    assert result["video_encode"] == "AVC"
    assert result["audio_encode"] == "AAC"


def test_rust_metainfo_parser_handles_episode_group():
    """
    Rust MetaInfo 入口应识别显式媒体标签中的 g 剧集组参数。
    """
    group_id = "5ad0ec240e0a26303f00d84d"
    result = rust_accel.parse_metainfo(
        f"物语系列 {{[tmdbid=46195;type=tv;g={group_id};s=1]}} 01",
        options=_metainfo_options(),
    )

    assert result["tmdbid"] == 46195
    assert result["type"] == MediaType.TV.value
    assert result["episode_group"] == group_id
    assert result["begin_season"] == 1


def test_rust_metainfo_parser_handles_subtitle_episode_range_fin():
    """
    Rust MetaInfo 入口应识别副标题中的数字范围完结标记。
    """
    result = rust_accel.parse_metainfo(
        "JoJos Bizarre Adventure S01 2012 1080i BluRay x264 FLAC 2.0-AnimeF@ADE",
        subtitle="JOJO的奇妙冒险 第一季 / JoJo's Bizarre Adventure [01-26Fin] [简繁字幕]",
        options=_metainfo_options(),
    )

    assert result["type"] == MediaType.TV.value
    assert result["begin_season"] == 1
    assert result["begin_episode"] == 1
    assert result["end_episode"] == 26
    assert result["total_episode"] == 26


def test_rust_metainfo_path_parser_merges_parent_title():
    """
    Rust MetaInfoPath 入口应在 Rust 内完成父目录标题合并。
    """
    result = rust_accel.parse_metainfo_path(
        "/Marty Supreme 2025 2160p DoVi HDR Atmos TrueHD 7.1 x265-PbK/简英双语特效.mp4",
        options=_metainfo_options(),
    )

    assert result["kind"] == "video"
    assert result["en_name"] == "Marty Supreme"
    assert result["year"] == "2025"
    assert result["original_name"] == "Marty Supreme"
    assert result["resource_pix"] == "2160p"


def test_metainfo_public_entry_uses_rust(monkeypatch):
    """
    MetaInfo 公共入口应调用 Rust 解析器，而不是直接进入 Python 旧解析逻辑。
    """
    calls = []
    original_parse = metainfo_module.rust_accel.parse_metainfo

    def wrapped_parse(*args, **kwargs):
        """
        记录 Rust 入口调用并透传结果。
        """
        calls.append(args[0])
        return original_parse(*args, **kwargs)

    monkeypatch.setattr(metainfo_module.rust_accel, "parse_metainfo", wrapped_parse)

    meta = metainfo_module.MetaInfo("旧名 第03集", custom_words=["旧名 => 新名 && 第 <> 集 >> EP+1"])

    assert calls == ["旧名 第03集"]
    assert meta.name == "新名"
    assert meta.episode == "E04"
    assert meta.apply_words == ["旧名 => 新名 && 第 <> 集 >> EP+1"]

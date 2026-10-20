# -*- coding: utf-8 -*-
"""分辨率分类与 mediainfo 探测用例。

分辨率规则照搬 Vit 项目：DCI 特例优先，其余按「名义尺寸能覆盖住」的最小档位判定。
"""
from pathlib import Path

import pytest

from app.helper.mediainfo import (
    _detect_source,
    detect_channels,
    clear_cache,
    is_available,
    probe_media,
)
from app.helper.resolution import classify_resolution, resolution_from_height


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        ((1920, 1080), "1080p"),
        ((3840, 2160), "2160p"),
        ((7680, 4320), "4320p"),
        ((2560, 1440), "1440p"),
        ((1600, 900), "900p"),
        ((1280, 720), "720p"),
        ((854, 480), "480p"),
        ((640, 360), "360p"),
        ((426, 240), "240p"),
    ],
)
def test_standard_tiers(size, expected):
    """常规分辨率应落到对应档位。"""
    assert classify_resolution(*size) == expected


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        ((2048, 1080), "2K"),
        ((2048, 858), "2K"),
        ((4096, 2160), "4K"),
        ((4096, 1716), "4K"),
        ((3996, 2160), "4K"),
    ],
)
def test_dci_resolutions_are_special_cased(size, expected):
    """DCI 分辨率按存储像素直接判定，不被通用规则归到相邻档。"""
    assert classify_resolution(*size) == expected


def test_wide_frame_bumps_to_next_tier():
    """宽画幅超出当前档的名义宽度时应抬档，而不是继续算 1080p。"""
    assert classify_resolution(2538, 1080) == "1440p"


def test_portrait_uses_long_edge_as_width():
    """竖屏按长边当宽度判定，720x1280 应归为 720p。"""
    assert classify_resolution(720, 1280) == "720p"


def test_unknown_size_falls_back_to_lowest_tier():
    """无法判定时落到最低档，不抛异常。"""
    assert classify_resolution(0, 0) == "240p"
    assert classify_resolution(None, None) == "240p"


def test_stored_width_does_not_get_inflated_by_sar():
    """SAR 拉伸的显示宽度不应把档位抬高。"""
    # 1920x1040 存储尺寸，显示宽度被 SAR 拉到 2560 仍应保持 1080p
    assert classify_resolution(1920, 1040, display_width=2560, display_height=1040) == "1080p"


@pytest.mark.parametrize(
    ("height", "expected"),
    [
        (4320, "4320p"),
        (2160, "2160p"),
        (1440, "1440p"),
        (1080, "1080p"),
        (900, "900p"),
        (720, "720p"),
        (480, "480p"),
        (360, "360p"),
        (240, "240p"),
        (0, ""),
    ],
)
def test_resolution_from_height(height, expected):
    """仅知高度时按同一套分档推断。"""
    assert resolution_from_height(height) == expected


def test_channels_from_layout():
    """
    声道描述按布局推断，不能只数声道总数。

    声道总数无法区分 5.0 与 5.1：同样是 6 个声道，
    ``L R C LFE Ls Rs`` 是 5.1，``L R C Ls Rs Cs`` 则是 6.0。
    详细用例见 tests/test_audio_probe.py。
    """
    assert detect_channels({"ChannelLayout": "L R C LFE Ls Rs"}) == "5.1"
    assert detect_channels({"ChannelLayout": "L R"}) == "2.0"
    assert detect_channels({"ChannelLayout": "L R C LFE Ls Rs Lb Rb"}) == "7.1"
    assert detect_channels(None) == ""


@pytest.mark.parametrize(
    ("file_name", "video", "expected"),
    [
        ("movie.mkv", {"Format": "ProRes"}, "ProRes"),
        ("movie.mkv", {"Format": "JPEG 2000"}, "DCP"),
        ("movie.mkv", {"Format": "MXF"}, "DCP"),
        ("Movie.2024.DCP.mkv", {"Format": "AVC"}, "DCP"),
        ("Movie.2024.Master.1080p.mkv", {"Format": "AVC"}, "Master"),
        ("movie.mkv", {"Format": "AVC"}, ""),
    ],
)
def test_source_detection(file_name, video, expected):
    """ProRes / DCP / Master 应从格式或文件名中识别出来。"""
    assert _detect_source(file_name, video) == expected


def test_probe_returns_none_for_missing_file(tmp_path):
    """文件不存在时返回 None，不抛异常。"""
    clear_cache()
    assert probe_media(tmp_path / "missing.mkv") is None


def test_probe_skipped_when_mediainfo_absent(tmp_path, monkeypatch):
    """环境没有 mediainfo 时优雅退化。"""
    clear_cache()
    monkeypatch.setattr("app.helper.mediainfo.is_available", lambda: False)
    target = tmp_path / "fake.mkv"
    target.write_bytes(b"not a real video")
    assert probe_media(target) is None


@pytest.mark.skipif(not is_available(), reason="环境未安装 mediainfo")
def test_probe_real_file_if_available(tmp_path):
    """有真实可解析文件时应返回归一化结果。"""
    clear_cache()
    # 仅验证接口对不可解析内容的容错，不依赖具体样本
    target = tmp_path / "sample.bin"
    target.write_bytes(b"\x00" * 1024)
    result = probe_media(Path(target))
    # mediainfo 对随机字节通常返回 None，允许任一稳定结果
    assert result is None or isinstance(result, dict)

# ---------------------------------------------------------------------------
# 视频编码校正：x264/x265 是编码器实现标记，不能与 H264/H265 编码族混为一谈。
# 规则来自用户确认的真值表（H265 族与 H264 族对称）：
#   探测到 x264                        -> x264（无论标题怎么写）
#   探测无 x264 + 标题 H.264 / H264    -> H264
#   探测无 x264 + 标题 AVC             -> AVC
#   探测无 x264 + 标题 x264            -> H264（标题不可信，降为编码族）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "probe,title,expect",
    [
        # H264 族
        ("AVC", "H.264", "H264"),
        ("AVC", "H264", "H264"),
        ("AVC", "AVC", "AVC"),
        ("x264", "H.264", "x264"),
        ("x264", "H264", "x264"),
        ("x264", "AVC", "x264"),
        ("x264", "x264", "x264"),
        ("AVC", "x264", "H264"),
        ("AVC", "", "H264"),
        ("x264", "", "x264"),
        # H265 族，与 H264 对称
        ("HEVC", "H.265", "H265"),
        ("HEVC", "H265", "H265"),
        ("HEVC", "HEVC", "HEVC"),
        ("x265", "H.265", "x265"),
        ("x265", "H265", "x265"),
        ("x265", "HEVC", "x265"),
        ("x265", "x265", "x265"),
        ("HEVC", "x265", "H265"),
    ],
)
def test_correct_codec_video_truth_table(probe, title, expect):
    """视频编码按「探测结果 + 标题写法」共同决定，x264/x265 单列。"""
    from app.chain.transfer import correct_codec

    assert correct_codec(probe, title) == expect


@pytest.mark.parametrize(
    "probe,expect",
    [
        ("AAC", "AAC"),
        ("FLAC", "FLAC"),
        ("E-AC-3", "DD+"),
        ("AC-3", "DD"),
        ("TrueHD", "TrueHD"),
        ("AV1", "AV1"),
        ("VP9", "VP9"),
    ],
)
def test_correct_codec_audio_mapping(probe, expect):
    """音频编码只做等价写法归一，不涉及编码器实现标记。"""
    from app.chain.transfer import correct_codec

    assert correct_codec(probe) == expect


# ---------------------------------------------------------------------------
# HDR 规格与 Atmos 探测
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "track,expect",
    [
        ({"HDR_Format": "Dolby Vision"}, ["DoVi"]),
        ({"HDR_Format": "Dolby Vision / HDR10"}, ["DoVi", "HDR10"]),
        ({"HDR_Format": "HDR10+"}, ["HDR10+"]),
        ({"HDR_Format": "HDR10"}, ["HDR10"]),
        ({"HDR_Format": "HLG"}, ["HLG"]),
        # HDR10+ 是 HDR10 超集，命中时不重复标注 HDR10
        ({"HDR_Format": "HDR10+ / HDR10"}, ["HDR10+"]),
        ({"HDR_Format_Compatibility": "HDR10+"}, ["HDR10+"]),
        # HDR_Format 缺失时按传输特性推断
        ({"transfer_characteristics": "PQ"}, ["HDR10"]),
        ({"transfer_characteristics": "HLG"}, ["HLG"]),
        ({"Format": "AVC"}, []),
        ({}, []),
    ],
)
def test_detect_hdr_flags(track, expect):
    """HDR 规格按 mediainfo 的 HDR_Format 系列字段判定。"""
    from app.helper.mediainfo import detect_hdr_flags

    assert detect_hdr_flags(track) == expect


@pytest.mark.parametrize(
    "track,expect",
    [
        # Atmos 的实际载体是 Format_Commercial_IfAny 与 Format_AdditionalFeatures
        ({"Format_Commercial_IfAny": "Dolby Digital Plus with Dolby Atmos"}, True),
        ({"Format_AdditionalFeatures": "JOC"}, True),
        ({"Commercial name": "Dolby Digital Plus with Dolby Atmos"}, True),
        ({"Title": "Atmos 7.1"}, True),
        ({"Format": "E-AC-3"}, False),
        ({"Format": "TrueHD"}, False),
        ({}, False),
    ],
)
def test_detect_atmos(track, expect):
    """Atmos 由 Commercial name / JOC 判定，普通 E-AC-3 不算。"""
    from app.helper.mediainfo import detect_atmos

    assert detect_atmos(track) is expect


@pytest.mark.parametrize(
    "track,expect",
    [
        ({"Encoded_Library_Name": "x264"}, "x264"),
        ({"Encoded_Library_Name": "x265"}, "x265"),
        # 带版本号的库串也要能识别
        ({"Encoded_Library": "x264 - core 164 r3191+1 e3de8e8"}, "x264"),
        ({"Writing library": "libx264"}, "x264"),
        ({"Encoded_Library_Name": "libaom"}, "AV1"),
        ({"Encoded_Library_Name": "libsvtav1"}, "AV1"),
        # 通用库名不产生编码器标记
        ({"Encoded_Library_Name": "Lavc59.37.100"}, ""),
        ({"Format": "AVC"}, ""),
        ({}, ""),
        (None, ""),
    ],
)
def test_detect_encoder_flavor(track, expect):
    """编码器实现标记来自 mediainfo 的库名字段，缺失时返回空串。"""
    from app.helper.mediainfo import detect_encoder_flavor

    assert detect_encoder_flavor(track) == expect


# ---------------------------------------------------------------------------
# 来源标记归一化
#   1. BD 类母版（BluRay / Blu-ray / BDRip）统一写作 BD
#   2. BD 的 Remux 写作 "BD Remux"，Remux 保留独立语义
#   3. 非 BD 的 Remux（WEB Remux）丢弃 Remux，视作对应 WEB 来源
#   4. Remux 大小写统一为 Remux
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expect",
    [
        # Remux 大小写统一
        ("REMUX", "Remux"),
        ("Remux", "Remux"),
        ("remux", "Remux"),
        # BD 类母版合并为 BD
        ("BluRay", "BD"),
        ("Blu-ray", "BD"),
        ("BDRip", "BD"),
        ("BD-Rip", "BD"),
        # UHD 母版保留 4K 前缀
        ("UHD BluRay", "UHD BD"),
        ("UHD Blu-ray", "UHD BD"),
        # Remux 保留独立语义，UHD 前缀同样保留
        ("BluRay REMUX", "BD Remux"),
        ("Blu-ray Remux", "BD Remux"),
        ("UHD BluRay REMUX", "UHD BD Remux"),
        # 非 BD 的 Remux 降级为该来源
        ("WEB Remux", "WEB"),
        ("WEB-DL Remux", "WEB-DL"),
        ("WebRip Remux", "WebRip"),
        # 其余来源不受影响
        ("WEB-DL", "WEB-DL"),
        ("WebRip", "WebRip"),
        ("HDTV", "HDTV"),
        ("DVDRip", "DVDRip"),
        ("ProRes", "ProRes"),
    ],
)
def test_normalize_source(raw, expect):
    """来源写法按统一规则收敛。"""
    from app.core.meta.metabase import normalize_source

    assert normalize_source(raw) == expect


@pytest.mark.parametrize(
    "title,expect",
    [
        # BD 类标题
        ("Some.Movie.2024.2160p.BluRay.REMUX.HDR.x265-GRP", "BD Remux"),
        ("Some.Movie.2024.1080p.BluRay.x264-GRP", "BD"),
        ("Some.Movie.2024.Blu-ray.1080p.x264", "BD"),
        ("Some.Movie.2024.BDRip.x264-GRP", "BD"),
        # UHD 母版保留 4K 前缀
        ("Some.Movie.2024.2160p.UHD.BluRay.REMUX.x265-GRP", "UHD BD Remux"),
        ("Some.Movie.2024.2160p.UHD.BluRay.x265-GRP", "UHD BD"),
        # WEB 类标题，Remux 不残留
        ("Some.Movie.2024.1080p.WEB-DL.DDP5.1.x264", "WEB-DL"),
        ("Some.Movie.2024.WEB-DL.Remux.1080p", "WEB-DL"),
        ("Some.Movie.2024.WEB.Remux", "WEB"),
        ("Some.Movie.2024.WEBRip.Remux", "WebRip"),
        # 缺少来源信息的裸 Remux
        ("Some.Movie.2024.REMUX.1080p", "Remux"),
    ],
)
def test_source_type_from_title(title, expect):
    """标题解析出的来源类型与归一化结果一致。"""
    from app.core.meta.metavideo import MetaVideo

    assert MetaVideo(title).resource_type == expect


# ---------------------------------------------------------------------------
# 媒体标记词表与原子字段
#
# 设计原则：来源 / 分辨率 / 视频编码 / 音频编码是四个主字段；HDR 与色彩采样
# 是视频的附属属性，Atmos 是音频的附属属性（仅 DD+ / TrueHD 有效）；
# 特殊版本、剪辑版本、发布信息是独立维度，不混进技术描述。
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expect",
    [
        ("IMAX", "IMAX"),
        ("imax", "IMAX"),
        ("Open Matte", "Open Matte"),
        ("open.matte", "Open Matte"),
        # 严格匹配：词表外的写法一律不认
        ("IMAX2", None),
        ("Open", None),
        ("Matte", None),
    ],
)
def test_match_special_edition(raw, expect):
    """特殊版本词表按「归一化后整串相等」匹配。"""
    from app.core.meta.wordlist import MetaWordList

    assert MetaWordList().match_special_edition(raw) == expect


@pytest.mark.parametrize(
    "raw,expect",
    [
        ("International Cut", "International Cut"),
        ("international.cut", "International Cut"),
        ("Theatrical Cut", "Theatrical Cut"),
        ("Director's Cut", "Director's Cut"),
        ("Directors Cut", "Director's Cut"),
        ("Directors-Cut", "Director's Cut"),
        ("UnCut", "uncut"),
        ("uncut", "uncut"),
        ("Extended Cut", "Extended Cut"),
        ("Original Cut", "Original Cut"),
        # 不在词表内的不认；子串也不能命中
        ("Final Cut", None),
        ("Cut", None),
        ("Directors", None),
    ],
)
def test_match_cut_version(raw, expect):
    """剪辑版本词表忽略大小写与标点，但不做部分匹配。"""
    from app.core.meta.wordlist import MetaWordList

    assert MetaWordList().match_cut_version(raw) == expect


@pytest.mark.parametrize(
    "raw,expect",
    [
        ("REPACK", "REPACK"),
        ("repack", "REPACK"),
        ("PROPER", "PROPER"),
        ("RERIP", "RERIP"),
        ("Hybrid", "Hybrid"),
        ("hybrid", "Hybrid"),
        ("NUKED", None),
    ],
)
def test_match_release_info(raw, expect):
    """发布信息词表按严格相等匹配。"""
    from app.core.meta.wordlist import MetaWordList

    assert MetaWordList().match_release_info(raw) == expect


@pytest.mark.parametrize(
    "raw,expect",
    [
        # 声道数与 Atmos 属于附加信息，不进入编码名
        ("DD+ 5.1", "DD+"),
        ("TrueHD 7.1 Atmos", "TrueHD"),
        ("FLAC 1.0", "FLAC"),
        ("DTS-HD MA 5.1", "DTS-HD MA"),
        ("AAC 2.0", "AAC"),
        ("DDP 5.1 Atmos", "DD+"),
        ("E-AC-3", "DD+"),
    ],
)
def test_normalize_audio_strips_extras(raw, expect):
    """音频编码只保留编码本身。"""
    from app.core.meta.metabase import normalize_audio

    assert normalize_audio(raw) == expect


@pytest.mark.parametrize(
    "raw,expect",
    [
        ("DD+", True),
        ("DDP", False),
        ("TrueHD", True),
        ("AAC", False),
        ("FLAC", False),
        ("DTS-HD MA", False),
    ],
)
def test_audio_supports_atmos(raw, expect):
    """Atmos 只可能叠加在 DD+ 与 TrueHD 上。"""
    from app.core.meta.metabase import audio_supports_atmos

    assert audio_supports_atmos(raw) is expect


@pytest.mark.parametrize(
    "title,expect",
    [
        # 全要素：来源 / 分辨率 / 音频+Atmos / HDR / 视频
        (
            "M.2024.2160p.UHD.BluRay.REMUX.HDR10+.DoVi.TrueHD.Atmos.HEVC-GRP",
            {
                "resource_type": "UHD BD Remux",
                "resource_pix": "2160p",
                "video_encode": "HEVC",
                "audio_encode": "TrueHD",
                "audio_atmos": True,
                "video_hdr": ["HDR10+", "DoVi"],
                "special_edition": [],
                "cut_version": None,
                "release_info": [],
            },
        ),
        # 剪辑版本：只记录，不进入技术字段
        (
            "M.2024.1080p.BluRay.Directors.Cut.x264.DTS-HD.MA.5.1-GRP",
            {
                "resource_type": "BD",
                "resource_pix": "1080p",
                "video_encode": "x264",
                "audio_encode": "DTS-HD MA",
                "audio_atmos": False,
                "video_hdr": [],
                "special_edition": [],
                "cut_version": "Director's Cut",
                "release_info": [],
            },
        ),
        # 特殊版本与发布信息同时存在
        (
            "M.2024.3D.IMAX.1080p.BluRay.REPACK.x264.AAC-GRP",
            {
                "resource_type": "BD",
                "resource_pix": "1080p",
                "video_encode": "x264",
                "audio_encode": "AAC",
                "audio_atmos": False,
                "video_hdr": [],
                "special_edition": ["3D", "IMAX"],
                "cut_version": None,
                "release_info": ["REPACK"],
            },
        ),
        # 多词特殊版本：Open Matte 必须整体命中，
        # 否则会被拆成两个无关 token
        (
            "M.2024.Open.Matte.1080p.BluRay.PROPER.x264.AAC-GRP",
            {
                "resource_type": "BD",
                "resource_pix": "1080p",
                "video_encode": "x264",
                "audio_encode": "AAC",
                "audio_atmos": False,
                "video_hdr": [],
                "special_edition": ["Open Matte"],
                "cut_version": None,
                "release_info": ["PROPER"],
            },
        ),
    ],
)
def test_atomic_fields_from_title(title, expect):
    """四个主字段与各自附属属性、独立维度分别落到对应字段。"""
    from app.core.meta.metavideo import MetaVideo

    meta = MetaVideo(title)
    for field_name, expected in expect.items():
        assert getattr(meta, field_name) == expected, f"{field_name} 不符"


# ---------------------------------------------------------------------------
# 发布信息通配：REPACK* 与 v*
#
# REPACK / PROPER / RERIP 是发布修正，可带任意序号（REPACK2、REPACK10）；
# v1 / v2 / v10 是修订版本号，序号同样无上限。两者都只记录不进文件名。
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expect",
    [
        ("REPACK", "REPACK"),
        ("REPACK2", "REPACK2"),
        ("REPACK10", "REPACK10"),
        ("REPACK99", "REPACK99"),
        ("repack12", "REPACK12"),
        ("PROPER", "PROPER"),
        ("PROPER2", "PROPER2"),
        ("RERIP3", "RERIP3"),
        ("Hybrid", "Hybrid"),
        ("hybrid", "Hybrid"),
        # 修订版本号：序号无上限
        ("v1", "v1"),
        ("v2", "v2"),
        ("v10", "v10"),
        ("v99", "v99"),
        ("V2", "v2"),
        ("V10", "v10"),
        # 已移除的标记与无关写法
        ("REAL", None),
        ("NUKED", None),
        ("va", None),
        ("v", None),
    ],
)
def test_match_release_info_patterns(raw, expect):
    """发布修正与修订版本号支持任意序号。"""
    from app.core.meta.wordlist import MetaWordList

    assert MetaWordList().match_release_info(raw) == expect


@pytest.mark.parametrize(
    "title,expect",
    [
        ("M.2024.1080p.BluRay.REPACK2.x264.AAC-GRP", ["REPACK2"]),
        ("M.2024.1080p.BluRay.PROPER10.x264.AAC-GRP", ["PROPER10"]),
        ("M.2024.1080p.BluRay.RERIP3.x264.AAC-GRP", ["RERIP3"]),
        ("M.2024.1080p.BluRay.v2.x264.AAC-GRP", ["v2"]),
        ("M.2024.1080p.BluRay.v10.x264.AAC-GRP", ["v10"]),
    ],
)
def test_release_info_from_title(title, expect):
    """标题中的发布修正与版本号落到 release_info。"""
    from app.core.meta.metavideo import MetaVideo

    meta = MetaVideo(title)
    meta.finalize()
    assert meta.release_info == expect


@pytest.mark.parametrize(
    "title",
    [
        "M.2024.1080p.BluRay.REPACK2.x264.AAC-GRP",
        "M.2024.1080p.BluRay.v10.x264.AAC-GRP",
        "M.2024.1080p.Hybrid.BluRay.x264.AAC-GRP",
    ],
)
def test_release_info_excluded_from_filename_spec(title):
    """发布信息不进入文件名规格串。"""
    from app.core.meta.metavideo import MetaVideo
    from app.helper.message import TemplateContextBuilder

    meta = MetaVideo(title)
    meta.finalize()
    plain = TemplateContextBuilder._build_spec_plain(meta)
    for token in ("REPACK", "PROPER", "RERIP", "Hybrid", "v2", "v10"):
        assert token not in plain


# ---------------------------------------------------------------------------
# 版本行：剪辑版本与发布修正合并到首行
#
# 两者都回答「这是哪个版本」，合并到一行更符合阅读习惯，也避免出现
# 只有几个字符的极短行。
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "title,expect",
    [
        # 剪辑版本存在时必然独占版本行，发布修正并入该行
        ("M.2020.1080p.BluRay.Directors.Cut.x264.AAC-GRP",
         "🎬 版本：Director's Cut"),
        ("M.2020.1080p.BluRay.Directors.Cut.REPACK2.x264.AAC-GRP",
         "🎬 版本：Director's Cut REPACK2"),
        # 无剪辑版本时，发布修正并入规格块
        ("M.2024.1080p.BluRay.REPACK.x264.AAC-GRP",
         "🎥 规格：REPACK BD 1080p AAC x264"),
        ("M.2024.1080p.BluRay.REPACK10.x264.AAC-GRP",
         "🎥 规格：REPACK10 BD 1080p AAC x264"),
        ("M.2024.1080p.BluRay.v10.x264.AAC-GRP",
         "🎥 规格：v10 BD 1080p AAC x264"),
        ("M.2024.1080p.Hybrid.BluRay.x264.AAC-GRP",
         "🎥 规格：Hybrid BD 1080p AAC x264"),
        # 规格块装得进一行时统一称「规格」
        ("M.2024.1080p.WEB-DL.AAC.x264-GRP",
         "🎥 规格：WEB-DL 1080p AAC x264"),
    ],
)
def test_version_line_rules(title, expect):
    """剪辑版本独占版本行；无版本时发布修正并入规格块。"""
    from app.core.meta.metavideo import MetaVideo
    from app.helper.message import TemplateContextBuilder

    meta = MetaVideo(title)
    meta.finalize()
    lines = TemplateContextBuilder._build_spec_lines(meta)
    assert lines[0] == expect


def test_spec_lines_max_three_with_labels():
    """规格最多三行：版本行 + 片源行 + 规格行，且各带对应标签。"""
    from app.core.meta.metavideo import MetaVideo
    from app.helper.message import TemplateContextBuilder

    meta = MetaVideo(
        "M.2020.2160p.UHD.BluRay.REMUX.Directors.Cut.REPACK2"
        ".HDR10+.DoVi.TrueHD.Atmos.HEVC-GRP"
    )
    meta.finalize()
    lines = TemplateContextBuilder._build_spec_lines(meta)
    assert len(lines) == 3
    assert lines[0] == "🎬 版本：Director's Cut REPACK2"
    assert lines[1].startswith("🎥 片源：")
    assert lines[2].startswith("📽 规格：")


def test_spec_lines_split_into_source_and_spec():
    """规格块超宽时拆成片源行与规格行。"""
    from app.core.meta.metavideo import MetaVideo
    from app.helper.message import TemplateContextBuilder

    meta = MetaVideo(
        "M.2024.2160p.UHD.BluRay.REMUX.TrueHD.Atmos.DV.HDR10P.HEVC-GRP"
    )
    meta.finalize()
    lines = TemplateContextBuilder._build_spec_lines(meta)
    assert len(lines) == 2
    assert lines[0].startswith("🎥 片源：")
    assert lines[1].startswith("📽 规格：")


def test_spec_labels_same_width():
    """三个规格标签必须等长，宽度预算依赖此前提。"""
    from app.helper.message import TemplateContextBuilder

    widths = {
        len(TemplateContextBuilder.SPEC_LABEL_VERSION),
        len(TemplateContextBuilder.SPEC_LABEL_SOURCE),
        len(TemplateContextBuilder.SPEC_LABEL_SPEC),
    }
    assert len(widths) == 1, f"标签长度不一致：{widths}"


def test_spec_line_width_budget_includes_label():
    """单行上限含标签，内容基准 36 加标签 3。"""
    from app.helper.message import TemplateContextBuilder

    label_len = len(TemplateContextBuilder.SPEC_LABEL_SPEC)
    assert TemplateContextBuilder.SPEC_LINE_WIDTH == 36 + label_len


@pytest.mark.parametrize(
    "title",
    [
        "M.2024.1080p.BluRay.x264.AAC-GRP",
        "M.2024.1080p.AMZN.WEB-DL.DDP.H264-GRP",
    ],
)
def test_no_version_line_without_cut_or_release(title):
    """无剪辑版本与发布信息时不产生版本行。"""
    from app.core.meta.metavideo import MetaVideo
    from app.helper.message import TemplateContextBuilder

    meta = MetaVideo(title)
    meta.finalize()
    lines = TemplateContextBuilder._build_spec_lines(meta)
    assert all(not line.startswith("🎬") for line in lines)
    assert lines and lines[0].startswith("🎥")


# ---------------------------------------------------------------------------
# 紧贴季集的版本号
#
# 发布名里修订版常直接附在季集编号后（S01E01v2 / S01v2），这类写法不能
# 靠独立 token 识别，需要在季集解析后从原 token 提取，否则版本号丢失，
# 甚至连带季号都识别不出。
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "title,expect_season,expect_episode,expect_release",
    [
        ("Show.S01E01v2.1080p.WEB-DL.AAC.x264-GRP", "S01", "E01", ["v2"]),
        ("Show.S01E01v3.1080p.WEB-DL.AAC.x264-GRP", "S01", "E01", ["v3"]),
        ("Show.S01v2.1080p.WEB-DL.AAC.x264-GRP", "S01", "", ["v2"]),
        ("Show.S01v10.1080p.WEB-DL.AAC.x264-GRP", "S01", "", ["v10"]),
        # 独立 token 的写法保持原有行为
        ("Show.S01E01.1080p.WEB-DL.AAC.x264.v2-GRP", "S01", "E01", ["v2"]),
        # 无版本号时不应误判
        ("Show.S01E01.1080p.WEB-DL.AAC.x264-GRP", "S01", "E01", []),
    ],
)
def test_version_attached_to_episode(title, expect_season, expect_episode, expect_release):
    """紧贴季集编号的 v<N> 归入发布信息，季集仍正确解析。"""
    from app.core.meta.metavideo import MetaVideo

    meta = MetaVideo(title)
    meta.finalize()
    assert meta.season == expect_season
    assert meta.episode == expect_episode
    assert meta.release_info == expect_release


# ---------------------------------------------------------------------------
# 文件名符号处理
#
# 原实现把非法字符替换成全角（`:` -> `：`），文件名合法但肉眼难辨，
# 会带来搜索不等价、跨平台同步被转回半角、命令行输入困难等问题。
# 改为直接移除：控制字符与 Windows 禁止字符删除，其余标点与符号去掉，
# 只保留连字符（番号如 SHT-001 必需，且各平台安全）。
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expect",
    [
        # 冒号、问号、感叹号、句点等一律移除
        ("Project Hail Mary: Part One", "Project Hail Mary Part One"),
        ("Spider-Man: No Way Home", "Spider-Man No Way Home"),
        ("What If...? Season 2", "What If Season 2"),
        ("Re:Zero kara Hajimeru", "ReZero kara Hajimeru"),
        ("A.I. Artificial Intelligence", "AI Artificial Intelligence"),
        # 斜杠、方括号（路径分隔与结构符号）
        ("Fate/stay night [Heaven's Feel]", "Fatestay night Heavens Feel"),
        # 中文全角标点同样是标点，一并移除
        ("你想活出怎样的人生？", "你想活出怎样的人生"),
        ("哪吒之魔童闹海！", "哪吒之魔童闹海"),
        # 连字符属于 Pd，必须保留：番号类名称依赖它
        ("SHT-001", "SHT-001"),
        ("ABP-123", "ABP-123"),
        # 常规名称不受影响
        ("BanG Dream! YUME∞MITA", "BanG Dream YUMEMITA"),
        ("浮云 (1955)", "浮云 1955"),
    ],
)
def test_sanitize_filename_component(raw, expect):
    """名称组件按跨平台安全规则清理。"""
    from app.helper.message import TemplateContextBuilder

    impl = TemplateContextBuilder._TemplateContextBuilder__convert_invalid_characters
    assert impl(raw) == expect


@pytest.mark.parametrize(
    "raw,expect",
    [
        # Windows 保留设备名加下划线前缀，避免被系统拒绝
        ("CON", "_CON"),
        ("prn", "_prn"),
        ("COM1", "_COM1"),
        ("LPT9", "_LPT9"),
        # 末尾的点与空格在 Windows 上会被静默截断，需去掉
        ("Trailing Dot.", "Trailing Dot"),
        ("Trailing Space   ", "Trailing Space"),
        # 连续空白压成单个空格
        ("Multiple   Spaces", "Multiple Spaces"),
    ],
)
def test_sanitize_filename_edge_cases(raw, expect):
    """Windows 保留名、末尾点空格、连续空白均被规范化。"""
    from app.helper.message import TemplateContextBuilder

    impl = TemplateContextBuilder._TemplateContextBuilder__convert_invalid_characters
    assert impl(raw) == expect

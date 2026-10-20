# -*- coding: utf-8 -*-
"""
音频轨道探测的单元测试。

覆盖两条容易出错的推断链路：DTS 族的具体形态靠 AdditionalFeatures
判定，声道布局要靠解析内容而非数声道总数。
"""
import pytest

from app.helper.mediainfo import (
    detect_audio_format,
    detect_channels,
    pick_audio_track,
    _split_layout_tokens,
)


@pytest.mark.parametrize(
    "layout,expect",
    [
        # 标准布局与 LFE 位置无关：LFE 可以在末尾
        ("L R C LFE Ls Rs", "5.1"),
        ("C L R Ls Rs LFE", "5.1"),
        ("L R C LFE Ls Rs Lb Rb", "7.1"),
        # 无 LFE 时末位为 0，不能因为 6 个声道就写成 5.1
        ("L R C Ls Rs Cs", "6.0"),
        # 单声道两种写法都归为 1.0
        ("M", "1.0"),
        ("L", "1.0"),
        ("L R", "2.0"),
        # 3D 音频：仅在存在高度声道时追加第三段
        ("L R C LFE Ls Rs TFL TFR", "5.1.2"),
        ("L R C LFE Ls Rs Lb Rb TFL TFR TBL TBR", "7.1.4"),
        ("L R C LFE Ls Rs TFL TFR TBL TBR", "5.1.4"),
    ],
)
def test_detect_channels_from_layout(layout, expect):
    """按声道布局推断 x.y(.z)，.1 只在出现 LFE 时计入。"""
    assert detect_channels({"ChannelLayout": layout}) == expect


@pytest.mark.parametrize(
    "positions,expect",
    [
        # ChannelPositions 带分组前辍，剥离冒号前的标签后与布局等价
        ("Front: L C R, Side: L R, LFE", "5.1"),
        ("Front: L R", "2.0"),
        ("Front: L C R, LFE", "3.1"),
        ("Front: L C R, Side: L R, Back: L R, LFE", "7.1"),
    ],
)
def test_detect_channels_from_positions(positions, expect):
    """ChannelLayout 缺失时用 ChannelPositions 兜底。"""
    assert detect_channels({"ChannelPositions": positions}) == expect


def test_layout_tokens_keep_lfe():
    """LFE 是真声道，不能被当作分组标签过滤掉。"""
    assert "LFE" in _split_layout_tokens("L R C LFE Ls Rs")
    assert "LFE" in _split_layout_tokens("Front: L C R, Side: L R, LFE")


def test_layout_tokens_strip_group_labels():
    """带冒号的分组标签必须剥离，不能进入计数。"""
    tokens = _split_layout_tokens("Front: L C R, Side: L R, LFE")
    assert "FRONT" not in tokens
    assert "SIDE" not in tokens
    assert tokens == ["L", "C", "R", "L", "R", "LFE"]


def test_detect_channels_fallback_without_layout():
    """布局缺失时按声道数保守映射。"""
    assert detect_channels({"Channels": "6"}) == "5.1"
    assert detect_channels({"Channels": "8"}) == "7.1"
    assert detect_channels({"Channels": "2"}) == "2.0"


def test_detect_channels_empty():
    """无音轨或字段全空时返回空串。"""
    assert detect_channels(None) == ""
    assert detect_channels({}) == ""


@pytest.mark.parametrize(
    "track,expect",
    [
        # DTS 的形态落在 AdditionalFeatures，只取 Format 会降级为有损 DTS
        ({"Format": "DTS", "Format_AdditionalFeatures": "XLL"}, "DTS-HD MA"),
        ({"Format": "DTS", "Format_AdditionalFeatures": "LBR"}, "DTS Express"),
        ({"Format": "DTS"}, "DTS"),
        # TrueHD 的 Format 是 MLP FBA，须纠正
        ({"Format": "MLP FBA"}, "TrueHD"),
        ({"Format": "MLP FBA", "Format_Commercial_IfAny": "Dolby TrueHD with Dolby Atmos"},
         "TrueHD"),
        # 商业名映射
        ({"Format": "E-AC-3", "Format_Commercial_IfAny": "Dolby Digital Plus"}, "DD+"),
        ({"Format": "AC-3", "Format_Commercial_IfAny": "Dolby Digital"}, "DD"),
        ({"Format": "FLAC"}, "FLAC"),
        ({"Format": "AAC"}, "AAC"),
    ],
)
def test_detect_audio_format(track, expect):
    """音频编码保留区分有损与无损所需的规格后缀。"""
    assert detect_audio_format(track) == expect


def test_detect_audio_format_empty():
    """无音轨时返回空串。"""
    assert detect_audio_format(None) == ""
    assert detect_audio_format({}) == ""


def test_pick_audio_track_prefers_default():
    """Default=Yes 的轨道优先于首条。"""
    tracks = [
        {"@type": "Video"},
        {"@type": "Audio", "Format": "AC-3", "Default": "No"},
        {"@type": "Audio", "Format": "DTS", "Default": "Yes"},
    ]
    assert pick_audio_track(tracks)["Format"] == "DTS"


def test_pick_audio_track_first_when_no_default():
    """无 Default 标记时取首条音轨。"""
    tracks = [
        {"@type": "Audio", "Format": "AC-3"},
        {"@type": "Audio", "Format": "DTS"},
    ]
    assert pick_audio_track(tracks)["Format"] == "AC-3"


def test_pick_audio_track_without_audio():
    """无音轨时返回 None。"""
    assert pick_audio_track([{"@type": "Video"}]) is None
    assert pick_audio_track([]) is None

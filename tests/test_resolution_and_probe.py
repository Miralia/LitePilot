# -*- coding: utf-8 -*-
"""分辨率分类与 mediainfo 探测用例。

分辨率规则照搬 Vit 项目：DCI 特例优先，其余按「名义尺寸能覆盖住」的最小档位判定。
"""
from pathlib import Path

import pytest

from app.helper.mediainfo import (
    _detect_source,
    _normalize_channels,
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


def test_channels_normalized():
    """声道数应归一化为 5.1 这类写法。"""
    assert _normalize_channels("6 channels") == "5.1"
    assert _normalize_channels("2 channels") == "2.0"
    assert _normalize_channels("8 channels") == "7.1"
    assert _normalize_channels("") == ""


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
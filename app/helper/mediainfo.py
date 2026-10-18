# -*- coding: utf-8 -*-
"""
媒体文件技术信息探测。

调用系统 mediainfo（`--Output=JSON`）读取真实文件的技术参数，用于校正标题解析
得到的来源、分辨率等信息，并可写入 NFO。解析与字段归一化参考同一作者的 Vit 项目。

设计约束：

- mediainfo 不存在、文件不可读或输出异常时，一律返回 None，不影响整理主流程；
- 只读探测，不修改文件；
- 结果按文件大小与修改时间做进程内缓存，避免同一文件被反复探测。
"""
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.helper.resolution import classify_resolution
from app.log import logger

# mediainfo 可执行文件名
MEDIAINFO_BIN = "mediainfo"
# 探测超时（秒），大文件解析也可能耗时
TIMEOUT = 30
# 进程内结果缓存：key 为 (路径, 大小, mtime)
_CACHE: Dict[tuple, Optional[dict]] = {}

# 来源判定：按优先级从高到低匹配 mediainfo 的 Format / 文件名特征
SOURCE_RULES = [
    ("ProRes", ("prores",)),
    ("DCP", ("jpeg 2000", "jpeg2000", "mxf", "dcp")),
    ("Master", ("master",)),
]


def is_available() -> bool:
    """
    判断当前环境是否可用 mediainfo。

    :return: 可执行文件存在时返回 True
    """
    return shutil.which(MEDIAINFO_BIN) is not None


def _normalize_channels(value: str) -> str:
    """
    把声道数归一化为 5.1 这类常见写法。

    :param value: mediainfo 的 Channel(s) 原始值，如 "6 channels"
    :return: 归一化后的声道描述
    """
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if not digits:
        return str(value or "")
    count = int(digits)
    return {1: "1.0", 2: "2.0", 6: "5.1", 7: "6.1", 8: "7.1"}.get(count, f"{count}ch")


def _first(track: Dict[str, Any], *keys: str) -> str:
    """
    按顺序取第一个非空字段值。

    :param track: mediainfo 轨道字典
    :param keys: 候选字段名
    :return: 字段值字符串
    """
    for key in keys:
        value = track.get(key)
        if isinstance(value, list):
            value = value[0] if value else None
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _to_int(value: str) -> Optional[int]:
    """
    从带单位的字符串中提取整数。

    :param value: 原始值，如 "1 920 pixels"
    :return: 整数，无法解析时返回 None
    """
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return int(digits) if digits else None


def _pick_track(tracks: List[dict], kind: str) -> Optional[dict]:
    """
    取出指定类型的第一条轨道。

    :param tracks: 轨道列表
    :param kind: 轨道类型，如 Video / Audio / Text
    :return: 轨道字典，找不到时返回 None
    """
    for track in tracks or []:
        if str(track.get("@type") or "").lower() == kind.lower():
            return track
    return None


def _detect_source(file_name: str, video: Optional[dict]) -> str:
    """
    判定发布来源（ProRes / DCP / Master 等特殊类型）。

    :param file_name: 文件名，用于匹配 Master 这类只在命名上体现的来源
    :param video: 视频轨道信息
    :return: 来源名称，无法判定时返回空串
    """
    haystack: List[str] = []
    if video:
        haystack.extend(
            [
                _first(video, "Format", "Format_Info", "Commercial name"),
                _first(video, "Format_Profile", "Format profile"),
            ]
        )
    haystack.append(file_name)
    blob = " ".join(item.lower() for item in haystack if item)
    for source, keywords in SOURCE_RULES:
        if any(keyword in blob for keyword in keywords):
            return source
    return ""


def probe_media(path: Path) -> Optional[dict]:
    """
    探测单个媒体文件的技术信息。

    :param path: 媒体文件路径
    :return: 归一化后的技术信息；不可探测时返回 None
    """
    target = Path(path)
    try:
        stat = target.stat()
        cache_key = (str(target), stat.st_size, int(stat.st_mtime))
    except OSError:
        return None
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    if not is_available():
        _CACHE[cache_key] = None
        return None

    try:
        completed = subprocess.run(  # noqa: S603 - 参数固定，路径由调用方给出
            [MEDIAINFO_BIN, "--Output=JSON", str(target)],
            capture_output=True,
            timeout=TIMEOUT,
            check=False,
        )
    except (subprocess.SubprocessError, OSError) as err:
        logger.debug(f"mediainfo 探测失败：{target} - {err}")
        _CACHE[cache_key] = None
        return None

    if completed.returncode != 0 or not completed.stdout:
        logger.debug(f"mediainfo 返回异常：{target} - rc={completed.returncode}")
        _CACHE[cache_key] = None
        return None

    try:
        payload = json.loads(completed.stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as err:
        logger.debug(f"mediainfo 输出解析失败：{target} - {err}")
        _CACHE[cache_key] = None
        return None

    tracks = payload.get("media", {}).get("track") or []
    video = _pick_track(tracks, "Video")
    audio = _pick_track(tracks, "Audio")

    width = _to_int(_first(video, "Width")) if video else None
    height = _to_int(_first(video, "Height")) if video else None
    # 变形宽银幕按 SAR 拉伸后的显示尺寸判定档位
    display_width = _to_int(_first(video, "PixelAspectRatio", "DisplayAspectRatio")) if video else None

    result = {
        "path": str(target),
        "source": _detect_source(target.name, video),
        "width": width,
        "height": height,
        "resolution": classify_resolution(width, height) if width and height else "",
        "video_codec": _first(video, "Format", "CodecID") if video else "",
        "video_profile": _first(video, "Format_Profile", "Format profile") if video else "",
        "bit_depth": _first(video, "BitDepth") if video else "",
        "hdr": _first(video, "HDR_Format", "HDR format") if video else "",
        "frame_rate": _first(video, "FrameRate", "Frame rate") if video else "",
        "bit_rate": _first(video, "BitRate", "Bit rate") if video else "",
        "audio_codec": _first(audio, "Format", "Commercial name") if audio else "",
        "audio_channels": _normalize_channels(_first(audio, "Channels", "Channel(s)")) if audio else "",
        "duration": _first(_pick_track(tracks, "General") or {}, "Duration") or "",
        "file_size": _first(_pick_track(tracks, "General") or {}, "FileSize") or "",
        "track_count": len(tracks),
        "display_width": display_width,
    }
    _CACHE[cache_key] = result
    return result


def clear_cache() -> None:
    """清空探测缓存，便于测试或配置变更后重新读取。"""
    _CACHE.clear()
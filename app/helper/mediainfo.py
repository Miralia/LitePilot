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

# 编码器库名 -> 发布用编码标记。
# x264/x265 是压制组约定写法，与 H264/H265 同属一族但语义不同：前者说明
# 具体编码器实现，标题与重命名应保留。mediainfo 的 Encoded_Library_Name
# 字段直接给出该信息，缺失时才回退到 Format（AVC/HEVC）。
ENCODER_FLAVORS = {
    "x264": "x264",
    "libx264": "x264",
    "x265": "x265",
    "libx265": "x265",
    "libaom": "AV1",
    "libsvtav1": "AV1",
    "librav1e": "AV1",
    "libvpx-vp9": "VP9",
    "libvpx": "VP8",
    "openh264": "H264",
}


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


def _detect_chroma(video: Optional[dict]) -> str:
    """
    从视频轨道提取色彩采样格式。

    MediaInfo 用 ChromaSubsampling 描述采样方式（如 `4:2:2`），
    结合 ColorSpace=YUV 归一为发布名 YUV422P / YUV444P。
    4:2:0 是最常见的默认值，不作为发布信息标注。

    :param video: 视频轨道信息
    :return: YUV422P / YUV444P，不满足条件时返回空串
    """
    if not video:
        return ""
    color_space = _first(video, "ColorSpace", "colour_space").upper()
    subsampling = _first(video, "ChromaSubsampling", "chroma_subsampling")
    if not subsampling:
        return ""
    # 例：`4:2:2`、`4:2:0 (Type 0)`、`4:4:4`
    normalized = subsampling.replace(" ", "").split("(")[0]
    if "4:4:4" in normalized:
        return "YUV444P" if not color_space or "YUV" in color_space else ""
    if "4:2:2" in normalized:
        return "YUV422P" if not color_space or "YUV" in color_space else ""
    return ""


def detect_hdr_flags(video: Optional[dict]) -> List[str]:
    """
    识别视频轨道的 HDR 规格标记。

    依据 mediainfo 的 HDR_Format* 系列字段，逐项判定 Dolby Vision、
    HDR10+、HDR10、HLG。HDR_Format 缺失时回退到 transfer_characteristics
    推断，避免个别封装没写 HDR_Format 就漏判。

    :param video: mediainfo 的视频轨道字典
    :return: 命中的 HDR 标记列表，SDR 返回空列表
    """
    if not video:
        return []
    # HDR_Format 可能分成 HDR_Format、HDR_Format_Compatibility 等多列
    blob = " ".join(
        str(value or "") for key, value in video.items()
        if key.lower().startswith("hdr_format") and value
    ).lower()

    flags: List[str] = []
    if "dolby vision" in blob or "dovi" in blob:
        flags.append("DoVi")
    # HDR10+ 是 HDR10 的超集，命中时不再重复标注 HDR10
    if "hdr10+" in blob or "hdr10 plus" in blob:
        flags.append("HDR10+")
    elif "hdr10" in blob:
        flags.append("HDR10")
    if "hlg" in blob or "arib std-b67" in blob:
        flags.append("HLG")

    # HDR_Format 缺失时按传输特性推断
    if not flags:
        transfer = _first(video, "transfer_characteristics", "TransferCharacteristics").lower()
        if "bt.2020" in transfer or "2084" in transfer or "pq" in transfer:
            flags.append("HDR10")
        elif "hlg" in transfer or "arib" in transfer:
            flags.append("HLG")
    return flags


def detect_atmos(audio: Optional[dict]) -> bool:
    """
    判断音频轨道是否为 Dolby Atmos。

    mediainfo 不会在 Format 里直接写 Atmos，而是体现在 Commercial name
    （如 "Dolby Digital Plus with Dolby Atmos"）或 Title 中；JOC
    (Joint Object Coding) 是 Atmos 在 E-AC-3 上的承载方式，同样视为命中。

    :param audio: mediainfo 的音频轨道字典
    :return: 命中 Atmos 时返回 True
    """
    if not audio:
        return False
    # mediainfo 的 JSON 键可能是下划线式（commercial_name）也可能是
    # 空格式（Commercial name），两种都要覆盖，统一去空格与下划线后比对。
    # Atmos 的实际载体是 Format_Commercial_IfAny（如 "Dolby Digital Plus
    # with Dolby Atmos"）与 Format_AdditionalFeatures（JOC），两者都要查。
    wanted = {"commercialname", "formatprofile", "format", "title",
              "servicekind", "codecid", "formatcommercialifany",
              "formatadditionalfeatures"}
    blob = " ".join(
        str(value or "") for key, value in audio.items()
        if str(key).lower().replace("_", "").replace(" ", "") in wanted
    ).lower()
    return "atmos" in blob or "joc" in blob


def detect_encoder_flavor(video: Optional[dict]) -> str:
    """
    从视频轨道识别编码器实现对应的发布标记。

    mediainfo 的 Format 字段只给出编码族（AVC / HEVC），无法区分是否由
    x264 / x265 编码；Encoded_Library_Name 与 Encoded_Library 才是权威
    依据。缺失时返回空串，由调用方回退到编码族标记。

    :param video: mediainfo 的视频轨道字典
    :return: x264 / x265 / AV1 等标记，无法判定时返回空串
    """
    if not video:
        return ""
    # Encoded_Library_Name 是纯净库名；Encoded_Library 带版本号，
    # 形如 "x264 - core 164 r3191+1 e3de8e8 [Mod by Patman]"
    for key in ("Encoded_Library_Name", "Encoded_Library", "Writing library"):
        raw = _first(video, key).lower()
        if not raw:
            continue
        for lib_name, flavor in ENCODER_FLAVORS.items():
            if lib_name in raw:
                return flavor
    return ""


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
        # 优先取编码器实现（x264 / x265 / AV1），缺失才回退到编码族。
        # 只取 Format 会把 x264 压制的片子统一写成 H264，丢掉发布标记。
        "video_codec": (
            detect_encoder_flavor(video)
            or _first(video, "Format", "CodecID")
        ) if video else "",
        "video_encoder": detect_encoder_flavor(video) if video else "",
        "video_profile": _first(video, "Format_Profile", "Format profile") if video else "",
        "bit_depth": _first(video, "BitDepth") if video else "",
        # 色彩采样：仅 4:2:2 / 4:4:4 有意义，4:2:0 为常态不标注
        "chroma": _detect_chroma(video) if video else "",
        # HDR 规格：返回命中标记列表，便于上层按需组合成效果字段
        "hdr": _first(video, "HDR_Format", "HDR format") if video else "",
        "hdr_flags": detect_hdr_flags(video) if video else [],
        "frame_rate": _first(video, "FrameRate", "Frame rate") if video else "",
        "bit_rate": _first(video, "BitRate", "Bit rate") if video else "",
        "audio_codec": _first(audio, "Format", "Commercial name") if audio else "",
        "atmos": detect_atmos(audio) if audio else False,
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
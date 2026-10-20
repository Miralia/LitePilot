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
import re
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


# LFE 声道标记：`.1` 专指它，不是「多一个声道」
_LFE_TOKEN = "LFE"
# 3D 音频（Dolby Atmos / DTS:X）的高度层声道标记
_HEIGHT_TOKENS = frozenset(
    {"TFL", "TFR", "TFC", "TBL", "TBR", "TBC", "TSL", "TSR", "TOP"}
)
# 布局完全缺失时的保守映射：假设存在 LFE（业界常态）
_CHANNEL_FALLBACK = {1: "1.0", 2: "2.0", 4: "4.0", 6: "5.1", 8: "7.1"}


def _split_layout_tokens(text: str) -> List[str]:
    """
    把声道布局字符串切成声道标记列表。

    ``ChannelLayout`` 形如 ``L R C LFE Ls Rs``，声道顺序不固定；
    ``ChannelPositions`` 形如 ``Front: L C R, Side: L R, LFE``，多了
    分组前辍。两类字符串里的 ``LFE`` 都是真实声道，必须保留——只有
    带冒号的分组标签（``Front:`` / ``Side:``）才需要剥离。

    因此不能按固定词表过滤：``LFE`` 既可能是分组标签也可能正是要
    统计的声道，只有冒号能可靠区分。

    :param text: 布局或位置字符串
    :return: 纯声道标记列表，已转为大写
    """
    tokens: List[str] = []
    for segment in str(text or "").split(","):
        # 丢弃分组标签，冒号之后的才是声道
        channels = segment.split(":")[-1]
        for token in re.split(r"[\s\-/]+", channels.upper()):
            if token:
                tokens.append(token)
    return tokens


def detect_channels(audio: Optional[dict]) -> str:
    """
    按声道布局与声道数共同推断 ``主声道.低音.高度`` 描述。

    声道总数不足以判断低音声道：6 个声道既可能是
    ``L R C LFE Ls Rs``（5.1），也可能是 ``L R C Ls Rs Cs``
    （5.0 加后中置）。因此必须解析布局内容，``.1`` 只在出现 LFE
    标记时才计入。

    高度层（``.2``）仅在检测到顶部声道标记时追加，否则省略，
    保持 ``5.1`` 这类两段式写法。

    布局缺失时退回声道总数的保守映射，避免给出错误的三段式结果。

    :param audio: mediainfo 的 Audio 轨道
    :return: 如 ``7.1.4`` / ``5.1`` / ``1.0`` 的描述；无法判定时返回空串
    """
    if not audio:
        return ""
    declared = _to_int(_first(audio, "Channels", "Channel(s)"))
    tokens = _split_layout_tokens(_first(audio, "ChannelLayout"))
    if not tokens:
        tokens = _split_layout_tokens(_first(audio, "ChannelPositions"))

    if tokens:
        lfe = sum(1 for token in tokens if token == _LFE_TOKEN)
        height = sum(1 for token in tokens if token in _HEIGHT_TOKENS)
        base = len(tokens) - lfe - height
        # 单声道写法不统一：M（mono）与 L（仅左声道）都归为 1.0
        if base == 1 and not lfe and not height:
            return "1.0"
        if base > 0:
            if declared and declared != len(tokens):
                logger.debug(
                    f"声道数 {declared} 与布局 {len(tokens)} 项不符，按布局计算"
                )
            return f"{base}.{lfe}.{height}" if height else f"{base}.{lfe}"

    if declared:
        return _CHANNEL_FALLBACK.get(declared, f"{declared}ch")
    return ""


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


# mediainfo 的 Format 与商业名对同一编码写法不一，需按商业名纠正。
# 例如 TrueHD 的 Format 是 "MLP FBA"，直接展示会得到无意义的字符串。
_AUDIO_COMMERCIAL_MAP = {
    "DOLBY TRUEHD WITH DOLBY ATMOS": "TrueHD",
    "DOLBY TRUEHD": "TrueHD",
    "DOLBY DIGITAL PLUS": "DD+",
    "DOLBY DIGITAL": "DD",
    "DTS-HD MASTER AUDIO": "DTS-HD MA",
    "DTS-HD HIGH RESOLUTION AUDIO": "DTS-HD HR",
    "DTS EXPRESS": "DTS Express",
}


def detect_audio_format(audio: Optional[dict]) -> str:
    """
    判定音频编码格式，保留区分有损与无损所需的规格后缀。

    mediainfo 的 ``Format`` 对同一族编码只给出基础名，具体形态落在
    ``Format_AdditionalFeatures`` 与 ``Format_Commercial_IfAny``：

    - ``Format=DTS`` + ``AdditionalFeatures=XLL`` 是 DTS-HD MA（无损），
      只取 ``Format`` 会降级成 ``DTS``（有损），两者不可混为一谈
    - TrueHD 的 ``Format`` 返回 ``MLP FBA``，需按商业名纠正

    因此先按 AdditionalFeatures 判定 DTS 族的具体形态，再对
    ``MLP`` 开头的结果统一纠正为 TrueHD，其余退回商业名或 Format。

    :param audio: mediainfo 的 Audio 轨道
    :return: 标准写法；无法判定时返回空串
    """
    if not audio:
        return ""
    fmt = _first(audio, "Format").upper()
    features = _first(audio, "Format_AdditionalFeatures").upper()

    if fmt == "DTS":
        if "XLL" in features:
            return "DTS-HD MA"
        if "LBR" in features:
            return "DTS Express"
        return "DTS"

    # TrueHD 统一以 MLP 开头（MLP FBA / MLP FBB）
    if fmt.startswith("MLP"):
        return "TrueHD"

    commercial = _first(audio, "Format_Commercial_IfAny").upper()
    if commercial in _AUDIO_COMMERCIAL_MAP:
        return _AUDIO_COMMERCIAL_MAP[commercial]
    return _first(audio, "Format")


def pick_audio_track(tracks: List[dict]) -> Optional[dict]:
    """
    从全部轨道中选出主音轨。

    多音轨文件里首条未必是主音轨（制作者常把配音放在前面），
    以 ``Default=Yes`` 为优先标记；没有标记时按轨道顺序取第一条。

    :param tracks: mediainfo 的全部 track
    :return: 主音轨字典；无音轨时返回 None
    """
    audios = [track for track in tracks if track.get("@type") == "Audio"]
    if not audios:
        return None
    for track in audios:
        if str(track.get("Default", "")).strip().lower() == "yes":
            return track
    return audios[0]


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
    audio = pick_audio_track(tracks)

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
        "audio_codec": detect_audio_format(audio),
        "atmos": detect_atmos(audio) if audio else False,
        "audio_channels": detect_channels(audio),
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
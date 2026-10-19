import traceback
from dataclasses import dataclass, field
from typing import Union, Optional, List, Self

import cn2an
import regex as re

from app.log import logger
from app.schemas.types import MediaType
from app.utils.string import StringUtils


TITLE_EPISODE_RE = re.compile(r"Episode\s+(\d{1,4})", re.IGNORECASE)
SUBTITLE_HAS_SEASON_EPISODE_RE = re.compile(r"[全第季集话話期幕]", re.IGNORECASE)
SUBTITLE_SEASON_RE = re.compile(r"(?<![全共]\s*)[第\s]+([0-9一二三四五六七八九十S\-]+)\s*季(?!\s*[全共])", re.IGNORECASE)
SUBTITLE_SEASON_ALL_RE = re.compile(r"[全共]\s*([0-9一二三四五六七八九十]+)\s*季", re.IGNORECASE)
SUBTITLE_EPISODE_RE = re.compile(r"(?<![全共]\s*)[第\s]+([0-9一二三四五六七八九十百零EP]+)\s*[集话話期幕](?!\s*[全共])", re.IGNORECASE)
SUBTITLE_EPISODE_BETWEEN_RE = re.compile(
    r"[第]*\s*([0-9一二三四五六七八九十百零]+)\s*[集话話期幕]?\s*-\s*第*\s*"
    r"([0-9一二三四五六七八九十百零]+)\s*[集话話期幕]",
    re.IGNORECASE,
)
SUBTITLE_EPISODE_ALL_RE = re.compile(
    r"([0-9一二三四五六七八九十百零]+)\s*集\s*全|[全共]\s*([0-9一二三四五六七八九十百零]+)\s*[集话話期幕]",
    re.IGNORECASE,
)
# 结尾分支显式区分有无右方括号，避免可选括号回溯后绕过数字后缀边界
SUBTITLE_EPISODE_RANGE_FIN_RE = re.compile(
    r"(?<!\d)\[?\s*(\d{1,4})\s*-\s*(\d{1,4})\s*"
    r"(?:(?:Fin|End)(?![a-z0-9])|完结(?![\u4e00-\u9fff]))"
    r"(?:\s*\](?!\d)|(?!\s*(?:\]\d|\d))\s*)",
    re.IGNORECASE,
)
# 位深标记：常规写法是 `10bit`；动漫圈还常用 `Ma10p`、`Hi10P` 表示 10bit 编码规格。
# 后者的 `p` 必须限定在 MA/Hi 这类前缀之后，否则会与分辨率里的逐行标记 `1080p` 混淆。
# --- 输出归一化 ---------------------------------------------------------------
# 以下映射把各种等价写法收敛成唯一标准写法，取代原先依赖「自定义识别词」的改写。
# 约定来源：用户确认的大小写规范。
_EFFECT_ALIASES = {
    "DV": "DoVi",
    "DOVI": "DoVi",
    "DOLBY": "DoVi",
    # mediainfo 的 HDR_Format 原文是 "Dolby Vision"，需收敛到 DoVi
    "DOLBY VISION": "DoVi",
    "DOLBYVISION": "DoVi",
    "HDR10PLUS": "HDR10+",
    "HDR10P": "HDR10+",
    "HDR10+": "HDR10+",
    # 基础 HDR10 与 HLG 在 mediainfo 里同样是独立规格
    "HDR10": "HDR10",
    "HDR": "HDR10",
    "HLG": "HLG",
    "HDRVIVID": "HDRVivid",
    "VIVID": "HDRVivid",
}

# 色彩采样：只保留 4:2:2 与 4:4:4 两类高位深色度
_CHROMA_ALIASES = {
    "YUV422P": "YUV422P",
    "YUV444P": "YUV444P",
}
_AUDIO_ALIASES = {
    # Dolby Digital Plus 的多种写法统一为 DD+
    "DDP": "DD+",
    "EAC3": "DD+",
    "E-AC-3": "DD+",
    "DD+": "DD+",
    # Dolby Digital
    "AC3": "DD",
    "AC-3": "DD",
    "DD": "DD",
    # 其余按专有名词大小写收敛
    "OPUS": "Opus",
    "TRUEHD": "TrueHD",
    "ATMOS": "Atmos",
    "VORBIS": "Vorbis",
    "LPCM": "LPCM",
    "FLAC": "FLAC",
    "AAC": "AAC",
    "DTS": "DTS",
    "DTSHD": "DTS-HD",
    "DTSHDMA": "DTS-HD MA",
    "DTS-HD": "DTS-HD",
    "DTS-HD MA": "DTS-HD MA",
}
_PIX_ALIASES = {"4K": "4K", "8K": "8K", "2K": "2K"}

# 来源写法的统一形态（仅规范大小写，不合并同义概念）
# 来源写法的唯一标准形态。
# BD 类来源（BDRip / BluRay / Blu-ray）统一写作 BD：它们指向同一份母版，
# 区分对入库没有意义，反而让同一部片子的不同版本落到不同目录。
# UHD 是分辨率维度但压制组习惯写进来源，保留为 UHD BD 以便区分 4K 母版。
# Remux 是独立的制作方式，必须保留在来源标记里。
_SOURCE_ALIASES = {
    "WEBRIP": "WebRip",
    "WEB-DL": "WEB-DL",
    "WEB": "WEB",
    # BD 类母版合并为 BD
    "BLURAY": "BD",
    "BLU-RAY": "BD",
    "BDRIP": "BD",
    "BD-RIP": "BD",
    "BD": "BD",
    # UHD 母版单独成形态
    "UHD": "UHD",
    "UHD BLURAY": "UHD BD",
    "UHD BLU-RAY": "UHD BD",
    "UHD BDRIP": "UHD BD",
    "UHD BD": "UHD BD",
    # Remux 保留独立形态，统一首字母大写
    "REMUX": "Remux",
    "HDTV": "HDTV",
    "DVDRIP": "DVDRip",
    "PRORES": "ProRes",
    "DCP": "DCP",
    "MASTER": "Master",
}

# 逐段归一化后的复合形态收敛表
_SOURCE_COMPOUND_ALIASES = {
    "BD REMUX": "BD Remux",
    "BD DIY": "BD DIY",
    "BD REMUX DIY": "BD Remux DIY",
    "UHD BD REMUX": "UHD BD Remux",
    "UHD BD DIY": "UHD BD DIY",
    "UHD BD REMUX DIY": "UHD BD Remux DIY",
}


def normalize_effect(value: Optional[str]) -> Optional[str]:
    """把 HDR/特效写法收敛为唯一标准写法。"""
    if not value:
        return value
    text = str(value).strip()
    upper = text.upper()
    if upper in _EFFECT_ALIASES:
        return _EFFECT_ALIASES[upper]
    # YUV422P10 这类带位深后缀的写法，收敛为 YUV422P
    for alias, canonical in _CHROMA_ALIASES.items():
        if upper.startswith(alias):
            return canonical
    return text


# 声道数与 Atmos 属于音轨的附加信息，单独记录，不写进编码名
_AUDIO_CHANNEL_RE = re.compile(
    r"\s*\b[1-9]\.[0-9]\b|\s*\b[1-9]\s*channels?\b", re.IGNORECASE
)
_ATMOS_RE = re.compile(r"\s*\batmos\b", re.IGNORECASE)
# 只有这两个编码承载 Atmos，其它编码带 Atmos 标记属于误识别
_ATMOS_CAPABLE = frozenset({"DD+", "TRUEHD"})


def normalize_audio(value: Optional[str]) -> Optional[str]:
    """
    把音频编码写法收敛为唯一标准写法。

    声道数（``5.1`` / ``1.0``）与 Atmos 属于附加信息，由探测层单独
    记录，编码名只保留编码本身，例如 ``DDP 5.1 Atmos`` -> ``DD+``。

    :param value: 原始音频编码描述
    :return: 归一化后的编码名
    """
    if not value:
        return value
    text = _ATMOS_RE.sub("", str(value))
    text = _AUDIO_CHANNEL_RE.sub("", text).strip()
    if not text:
        return ""
    upper = text.upper()
    if upper in _AUDIO_ALIASES:
        return _AUDIO_ALIASES[upper]
    # 带其它后缀时保留后缀，例如 DTS-HD -> DTS-HD
    for alias, canonical in _AUDIO_ALIASES.items():
        if upper.startswith(alias) and upper != alias:
            rest = text[len(alias):]
            return f"{canonical}{rest}"
    return text


def audio_supports_atmos(value: Optional[str]) -> bool:
    """
    判断该音频编码是否可能承载 Dolby Atmos。

    Atmos 是叠加在 DD+ 或 TrueHD 上的对象音频层，其它编码出现 Atmos
    标记属于误识别，应当丢弃。

    :param value: 音频编码名
    :return: 可能承载 Atmos 时返回 True
    """
    if not value:
        return False
    return str(value).strip().upper().replace(" ", "") in _ATMOS_CAPABLE


def normalize_pix(value: Optional[str]) -> Optional[str]:
    """把分辨率写法收敛：4k/8k 统一为大写 K。"""
    if not value:
        return value
    text = str(value).strip()
    upper = text.upper()
    return _PIX_ALIASES.get(upper, text)


def normalize_source(value: Optional[str]) -> Optional[str]:
    """
    把来源写法收敛为唯一标准形态。

    规则：

    - BD 类来源（BluRay / Blu-ray / BDRip）一律写作 BD
    - UHD 母版写作 ``UHD BD``，保留 4K 母版与普通 BD 的区别
    - BD 的 Remux 写作 ``BD Remux`` / ``UHD BD Remux``，Remux 保留独立语义
    - 非 BD 的 Remux（如 ``WEB Remux``）视作 WEB：Remux 只对 BD 母版有意义，
      WEB 源的 Remux 与普通 WEB 没有入库区别

    :param value: 原始来源标记
    :return: 归一化后的来源标记
    """
    if not value:
        return value
    text = str(value).strip()
    key = text.upper()
    if key in _SOURCE_ALIASES:
        return _SOURCE_ALIASES[key]

    # 组合形态（UHD BluRay / BluRay REMUX 等）逐段归一
    parts = [part for part in text.split() if part]
    normalized = [_SOURCE_ALIASES.get(part.upper(), part) for part in parts]

    deduped: List[str] = []
    for part in normalized:
        # HD 是冗余前缀，直接丢弃；UHD 单独成形态
        if part == "HD":
            continue
        if part == "BD" and "BD" in deduped:
            continue
        deduped.append(part)

    # UHD 与 BD 同时出现时合并为 UHD BD，避免 "UHD BD" 被拆成两段
    if "UHD" in deduped and "BD" in deduped:
        deduped = [part for part in deduped if part not in ("UHD", "BD")]
        insert_at = 0
        deduped.insert(insert_at, "UHD BD")

    result = " ".join(deduped)

    compound = _SOURCE_COMPOUND_ALIASES.get(result.upper())
    if compound:
        return compound

    # 非 BD 来源的 Remux 降级为该来源本身：WEB Remux -> WEB
    if "Remux" in deduped and "BD" not in deduped:
        return next((part for part in deduped if part != "Remux"), result)
    return result


VIDEO_BIT_RE = re.compile(
    r"(?<![A-Za-z0-9])(?P<bit>8|10|12|16)[\s._-]*bits?(?![A-Za-z0-9])"
    r"|(?:MA|HI)(?P<bit_p>8|10|12|16)P(?![A-Za-z0-9])",
    re.IGNORECASE,
)


@dataclass
class MetaBase(object):
    """
    媒体信息基类
    """
    # 是否处理的文件
    isfile: bool = False
    # 原标题字符串（未经过识别词处理）
    title: str = ""
    # 识别用字符串（经过识别词处理后）
    org_string: Optional[str] = None
    # 副标题
    subtitle: Optional[str] = None
    # 类型 电影、电视剧
    type: MediaType = MediaType.UNKNOWN
    # 识别的中文名
    cn_name: Optional[str] = None
    # 识别的英文名
    en_name: Optional[str] = None
    # 未应用识别词时识别出的名称
    original_name: Optional[str] = None
    # 年份
    year: Optional[str] = None
    # 总季数
    total_season: int = 0
    # 识别的开始季 数字
    begin_season: Optional[int] = None
    # 识别的结束季 数字
    end_season: Optional[int] = None
    # 总集数
    total_episode: int = 0
    # 识别的开始集
    begin_episode: Optional[int] = None
    # 识别的结束集
    end_episode: Optional[int] = None
    # Partx Cd Dvd Disk Disc
    part: Optional[str] = None
    # 识别的资源类型
    resource_type: Optional[str] = None
    # 视频 HDR 规格（HDR10 / HDR10+ / DoVi / HLG / HDRVivid）
    video_hdr: List[str] = field(default_factory=list)
    # 视频色彩采样（仅 4:2:2 / 4:4:4 这类高位深色度）
    video_chroma: Optional[str] = None
    # 特殊版本（3D / IMAX / Open Matte），影响播放方式或画幅
    special_edition: List[str] = field(default_factory=list)
    # 剪辑版本（Director's Cut / Extended Cut 等），影响片长与内容
    cut_version: Optional[str] = None
    # 发布信息（REPACK / PROPER / Hybrid 等），描述发布或制作方式
    release_info: List[str] = field(default_factory=list)
    # 识别的分辨率
    resource_pix: Optional[str] = None
    # 识别的制作组/字幕组（多个组以 @ 连接，保持既有语义）
    resource_team: Optional[str] = None
    # 识别的全部制作组/字幕组（合作发布时含多个）
    resource_teams: List[str] = field(default_factory=list)
    # 识别的自定义占位符
    customization: Optional[str] = None
    # 识别的流媒体平台
    web_source: Optional[str] = None
    # 视频编码
    video_encode: Optional[str] = None
    # 视频位深
    video_bit: Optional[str] = None
    # 音频编码
    audio_encode: Optional[str] = None
    # 是否为 Dolby Atmos 音轨（仅 DD+ / TrueHD 有效）
    audio_atmos: bool = False
    # 应用的识别词信息
    apply_words: Optional[List[str]] = None
    # 附加信息
    tmdbid: int = None
    doubanid: str = None
    bangumiid: int = None
    media_source: Optional[str] = None
    media_id: Optional[str] = None
    episode_group: Optional[str] = None
    # 帧率信息（纯数值）
    fps: Optional[int] = None


    # 副标题解析
    _subtitle_flag = False
    _title_episodel_re = r"Episode\s+(\d{1,4})"
    _subtitle_season_re = r"(?<![全共]\s*)[第\s]+([0-9一二三四五六七八九十S\-]+)\s*季(?!\s*[全共])"
    _subtitle_season_all_re = r"[全共]\s*([0-9一二三四五六七八九十]+)\s*季"
    _subtitle_episode_re = r"(?<![全共]\s*)[第\s]+([0-9一二三四五六七八九十百零EP]+)\s*[集话話期幕](?!\s*[全共])"
    _subtitle_episode_between_re = r"[第]*\s*([0-9一二三四五六七八九十百零]+)\s*[集话話期幕]?\s*-\s*第*\s*([0-9一二三四五六七八九十百零]+)\s*[集话話期幕]"
    _subtitle_episode_all_re = r"([0-9一二三四五六七八九十百零]+)\s*集\s*全|[全共]\s*([0-9一二三四五六七八九十百零]+)\s*[集话話期幕]"

    def __init__(self, title: str, subtitle: str = None, isfile: bool = False):
        # default_factory 字段不会生成类属性默认值，手写 __init__ 必须显式初始化，
        # 否则实例上不存在该属性（MetaAnime 曾因此缺失 resource_teams）
        self.resource_teams = []
        self.video_hdr = []
        self.special_edition = []
        self.release_info = []
        if not title:
            return
        self.org_string = title.strip() if title else None
        self.subtitle = subtitle.strip() if subtitle else None
        self.isfile = isfile

    @property
    def name(self) -> str:
        """
        返回名称
        """
        if self.cn_name and StringUtils.is_all_chinese(self.cn_name):
            return self.cn_name
        elif self.en_name:
            return self.en_name
        elif self.cn_name:
            return self.cn_name
        return ""

    @name.setter
    def name(self, name: str):
        """
        设置名称
        """
        if StringUtils.is_all_chinese(name):
            self.cn_name = name
        else:
            self.en_name = name
            self.cn_name = None

    def init_subtitle(self, title_text: str):
        """
        副标题识别
        """
        if not title_text:
            return
        title_text = f" {title_text} "
        episode_str = TITLE_EPISODE_RE.search(title_text)
        if episode_str:
            if episode_str:
                try:
                    episode = int(episode_str.group(1))
                except Exception as err:
                    logger.debug(f'识别集失败：{str(err)} - {traceback.format_exc()}')
                    return
                if episode >= 10000:
                    return
                if self.begin_episode is None:
                    self.begin_episode = episode
                    self.total_episode = 1
                self.type = MediaType.TV
                self._subtitle_flag = True
        elif SUBTITLE_HAS_SEASON_EPISODE_RE.search(title_text):
            # 全x季 x季全
            season_all_str = SUBTITLE_SEASON_ALL_RE.search(title_text)
            if season_all_str:
                season_all = season_all_str.group(1)
                if not season_all:
                    season_all = season_all_str.group(2)
                if season_all and self.begin_season is None and self.begin_episode is None:
                    try:
                        self.total_season = int(cn2an.cn2an(season_all.strip(), mode='smart'))
                    except Exception as err:
                        logger.debug(f'识别季失败：{str(err)} - {traceback.format_exc()}')
                        return
                    self.begin_season = 1
                    self.end_season = self.total_season
                    self.type = MediaType.TV
                    self._subtitle_flag = True
                return
            # 第x季
            season_str = SUBTITLE_SEASON_RE.search(title_text)
            if season_str:
                seasons = season_str.group(1)
                if seasons:
                    seasons = seasons.upper().replace("S", "").strip()
                else:
                    return
                try:
                    end_season = None
                    if seasons.find('-') != -1:
                        seasons = seasons.split('-')
                        begin_season = int(cn2an.cn2an(seasons[0].strip(), mode='smart'))
                        if len(seasons) > 1:
                            end_season = int(cn2an.cn2an(seasons[1].strip(), mode='smart'))
                    else:
                        begin_season = int(cn2an.cn2an(seasons, mode='smart'))
                except Exception as err:
                    logger.debug(f'识别季失败：{str(err)} - {traceback.format_exc()}')
                    return
                if begin_season and begin_season > 100:
                    return
                if end_season and end_season > 100:
                    return
                if self.begin_season is None and isinstance(begin_season, int):
                    self.begin_season = begin_season
                    self.total_season = 1
                if self.begin_season is not None \
                        and self.end_season is None \
                        and isinstance(end_season, int) \
                        and end_season != self.begin_season:
                    self.end_season = end_season
                    self.total_season = (self.end_season - self.begin_season) + 1
                self.type = MediaType.TV
                self._subtitle_flag = True
            # 第x-x集 第x集-x集
            episode_between_str = SUBTITLE_EPISODE_BETWEEN_RE.search(title_text)
            if episode_between_str:
                episodes = episode_between_str.groups()
                if episodes:
                    begin_episode = episodes[0]
                    end_episode = episodes[1]
                else:
                    return
                try:
                    begin_episode = int(cn2an.cn2an(begin_episode.strip(), mode='smart'))
                    end_episode = int(cn2an.cn2an(end_episode.strip(), mode='smart'))
                except Exception as err:
                    logger.debug(f'识别集失败：{str(err)} - {traceback.format_exc()}')
                    return
                if begin_episode and begin_episode >= 10000:
                    return
                if end_episode and end_episode >= 10000:
                    return
                if self.begin_episode is None and isinstance(begin_episode, int):
                    self.begin_episode = begin_episode
                    self.total_episode = 1
                if self.begin_episode is not None \
                        and self.end_episode is None \
                        and isinstance(end_episode, int) \
                        and end_episode != self.begin_episode:
                    self.end_episode = end_episode
                    self.total_episode = (self.end_episode - self.begin_episode) + 1
                self.type = MediaType.TV
                self._subtitle_flag = True
                return
            # 第x集
            episode_str = SUBTITLE_EPISODE_RE.search(title_text)
            if episode_str:
                episodes = episode_str.group(1)
                if episodes:
                    episodes = episodes.upper().replace("E", "").replace("P", "").strip()
                else:
                    return
                try:
                    end_episode = None
                    if episodes.find('-') != -1:
                        episodes = episodes.split('-')
                        begin_episode = int(cn2an.cn2an(episodes[0].strip(), mode='smart'))
                        if len(episodes) > 1:
                            end_episode = int(cn2an.cn2an(episodes[1].strip(), mode='smart'))
                    else:
                        begin_episode = int(cn2an.cn2an(episodes, mode='smart'))
                except Exception as err:
                    logger.debug(f'识别集失败：{str(err)} - {traceback.format_exc()}')
                    return
                if begin_episode and begin_episode >= 10000:
                    return
                if end_episode and end_episode >= 10000:
                    return
                if self.begin_episode is None and isinstance(begin_episode, int):
                    self.begin_episode = begin_episode
                    self.total_episode = 1
                if self.begin_episode is not None \
                        and self.end_episode is None \
                        and isinstance(end_episode, int) \
                        and end_episode != self.begin_episode:
                    self.end_episode = end_episode
                    self.total_episode = (self.end_episode - self.begin_episode) + 1
                self.type = MediaType.TV
                self._subtitle_flag = True
                return
            # x集全/全x集
            episode_all_str = SUBTITLE_EPISODE_ALL_RE.search(title_text)
            if episode_all_str:
                episode_all = episode_all_str.group(1)
                if not episode_all:
                    episode_all = episode_all_str.group(2)
                if episode_all and self.begin_episode is None:
                    try:
                        self.total_episode = int(cn2an.cn2an(episode_all.strip(), mode='smart'))
                    except Exception as err:
                        logger.debug(f'识别集失败：{str(err)} - {traceback.format_exc()}')
                        return
                    self.type = MediaType.TV
                    self._subtitle_flag = True
                return
            # 01-26Fin 等数字范围+完结标记
            self.__init_episode_range_fin(title_text)
        else:
            # 副标题无中文季集标记时，仍识别 01-26Fin 等数字范围+完结标记
            self.__init_episode_range_fin(title_text)

    def __init_episode_range_fin(self, title_text: str):
        """
        识别 01-26Fin / [01-38 END] 等"数字范围+完结标记"格式的集数信息
        """
        episode_range_str = SUBTITLE_EPISODE_RANGE_FIN_RE.search(title_text)
        if not episode_range_str:
            return
        try:
            begin_episode = int(episode_range_str.group(1))
            end_episode = int(episode_range_str.group(2))
        except Exception as err:
            logger.debug(f'识别集失败：{str(err)} - {traceback.format_exc()}')
            return
        if begin_episode < 1 or begin_episode > end_episode or end_episode >= 10000:
            return
        # 两个数字都落在常见年份区间时视为年份范围而非集数（如 2019-2020完结）
        if begin_episode >= 1900 and end_episode <= 2155:
            return
        if self.begin_episode is None:
            self.begin_episode = begin_episode
            self.end_episode = end_episode
            self.total_episode = end_episode
            self.type = MediaType.TV
            self._subtitle_flag = True

    @property
    def season(self) -> str:
        """
        返回开始季、结束季字符串，确定是剧集没有季的返回S01
        """
        if self.begin_season is not None:
            return "S%s" % str(self.begin_season).rjust(2, "0") \
                if self.end_season is None \
                else "S%s-S%s" % \
                     (str(self.begin_season).rjust(2, "0"),
                      str(self.end_season).rjust(2, "0"))
        else:
            if self.type == MediaType.TV:
                return "S01"
            else:
                return ""

    @property
    def sea(self) -> str:
        """
        返回开始季字符串，确定是剧集没有季的返回空
        """
        if self.begin_season is not None:
            return self.season
        else:
            return ""

    @property
    def season_seq(self) -> str:
        """
        返回begin_season 的数字，电视剧没有季的返回1
        """
        if self.begin_season is not None:
            return str(self.begin_season)
        else:
            if self.type == MediaType.TV:
                return "1"
            else:
                return ""

    @property
    def season_list(self) -> List[int]:
        """
        返回季的数组
        """
        if self.begin_season is None:
            if self.type == MediaType.TV:
                return [1]
            else:
                return []
        elif self.end_season is not None:
            return [season for season in range(self.begin_season, self.end_season + 1)]
        else:
            return [self.begin_season]

    @property
    def episode(self) -> str:
        """
        返回开始集、结束集字符串
        """
        if self.begin_episode is not None:
            return "E%s" % str(self.begin_episode).rjust(2, "0") \
                if self.end_episode is None \
                else "E%s-E%s" % \
                     (
                         str(self.begin_episode).rjust(2, "0"),
                         str(self.end_episode).rjust(2, "0"))
        else:
            return ""

    @property
    def episode_list(self) -> List[int]:
        """
        返回集的数组
        """
        if self.begin_episode is None:
            return []
        elif self.end_episode is not None:
            return [episode for episode in range(self.begin_episode, self.end_episode + 1)]
        else:
            return [self.begin_episode]

    @property
    def episodes(self) -> str:
        """
        返回集的并列表达方式，用于支持单文件多集
        """
        return "E%s" % "E".join(str(episode).rjust(2, '0') for episode in self.episode_list)

    @property
    def episode_seqs(self) -> str:
        """
        返回单文件多集的集数表达方式，用于支持单文件多集
        """
        episodes = self.episode_list
        if episodes:
            # 集 xx
            if len(episodes) == 1:
                return str(episodes[0])
            else:
                return "%s-%s" % (episodes[0], episodes[-1])
        else:
            return ""

    @property
    def episode_seq(self) -> str:
        """
        返回begin_episode 的数字
        """
        episodes = self.episode_list
        if episodes:
            return str(episodes[0])
        else:
            return ""

    @property
    def season_episode(self) -> str:
        """
        返回季集字符串
        """
        if self.type == MediaType.TV:
            seaion = self.season
            episode = self.episode
            if seaion and episode:
                return "%s %s" % (seaion, episode)
            elif seaion:
                return "%s" % seaion
            elif episode:
                return "%s" % episode
        else:
            return ""
        return ""

    def finalize(self) -> None:
        """
        解析收尾：把各字段统一收敛成标准写法。

        三条解析路径（MetaVideo / MetaAnime / Rust 加速）都在完成时调用一次，
        避免各处分别实现导致写法漂移。对应原先依赖「自定义识别词」的改写逻辑。
        """
        # HDR 规格与特殊版本按唯一标准写法收敛
        if self.video_hdr:
            normalized_hdr: List[str] = []
            for part in self.video_hdr:
                canonical = normalize_effect(part)
                if canonical and canonical not in normalized_hdr:
                    normalized_hdr.append(canonical)
            self.video_hdr = normalized_hdr
        if self.special_edition:
            normalized_special: List[str] = []
            for part in self.special_edition:
                canonical = normalize_effect(part)
                if canonical and canonical not in normalized_special:
                    normalized_special.append(canonical)
            self.special_edition = normalized_special
        if self.video_chroma:
            self.video_chroma = normalize_effect(self.video_chroma)
        self.audio_encode = normalize_audio(self.audio_encode)
        # Atmos 只叠加在 DD+ / TrueHD 上，其它编码出现该标记属于误识别
        if self.audio_atmos and not audio_supports_atmos(self.audio_encode):
            self.audio_atmos = False
        self.resource_pix = normalize_pix(self.resource_pix)
        self.resource_type = normalize_source(self.resource_type)
        if self.video_encode:
            text = str(self.video_encode)
            # x264/x265 官方写法为小写 x
            text = re.sub(r"\bx(26[45])\b", r"x\1", text, flags=re.IGNORECASE)
            # H.264 / H.265 去掉点号，统一为 H264 / H265
            text = re.sub(r"\bH\.(26[45])\b", r"H\1", text, flags=re.IGNORECASE)
            # 位深属于冗余信息，不进入编码描述（不进通知、不进文件名）
            text = re.sub(
                r"\s*\b(?:8|10|12|16)\s*bits?\b", "", text, flags=re.IGNORECASE
            )
            self.video_encode = text.strip()

    @property
    def release_group(self) -> str:
        """
        返回发布组/字幕组字符串
        """
        if self.resource_team:
            return self.resource_team
        if self.resource_teams:
            return "&".join(self.resource_teams)
        return ""

    @property
    def release_groups(self) -> List[str]:
        """
        返回全部发布组/字幕组，合作发布时包含多个。
        """
        if self.resource_teams:
            return list(self.resource_teams)
        return [self.resource_team] if self.resource_team else []

    @property
    def video_term(self) -> str:
        """
        返回视频编码
        """
        return self.video_encode or ""

    @property
    def audio_term(self) -> str:
        """
        返回音频编码
        """
        return self.audio_encode or ""

    @property
    def frame_rate(self) -> int:
        """
        返回帧率信息
        """
        return self.fps or None

    # 来源类型识别规则：按优先级从高到低匹配，先命中先返回。
    # 组合形态（UHD BluRay、BluRay REMUX、WEB-DL）必须排在基础形态之前，
    # 否则会先匹配到基础词而丢失更精确的来源描述。
    _RESOURCE_TYPE_RULES = [
        # BD 类母版的 Remux 组合形态，必须最先匹配
        ("BluRay REMUX", r"\b(?:UHD\s*)?Blu[\s.\-]?ray\b[\s.\-_]*(?:REMUX|UHD)"),
        # WEB 类的 Remux 组合同样要先于裸 REMUX，否则会丢掉 WEB 前缀，
        # 归一化后无法降级为 WEB
        ("WEB-DL Remux", r"\bWEB[\s.\-]?DL\b[\s.\-_]*REMUX\b"),
        ("WebRip Remux", r"\bWEB[\s.\-]?Rip\b[\s.\-_]*REMUX\b"),
        ("WEB Remux", r"\bWEB\b[\s.\-_]*REMUX\b"),
        ("BluRay", r"\b(?:UHD\s*)?Blu[\s.\-]?ray\b"),
        ("BDRip", r"\bBD[\s.\-]?Rip\b"),
        ("WEB-DL", r"\bWEB[\s.\-]?DL\b"),
        ("WebRip", r"\bWEB[\s.\-]?Rip\b"),
        ("WEB", r"\bWEB\b"),
        # 前面没匹配到的裸 REMUX：缺少来源信息，按 Remux 记录
        ("REMUX", r"\bREMUX\b"),
        ("HDTV", r"\bHDTV\b"),
        ("HDDVD", r"\bHD[\s.\-]?DVD\b"),
        ("DVDRip", r"\bDVD[\s.\-]?Rip\b"),
        ("DVD", r"\bDVD\b"),
        ("ProRes", r"\bProRes\b"),
        ("DCP", r"\bDCP\b"),
        ("Master", r"\bMaster\b"),
    ]
    _RESOURCE_TYPE_RES = [
        (name, re.compile(pattern, re.IGNORECASE))
        for name, pattern in _RESOURCE_TYPE_RULES
    ]

    # 视频编码识别：按优先级匹配，x264/x265 与 H264/H265 保留原文写法
    _VIDEO_ENCODE_RES = [
        (re.compile(r"(?<![A-Za-z0-9])(x26[45])(?![A-Za-z0-9])", re.IGNORECASE), None),
        (re.compile(r"(?<![A-Za-z0-9])(H\.?26[45])(?![A-Za-z0-9])", re.IGNORECASE), None),
        (re.compile(r"(?<![A-Za-z0-9])(HEVC|AVC|AV1|VC-?1|MPEG-?2|Xvid|DivX)(?![A-Za-z0-9])",
                    re.IGNORECASE), None),
    ]

    # 特效/画质标记：与 MetaVideo 的识别范围保持一致
    _EFFECT_TOKEN_RE = re.compile(
        r"(?<![A-Za-z0-9])("
        r"HDR10\+|HDR10Plus|HDR10P|HDRVivid|HDR|HLG|SDR|EDR|DoVi|DOVI|DV|"
        r"3D|REPACK|YUV4[24]4P\d*"
        r")(?![A-Za-z0-9])",
        re.IGNORECASE,
    )

    @staticmethod
    def extract_effect(value: Optional[str]) -> Optional[str]:
        """
        从标题中提取特效/画质标记。

        供 anitopy 路径（MetaAnime）使用：anitopy 不解析这类信息，
        需要与 MetaVideo 保持一致的输出。

        :param value: 原始标题
        :return: 用空格连接的规范化特效串，未识别到返回 None
        """
        if not value:
            return None
        found: List[str] = []
        for match in MetaBase._EFFECT_TOKEN_RE.finditer(str(value)):
            token = normalize_effect(match.group(1))
            if token and token not in found:
                found.append(token)
        return " ".join(found) if found else None

    @staticmethod
    def extract_video_encode(value: Optional[str]) -> Optional[str]:
        """
        从标题中提取视频编码。

        供 anitopy 路径（MetaAnime）兜底：anitopy 的 video_term 覆盖有限，
        像 HEVC 这类常见写法会漏识别，导致通知与重命名缺少编码信息。

        :param value: 原始标题
        :return: 编码名称，未识别到返回 None
        """
        if not value:
            return None
        text = str(value)
        for pattern, _ in MetaBase._VIDEO_ENCODE_RES:
            match = pattern.search(text)
            if not match:
                continue
            token = match.group(1)
            upper = token.upper()
            if upper.startswith("X26"):
                # x264/x265 官方写法为小写 x
                return f"x{upper[1:]}"
            if upper.startswith("H"):
                return upper.replace(".", "")
            return {
                "VC1": "VC1", "VC-1": "VC1",
                "MPEG2": "MPEG2", "MPEG-2": "MPEG2",
                "XVID": "Xvid", "DIVX": "DivX",
            }.get(upper, upper)
        return None

    @staticmethod
    def extract_resource_type(value: Optional[str]) -> Optional[str]:
        """
        从标题中提取来源类型。

        供 anitopy 路径（MetaAnime）使用：anitopy 不解析来源信息，
        导致动画资源拿不到 BluRay / WEB-DL / WebRip 等来源。

        :param value: 原始标题
        :return: 来源名称，未识别到返回 None
        """
        if not value:
            return None
        text = str(value)
        for name, pattern in MetaBase._RESOURCE_TYPE_RES:
            if pattern.search(text):
                return name
        return None

    @staticmethod
    def extract_video_bit(value: Optional[str]) -> Optional[str]:
        """
        从标题或编码文本中提取视频位深标签。
        """
        if not value:
            return None
        bit_match = VIDEO_BIT_RE.search(value)
        if not bit_match:
            return None
        bit = bit_match.group("bit") or bit_match.group("bit_p")
        return f"{bit}bit" if bit else None

    def is_in_season(self, season: Union[list, int, str]) -> bool:
        """
        是否包含季
        """
        if isinstance(season, list):
            if self.end_season is not None:
                meta_season = list(range(self.begin_season, self.end_season + 1))
            else:
                if self.begin_season is not None:
                    meta_season = [self.begin_season]
                else:
                    meta_season = [1]

            return set(meta_season).issuperset(set(season))
        else:
            if self.end_season is not None:
                return self.begin_season <= int(season) <= self.end_season
            else:
                if self.begin_season is not None:
                    return int(season) == self.begin_season
                else:
                    return int(season) == 1

    def is_in_episode(self, episode: Union[list, int, str]) -> bool:
        """
        是否包含集
        """
        if isinstance(episode, list):
            if self.end_episode is not None:
                meta_episode = list(range(self.begin_episode, self.end_episode + 1))
            else:
                meta_episode = [self.begin_episode]
            return set(meta_episode).issuperset(set(episode))
        else:
            if self.end_episode is not None:
                return self.begin_episode <= int(episode) <= self.end_episode
            else:
                return int(episode) == self.begin_episode

    def set_season(self, sea: Union[list, int, str]):
        """
        更新季
        """
        if not sea:
            return
        if isinstance(sea, list):
            if len(sea) == 1 and str(sea[0]).isdigit():
                self.begin_season = int(sea[0])
                self.end_season = None
            elif len(sea) > 1 and str(sea[0]).isdigit() and str(sea[-1]).isdigit():
                self.begin_season = int(sea[0])
                self.end_season = int(sea[-1])
        elif str(sea).isdigit():
            self.begin_season = int(sea)
            self.end_season = None

    def set_episode(self, ep: Union[list, int, str]):
        """
        更新集
        """
        if not ep:
            return
        if isinstance(ep, list):
            if len(ep) == 1 and str(ep[0]).isdigit():
                self.begin_episode = int(ep[0])
                self.end_episode = None
            elif len(ep) > 1 and str(ep[0]).isdigit() and str(ep[-1]).isdigit():
                self.begin_episode = int(ep[0])
                self.end_episode = int(ep[-1])
                self.total_episode = (self.end_episode - self.begin_episode) + 1
        elif str(ep).isdigit():
            self.begin_episode = int(ep)
            self.end_episode = None

    def set_episodes(self, begin: int, end: int):
        """
        设置开始集结束集
        """
        if begin:
            self.begin_episode = begin
        if end:
            self.end_episode = end
        if self.begin_episode and self.end_episode:
            self.total_episode = (self.end_episode - self.begin_episode) + 1

    def merge(self, meta: Self):
        """
        合并Meta信息
        """
        # 类型
        if self.type == MediaType.UNKNOWN \
                and meta.type != MediaType.UNKNOWN:
            self.type = meta.type
        # 名称
        if not self.name:
            self.cn_name = meta.cn_name
            self.en_name = meta.en_name
        # 未应用识别词时识别出的名称
        if not self.original_name:
            self.original_name = meta.original_name
        # 年份
        if not self.year:
            self.year = meta.year
        # 季
        if (self.type == MediaType.TV
                and self.begin_season is None):
            self.begin_season = meta.begin_season
            self.end_season = meta.end_season
            self.total_season = meta.total_season
        # 开始集
        if (self.type == MediaType.TV
                and self.begin_episode is None):
            self.begin_episode = meta.begin_episode
            self.end_episode = meta.end_episode
            self.total_episode = meta.total_episode
        # 版本
        if not self.resource_type:
            self.resource_type = meta.resource_type
        # 分辨率
        if not self.resource_pix:
            self.resource_pix = meta.resource_pix
        # 制作组/字幕组
        if not self.resource_team:
            self.resource_team = meta.resource_team
        # meta 也可能是 schemas.MetaInfo（无该字段），这里做兼容读取
        _incoming_teams = getattr(meta, "resource_teams", None)
        if not self.resource_teams and _incoming_teams:
            self.resource_teams = list(_incoming_teams)
        # 自定义占位符
        if not self.customization:
            self.customization = meta.customization
        # 特效：按归属分别合并，任一侧为空时取另一侧
        _incoming_hdr = getattr(meta, "video_hdr", None)
        if not self.video_hdr and _incoming_hdr:
            self.video_hdr = list(_incoming_hdr)
        if not self.video_chroma:
            self.video_chroma = getattr(meta, "video_chroma", None)
        _incoming_special = getattr(meta, "special_edition", None)
        if not self.special_edition and _incoming_special:
            self.special_edition = list(_incoming_special)
        if not self.cut_version:
            self.cut_version = getattr(meta, "cut_version", None)
        _incoming_release = getattr(meta, "release_info", None)
        if not self.release_info and _incoming_release:
            self.release_info = list(_incoming_release)
        # 视频编码
        if not self.video_encode:
            self.video_encode = meta.video_encode
        # 视频位深
        if not self.video_bit:
            self.video_bit = meta.video_bit
        # 音频编码
        if not self.audio_encode:
            self.audio_encode = meta.audio_encode
        # 帧率信息
        if not self.fps:
            self.fps = meta.fps
        # Part
        if not self.part:
            self.part = meta.part
        # tmdbid
        if not self.tmdbid and meta.tmdbid:
            self.tmdbid = meta.tmdbid
        # doubanid
        if not self.doubanid and meta.doubanid:
            self.doubanid = meta.doubanid
        # 通用媒体来源与ID
        if not self.media_source and meta.media_source:
            self.media_source = meta.media_source
        if not self.media_id and meta.media_id:
            self.media_id = meta.media_id
        # 剧集组
        if not self.episode_group and meta.episode_group:
            self.episode_group = meta.episode_group

    def to_dict(self):
        """
        转为字典
        """
        dicts = vars(self).copy()
        dicts["type"] = self.type.value if self.type else None
        dicts["season_episode"] = self.season_episode
        dicts["name"] = self.name
        dicts["episode_list"] = self.episode_list
        return dicts

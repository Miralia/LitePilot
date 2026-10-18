# -*- coding: utf-8 -*-
"""
动漫标题识别。

本类只负责 anitopy 真正擅长、而通用正则难以覆盖的部分：**作品名称与季集号**。
典型场景包括中文季号（「第四季」）、`Season 2 - 03`、纯数字集号 `- 14`、
以及 `03v2` 这类带版本后缀的集号——这些是 anitopy 的强项。

其余技术字段（来源、分辨率、编码、位深、平台、特效、制作组、帧率）
一律委托给 MetaVideo，避免同一套规则在两处各写一遍导致行为漂移。
"""
import re
import traceback

import anitopy

from app.core.meta.metabase import MetaBase
from app.core.meta.metavideo import MetaVideo
from app.log import logger
from app.schemas.types import MediaType
from app.utils.string import StringUtils
from app.utils.zhconv import convert as zhconv_convert

# 括号内的完整标题，用于 anitopy 取不到名称时兜底
BRACKET_TITLE_RE = re.compile(r"\[(.+?)]")
ANIME_MARK_RE = re.compile(r"新番|月?番|[日美国][漫剧]")
ANIME_PREFIX_RE = re.compile(r".*番.|.*[日美国][漫剧].")
CATEGORY_TAG_RE = re.compile(
    r"[动漫画纪录片电影视连续剧集日美韩中港台海外亚洲华语大陆综艺原盘高清]{2,}"
    r"|TV|Animation|Movie|Documentar|Anime",
    re.IGNORECASE,
)
LEADING_BRACKET_BLOCK_RE = re.compile(r"^[^]]*]")
FILE_SIZE_RE = re.compile(r"[0-9.]+\s*[MGT]i?B(?![A-Z]+)", re.IGNORECASE)
TV_EPISODE_BRACKET_RE = re.compile(r"\[TV\s+(\d{1,4})", re.IGNORECASE)
FOUR_K_BRACKET_RE = re.compile(r"\[4k]", re.IGNORECASE)
NUMERIC_BRACKET_RE = re.compile(r"\[\d+", re.IGNORECASE)
MIXED_CHINESE_TOKEN_RE = re.compile(r"[\d|#:：\-()（）\u4e00-\u9fff]")


class MetaAnime(MetaBase):
    """
    识别动漫。

    名称与季集来自 anitopy，技术字段来自 MetaVideo。
    """

    # anitopy 可能返回这些无意义名称，需要重新解析
    _anime_no_words = ["CHS&CHT", "MP4", "GB MP4", "WEB-DL"]
    # 名称中需要剔除的季集残留，形如 S01、EP12、S01-S02
    _name_nostring_re = (
        r"S\d{2}\s*-\s*S\d{2}|S\d{2}|\s+S\d{1,2}"
        r"|EP?\d{2,4}\s*-\s*EP?\d{2,4}|EP?\d{2,4}|\s+EP?\d{1,4}|\s+GB"
    )
    _name_nostring_pattern = re.compile(_name_nostring_re, re.IGNORECASE)

    @staticmethod
    def _parse_season_number(value):
        """解析第三方动漫季号，仅接受整数或纯数字字符串并保留数值 0。"""
        if value is None:
            return None
        text = str(value).strip()
        return int(text) if text.isdigit() else None

    def __init__(self, title: str, subtitle: str = None, isfile: bool = False):
        super().__init__(title, subtitle, isfile)
        if not title:
            return
        original_title = title
        try:
            info = anitopy.parse(title)
            prepared_title = self.__prepare_title(title)
            info = anitopy.parse(prepared_title) or info
            if info:
                self.__apply_title(info, prepared_title)
                self.__apply_year(info)
                self.__apply_season(info)
                self.__apply_episode(info)
                self.__apply_type(info)
                # 技术字段统一交由 MetaVideo 解析，保证与普通影视标题同源
                self.__apply_technical_fields(original_title)
                # anitopy 对动漫括号写法覆盖更全（如 `[1080]`、`[5.1]`），
                # 仅在通用解析器未取到时用它兜底，不覆盖已有结果
                self.__fill_from_anitopy(info)
                # 副标题只取季集
                self.init_subtitle(self.org_string)
                if not self._subtitle_flag and self.subtitle:
                    self.init_subtitle(self.subtitle)
            if not self.type:
                self.type = MediaType.TV
            self.finalize()
        except Exception as err:  # pylint: disable=broad-except
            logger.error(f"解析动漫信息失败：{err} - {traceback.format_exc()}")

    def __apply_title(self, info: dict, prepared_title: str) -> None:
        """
        从 anitopy 结果提取作品名称，并拆分中英文。

        :param info: anitopy 解析结果
        :param prepared_title: 预处理后的标题
        """
        name = info.get("anime_title")
        if not name or name in self._anime_no_words or (
                len(name) < 5 and not StringUtils.is_chinese(name)
        ):
            fallback = anitopy.parse("[ANIME]" + prepared_title)
            if fallback:
                name = fallback.get("anime_title")
        if not name or name in self._anime_no_words or (
                len(name) < 5 and not StringUtils.is_chinese(name)
        ):
            match = BRACKET_TITLE_RE.search(prepared_title)
            if match and match.group(1):
                name = match.group(1).strip()
        if not name:
            return

        split_done = False
        # 形如「中文名 / English Name」时按斜杠拆分
        if "/" in name:
            names = name.split("/")
            if StringUtils.is_chinese(names[0]):
                self.cn_name = names[0]
                if len(names) > 1:
                    self.en_name = names[1]
                split_done = True
            elif StringUtils.is_chinese(names[-1]):
                self.cn_name = names[-1]
                if len(names) > 1:
                    self.en_name = names[0]
                split_done = True
            else:
                name = names[-1]

        if not split_done:
            lastword_type = ""
            for word in name.split():
                if not word:
                    continue
                if word.endswith("]"):
                    word = word[:-1]
                if word.isdigit():
                    if lastword_type == "cn":
                        self.cn_name = f"{self.cn_name or ''} {word}"
                    elif lastword_type == "en":
                        self.en_name = f"{self.en_name or ''} {word}"
                elif StringUtils.is_chinese(word):
                    self.cn_name = f"{self.cn_name or ''} {word}"
                    lastword_type = "cn"
                else:
                    self.en_name = f"{self.en_name or ''} {word}"
                    lastword_type = "en"

        if self.cn_name:
            _, self.cn_name, _, _, _, _ = StringUtils.get_keyword(self.cn_name)
            if self.cn_name:
                self.cn_name = self._name_nostring_pattern.sub("", self.cn_name).strip()
        if self.en_name:
            self.en_name = self._name_nostring_pattern.sub("", self.en_name).strip().title()

    def __apply_year(self, info: dict) -> None:
        """提取年份。"""
        year = info.get("anime_year")
        if str(year).isdigit():
            self.year = str(year)

    def __apply_season(self, info: dict) -> None:
        """提取季号，支持起止季。"""
        anime_season = info.get("anime_season")
        if isinstance(anime_season, list):
            seasons = [
                season
                for item in anime_season
                if (season := self._parse_season_number(item)) is not None
            ]
            begin_season = seasons[0] if seasons else None
            end_season = seasons[-1] if len(seasons) > 1 else None
        else:
            begin_season = self._parse_season_number(anime_season)
            end_season = None
        if begin_season is None:
            return
        self.begin_season = begin_season
        if end_season is not None and end_season != self.begin_season:
            self.end_season = end_season
            self.total_season = (self.end_season - self.begin_season) + 1
        else:
            self.total_season = 1
        self.type = MediaType.TV

    def __apply_episode(self, info: dict) -> None:
        """提取集号，支持区间。"""
        episode_number = info.get("episode_number")
        if isinstance(episode_number, list):
            begin_episode = episode_number[0] if episode_number else None
            end_episode = episode_number[-1] if len(episode_number) > 1 else None
        else:
            begin_episode = episode_number
            end_episode = None
        if not begin_episode:
            return
        try:
            self.begin_episode = int(begin_episode)
            if end_episode and int(end_episode) != self.begin_episode:
                self.end_episode = int(end_episode)
                self.total_episode = (self.end_episode - self.begin_episode) + 1
            else:
                self.total_episode = 1
        except (TypeError, ValueError) as err:
            logger.debug(f"解析集数失败：{err}")
            self.begin_episode = None
            self.end_episode = None
            return
        self.type = MediaType.TV

    def __apply_type(self, info: dict) -> None:
        """anitopy 未给出季集时，用 anime_type 判断媒体类型。"""
        if self.type:
            return
        anime_type = info.get("anime_type")
        if isinstance(anime_type, list):
            anime_type = anime_type[0] if anime_type else None
        if anime_type and str(anime_type).upper() == "TV":
            self.type = MediaType.TV
        else:
            self.type = MediaType.MOVIE

    def __apply_technical_fields(self, original_title: str) -> None:
        """
        从 MetaVideo 取技术字段。

        这些字段与「是否为动漫」无关，统一由通用解析器负责，
        避免两套实现各写一遍后互相漂移。

        :param original_title: 原始标题
        """
        video = MetaVideo(original_title)
        self.resource_pix = video.resource_pix
        self.resource_type = video.resource_type
        self.resource_effect = video.resource_effect
        self.video_encode = video.video_encode
        self.video_bit = video.video_bit
        self.audio_encode = video.audio_encode
        self.fps = video.fps
        self.web_source = video.web_source
        self.customization = video.customization
        self.resource_teams = list(video.resource_teams or [])
        self.resource_team = video.resource_team
        if not self.year:
            self.year = video.year

    def __fill_from_anitopy(self, info: dict) -> None:
        """
        用 anitopy 结果补齐通用解析器漏掉的字段。

        动漫命名常见 `[1080]`、`[5.1]`、`[1920x1080]` 这类括号写法，
        通用正则不做兜底，这里在缺值时补上。

        :param info: anitopy 解析结果
        """
        if not self.resource_pix:
            pix = info.get("video_resolution")
            if isinstance(pix, list):
                pix = pix[0] if pix else None
            if pix:
                text = str(pix).strip().lower()
                if "x" in text:
                    text = text.split("x")[-1]
                if text.isdigit():
                    text = f"{text}p"
                self.resource_pix = text or None
        if not self.audio_encode:
            audio = info.get("audio_term")
            if isinstance(audio, list):
                audio = audio[0] if audio else None
            if audio:
                self.audio_encode = str(audio).strip() or None

    @staticmethod
    def __prepare_title(title: str):
        """
        对命名进行预处理。
        """
        if not title:
            return title
        # 所有【】换成[]
        title = title.replace("【", "[").replace("】", "]").strip()
        # 截掉xx番剧漫
        match = ANIME_MARK_RE.search(title)
        if match and match.span()[1] < len(title) - 1:
            title = ANIME_PREFIX_RE.sub("", title)
        elif match:
            title = title[:title.rfind("[")]
        # 截掉分类
        first_item = title.split("]")[0]
        if first_item and CATEGORY_TAG_RE.search(zhconv_convert(first_item, "zh-hans")):
            title = LEADING_BRACKET_BLOCK_RE.sub("", title).strip()
        # 去掉大小
        title = FILE_SIZE_RE.sub("", title)
        # 将TVxx改为xx
        title = TV_EPISODE_BRACKET_RE.sub(r"[\1", title)
        # 将4K转为2160p
        title = FOUR_K_BRACKET_RE.sub("2160p", title)
        # 处理/分隔的中英文标题
        names = title.split("]")
        if len(names) > 1 and title.find("- ") == -1:
            titles = []
            for name in names:
                if not name:
                    continue
                left_char = ""
                if name.startswith("["):
                    left_char = "["
                    name = name[1:]
                if name and name.find("/") != -1:
                    if name.split("/")[-1].strip():
                        titles.append("%s%s" % (left_char, name.split("/")[-1].strip()))
                    else:
                        titles.append("%s%s" % (left_char, name.split("/")[0].strip()))
                elif name:
                    if StringUtils.is_chinese(name) and not StringUtils.is_all_chinese(name):
                        if not NUMERIC_BRACKET_RE.search(name):
                            name = MIXED_CHINESE_TOKEN_RE.sub("", name).strip()
                        if not name or name.strip().isdigit():
                            continue
                    if name == "[":
                        titles.append("")
                    else:
                        titles.append("%s%s" % (left_char, name.strip()))
            return "]".join(titles)
        return title

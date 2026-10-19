# -*- coding: utf-8 -*-
"""媒体标记词表：特殊版本、剪辑版本、发布信息。

这三类标记与「来源 / 分辨率 / 编码」不同，它们描述的是**作品形态**或
**发布状态**，而非技术规格，因此单独记录、不进入技术描述：

- 特殊版本：3D / IMAX / Open Matte，影响播放方式或画幅
- 剪辑版本：Director's Cut / Extended Cut 等，影响片长与内容
- 发布信息：REPACK / PROPER / Hybrid，描述发布或制作方式

词表可配置（``SystemConfigKey`` 下的三项），首次运行写入内置默认值。
匹配采用严格相等：待判定文本归一化后必须与词表项完全一致，不做子串
匹配，避免 ``Directors`` 命中 ``Directors Cut`` 这类误判。
"""
import re
from typing import Dict, List, Optional, Tuple

from app.log import logger

# 词表行格式说明：`写法 = 标准名`，只写一个值时两者相同，# 开头为注释
_COMMENT_PREFIX = "#"

# 归一化时剔除的字符：点号、下划线、连字符、撇号与空白在发布名里
# 常互相替代（Director's.Cut / Directors-Cut / directors cut 同义）
_NORMALIZE_STRIP_RE = re.compile(r"[._\-'\s]+")


def _normalize(text: str) -> str:
    """
    把待匹配文本归一化为可比较的形态。

    发布名里 ``Director's.Cut`` / ``Directors-Cut`` / ``directors cut``
    指向同一含义，因此统一去除标点与空白并转小写后再比较，只保留
    字母数字，确保「严格相等」不被书写差异干扰。

    :param text: 原始文本
    :return: 归一化后的文本
    """
    lowered = str(text or "").strip().lower()
    return _NORMALIZE_STRIP_RE.sub("", lowered)


def parse_custom_words(words: Optional[List[str]]) -> List[Tuple[str, str]]:
    """
    解析词表行。

    每行格式为 `写法 = 标准名`；只写一个值时写法与标准名相同。
    以 # 开头的行与空行忽略。

    :param words: 词表行列表
    :return: (写法, 标准名) 列表
    """
    result: List[Tuple[str, str]] = []
    for raw in words or []:
        line = str(raw or "").strip()
        if not line or line.startswith(_COMMENT_PREFIX):
            continue
        if "=" in line:
            pattern, _, canonical = line.partition("=")
            pattern, canonical = pattern.strip(), canonical.strip()
        else:
            pattern = canonical = line
        if not pattern and not canonical:
            continue
        result.append((pattern, canonical or pattern))
    return result


class MetaWordList:
    """
    三类媒体标记词表的加载与严格匹配。

    词表来源是系统配置，识别是高频路径，因此只在配置变化时重建缓存。
    任一词表为空时用内置默认值初始化一次，之后完全由配置驱动。
    """

    # 特殊版本：影响播放方式或画幅的作品形态
    SPECIAL_EDITION: List[Tuple[str, str]] = [
        ("3D", "3D"),
        ("IMAX", "IMAX"),
        ("Open Matte", "Open Matte"),
    ]

    # 剪辑版本：影响片长与内容的版本。
    # 归一化会忽略大小写、点号、连字符与撇号，因此
    # "Director's.Cut" / "Directors-Cut" / "directors cut" 均可命中。
    CUT_VERSION: List[Tuple[str, str]] = [
        ("International Cut", "International Cut"),
        ("Theatrical Cut", "Theatrical Cut"),
        ("Director's Cut", "Director's Cut"),
        ("UnCut", "uncut"),
        ("Extended Cut", "Extended Cut"),
        ("Original Cut", "Original Cut"),
    ]

    # 发布信息：发布或制作方式，不影响内容。
    # 支持「基名 + 序号」变体（REPACK2 / PROPER2 等），由 match_release_info 处理；
    # v2 / v3 这类修订版本号同样归入本维度。
    RELEASE_INFO: List[Tuple[str, str]] = [
        ("REPACK", "REPACK"),
        ("PROPER", "PROPER"),
        ("RERIP", "RERIP"),
        ("Hybrid", "Hybrid"),
    ]

    # 修订版本号的通用前缀：v1 / v2 / v10 都是「第 N 版」，
    # 数量无上限，不适合在词表里逐个枚举
    VERSION_PREFIX = "v"

    def __init__(self) -> None:
        self._special_cache: Dict[str, str] = {}
        self._cut_cache: Dict[str, str] = {}
        self._release_cache: Dict[str, str] = {}
        self._loaded: Optional[Tuple[Tuple[str, ...], ...]] = None
        self._seeded = False
        self._build_caches(
            self.SPECIAL_EDITION, self.CUT_VERSION, self.RELEASE_INFO
        )

    # ------------------------------------------------------------------
    # 词表装配
    # ------------------------------------------------------------------
    @staticmethod
    def _to_lines(pairs: List[Tuple[str, str]]) -> List[str]:
        """
        把 (写法, 标准名) 列表转成词表行。

        :param pairs: 词表项
        :return: `写法 = 标准名` 形式的行列表
        """
        lines: List[str] = []
        for pattern, canonical in pairs:
            if not pattern and not canonical:
                continue
            line = f"{pattern} = {canonical}" if pattern and canonical and pattern != canonical else (pattern or canonical)
            if line and line not in lines:
                lines.append(line)
        return lines

    def builtin_special_edition(self) -> List[str]:
        """返回内置特殊版本词表行。"""
        return self._to_lines(self.SPECIAL_EDITION)

    def builtin_cut_version(self) -> List[str]:
        """返回内置剪辑版本词表行。"""
        return self._to_lines(self.CUT_VERSION)

    def builtin_release_info(self) -> List[str]:
        """返回内置发布信息词表行。"""
        return self._to_lines(self.RELEASE_INFO)

    def _build_caches(
        self,
        special: List[Tuple[str, str]],
        cut: List[Tuple[str, str]],
        release: List[Tuple[str, str]],
    ) -> None:
        """
        重建三张查找表。用户词表追加在内置表之后，同名时后写入的覆盖前者。

        :param special: 特殊版本词表
        :param cut: 剪辑版本词表
        :param release: 发布信息词表
        """
        self._special_cache = {
            _normalize(pattern): canonical
            for pattern, canonical in list(self.SPECIAL_EDITION) + list(special)
            if _normalize(pattern)
        }
        self._cut_cache = {
            _normalize(pattern): canonical
            for pattern, canonical in list(self.CUT_VERSION) + list(cut)
            if _normalize(pattern)
        }
        self._release_cache = {
            _normalize(pattern): canonical
            for pattern, canonical in list(self.RELEASE_INFO) + list(release)
            if _normalize(pattern)
        }

    # ------------------------------------------------------------------
    # 配置加载
    # ------------------------------------------------------------------
    def ensure_loaded(self) -> None:
        """
        按需加载配置词表。

        只在配置内容变化（或首次调用）时查库并重建缓存，避免每次识别都
        访问数据库。
        """
        try:
            from app.db.systemconfig_oper import SystemConfigOper  # pylint: disable=import-outside-toplevel
            from app.schemas.types import SystemConfigKey  # pylint: disable=import-outside-toplevel

            config = SystemConfigOper()
            special_words = config.get(SystemConfigKey.SpecialEditionWords) or []
            cut_words = config.get(SystemConfigKey.CutVersionWords) or []
            release_words = config.get(SystemConfigKey.ReleaseInfoWords) or []
        except Exception as err:  # pylint: disable=broad-except
            logger.debug(f"读取媒体标记词表失败，使用内置表：{err}")
            return

        if not special_words and not cut_words and not release_words and not self._seeded:
            # 三张词表都为空时用内置表初始化一次，之后完全由配置驱动
            special_words = self.builtin_special_edition()
            cut_words = self.builtin_cut_version()
            release_words = self.builtin_release_info()
            try:
                config.set(SystemConfigKey.SpecialEditionWords, special_words)
                config.set(SystemConfigKey.CutVersionWords, cut_words)
                config.set(SystemConfigKey.ReleaseInfoWords, release_words)
                self._seeded = True
            except Exception as err:  # pylint: disable=broad-except
                logger.debug(f"写入默认媒体标记词表失败：{err}")

        fingerprint = (
            tuple(str(item) for item in special_words),
            tuple(str(item) for item in cut_words),
            tuple(str(item) for item in release_words),
        )
        if fingerprint == self._loaded:
            return
        self._loaded = fingerprint
        self.apply_custom(
            special=parse_custom_words(special_words),
            cut=parse_custom_words(cut_words),
            release=parse_custom_words(release_words),
        )

    def apply_custom(
        self,
        special: Optional[List[Tuple[str, str]]] = None,
        cut: Optional[List[Tuple[str, str]]] = None,
        release: Optional[List[Tuple[str, str]]] = None,
    ) -> None:
        """
        应用用户词表并重建查找缓存。

        :param special: 特殊版本 (写法, 标准名) 列表
        :param cut: 剪辑版本 (写法, 标准名) 列表
        :param release: 发布信息 (写法, 标准名) 列表
        """
        self._build_caches(special or [], cut or [], release or [])

    # ------------------------------------------------------------------
    # 严格匹配
    # ------------------------------------------------------------------
    def match_special_edition(self, text: str) -> Optional[str]:
        """
        匹配特殊版本标记。

        :param text: 待判定文本
        :return: 标准名，未命中返回 None
        """
        self.ensure_loaded()
        return self._special_cache.get(_normalize(text))

    def match_cut_version(self, text: str) -> Optional[str]:
        """
        匹配剪辑版本标记。

        :param text: 待判定文本
        :return: 标准名，未命中返回 None
        """
        self.ensure_loaded()
        return self._cut_cache.get(_normalize(text))

    def match_release_info(self, text: str) -> Optional[str]:
        """
        匹配发布信息标记。

        除词表精确匹配外，还支持「基名 + 序号」形式：``REPACK2``、
        ``PROPER3`` 这类同一发布方式的第 N 次修正，按基名判定后保留
        序号，因为它们指向不同的发布批次，合并会丢掉版本信息。

        :param text: 待判定文本
        :return: 标准名，未命中返回 None
        """
        self.ensure_loaded()
        normalized = _normalize(text)
        hit = self._release_cache.get(normalized)
        if hit:
            return hit
        # 修订版本号：v1 / v2 / v10 —— 序号无上限，按通用前缀识别
        version = re.fullmatch(rf"{self.VERSION_PREFIX}(\d+)", normalized)
        if version:
            return f"{self.VERSION_PREFIX}{int(version.group(1))}"

        # 基名 + 纯数字：REPACK2 / RERIP3 / PROPER12
        matched = re.fullmatch(r"([a-z]+)(\d+)", normalized)
        if not matched:
            return None
        base = self._release_cache.get(matched.group(1))
        if not base:
            return None
        return f"{base}{int(matched.group(2))}"


# 全局单例：识别路径共享同一份缓存
meta_word_list = MetaWordList()

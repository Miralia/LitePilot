import re as _std_re
from typing import List, Optional, Tuple

import regex as re

from app.db.systemconfig_oper import SystemConfigOper
from app.schemas.types import SystemConfigKey
from app.utils.singleton import Singleton

# 判断一条内容是否包含「结构性」正则元字符。
# 只认分组、分支、字符类、锚点这类真正改变匹配含义的结构；
# `SubsPlus+` 中的 `+`、`VCB-Studio` 中的 `-` 都按字面量处理。
_REGEX_STRUCTURE = _std_re.compile(r"\(\?:|\(\?=|\(\?!|\\[dDwWsS]|\[\^?[^\]]*\]|\|")

# @ 上游部分的停止字符：常规分段符都算，避免把标题前缀当成组名
_UPSTREAM_STOP_CHARS = frozenset("[]【】￡@&/\\ ._-")

# 组名分段的边界符：@ 回溯上游时遇到这些字符即停止
_GROUP_BOUNDARIES = frozenset("[]【】￡@&/\\ \t")

# 候选组名的边界：出现在 - @ [ ￡ 【 & 之后，且到结尾或分隔符为止
_CANDIDATE_TAIL = re.compile(r"(?<=[-@\[￡【&])([^@.\s\]\[】&/]{2,40})(?=$|[@.\s\]\[】&])", re.I)


def is_regex_pattern(value: str) -> bool:
    """
    判断词表条目是否已经是正则片段。

    :param value: 词表条目
    :return: 含正则元字符时返回 True
    """
    return bool(value) and bool(_REGEX_STRUCTURE.search(value))


class ReleaseGroupsMatcher(metaclass=Singleton):
    """
    识别制作组、字幕组。

    组表本身不再作为唯一来源：内置表只用于首次初始化（作为默认值写入配置），
    之后完全以「词表 → 制作组/字幕组」中的配置为准，可随时增删改。
    """
    # 内置组（首次初始化时写入配置，之后以配置为准）
    RELEASE_GROUPS: dict = {
        "0ff": ['FF(?:(?:A|WE)B|CD|E(?:DU|B)|TV)'],
        "1pt": [],
        "52pt": [],
        "audiences": ['Audies', 'AD(?:Audio|E(?:book|)|Music|Web)'],
        "azusa": [],
        "beitai": ['BeiTai'],
        "btschool": ['Bts(?:CHOOL|HD|PAD|TV)', 'Zone'],
        "carpt": ['CarPT'],
        "chdbits": ['CHD(?:Bits|PAD|(?:|HK)TV|WEB|)', 'StBOX', 'OneHD', 'Lee', 'xiaopie'],
        "discfan": [],
        "dragonhd": [],
        "eastgame": ['(?:(?:iNT|(?:HALFC|Mini(?:S|H|FH)D))-|)TLF'],
        "filelist": [],
        "gainbound": ['(?:DG|GBWE)B'],
        "hares": ['Hares(?:(?:M|T)V|Web|)'],
        "hd4fans": [],
        "hdarea": ['HDA(?:pad|rea|TV)', 'EPiC'],
        "hdatmos": [],
        "hdbd": [],
        "hdchina": ['HDC(?:hina|TV|)', 'k9611', 'tudou', 'iHD'],
        "hddolby": ['D(?:ream|BTV)', '(?:HD|QHstudI)o'],
        "hdfans": ['beAst(?:TV|)'],
        "hdhome": ['HDH(?:ome|Pad|TV|WEB|)'],
        "hdpt": ['HDPT(?:Web|)'],
        "hdsky": ['HDS(?:ky|TV|Pad|WEB|)', 'AQLJ'],
        "hdtime": [],
        "HDU": [],
        "hdvideo": [],
        "hdzone": ['HDZ(?:one|)'],
        "hhanclub": ['HHWEB'],
        "hitpt": [],
        "htpt": ['HTPT'],
        "iptorrents": [],
        "joyhd": [],
        "keepfrds": ['FRDS', 'Yumi', 'cXcY'],
        "lemonhd": ['L(?:eague(?:(?:C|H)D|(?:M|T)V|NF|WEB)|HD)', 'i18n', 'CiNT'],
        "mteam": ['MTeam(?:TV|)', 'MPAD', 'MWeb'],
        "nanyangpt": [],
        "nicept": [],
        "oshen": [],
        "ourbits": ['Our(?:Bits|TV)', 'FLTTH', 'Ao', 'PbK', 'MGs', 'iLove(?:HD|TV)'],
        "panda": ['Panda', 'AilMWeb'],
        "piggo": ['PiGo(?:NF|(?:H|WE)B)'],
        "ptchina": [],
        "pterclub": ['PTer(?:DIY|Game|(?:M|T)V|WEB|)'],
        "pthome": ['PTH(?:Audio|eBook|music|ome|tv|WEB|)'],
        "ptmsg": [],
        "ptsbao": ['PTsbao', 'OPS', 'F(?:Fans(?:AIeNcE|BD|D(?:VD|IY)|TV|WEB)|HDMv)', 'SGXT'],
        "pttime": [],
        "putao": ['PuTao'],
        "soulvoice": [],
        "springsunday": ['CMCT(?:V|)'],
        "sharkpt": ['Shark(?:WEB|DIY|TV|MV|)'],
        "tccf": [],
        "tjupt": ['TJUPT'],
        "totheglory": ['TTG', 'WiKi', 'NGB', 'DoA', '(?:ARi|ExRE)N'],
        "U2": [],
        "ultrahd": [],
        "others": ['B(?:MDru|eyondHD|TN)', 'C(?:fandora|trlhd|MRG)', 'DON', 'EVO', 'FLUX', 'HONE(?:yG|)',
                   'N(?:oGroup|T(?:b|G))', 'PandaMoon', 'SMURF', 'T(?:EPES|aengoo|rollHD )'],
        "anime": ['ANi', 'HYSUB', 'KTXP', 'LoliHouse', 'MCE', 'Nekomoe kissaten', 'SweetSub', 'MingY',
                  '(?:Lilith|NC)-Raws', '织梦字幕组', '枫叶字幕组', '猎户手抄部', '喵萌奶茶屋', '漫猫字幕社',
                  '霜庭云花Sub', '北宇治字幕组', '氢气烤肉架', '云歌字幕组', '萌樱字幕组', '极影字幕社',
                  '悠哈璃羽字幕社',
                  '❀拨雪寻春❀', '沸羊羊(?:制作|字幕组)', '(?:桜|樱)都字幕组'],
        "forge": ['FROG(?:E|Web|)'],
        "ubits": ['UB(?:its|WEB|TV)'],
    }

    @classmethod
    def builtin_group_list(cls) -> List[str]:
        """
        返回内置表摊平后的组名列表。

        用于首次初始化配置：此时配置为空，把内置条目一次性写入词表，
        之后用户可以在页面上自由增删，不再受代码影响。

        :return: 组名/正则片段列表
        """
        groups: List[str] = []
        for site_groups in cls.RELEASE_GROUPS.values():
            for release_group in site_groups:
                if release_group and release_group not in groups:
                    groups.append(release_group)
        return groups

    def __init__(self):
        self.systemconfig = SystemConfigOper()
        self.__groups_re_cache = {}
        self.__seed_applied = False

    def _load_group_words(self) -> List[str]:
        """
        读取配置里的组表；配置为空时用内置表初始化一次。

        :return: 组名列表
        """
        words = self.systemconfig.get(SystemConfigKey.CustomReleaseGroups)
        if isinstance(words, list):
            cleaned = [str(w).strip() for w in words if str(w or "").strip()]
            if cleaned:
                return cleaned
        # 配置为空（首次运行或用户清空）时，用内置表兜底并落库，
        # 使用户之后能在页面上看到并修改这些条目
        defaults = self.builtin_group_list()
        if defaults and not self.__seed_applied:
            self.systemconfig.set(SystemConfigKey.CustomReleaseGroups, defaults)
            self.__seed_applied = True
        return defaults

    def get_release_groups(self) -> str:
        """
        返回当前的制作组匹配规则。

        完全由配置驱动；配置里写的是纯组名，这里统一按字面量转义，
        避免 `VCB-Studio`、`SubsPlus+` 这类名称被当成正则而失效或误匹配。
        以 `re:` 开头或明显含正则结构的条目按正则处理，便于高级用法。
        """
        escaped = []
        for name in self._load_group_words():
            cleaned = name.strip()
            if not cleaned:
                continue
            if cleaned.startswith("re:"):
                # 显式声明为正则片段
                escaped.append(cleaned[3:])
            elif is_regex_pattern(cleaned):
                # 内置表搬过来的条目本身就是正则（如 FF(?:(?:A|WE)B|...)），保持原样
                escaped.append(cleaned)
            else:
                # 用户手写的纯组名按字面量转义，保证 `VCB-Studio`、`SubsPlus+` 精确匹配
                escaped.append(_std_re.escape(cleaned))
        return "|".join(escaped)

    def __get_groups_re(self, groups: str):
        """
        发布组规则通常很长，按规则文本缓存编译结果，避免每个标题都重复编译。
        """
        groups_re = self.__groups_re_cache.get(groups)
        if not groups_re:
            groups_re = re.compile(r"(?<=[-@\[￡【&])(?:(?:%s))(?=$|[@.\s\]\[】&])" % groups, re.I)
            self.__groups_re_cache[groups] = groups_re
        return groups_re

    def match_list(self, title: str = None, groups: str = None) -> List[str]:
        """
        匹配出全部制作组，支持合作发布。

        两条语义：

        - `&` 是合作发布，两侧各算一个小组：`SweetSub&VCB-Studio` 得到两个组。
        - `@` 是从属关系，整体算一个小组：`Baha@SweetSub` 得到 `Baha@SweetSub`。

        :param title: 资源标题或文件名
        :param groups: 制作组/字幕组
        :return: 去重后的组名列表，按出现顺序
        """
        if not title:
            return []
        if not groups:
            groups = self.get_release_groups()
        groups_re = self.__get_groups_re(groups)
        unique_groups: List[str] = []
        for match in groups_re.finditer(title):
            start, end = match.start(), match.end()

            # 命中项前面是 @：把它与上游合起来当作一个小组，
            # `Baha@SweetSub` 记为 `Baha@SweetSub` 而不是两个组。
            while start > 0 and title[start - 1] == "@":
                cursor = start - 1
                while cursor > 0 and title[cursor - 1] not in _UPSTREAM_STOP_CHARS:
                    cursor -= 1
                if cursor == start - 1:
                    break
                start = cursor

            # 命中项后面是 @：把下游一起并入，`CMCT@制作者` 记为 `CMCT@制作者`。
            while end < len(title) and title[end] == "@":
                cursor = end + 1
                while cursor < len(title) and title[cursor] not in _UPSTREAM_STOP_CHARS:
                    cursor += 1
                if cursor == end + 1:
                    break
                end = cursor

            item_str = title[start:end]
            if item_str.strip():
                unique_groups.append(item_str)

        # 链式 @ 会同时产出 `Baha@SweetSub` 与 `Baha@SweetSub@VCB-Studio`，
        # 只保留被更长命中包含的那一条，避免重复计数。
        deduped: List[str] = []
        for item in unique_groups:
            if any(item != other and item in other for other in unique_groups):
                continue
            if item not in deduped:
                deduped.append(item)
        return deduped

    def match(self, title: str = None, groups: str = None):
        """
        匹配制作组，多个组时以 @ 连接（保持既有行为）。

        :param title: 资源标题或文件名
        :param groups: 制作组/字幕组
        :return: 匹配结果
        """
        return "@".join(self.match_list(title=title, groups=groups))

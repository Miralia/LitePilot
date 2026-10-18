import re
from typing import Dict, List, Optional, Tuple

from app.log import logger
from app.utils.singleton import Singleton

# 输出形态：全称（默认，保持既有整理结果不变）或简称
DISPLAY_FULL = "full"
DISPLAY_SHORT = "short"


class StreamingPlatforms(metaclass=Singleton):
    """
    流媒体平台简称与全称。

    内置表只用于首次初始化：首次读取时把内置条目写入「词表 → 流媒体平台」，
    之后完全以配置为准，可随时增删改。输出形态（全称/简称）由系统配置控制。
    """
    STREAMING_PLATFORMS: List[Tuple[str, str]] = [
        ("AMZN", "Amazon"),
        ("NF", "Netflix"),
        ("ATVP", "Apple TV+"),
        ("iT", "iTunes"),
        ("DSNP", "Disney+"),
        ("HS", "Hotstar"),
        ("APPS", "Disney+ MENA"),
        ("PMTP", "Paramount+"),
        ("HMAX", "Max"),
        ("", "Max"),
        ("HULU", "Hulu Networks"),
        ("MA", "Movies Anywhere"),
        ("BCORE", "Bravia Core"),
        ("MS", "Microsoft Store"),
        ("SHO", "Showtime"),
        ("STAN", "Stan"),
        ("PCOK", "Peacock"),
        ("SKST", "SkyShowtime"),
        ("NOW", "Now"),
        ("FXTL", "Foxtel Now"),
        ("BNGE", "Binge"),
        ("CRKL", "Crackle"),
        ("RKTN", "Rakuten TV"),
        ("ALL4", "Channel 4"),
        ("AS", "Adult Swim"),
        ("BRTB", "Brtb TV"),
        ("CNLP", "Canal+"),
        ("CRIT", "Criterion Channel"),
        ("DSCP", "Discovery+"),
        ("FOOD", "Food Network"),
        ("MUBI", "Mubi"),
        ("PLAY", "Google Play"),
        ("YT", "YouTube"),
        ("", "friDay"),
        ("", "KKTV"),
        ("", "ofiii"),
        ("", "LiTV"),
        ("", "MyVideo"),
        ("Hami", "Hami Video"),
        ("HamiVideo", "Hami Video"),
        ("MW", "meWATCH"),
        ("CATCHPLAY", "CATCHPLAY+"),
        ("CPP", "CATCHPLAY+"),
        ("LINETV", "LINE TV"),
        ("VIU", "Viu"),
        ("IQ", ""),
        ("", "WeTV"),
        ("ABMA", "Abema"),
        ("ADN", ""),
        ("AT-X", ""),
        ("Baha", ""),
        ("BG", "B-Global"),
        ("CR", "Crunchyroll"),
        ("", "DMM"),
        ("FOD", ""),
        ("FUNi", "Funimation"),
        ("HIDI", "HIDIVE"),
        ("UNXT", "U-NEXT"),
        ("FAA", "Filmarchiv Austria"),
        ("CC", "Comedy Central"),
        ("iP", "BBC iPlayer"),
        ("9NOW", "9Now"),
        ("ABC", ""),
        ("", "AMC"),
        ("", "ZEE5"),
        ("", "WAVO"),
        ("SHAHID", "Shahid"),
        ("Flixole", "FlixOlé"),
        ("TOU", "Ici TOU.TV"),
        ("ROKU", "Roku"),
        ("KNPY", "Kanopy"),
        ("SNXT", "Sun NXT"),
        ("CUR", "Curiosity Stream"),
        ("MY5", "Channel 5"),
        ("AHA", "aha"),
        ("WOWP", "WOW Presents Plus"),
        ("JC", "JioCinema"),
        ("", "Dekkoo"),
        ("FILMZIE", "Filmzie"),
        ("HoiChoi", "Hoichoi"),
        ("VIKI", "Rakuten Viki"),
        ("SF", "SF Anytime"),
        ("PLEX", "Plex"),
        ("SHDR", "Shudder"),
        ("CRAV", "Crave"),
        ("CPE", "Cineplex Entertainment"),
        ("JF HC", ""),
        ("JF", ""),
        ("JFFP", ""),
        ("VIAP", "Viaplay"),
        ("TUBI", "TubiTV"),
        ("", "PBS"),
        ("PBSK", "PBS KIDS"),
        ("LGP", "Lionsgate Play"),
        ("", "CTV"),
        ("", "Cineverse"),
        ("LN", "Love Nature"),
        ("MP", "Movistar Plus+"),
        ("RUNTIME", "Runtime"),
        ("STZ", "STARZ"),
        ("FUBO", "fuboTV"),
        ("TENK", "Tënk"),
        ("KNOW", "Knowledge Network"),
        ("TVO", "tvo"),
        ("", "OVID"),
        ("CBC", "CBC Gem"),
        ("FANDOR", "fandor"),
        ("CW", "The CW"),
        ("KNPY", "Kanopy"),
        ("FREE", "Freeform"),
        ("AE", "A&E"),
        ("LIFE", "Lifetime"),
        ("WWEN", "WWE Network"),
        ("CMAX", "Cinemax"),
        ("HLMK", "Hallmark"),
        ("BYU", "BYUtv"),
        ("", "ViX"),
        ("VICE", "Viceland"),
        ("", "TVING"),
        ("USAN", "USA Network"),
        ("FOX", ""),
        ("", "TCM"),
        ("BRAV", "BravoTV"),
        ("", "TNT"),
        ("", "ZDF"),
        ("", "IndieFlix"),
        ("", "TLC"),
        ("", "HGTV"),
        ("ANPL", "Animal Planet"),
        ("TRVL", "Travel Channel"),
        ("", "VH1"),
        ("SAINA", "Saina Play"),
        ("SP", "Saina Play"),
        ("OXGN", "Oxygen"),
        ("PSN", "PlayStation Network"),
        ("PMNT", "Paramount Network"),
        ("FAWESOME", "Fawesome"),
        ("KLASSIKI", "Klassiki"),
        ("STRP", "Star+"),
        ("NATG", "National Geographic"),
        ("REVEEL", "Reveel"),
        ("FYI", "FYI Network"),
        ("WatchiT", "WATCH IT"),
        ("ITVX", "ITV"),
        ("GAIA", "Gaia"),
        ("", "FlixLatino"),
        ("CNNP", "CNN+"),
        ("TROMA", "Troma"),
        ("IVI", "Ivi"),
        ("9NOW", "9Now"),
        ("A3P", "Atresplayer"),
        ("7PLUS", "7plus"),
        ("", "SBS"),
        ("TEN", "10Play"),
        ("AUBC", ""),
        ("DSNY", "Disney Networks"),
        ("OSN", "OSN+"),
        ("SVT", "Sveriges Television"),
        ("LACINETEK", "LaCinetek"),
        ("", "Maxdome"),
        ("RTL", "RTL+"),
        ("ARTE", "Arte"),
        ("JOYN", "Joyn"),
        ("TV2", "TV 2"),
        ("3SAT", "3sat"),
        ("FILMINGO", "filmingo"),
        ("", "WOW"),
        ("OKKO", "Okko"),
        ("", "Go3"),
        ("ARGP", "Argo"),
        ("VOYO", "Voyo"),
        ("VMAX", "vivamax"),
        ("FILMIN", "Filmin"),
        ("", "Mitele"),
        ("MY5", "Channel 5"),
        ("", "ARD"),
        ("BK", "Bentkey"),
        ("BOOM", "Boomerang"),
        ("", "CBS"),
        ("CLBI", "Club illico"),
        ("CMOR", "C More"),
        ("CMT", ""),
        ("", "CNBC"),
        ("COOK", "Cooking Channel"),
        ("CWS", "CW Seed"),
        ("DCU", "DC Universe"),
        ("DDY", "Digiturk Dilediğin Yerde"),
        ("DEST", "Destination America"),
        ("DISC", "Discovery Channel"),
        ("DW", "DailyWire+"),
        ("DLWP", "DailyWire+"),
        ("DPLY", "dplay"),
        ("DRPO", "Dropout"),
        ("EPIX", "EPIX MGM+"),
        ("ESQ", "Esquire"),
        ("ETV", "E!"),
        ("FBWatch", "Facebook Watch"),
        ("FPT", "FPT Play"),
        ("FTV", "France.tv"),
        ("GLOB", "GloboSat Play"),
        ("GLBO", "Globoplay"),
        ("GO90", "go90"),
        ("HIST", "History Channel"),
        ("HPLAY", "Hungama Play"),
        ("KS", "Kaleidescape"),
        ("", "MBC"),
        ("MMAX", "ManoramaMAX"),
        ("MNBC", "MSNBC"),
        ("MTOD", "Motor Trend OnDemand"),
        ("NBC", ""),
        ("NBLA", "Nebula"),
        ("NICK", "Nickelodeon"),
        ("ODK", "OnDemandKorea"),
        ("POGO", "PokerGO"),
        ("PUHU", "puhutv"),
        ("QIBI", "Quibi"),
        ("RTE", "RTÉ"),
        ("SESO", "Seeso"),
        ("SPIK", "Spike"),
        ("SS", "Simply South"),
        ("SYFY", "SyFy"),
        ("TIMV", "TIMvision"),
        ("TK", "Tentkotta"),
        ("", "TV4"),
        ("TVL", "TV Land"),
        ("", "TVNZ"),
        ("", "UKTV"),
        ("VLCT", "Discovery Velocity"),
        ("VMEO", "Vimeo"),
        ("VRV", "VRV Defunct"),
        ("WTCH", "Watcha"),
        ("", "NowPlayer"),
        ("HuluJP", "Hulu Networks"),
        ("Gaga", "GagaOOLala"),
        ("MyTVS", "MyTVSuper"),
        ("", "BBC"),
        ("CC", "Comedy Central"),
        ("NowE", "Now E"),
        ("WAVVE", "Wavve"),
        ("SE", ""),
        ("", "BritBox"),
        ("AOD", "Anime on Demand"),
        ("AF", ""),
        ("BCH", "Bandai Channel"),
        ("VMJ", "VideoMarket"),
        ("LFTL", "Laftel"),
        ("WAKA", "Wakanim"),
        ("WAKANIM", "Wakanim"),
        ("AO", "AnimeOnegai"),
        ("", "Lemino"),
        ("VIDIO", "Vidio"),
        ("TVER", "TVer"),
        ("", "MBS"),
        ("LFTLNET", "Laftel"),
        ("JONU", "Jonu Play"),
        ("PlutoTV", "Pluto TV"),
        ("AbemaTV", "Abema"),
        ("", "dTV"),
        ("NYMEY", "Nymey"),
        ("SMNS", "SAMANSA"),
        ("CTHP", "CATCHPLAY+"),
        ("HBOGO", "HBO GO"),
        ("HBO", "HBO"),
        ("FPTP", "FPT Play"),
        ("", "LOCIPO"),
        ("DANT", "DANET"),
        ("OV", "OceanVeil"),
    ]

    def __init__(self):
        """初始化流媒体平台匹配器"""
        self._lookup_cache: Dict[str, str] = {}
        self._short_lookup: Dict[str, str] = {}
        self._display_mode = DISPLAY_FULL
        # 已加载的配置快照，用于判断是否需要在配置变更后重建缓存
        self._loaded_words: Optional[List[str]] = None
        self._loaded_mode: Optional[str] = None
        self._seeded = False
        self._build_cache()

    @classmethod
    def builtin_word_list(cls) -> List[str]:
        """
        返回内置平台表对应的词表行。

        首次初始化时写入配置，让用户能在页面上看到并修改这些条目。

        :return: `简称 = 全称` 形式的行列表
        """
        lines: List[str] = []
        for short_name, full_name in cls.STREAMING_PLATFORMS:
            if not short_name and not full_name:
                continue
            line = f"{short_name} = {full_name}" if short_name and full_name else (short_name or full_name)
            if line and line not in lines:
                lines.append(line)
        return lines

    def ensure_loaded(self) -> None:
        """
        按需加载用户词表与输出形态。

        识别是高频路径，因此只在配置发生变化（或首次调用）时查库并重建缓存。
        """
        try:
            from app.db.systemconfig_oper import SystemConfigOper  # pylint: disable=import-outside-toplevel
            from app.schemas.types import SystemConfigKey  # pylint: disable=import-outside-toplevel

            config = SystemConfigOper()
            words = config.get(SystemConfigKey.CustomStreamingPlatforms) or []
            mode = config.get(SystemConfigKey.StreamingPlatformDisplay)
        except Exception as err:  # pylint: disable=broad-except
            logger.debug(f"读取流媒体平台配置失败，使用内置表：{err}")
            return

        if not words and not self._seeded:
            # 配置为空时用内置表初始化一次，之后完全由配置驱动
            words = self.builtin_word_list()
            if words:
                config.set(SystemConfigKey.CustomStreamingPlatforms, words)
                self._seeded = True

        if words == (self._loaded_words or []) and mode == self._loaded_mode:
            return
        self._loaded_words = list(words)
        self._loaded_mode = mode
        self.apply_custom(words=words, display_mode=mode)

    @staticmethod
    def parse_custom_words(words: Optional[List[str]]) -> List[Tuple[str, str]]:
        """
        解析用户自定义词表。

        每行格式为 `简称 = 全称`；只写一个值时简称与全称相同。
        以 # 开头的行为注释，空行忽略。

        :param words: 词表行列表
        :return: (简称, 全称) 列表
        """
        result: List[Tuple[str, str]] = []
        for raw in words or []:
            line = str(raw or "").strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                short_name, _, full_name = line.partition("=")
                short_name, full_name = short_name.strip(), full_name.strip()
            else:
                short_name = full_name = line
            if not short_name and not full_name:
                continue
            result.append((short_name, full_name or short_name))
        return result

    def apply_custom(
        self,
        words: Optional[List[str]] = None,
        display_mode: Optional[str] = None,
    ) -> None:
        """
        应用用户词表与输出形态，并重建查询缓存。

        :param words: 用户自定义词表行
        :param display_mode: full 输出全称、short 输出简称
        """
        self._display_mode = (
            display_mode if display_mode in (DISPLAY_FULL, DISPLAY_SHORT) else DISPLAY_FULL
        )
        custom = self.parse_custom_words(words)
        # 用户词表放后面，同名时覆盖内置表
        self._build_cache(custom)

    def _resolve_display(self, short_name: str, full_name: str) -> str:
        """
        按当前输出形态返回展示值。

        :param short_name: 简称
        :param full_name: 全称
        :return: 展示值
        """
        canonical_short = short_name or full_name
        canonical_full = full_name or short_name
        if self._display_mode == DISPLAY_SHORT:
            return canonical_short
        return canonical_full

    def _build_cache(self, custom: Optional[List[Tuple[str, str]]] = None) -> None:
        """
        构建查询缓存。

        :param custom: 用户自定义 (简称, 全称) 列表，优先级高于内置表
        """
        self._lookup_cache.clear()
        self._short_lookup.clear()
        for short_name, full_name in list(self.STREAMING_PLATFORMS) + list(custom or []):
            canonical_name = self._resolve_display(short_name, full_name)
            if not canonical_name:
                continue

            # 记录简称与全称的对应关系，供输出形态切换时反查
            if short_name and full_name:
                self._short_lookup[full_name.upper()] = short_name

            aliases = {short_name, full_name}
            for alias in aliases:
                if alias:
                    self._lookup_cache[alias.upper()] = canonical_name

    def get_short_name(self, platform_code: str) -> Optional[str]:
        """
        根据简称或全称取回简称，用于输出形态为简称时的反查。

        :param platform_code: 平台简称或全称
        :return: 简称，未知时返回 None
        """
        if platform_code is None:
            return None
        key = platform_code.upper()
        resolved = self._lookup_cache.get(key)
        if not resolved:
            return None
        return self._short_lookup.get(key, resolved)

    def get_display_name(self, platform_code: str) -> Optional[str]:
        """
        把任意写法（简称或全称）转换成当前输出形态的展示名。

        Rust 解析路径只返回内置表的全称，用户开启简称后需要用这里重新归一，
        否则页面开关对这条路径无效。

        :param platform_code: 平台简称或全称
        :return: 按当前输出形态的展示名，未知时原样返回
        """
        if not platform_code:
            return platform_code
        resolved = self._lookup_cache.get(str(platform_code).upper())
        return resolved or platform_code

    def detect_from_text(self, text: str) -> Optional[str]:
        """
        从标题文本中识别流媒体平台，按当前输出形态返回展示名。

        :param text: 原始标题
        :return: 展示名，未识别到返回 None
        """
        if not text:
            return None
        # 按分隔符切分后逐段匹配，避免把标题里的普通单词误判成平台
        for token in re.split(r"[\s\.\[\]\(\)【】_]+", str(text)):
            if not token:
                continue
            resolved = self._lookup_cache.get(token.upper())
            if resolved:
                return resolved
        return None

    def get_lookup_cache(self) -> dict:
        """
        返回流媒体平台查询表副本，供批量解析配置复用。
        """
        return dict(self._lookup_cache)

    def get_streaming_platform_name(self, platform_code: str) -> Optional[str]:
        """
        根据流媒体平台简称或全称获取标准名称。
        """
        if platform_code is None:
            return None
        return self._lookup_cache.get(platform_code.upper())

    def is_streaming_platform(self, name: str) -> bool:
        """
        判断给定的字符串是否为已知的流媒体平台代码或名称。
        """
        if name is None:
            return False
        return name.upper() in self._lookup_cache

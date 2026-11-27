import bisect
import hashlib
import re
import unicodedata
from typing import Union, Tuple, Optional, Any, List, Dict

import cn2an

from app.schemas.types import MediaType

_max_media_title_words = 10
_min_media_title_length = 2
_non_media_title_pattern = re.compile(r"^#|^请[问帮你]|[?？]$|^继续$")
_chat_intent_pattern = re.compile(r"帮我|请问|怎么|如何|为什么|可以|能否|推荐|介绍|谢谢|想看|找一下|搜一下")
_media_feature_pattern = re.compile(
    r"第\s*[0-9一二三四五六七八九十百零]+\s*[季集]|S\d{1,2}(?:E\d{1,4})?|E\d{1,4}|(?:19|20)\d{2}",
    re.IGNORECASE
)
_media_separator_pattern = re.compile(r"[\s\-_.:：·'\"()\[\]【】]+")
_media_sentence_punctuation_pattern = re.compile(r"[，。！？!?,；;]")
_media_title_char_pattern = re.compile(r"[\u4e00-\u9fffA-Za-z]")


class StringUtils:

    @staticmethod
    def str_secends(time_sec: Union[str, int, float]) -> str:
        """
        将秒转为时分秒字符串
        """
        hours = time_sec // 3600
        remainder_seconds = time_sec % 3600
        minutes = remainder_seconds // 60
        seconds = remainder_seconds % 60

        time: str = str(int(seconds)) + '秒'
        if minutes:
            time = str(int(minutes)) + '分' + time
        if hours:
            time = str(int(hours)) + '时' + time
        return time

    @staticmethod
    def is_chinese(word: Union[str, list]) -> bool:
        """
        判断是否含有中文
        """
        if not word:
            return False
        if isinstance(word, list):
            word = " ".join(word)
        chn = re.compile(r'[\u4e00-\u9fff]')
        if chn.search(word):
            return True
        else:
            return False

    @staticmethod
    def is_all_chinese(word: str) -> bool:
        """
        判断是否全是中文
        """
        for ch in word:
            if ch == ' ':
                continue
            if '\u4e00' <= ch <= '\u9fff':
                continue
            else:
                return False
        return True

    @staticmethod
    def clear(text: Union[list, str], replace_word: str = "",
              allow_space: bool = False) -> Union[list, str]:
        """
        忽略特殊字符
        """
        # 需要忽略的特殊字符
        CONVERT_EMPTY_CHARS = r"[、.。,，·:：;；!！?？'’\"“”()（）\[\]【】「」\-—―\+\|\\_/&#～~]"
        if not text:
            return text
        if not isinstance(text, list):
            # 先做 Unicode 兼容分解并剥离组合记号，让 É / ñ / ü 这类带变音
            # 符号的字母退回基本字母。片名的罗马字写法与 TMDB 别名常常只差
            # 一个重音符号（如 Paris ni Saku Étoile），不做归一化会导致
            # 完全相同的名称判为不等而匹配失败。
            text = "".join(
                ch for ch in unicodedata.normalize("NFKD", str(text))
                if not unicodedata.combining(ch)
            )
            text = re.sub(r"[\u200B-\u200D\uFEFF]",
                          "",
                          re.sub(r"%s" % CONVERT_EMPTY_CHARS, replace_word, text),
                          flags=re.IGNORECASE)
            if not allow_space:
                return re.sub(r"\s+", "", text)
            else:
                return re.sub(r"\s+", " ", text).strip()
        else:
            return [StringUtils.clear(x) for x in text]

    @staticmethod
    def clear_upper(text: Optional[str]) -> str:
        """
        去除特殊字符，同时大写
        """
        if not text:
            return ""
        return StringUtils.clear(text).upper().strip()

    @staticmethod
    def str_filesize(size: Union[str, float, int], pre: int = 2) -> str:
        """
        将字节计算为文件大小描述（带单位的格式化后返回）
        """
        if size is None:
            return ""
        size = re.sub(r"\s|B|iB", "", str(size), re.I)
        if size.replace(".", "").isdigit():
            try:
                size = float(size)
                d = [(1024 - 1, 'K'), (1024 ** 2 - 1, 'M'), (1024 ** 3 - 1, 'G'), (1024 ** 4 - 1, 'T')]
                s = [x[0] for x in d]
                index = bisect.bisect_left(s, size) - 1  # noqa
                if index == -1:
                    return str(size) + "B"
                else:
                    b, u = d[index]
                return str(round(size / (b + 1), pre)) + u
            except ValueError:
                return ""
        if re.findall(r"[KMGTP]", size, re.I):
            return size
        else:
            return size + "B"

    @staticmethod
    def md5_hash(data: Any) -> str:
        """
        MD5 HASH
        """
        if not data:
            return ""
        return hashlib.md5(str(data).encode()).hexdigest()

    @staticmethod
    def count_words(text: str) -> int:
        """
        计算字符串中包含的单词或汉字的数量，需要兼容中英文混合的情况
        :param text: 要计算的字符串
        :return: 字符串中包含的词数量
        """
        if not text:
            return 0
        # 使用正则表达式匹配汉字和英文单词
        chinese_pattern = '[\u4e00-\u9fa5]'
        english_pattern = '[a-zA-Z]+'

        # 匹配汉字和英文单词
        chinese_matches = re.findall(chinese_pattern, text)
        english_matches = re.findall(english_pattern, text)

        # 过滤掉空格和数字
        chinese_words = [word for word in chinese_matches if word.isalpha()]
        english_words = [word for word in english_matches if word.isalpha()]

        # 计算汉字和英文单词的数量
        chinese_count = len(chinese_words)
        english_count = len(english_words)

        return chinese_count + english_count

    @staticmethod
    def is_media_title_like(text: str) -> bool:
        """
        判断文本是否像影视剧名称
        """
        if not text:
            return False
        text = re.sub(r'\s+', ' ', text).strip()
        if not text:
            return False
        if _non_media_title_pattern.search(text) \
                or StringUtils.count_words(text) > _max_media_title_words:
            return False
        if "://" in text or text.startswith("magnet:?"):
            return False
        if _chat_intent_pattern.search(text):
            return False
        if _media_sentence_punctuation_pattern.search(text):
            return False

        # 先移除季/集/年份等媒体特征，再移除分隔符，只保留核心名称用于最终判定
        candidate = _media_feature_pattern.sub("", text)
        candidate = _media_separator_pattern.sub("", candidate)
        return len(candidate) >= _min_media_title_length and _media_title_char_pattern.search(candidate) is not None

    @staticmethod
    def get_keyword(content: str) \
            -> Tuple[Optional[MediaType], Optional[str], Optional[int], Optional[int], Optional[str], Optional[str]]:
        """
        从搜索关键字中拆分中年份、季、集、类型
        """
        if not content:
            return None, None, None, None, None, None

        # 去掉查询中的电影或电视剧关键字
        mtype = MediaType.TV if re.search(r'^(电视剧|动漫|\s+电视剧|\s+动漫)', content) else None
        content = re.sub(r'^(电影|电视剧|动漫|\s+电影|\s+电视剧|\s+动漫)', '', content).strip()

        # 稍微切一下剧集吧
        season_num = None
        episode_num = None
        season_re = re.search(r'第\s*([0-9一二三四五六七八九十]+)\s*季', content, re.IGNORECASE)
        if season_re:
            mtype = MediaType.TV
            season_num = int(cn2an.cn2an(season_re.group(1), mode='smart'))

        episode_re = re.search(r'第\s*([0-9一二三四五六七八九十百零]+)\s*集', content, re.IGNORECASE)
        if episode_re:
            mtype = MediaType.TV
            episode_num = int(cn2an.cn2an(episode_re.group(1), mode='smart'))
            if episode_num is not None and season_num is None:
                season_num = 1

        year_re = re.search(r'[\s(]+(\d{4})[\s)]*', content)
        year = year_re.group(1) if year_re else None

        key_word = re.sub(
            r'第\s*[0-9一二三四五六七八九十]+\s*季|第\s*[0-9一二三四五六七八九十百零]+\s*集|[\s(]+(\d{4})[\s)]*', '',
            content, flags=re.IGNORECASE).strip()
        key_word = re.sub(r'\s+', ' ', key_word) if key_word else year

        return mtype, key_word, season_num, episode_num, year, content

    @staticmethod
    def str_title(s: Optional[str]) -> str:
        """
        大写首字母兼容None
        """
        return s.title() if s else s

    @staticmethod
    def get_domain_address(address: str, prefix: bool = True) -> Tuple[Optional[str], Optional[int]]:
        """
        从地址中获取域名和端口号
        :param address: 地址
        :param prefix：返回域名是否要包含协议前缀
        """
        if not address:
            return None, None
        # 去掉末尾的/
        address = address.rstrip("/")
        if prefix and not address.startswith("http"):
            # 如果需要包含协议前缀，但地址不包含协议前缀，则添加
            address = "http://" + address
        elif not prefix and address.startswith("http"):
            # 如果不需要包含协议前缀，但地址包含协议前缀，则去掉
            address = address.split("://")[-1]
        # 拆分域名和端口号
        parts = address.split(":")
        if len(parts) > 3:
            # 处理不希望包含多个冒号的情况（除了协议后的冒号）
            return None, None
        elif len(parts) == 3:
            port = int(parts[-1])
            # 不含端口地址
            domain = ":".join(parts[:-1]).rstrip('/')
        elif len(parts) == 2:
            port = 443 if address.startswith("https") else 80
            domain = address
        else:
            return None, None
        return domain, port

    @staticmethod
    def format_season_episode(pairs: List[Tuple[int, int]]) -> str:
        """
        把 (季, 集) 列表格式化为紧凑的季集区间。

        季集要连写成 ``S02E50``，而不是 ``S02 E50``——前者是发布名与媒体
        库通用的写法，也便于一眼读出属于哪一季哪一集。

        输出规则：

        - 单集：``S02E50``
        - 同季连续：``S02E50-E52``
        - 同季不连续：``S02E50、S02E52``（全部列出，不做折叠）
        - 跨季：``S02E50-S03E02``，首集与末集各带完整季号

        :param pairs: (季, 集) 元组列表
        :return: 格式化后的季集串，无有效输入时返回空串
        """
        if not pairs:
            return ""
        # 去重并排序，季优先
        ordered = sorted({(int(s), int(e)) for s, e in pairs if s is not None and e is not None})
        if not ordered:
            return ""
        if len(ordered) == 1:
            season, episode = ordered[0]
            return f"S{season:02d}E{episode:02d}"

        # 按季分组
        grouped: Dict[int, List[int]] = {}
        for season, episode in ordered:
            grouped.setdefault(season, []).append(episode)

        # 单季：区间或逐个列出
        if len(grouped) == 1:
            season = next(iter(grouped))
            episodes = sorted(grouped[season])
            if episodes[-1] - episodes[0] + 1 == len(episodes):
                return f"S{season:02d}E{episodes[0]:02d}-E{episodes[-1]:02d}"
            return "、".join(f"S{season:02d}E{episode:02d}" for episode in episodes)

        # 跨季：首集与末集各带季号
        first_season, first_episode = ordered[0]
        last_season, last_episode = ordered[-1]
        return (
            f"S{first_season:02d}E{first_episode:02d}"
            f"-S{last_season:02d}E{last_episode:02d}"
        )

    @staticmethod
    def natural_sort_key(text: str) -> List[Union[int, str]]:
        """
        自然排序
        将字符串拆分为数字和非数字部分，数字部分转换为整数，非数字部分转换为小写字母
        :param text: 要处理的字符串
        :return 用于排序的数字和字符串列表
        """
        if text is None:
            return []

        if not isinstance(text, str):
            text = str(text)

        return [int(part) if part.isdigit() else part.lower() for part in re.split(r'(\d+)', text)]

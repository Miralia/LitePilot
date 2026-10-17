"""
封面字体解析。

原插件通过 utils/network_helper.py 维护了多策略下载器（镜像站、重试、wget 兜底）与独立的
性能监控工具；内置化后只需要「本地字体目录 + 可选网络下载」这一条路径，因此这里收敛为：
先命中本地字体搜索目录，再按需从网络下载并校验，下载失败时降级回本地搜索目录，
仍无可用字体时回退到 Pillow 内置字体。任何一步失败都不向上抛异常，避免个别字体缺失
导致整批封面生成中断。
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from PIL import ImageFont

from app.core.config import settings
from app.log import logger
from app.utils.http import RequestUtils

# 可被 Pillow 直接加载的字体扩展名
FONT_EXTENSIONS: Tuple[str, ...] = (".ttf", ".otf", ".ttc", ".woff", ".woff2")

# 内置字体搜索目录中的常见字体别名，用于把预设名匹配到实际字体文件
ZH_FONT_PRESETS: List[Dict[str, str]] = [
    {"title": "潮黑", "value": "chaohei"},
    {"title": "粗雅宋", "value": "yasong"},
    {"title": "真楷", "value": "zhenkai"},
]

EN_FONT_PRESETS: List[Dict[str, str]] = [
    {"title": "EmblemaOne", "value": "EmblemaOne"},
    {"title": "Melete", "value": "Melete"},
    {"title": "Phosphate", "value": "Phosphate"},
    {"title": "JosefinSans", "value": "JosefinSans"},
    {"title": "LilitaOne", "value": "LilitaOne"},
    {"title": "Monoton", "value": "Monoton"},
    {"title": "Plaster", "value": "Plaster"},
]

DEFAULT_ZH_PRESET = "chaohei"
DEFAULT_EN_PRESET = "EmblemaOne"

# 预设名到候选字体文件别名；匹配时忽略大小写、空格、下划线与连字符
FONT_PRESET_ALIASES: Dict[str, List[str]] = {
    "chaohei": ["chaohei", "chao_hei", "wendao", "wen_dao", "潮流黑体", "潮黑"],
    "yasong": ["yasong", "ya_song", "粗雅宋", "NotoSerif", "noto_serif"],
    "zhenkai": ["zhenkai", "zhen_kai", "lxgw", "霞鹜", "真楷"],
    "EmblemaOne": ["emblemaone", "emblema_one", "Emblema"],
    "Melete": ["melete"],
    "Phosphate": ["phosphate", "phosphat"],
    "JosefinSans": ["josefinsans", "josefin_sans", "Josefin"],
    "LilitaOne": ["lilitaone", "lilita_one", "Lilita"],
    "Monoton": ["monoton"],
    "Plaster": ["plaster"],
}

# 预设名到公认的下载地址；没有稳定来源的预设只做本地查找，不做网络下载
FONT_DOWNLOAD_URLS: Dict[str, str] = {
    "zhenkai": (
        "https://github.com/lxgw/LxgwZhenKai/releases/download/v0.827/"
        "LXGWZhenKaiGB-Regular.ttf"
    ),
    "chaohei": (
        "https://github.com/lxgw/LxgwWenKai/releases/download/v1.510/"
        "LXGWWenKai-Regular.ttf"
    ),
    "JosefinSans": (
        "https://github.com/google/fonts/raw/main/ofl/josefinsans/"
        "JosefinSans%5Bwght%5D.ttf"
    ),
}

# 字体文件体积上限，超过该值说明服务器返回了错误页面而非字体
MAX_FONT_SIZE = 32 * 1024 * 1024


def normalize_font_name(value: str) -> str:
    """
    归一化字体名，用于在别名匹配时忽略大小写与分隔符差异。

    :param value: 原始字体名或文件名主干
    :return: 去掉空格、下划线与连字符并转为小写的字符串
    """
    return "".join(str(value or "").split()).replace("_", "").replace("-", "").lower()


def font_search_dirs(font_dir: Optional[Path] = None) -> List[Path]:
    """
    汇总可用的字体搜索目录。

    配置目录优先于内置目录，便于用户放入自己的字体覆盖预设；系统字体目录放在最后，
    只在用户没有提供字体时作为兜底。

    :param font_dir: 额外的首选字体目录
    :return: 已存在且去重后的目录列表
    """
    candidates: List[Path] = []
    if font_dir:
        candidates.append(Path(font_dir))
    candidates.append(settings.CONFIG_PATH / "fonts")
    candidates.append(settings.ROOT_PATH / "fonts")
    candidates.extend(
        [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), Path("/Library/Fonts")]
    )

    unique_dirs: List[Path] = []
    seen = set()
    for directory in candidates:
        try:
            key = str(directory.resolve())
        except OSError:
            continue
        if key in seen or not directory.is_dir():
            continue
        seen.add(key)
        unique_dirs.append(directory)
    return unique_dirs


def find_font_file(preset: str, font_dir: Optional[Path] = None) -> Optional[Path]:
    """
    在本地字体搜索目录中按预设别名查找字体文件。

    :param preset: 字体预设名
    :param font_dir: 额外的首选字体目录
    :return: 匹配到的字体文件路径，未找到时返回 None
    """
    aliases = FONT_PRESET_ALIASES.get(preset) or [preset]
    normalized_aliases = [normalize_font_name(alias) for alias in aliases if alias]
    if not normalized_aliases:
        return None

    for directory in font_search_dirs(font_dir):
        try:
            candidates = sorted(directory.iterdir(), key=lambda item: item.name.lower())
        except OSError as err:
            logger.debug(f"读取字体目录 {directory} 失败：{err}")
            continue
        for candidate in candidates:
            if not candidate.is_file() or candidate.suffix.lower() not in FONT_EXTENSIONS:
                continue
            stem = normalize_font_name(candidate.stem)
            name = normalize_font_name(candidate.name)
            if any(alias in stem or alias in name for alias in normalized_aliases):
                return candidate
    return None


def validate_font_file(font_path: Optional[Path]) -> bool:
    """
    校验字体文件是否可被 Pillow 真正加载。

    只按魔数判断会在字体被截断时误判，因此这里以实际加载一次为准。

    :param font_path: 字体文件路径
    :return: 字体可用时返回 True
    """
    if not font_path:
        return False
    path = Path(font_path)
    try:
        if not path.is_file() or path.stat().st_size == 0:
            return False
        ImageFont.truetype(str(path), 12)
        return True
    except Exception as err:
        logger.warning(f"字体文件校验失败 {path}：{err}")
        return False


def download_font(url: str, target_dir: Path, timeout: int = 60) -> Optional[Path]:
    """
    从网络下载字体到目标目录，下载后立即校验。

    下载失败、响应异常或校验不通过时只记录日志并返回 None，由调用方降级到本地搜索目录。

    :param url: 字体文件地址
    :param target_dir: 字体保存目录
    :param timeout: 下载超时时间（秒）
    :return: 已落盘的字体文件路径，失败时返回 None
    """
    if not url:
        return None
    filename = Path(urlparse(url).path).name or "downloaded-font.ttf"
    if Path(filename).suffix.lower() not in FONT_EXTENSIONS:
        filename = f"{Path(filename).stem or 'downloaded-font'}.ttf"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename

    try:
        logger.info(f"正在下载封面字体：{url}")
        response = RequestUtils(proxies=settings.PROXY, timeout=timeout).get_res(url)
    except Exception as err:
        logger.error(f"下载封面字体失败：{err}")
        return None

    if not response or response.status_code != 200 or not response.content:
        logger.error(f"下载封面字体失败，响应异常：{url}")
        return None
    if len(response.content) > MAX_FONT_SIZE:
        logger.error(f"下载封面字体失败，文件体积异常：{url}")
        return None

    try:
        target_path.write_bytes(response.content)
    except OSError as err:
        logger.error(f"保存封面字体失败：{err}")
        return None

    if not validate_font_file(target_path):
        # 校验不通过的文件必须删除，否则下次会误当成已有字体直接使用
        target_path.unlink(missing_ok=True)
        logger.error(f"下载的封面字体校验失败，已丢弃：{url}")
        return None

    logger.info(f"封面字体已保存：{target_path}")
    return target_path


class FontResolver:
    """
    字体解析器

    按「自定义地址 → 本地搜索目录 → 预设下载地址 → 本地搜索目录」的顺序为一个字体预设
    解析出可用文件，并缓存结果；网络下载失败时静默降级，不阻断封面渲染。
    """

    def __init__(self, font_dir: Optional[Path] = None):
        """
        初始化字体解析器。

        :param font_dir: 优先使用的字体目录，缺省为配置目录下的 fonts
        """
        self.font_dir = Path(font_dir) if font_dir else settings.CONFIG_PATH / "fonts"
        self._cache: Dict[str, Optional[Path]] = {}

    def resolve(self, preset: str, custom: Optional[str] = None) -> Optional[Path]:
        """
        解析预设对应的字体文件。

        :param preset: 字体预设名
        :param custom: 自定义字体文件路径或下载地址
        :return: 可用字体路径，全部策略失败时返回 None
        """
        cache_key = f"{preset}|{custom or ''}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        resolved = self._resolve_custom(custom) or self._resolve_preset(preset)
        self._cache[cache_key] = resolved
        if not resolved:
            logger.warning(f"未找到字体预设 {preset} 对应的字体文件，将使用内置字体")
        return resolved

    def _resolve_custom(self, custom: Optional[str]) -> Optional[Path]:
        """
        解析用户指定的字体文件或下载地址。

        :param custom: 本地路径或 http(s) 地址
        :return: 可用字体路径，未提供或不可用时返回 None
        """
        value = str(custom or "").strip()
        if not value:
            return None
        if value.lower().startswith(("http://", "https://")):
            return download_font(value, self.font_dir)
        path = Path(value).expanduser()
        if validate_font_file(path):
            return path
        logger.warning(f"自定义字体不可用：{value}")
        return None

    def _resolve_preset(self, preset: str) -> Optional[Path]:
        """
        解析内置预设：先找本地，再尝试下载，下载失败后重新扫描本地目录。

        :param preset: 字体预设名
        :return: 可用字体路径，未找到时返回 None
        """
        local_font = find_font_file(preset, self.font_dir)
        if local_font:
            return local_font

        download_url = FONT_DOWNLOAD_URLS.get(preset)
        if not download_url:
            return None
        if download_font(download_url, self.font_dir):
            # 下载成功后仍走一次本地查找，使匹配规则保持单一实现
            return find_font_file(preset, self.font_dir)
        return None


def load_font(font_path: Optional[Path], size: int) -> ImageFont.ImageFont:
    """
    加载字体对象，路径不可用时回退到 Pillow 内置字体。

    :param font_path: 字体文件路径，可为 None
    :param size: 字号
    :return: 可用于绘制的字体对象
    """
    safe_size = max(1, int(size))
    if font_path:
        try:
            return ImageFont.truetype(str(font_path), safe_size)
        except Exception as err:
            logger.warning(f"加载字体 {font_path} 失败，回退到内置字体：{err}")
    try:
        return ImageFont.load_default(size=safe_size)
    except TypeError:
        # 低版本 Pillow 的 load_default 不接受尺寸参数
        return ImageFont.load_default()
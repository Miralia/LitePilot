# -*- coding: utf-8 -*-
"""
分辨率与来源档位分类。

逻辑移植自同一作者的 Vit 项目（`vcore/release.py` 的 `classify_resolution`），
规则保持一致：

- DCI 等特殊分辨率按原始像素判定（2048x1080 → 2K，4096x2160 → 4K）；
- 其余按「最小够用档位」判定：存储宽度与显示高度都不超过该档位名义尺寸时才落到该档，
  因此 2538x1080 这类宽画幅会从 1080p 抬到 1440p，而不是被误判成 1080p；
- 宽度用存储宽度而非 SAR 拉伸后的显示宽度，避免变形宽银幕被虚抬档位；
- 竖屏（h > w）按长边当宽度、短边当高度判定，720x1280 归为 720p。
"""
from typing import Optional

# 分辨率档位：名称与名义尺寸，按从高到低排列，便于顺序匹配
RES_TIERS = [
    ("4320p", 7680, 4320),
    ("2160p", 3840, 2160),
    ("1440p", 2560, 1440),
    ("1080p", 1920, 1080),
    ("900p", 1600, 900),
    ("720p", 1280, 720),
    ("480p", 854, 480),
    ("360p", 640, 360),
    ("240p", 426, 240),
]

# DCI 数字电影分辨率：按存储像素直接判定
DCI_2K = ((2048, 1080), (2048, 858))
DCI_4K = ((4096, 2160), (4096, 1714), (4096, 1716), (3996, 2160))

# 最低档位兜底
_LOWEST_TIER = "240p"


def classify_resolution(
    width: Optional[int],
    height: Optional[int],
    display_width: Optional[int] = None,
    display_height: Optional[int] = None,
) -> str:
    """
    把像素尺寸归类为发布档位标签。

    :param width: 存储宽度
    :param height: 存储高度
    :param display_width: SAR 拉伸后的显示宽度，缺省时用存储宽度
    :param display_height: SAR 拉伸后的显示高度，缺省时用存储高度
    :return: 档位标签，如 2160p、1080p、2K、4K；无法判定时返回 240p
    """
    w, h = int(width or 0), int(height or 0)
    dw = int(display_width or w)
    dh = int(display_height or h)

    # 1. DCI 特殊分辨率按存储像素判定，避免被通用规则归到相邻档
    if (w, h) in DCI_2K:
        return "2K"
    if (w, h) in DCI_4K:
        return "4K"
    if w == 2048 and h >= 1080:
        return "2K"

    if dw <= 0 or dh <= 0:
        return _LOWEST_TIER

    # 2. 覆盖规则：取「名义尺寸能覆盖住存储宽度与显示高度」的最小档位。
    #    从低到高找第一个覆盖得住的档，因此 1920x1080 落在 1080p；
    #    而 2538x1080 的宽画幅超出 1080p 的 1920 宽度，抬到 1440p。
    #    宽度用存储宽度，避免 SAR 拉伸把变形宽银幕虚抬一档；
    #    长边当宽度、短边当高度，兼容竖屏（720x1280 → 720p）。
    long_edge, short_edge = (h, w) if h > w else (w, h)
    for label, tier_width, tier_height in reversed(RES_TIERS):
        if long_edge <= tier_width and short_edge <= tier_height:
            return label
    return _LOWEST_TIER


def resolution_from_height(height: Optional[int]) -> str:
    """
    仅按高度推断档位。

    用于只知道高度、拿不到宽度的场景（例如从标题里只解析到 1080 这种数字）。
    与 `classify_resolution` 的分档保持一致。

    :param height: 画面高度
    :return: 档位标签
    """
    value = int(height or 0)
    if value <= 0:
        return ""
    if value >= 4320:
        return "4320p"
    if value >= 2160:
        return "2160p"
    if value >= 1440:
        return "1440p"
    if value >= 1080:
        return "1080p"
    if value >= 900:
        return "900p"
    if value >= 720:
        return "720p"
    if value >= 480:
        return "480p"
    if value >= 360:
        return "360p"
    return "240p"
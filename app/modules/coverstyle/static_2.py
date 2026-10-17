# -*- coding: utf-8 -*-
"""
静态风格 2 的媒体库封面渲染。

从社区插件 mediacovergenerator 的 style_static_2 移植而来，按本分支需要做了裁剪：
只保留这一种静态样式、去掉风格切换与缓存/历史等附属能力，字体与排版参数固定内置。
"""

import colorsys
import re
import random
from collections import Counter
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from app.log import logger

# 取色失败时的柔和备选色，避免封面出现突兀的默认色
SOFT_FALLBACK_COLORS = [
    (237, 159, 77),
    (255, 183, 197),
    (186, 225, 255),
    (255, 223, 186),
    (202, 231, 200),
    (245, 203, 255),
]

# 固定使用霞鹜真楷作为中文字体，英文标题复用同一字体
FIXED_ZH_FONT_SIZE = 150
FIXED_EN_FONT_SIZE = 62
FIXED_TITLE_SPACING = 34
FIXED_EN_LINE_SPACING = 20
FIXED_FONT_OFFSET = 0
FIXED_BLUR_SIZE = 50
FIXED_COLOR_RATIO = 0.8

# ========== 配置 ==========
canvas_size = (1920, 1080)

def parse_color_string(color_str: Optional[str]) -> Optional[Tuple[int, int, int]]:
    """
    解析颜色字符串，支持十六进制、rgb()/rgba() 与常见英文颜色名。

    :param color_str: 颜色字符串
    :return: RGB 元组，无法解析时返回 None
    """
    if not color_str:
        return None
    value = color_str.strip().lower()
    if value.startswith("#"):
        hex_color = value[1:]
        if len(hex_color) in (3, 4):
            hex_color = "".join(char * 2 for char in hex_color)
        if len(hex_color) in (6, 8):
            try:
                return (
                    int(hex_color[0:2], 16),
                    int(hex_color[2:4], 16),
                    int(hex_color[4:6], 16),
                )
            except ValueError:
                logger.warning(f"无效的十六进制颜色：{color_str}")
                return None
        return None
    rgb_match = re.match(
        r"rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,[^)]*)?\)", value
    )
    if rgb_match:
        channels = tuple(int(item) for item in rgb_match.groups())
        if all(0 <= item <= 255 for item in channels):
            return channels
        return None
    named = {
        "black": (0, 0, 0),
        "white": (255, 255, 255),
        "red": (255, 0, 0),
        "green": (0, 128, 0),
        "blue": (0, 0, 255),
        "orange": (255, 165, 0),
        "purple": (128, 0, 128),
        "pink": (255, 192, 203),
        "gray": (128, 128, 128),
        "grey": (128, 128, 128),
        "lightblue": (173, 216, 230),
        "darkblue": (0, 0, 139),
    }
    if value in named:
        return named[value]
    logger.warning(f"无法解析的颜色：{color_str}")
    return None


def get_background_color(image: Image.Image, custom_color: Optional[str] = None) -> Tuple[int, int, int]:
    """
    获取背景颜色：优先使用自定义色，否则从图像中提取主色调。

    :param image: 来源图像
    :param custom_color: 自定义背景色字符串
    :return: RGB 颜色
    """
    parsed = parse_color_string(custom_color)
    if parsed:
        return parsed
    colors = find_dominant_vibrant_colors(image, num_colors=1)
    if colors:
        return colors[0]
    return random.choice(SOFT_FALLBACK_COLORS)


def is_not_black_white_gray_near(color, threshold=20):
    """判断颜色是否远离黑白灰（用于过滤背景噪声色）。"""
    r, g, b = color
    if (r < threshold and g < threshold and b < threshold) or \
       (r > 255 - threshold and g > 255 - threshold and b > 255 - threshold):
        return False
    gray_diff_threshold = 10
    if abs(r - g) < gray_diff_threshold and abs(g - b) < gray_diff_threshold and abs(r - b) < gray_diff_threshold:
        return False
    return True

def rgb_to_hsv(color):
    """RGB 转 HSV。"""
    r, g, b = [x / 255.0 for x in color]
    return colorsys.rgb_to_hsv(r, g, b)

def hsv_to_rgb(h, s, v):
    """HSV 转 RGB。"""
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))

def adjust_to_macaron(h, s, v, target_saturation_range=(0.2, 0.7), target_value_range=(0.55, 0.85)):
    """把颜色调整到马卡龙风格的饱和度和明度区间。"""
    adjusted_s = min(max(s, target_saturation_range[0]), target_saturation_range[1])
    adjusted_v = min(max(v, target_value_range[0]), target_value_range[1])
    return adjusted_s, adjusted_v

def find_dominant_vibrant_colors(image, num_colors=5):
    """
    从图像中提取出现次数较多的前 N 种非黑非白非灰的颜色，
    并将其调整到接近马卡龙色系。
    """
    img = image.copy()  
    img.thumbnail((100, 100))
    img = img.convert('RGB')
    pixels = list(img.getdata())
    filtered_pixels = [p for p in pixels if is_not_black_white_gray_near(p)]
    if not filtered_pixels:
        return []
    color_counter = Counter(filtered_pixels)
    dominant_colors = color_counter.most_common(num_colors * 3) # 提取更多候选

    macaron_colors = []
    seen_hues = set() # 避免提取过于相似的颜色

    for color, count in dominant_colors:
        h, s, v = rgb_to_hsv(color)
        adjusted_s, adjusted_v = adjust_to_macaron(h, s, v)
        adjusted_rgb = hsv_to_rgb(h, adjusted_s, adjusted_v)

        # 可以加入一些色调的判断，例如避免过于接近的色调
        hue_degree = int(h * 360)
        is_similar_hue = any(abs(hue_degree - seen) < 15 for seen in seen_hues) # 15度范围内的色调认为是相似的

        if not is_similar_hue and adjusted_rgb not in macaron_colors:
            macaron_colors.append(adjusted_rgb)
            seen_hues.add(hue_degree)
            if len(macaron_colors) >= num_colors:
                break

    return macaron_colors

def darken_color(color, factor=0.7):
    """
    将颜色加深。
    """
    r, g, b = color
    return (int(r * factor), int(g * factor), int(b * factor))


def add_film_grain(image, intensity=0.05):
    """叠加轻微胶片颗粒，避免大面积纯色显得扁平。"""
    img_array = np.array(image)
    
    # 创建随机噪点
    noise = np.random.normal(0, intensity * 255, img_array.shape)
    
    # 应用噪点
    img_array = img_array + noise
    img_array = np.clip(img_array, 0, 255).astype(np.uint8)
    
    return Image.fromarray(img_array)

def _premium_finish(image, accent_color=None, vignette_strength=0.30, glow_strength=0.22):
    """叠加光晕与暗角，提升背景的高级感。"""
    base = image.convert("RGBA")
    width, height = base.size
    if accent_color is None:
        accent_color = (220, 170, 112)
    accent = tuple(int(max(0, min(255, c))) for c in accent_color[:3])

    x = np.linspace(-1, 1, width)
    y = np.linspace(-1, 1, height)
    X, Y = np.meshgrid(x, y)
    glow_left = np.exp(-(((X + 0.68) ** 2) / 0.35 + ((Y + 0.25) ** 2) / 0.62))
    glow_right = np.exp(-(((X - 0.35) ** 2) / 0.48 + ((Y - 0.50) ** 2) / 0.30))
    vignette = np.clip((np.sqrt((X * 0.9) ** 2 + (Y * 1.05) ** 2) - 0.15) / 0.95, 0, 1)

    overlay = np.zeros((height, width, 4), dtype=np.uint8)
    overlay[..., 0] = np.clip(255 * glow_left + accent[0] * glow_right, 0, 255)
    overlay[..., 1] = np.clip(240 * glow_left + accent[1] * glow_right, 0, 255)
    overlay[..., 2] = np.clip(210 * glow_left + accent[2] * glow_right, 0, 255)
    overlay[..., 3] = np.clip((glow_left * 48 + glow_right * 36) * glow_strength, 0, 54).astype(np.uint8)
    base = Image.alpha_composite(base, Image.fromarray(overlay, "RGBA"))

    shade = np.zeros((height, width, 4), dtype=np.uint8)
    shade[..., 3] = np.clip(vignette * 255 * vignette_strength, 0, 128).astype(np.uint8)
    return Image.alpha_composite(base, Image.fromarray(shade, "RGBA")).convert("RGB")


def _polish_foreground(image):
    """对前景图做轻微色彩润饰。"""
    polished = ImageEnhance.Color(image.convert("RGB")).enhance(1.04)
    polished = ImageEnhance.Contrast(polished).enhance(1.05)
    return ImageEnhance.Sharpness(polished).enhance(1.06)


def _adaptive_background_tone(image, bg_color, color_ratio):
    """根据前景图明度自适应调整背景色与混合比例。"""
    try:
        lum = float(np.array(image.convert("L").resize((64, 64), Image.LANCZOS)).mean())
    except Exception:
        lum = 128.0
    ratio = float(color_ratio)
    r, g, b = bg_color[:3]
    if lum > 180:
        ratio = min(0.95, ratio + 0.10)
        bg_color = darken_color((r, g, b), 0.68)
    elif lum < 55:
        ratio = max(0.56, ratio - 0.14)
        bg_color = tuple(min(255, int(c * 1.16 + 12)) for c in (r, g, b))
    return bg_color, ratio



def align_image_right(img, canvas_size):
    """
    将图片调整为与画布相同高度，裁剪出画布60%宽度的部分，
    然后将裁剪后的图片靠右放置（因为左侧40%会被其他内容遮盖）。
    """
    canvas_width, canvas_height = canvas_size
    target_width = int(canvas_width * 0.675)  # 只需要画布60%的宽度
    img_width, img_height = img.size

    # 计算缩放比例以匹配画布高度
    scale_factor = canvas_height / img_height
    new_img_width = int(img_width * scale_factor)
    resized_img = img.resize((new_img_width, canvas_height), Image.LANCZOS)
    
    # 检查缩放后的图片是否足够宽以覆盖目标宽度
    if new_img_width < target_width:
        # 如果图片不够宽，基于宽度而非高度进行缩放
        scale_factor = target_width / img_width
        new_img_height = int(img_height * scale_factor)
        resized_img = img.resize((target_width, new_img_height), Image.LANCZOS)
        
        # 将图片垂直居中裁剪
        if new_img_height > canvas_height:
            crop_top = (new_img_height - canvas_height) // 2
            resized_img = resized_img.crop((0, crop_top, target_width, crop_top + canvas_height))
        
        # 创建画布并将图片靠右放置
        final_img = Image.new("RGB", canvas_size)
        final_img.paste(resized_img, (canvas_width - target_width, 0))
        return final_img
    
    # 以下是原始图片足够宽的情况处理
    
    # 计算图片中心，确保主体在截取的部分中居中
    resized_img_center_x = new_img_width / 2
    
    # 计算裁剪的左右边界，使目标部分居中
    crop_left = max(0, resized_img_center_x - target_width / 2)
    # 确保右边界不超过图片宽度
    if crop_left + target_width > new_img_width:
        crop_left = new_img_width - target_width
    crop_right = crop_left + target_width
    
    # 确保裁剪边界不为负
    crop_left = max(0, crop_left)
    crop_right = min(new_img_width, crop_right)
    
    # 进行裁剪
    cropped_img = resized_img.crop((int(crop_left), 0, int(crop_right), canvas_height))
    
    # 创建画布并将裁剪后的图片靠右放置
    final_img = Image.new("RGB", canvas_size)
    paste_x = canvas_width - cropped_img.width + int(canvas_width * 0.075)
    final_img.paste(cropped_img, (paste_x, 0))
    
    return final_img

def create_diagonal_mask(size, split_top=0.5, split_bottom=0.33):
    """
    创建斜线分割的蒙版。左侧为背景 (255)，右侧为前景 (0)。
    """
    mask = Image.new('L', size, 255)
    draw = ImageDraw.Draw(mask)
    width, height = size
    top_x = int(width * split_top)
    bottom_x = int(width * split_bottom)

    # 绘制前景区域 (右侧) - 填充为黑色
    draw.polygon(
        [
            (top_x, 0),
            (width, 0),
            (width, height),
            (bottom_x, height)
        ],
        fill=0
    )

    # 绘制背景区域 (左侧) - 填充为白色
    draw.polygon(
        [
            (0, 0),
            (top_x, 0),
            (bottom_x, height),
            (0, height)
        ],
        fill=255
    )
    return mask

def create_shadow_mask(size, split_top=0.5, split_bottom=0.33, feather_size=40):
    """
    创建一个阴影蒙版，用于左侧图片向右侧图片投射阴影
    """
    width, height = size
    top_x = int(width * split_top)
    bottom_x = int(width * split_bottom)
    
    # 创建基础蒙版 - 左侧完全透明，右侧完全不透明
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    
    # 阴影宽度再缩小一半 (原来的六分之一)
    shadow_width = feather_size // 3
    
    # 绘制阴影区域的多边形 - 向左靠拢
    draw.polygon(
        [
            (top_x - 5, 0),  # 向左偏移5像素，确保没有空隙
            (top_x - 5 + shadow_width, 0),
            (bottom_x - 5 + shadow_width, height),
            (bottom_x - 5, height)
        ],
        fill=255
    )
    
    # 模糊阴影边缘，创造渐变效果，但保持较小的模糊半径
    mask = mask.filter(ImageFilter.GaussianBlur(radius=feather_size//3))
    
    return mask


def create_style_static_2(
    image_path,
    title,
    font_path,
    font_size=None,
    font_offset=None,
    blur_size=None,
    color_ratio=None,
    resolution_config=None,
    bg_color_config=None,
):
    """
    生成静态风格 2 的媒体库封面。

    前景图按画面右侧对齐，左侧为斜线分割的模糊背景与中英标题；参数全部内置固定，
    调用方只需给出图片路径、标题与字体路径。

    :param image_path: 前景图路径
    :param title: (中文标题, 英文标题) 元组
    :param font_path: (中文字体路径, 英文字体路径) 元组
    :param resolution_config: 输出画布尺寸配置
    :param bg_color_config: 背景颜色配置，支持 custom_color
    :return: PIL 图像对象，失败时返回 None
    """
    try:
        zh_font_path, en_font_path = font_path
        font_size = font_size or (FIXED_ZH_FONT_SIZE, FIXED_EN_FONT_SIZE)
        font_offset = font_offset or (FIXED_FONT_OFFSET, FIXED_TITLE_SPACING, FIXED_EN_LINE_SPACING)
        blur_size = FIXED_BLUR_SIZE if blur_size is None else blur_size
        color_ratio = FIXED_COLOR_RATIO if color_ratio is None else color_ratio
        title_zh, title_en = title
        zh_font_size, en_font_size = font_size
        zh_font_offset, title_spacing, en_line_spacing = font_offset

        if int(blur_size) < 0:
            blur_size = 50

        if float(color_ratio) < 0 or float(color_ratio) > 1:
            color_ratio = 0.8

        if not float(zh_font_size) > 0:
            zh_font_size = 170
        if not float(en_font_size) > 0:
            en_font_size = 75
        style_font_scale = 1.1
        zh_font_size = float(zh_font_size) * style_font_scale
        en_font_size = float(en_font_size) * style_font_scale

        if resolution_config:
            canvas_size = resolution_config.size
        else:
            canvas_size = (1920, 1080)

        # 定义斜线分割位置
        split_top = 0.55    # 顶部分割点在画面五分之三的位置
        split_bottom = 0.4  # 底部分割点在画面二分之一的位置
        
        # 加载前景图片并处理
        fg_img_original = Image.open(image_path).convert("RGB")
        # 以画面四分之三处为中心处理前景图
        fg_img = align_image_right(_polish_foreground(fg_img_original), canvas_size)
        
        # 获取前景图中最鲜明的颜色
        vibrant_colors = find_dominant_vibrant_colors(fg_img)
        
        # 柔和的颜色备选（马卡龙风格）
        soft_colors = [
            (237, 159, 77),    # 原默认色
            (255, 183, 197),   # 淡粉色
            (186, 225, 255),   # 淡蓝色
            (255, 223, 186),   # 浅橘色
            (202, 231, 200),   # 淡绿色
            (245, 203, 255),   # 淡紫色
        ]
        # 背景色模式：auto/custom/config
        if bg_color_config:
            bg_color = get_background_color(
                fg_img,
                custom_color=bg_color_config.get('custom_color'),
            )
        elif vibrant_colors:
            bg_color = vibrant_colors[0]
        else:
            bg_color = random.choice(soft_colors) # 默认橙色
        bg_color, color_ratio = _adaptive_background_tone(fg_img_original, bg_color, color_ratio)
        shadow_color = darken_color(bg_color, 0.46)
        
        # 加载背景图片
        bg_img_original = Image.open(image_path).convert("RGB")
        bg_img = ImageOps.fit(bg_img_original, canvas_size, method=Image.LANCZOS)

        # 强烈模糊化背景图
        bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=int(blur_size)))

        # 将背景图片与背景色混合
        bg_color = darken_color(bg_color, 0.85)
        bg_img_array = np.array(bg_img, dtype=float)
        bg_color_array = np.array([[bg_color]], dtype=float)
        
        # 混合背景图和颜色 (10% 背景图 + 90% 颜色) - 使原图几乎不可见，只保留极少纹理
        blended_bg = bg_img_array * (1 - float(color_ratio)) + bg_color_array * float(color_ratio)
        blended_bg = np.clip(blended_bg, 0, 255).astype(np.uint8)
        blended_bg_img = Image.fromarray(blended_bg)
        
        # 添加高级感光晕、暗角与更克制的颗粒
        blended_bg_img = _premium_finish(blended_bg_img, bg_color, vignette_strength=0.28, glow_strength=0.90)
        blended_bg_img = add_film_grain(blended_bg_img, intensity=0.018)
        
        # 创建斜线分割的蒙版
        diagonal_mask = create_diagonal_mask(canvas_size, split_top, split_bottom)
        
        # 创建基础画布 - 前景图
        canvas = fg_img.copy()
        
        # 创建阴影蒙版 - 使用加深的背景色作为阴影颜色，减小阴影距离
        shadow_mask = create_shadow_mask(canvas_size, split_top, split_bottom, feather_size=46)
        
        # 创建阴影层 - 使用更加深的背景色
        shadow_layer = Image.new('RGB', canvas_size, shadow_color)
        
        # 创建临时画布用于组合
        temp_canvas = Image.new('RGB', canvas_size)
        
        # 应用阴影到前景图（先将阴影应用到前景图上）
        temp_canvas.paste(canvas)
        temp_canvas.paste(shadow_layer, mask=shadow_mask)
        
        # 使用蒙版将背景图应用到画布上（背景图会覆盖前景图的左侧部分）
        canvas = Image.composite(blended_bg_img, temp_canvas, diagonal_mask)
        
        # ===== 标题绘制 =====
        # 使用RGBA模式进行绘制，以便设置文字透明度

        canvas = canvas.convert('RGBA')
        # 5. 文字处理
        text_layer = Image.new('RGBA', canvas_size, (255, 255, 255, 0))
        shadow_layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))

        shadow_draw = ImageDraw.Draw(shadow_layer)
        draw = ImageDraw.Draw(text_layer)
        
        # 计算左侧区域的中心 X 位置 (画布宽度的四分之一处)
        left_area_center_x = int(canvas_size[0] * 0.25)
        left_area_center_y = canvas_size[1] // 2
        
        # zh_font_size = int(canvas_size[1] * 0.17 * float(zh_font_size_ratio))
        # en_font_size = int(canvas_size[1] * 0.07 * float(en_font_size_ratio))
        
        zh_font = ImageFont.truetype(zh_font_path, zh_font_size)
        en_font = ImageFont.truetype(en_font_path, en_font_size)
            
        # 文字颜色和阴影颜色
        text_color = (255, 255, 255, 229)  # 85% 不透明度
        shadow_color = darken_color(bg_color, 0.58) + (96,)
        shadow_offset = 14
        shadow_alpha = 72
        
        # 计算中文标题的位置
        zh_bbox = draw.textbbox((0, 0), title_zh, font=zh_font)
        zh_text_w = zh_bbox[2] - zh_bbox[0]
        zh_text_h = zh_bbox[3] - zh_bbox[1]
        
        # 定义英文行间距
        en_line_spacing = int(en_font_size * 0.3)  # 英文行间距为字体大小的30%
        
        # 处理英文标题（如果有）
        en_lines = []
        en_text_w = 0
        en_text_h = 0
        total_en_height = 0
        
        if title_en:
            # 检查英文标题是否需要分行
            en_bbox = draw.textbbox((0, 0), title_en, font=en_font)
            en_full_width = en_bbox[2] - en_bbox[0]
            
            # 如果英文标题比中文标题宽，且包含多个单词，则分行处理
            if en_full_width > zh_text_w and " " in title_en:
                words = title_en.split(" ")
                current_line = words[0]
                
                for word in words[1:]:
                    test_line = current_line + " " + word
                    test_bbox = draw.textbbox((0, 0), test_line, font=en_font)
                    test_width = test_bbox[2] - test_bbox[0]
                    
                    # 如果添加新单词后超过中文宽度，则换行
                    if test_width > zh_text_w:
                        en_lines.append(current_line)
                        current_line = word
                    else:
                        current_line = test_line
                
                # 添加最后一行
                if current_line:
                    en_lines.append(current_line)
                
                # 计算所有英文行的最大宽度和总高度
                for line in en_lines:
                    line_bbox = draw.textbbox((0, 0), line, font=en_font)
                    line_width = line_bbox[2] - line_bbox[0]
                    line_height = line_bbox[3] - line_bbox[1]
                    en_text_w = max(en_text_w, line_width)
                    total_en_height += line_height + en_line_spacing
                
                # 减去最后一个多余的行间距
                if en_lines:
                    total_en_height -= en_line_spacing
                    
                en_text_h = total_en_height
            else:
                # 英文标题不需要分行
                en_lines = [title_en]
                en_text_w = en_full_width
                en_text_h = en_bbox[3] - en_bbox[1]
                total_en_height = en_text_h
        
        # 定义中英文标题间距
        title_spacing = float(title_spacing) if title_en else 0

        # 计算整体文本高度：中文标题高度 + 英文标题高度（如果有）+ 间距（如果有英文标题）
        total_text_height = zh_text_h + total_en_height + title_spacing

        # 计算整体的垂直居中起始位置
        total_text_y = left_area_center_y - total_text_height // 2

        # 中文标题位置
        zh_x = left_area_center_x - zh_text_w // 2
        zh_y = total_text_y + float(zh_font_offset)

        # 中文标题阴影效果
        for offset in range(3, shadow_offset + 1, 2):
            current_shadow_color = shadow_color[:3] + (shadow_alpha,)
            shadow_draw.text((zh_x + offset, zh_y + offset), title_zh, font=zh_font, fill=current_shadow_color)
        
        # 中文标题
        draw.text((zh_x, zh_y), title_zh, font=zh_font, fill=text_color)

        if en_lines:
            # 英文标题起始位置
            en_y = zh_y + zh_text_h + title_spacing
            
            # 处理多行英文
            for i, line in enumerate(en_lines):
                # 计算每行的水平居中位置
                line_bbox = draw.textbbox((0, 0), line, font=en_font)
                line_width = line_bbox[2] - line_bbox[0]
                line_height = line_bbox[3] - line_bbox[1]
                
                en_x = left_area_center_x - line_width // 2
                current_y = en_y + i * (line_height + en_line_spacing)
                
                # 英文标题阴影效果
                for offset in range(2, shadow_offset // 2 + 1):
                    current_shadow_color = shadow_color[:3] + (shadow_alpha,)
                    shadow_draw.text((en_x + offset, current_y + offset), line, font=en_font, fill=current_shadow_color)
                
                # 英文标题
                draw.text((en_x, current_y), line, font=en_font, fill=text_color)
        
        blurred_shadow = shadow_layer.filter(ImageFilter.GaussianBlur(radius=shadow_offset))
        combined = Image.alpha_composite(canvas, blurred_shadow)
        # 合并所有图层
        combined = Image.alpha_composite(combined, text_layer)

        return combined
    except Exception as err:
        logger.error(f"生成静态风格 2 封面失败：{err}")
        return None

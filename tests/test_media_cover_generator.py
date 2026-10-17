# -*- coding: utf-8 -*-
"""媒体库封面生成的内置能力用例。

覆盖纯逻辑：颜色解析、背景色回退、素材标题拆分、目标尺寸与斜线蒙版的几何约定，
以及渲染入口在缺参时的降级行为。渲染用例使用极小的假图，不访问网络。
"""
from pathlib import Path

import pytest
from PIL import Image

from app.chain.mediacover import MediaCoverChain
from app.modules.coverstyle.static_2 import (
    align_image_right,
    create_diagonal_mask,
    create_style_static_2,
    darken_color,
    get_background_color,
    parse_color_string,
)
from app.schemas.mediaserver import MediaServerLibrary


class _Resolution:
    """渲染入口接受的分辨率配置替身。"""

    size = (640, 360)


def _poster(path: Path, size=(240, 360), color=(40, 90, 160)) -> Path:
    """生成一张纯色假海报，并叠加少量色块避免主色提取退化。"""
    image = Image.new("RGB", size, color)
    for x in range(0, size[0], 20):
        for y in range(0, size[1], 20):
            image.putpixel((x, y), (210, 130, 70))
    image.save(path, "JPEG")
    return path


def _first_available_font() -> str | None:
    """在本机查找一个可用于渲染的中文字体，找不到则跳过渲染用例。"""
    for candidate in (
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(candidate).exists():
            return candidate
    return None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("#f00", (255, 0, 0)),
        ("#FF8800", (255, 136, 0)),
        ("#11223344", (17, 34, 51)),
        ("rgb(12, 34, 56)", (12, 34, 56)),
        ("rgba(12, 34, 56, 0.5)", (12, 34, 56)),
        ("LightBlue", (173, 216, 230)),
    ],
)
def test_parse_color_string_supported_formats(value, expected):
    """常见颜色写法应被正确解析为 RGB。"""
    assert parse_color_string(value) == expected


@pytest.mark.parametrize("value", [None, "", "not-a-color", "#12345", "rgb(999, 0, 0)"])
def test_parse_color_string_rejects_invalid(value):
    """非法颜色应返回 None，由调用方回退到自动取色。"""
    assert parse_color_string(value) is None


def test_get_background_color_prefers_custom(tmp_path):
    """给出自定义颜色时应直接采用，不再从图像取色。"""
    poster = _poster(tmp_path / "poster.jpg")

    with Image.open(poster) as image:
        assert get_background_color(image, custom_color="#123456") == (18, 52, 86)


def test_get_background_color_falls_back_to_image(tmp_path):
    """未给出自定义颜色时应从图像中提取主色。"""
    poster = _poster(tmp_path / "poster.jpg")

    with Image.open(poster) as image:
        color = get_background_color(image)

    assert len(color) == 3
    assert all(0 <= channel <= 255 for channel in color)


def test_darken_color_scales_channels():
    """加深颜色按比例缩放各通道。"""
    assert darken_color((200, 100, 50), 0.5) == (100, 50, 25)


def test_align_image_right_fills_canvas_height_and_right_side():
    """前景图应缩放至画布高度并靠右放置。"""
    source = Image.new("RGB", (300, 600), (10, 20, 30))

    aligned = align_image_right(source, (1920, 1080))

    assert aligned.height == 1080
    assert aligned.width >= int(1920 * 0.675)


def test_diagonal_mask_is_single_channel_and_splits_left_right():
    """斜线蒙版应为单通道，左侧背景、右侧前景。"""
    mask = create_diagonal_mask((640, 360), split_top=0.55, split_bottom=0.4)

    assert mask.size == (640, 360)
    assert mask.mode == "L"
    assert mask.getpixel((5, 180)) == 255
    assert mask.getpixel((634, 180)) == 0


@pytest.mark.parametrize(
    ("library_name", "expected"),
    [
        ("电影 - Movies", ("电影", "Movies")),
        ("剧集-Movies", ("剧集", "Movies")),
        ("动漫/Anime", ("动漫", "Anime")),
        ("Movies", ("Movies", "")),
        ("", ("", "")),
    ],
)
def test_library_title_splits_zh_and_en(library_name, expected):
    """媒体库名带分隔符时拆成中英双行，否则只渲染单行。"""
    assert MediaCoverChain._library_title(MediaServerLibrary(name=library_name)) == expected


def test_render_cover_requires_source_image():
    """缺少素材时渲染入口应直接返回 None，不抛异常。"""
    chain = object.__new__(MediaCoverChain)
    assert chain._render_cover(MediaServerLibrary(name="电影 - Movies")) is None


def test_create_style_static_2_returns_canvas_sized_image(tmp_path):
    """静态风格 2 应输出与配置分辨率一致的图像。"""
    font = _first_available_font()
    if not font:
        pytest.skip("本机没有可用于渲染的字体")

    poster = _poster(tmp_path / "poster.jpg")
    image = create_style_static_2(
        image_path=str(poster),
        title=("测试媒体库", "Test Library"),
        font_path=(font, font),
        resolution_config=_Resolution(),
    )

    assert image is not None
    assert image.size == _Resolution.size


def test_create_style_static_2_returns_none_on_bad_input(tmp_path):
    """素材不可读时渲染入口应记录错误并返回 None，而不是抛出异常。"""
    missing = tmp_path / "missing.jpg"
    font = _first_available_font()
    if not font:
        pytest.skip("本机没有可用于渲染的字体")

    assert (
        create_style_static_2(
            image_path=str(missing),
            title=("测试", "Test"),
            font_path=(font, font),
            resolution_config=_Resolution(),
        )
        is None
    )
"""手动整理集数偏移表达式的安全边界测试。"""
from types import SimpleNamespace

import pytest

from app.helper.format import FormatParser


def test_episode_offset_rejects_non_arithmetic_payload(capsys):
    """集数偏移不得通过 eval 执行任意 Python 表达式。"""
    parser = FormatParser(
        eformat="",
        offset="(EP,print('offset-payload-executed'))[0]",
    )
    meta = SimpleNamespace(begin_episode=10, end_episode=None)

    with pytest.raises(ValueError, match="集数偏移"):
        parser.split_episode("Show.mkv", meta)

    assert "offset-payload-executed" not in capsys.readouterr().out


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        ("EP+1", 11),
        ("2*EP-1", 19),
        ("EP+EP-1", 19),
        ("(EP+1)*2", 22),
        ("-1", 9),
    ],
)
def test_episode_offset_keeps_supported_arithmetic(offset, expected):
    """白名单算术表达式仍应保持原有计算结果。"""
    parser = FormatParser(eformat="", offset=offset)
    meta = SimpleNamespace(begin_episode=10, end_episode=None)

    start_ep, end_ep, _ = parser.split_episode("Show.mkv", meta)

    assert start_ep == expected
    assert end_ep is None


def test_episode_format_matches_episode_zero():
    """集数定位模板应把 E00 视为有效集号。"""
    parser = FormatParser(eformat="Show.E{ep}.mkv")

    assert parser.match("Show.E00.mkv") is True


def test_episode_offset_applies_to_episode_zero_without_format():
    """无定位模板时，显式集数偏移仍应作用于第 0 集。"""
    parser = FormatParser(eformat="", offset="EP+1")
    meta = SimpleNamespace(begin_episode=0, end_episode=None)

    start_ep, end_ep, _ = parser.split_episode("Show.E00.mkv", meta)

    assert start_ep == 1
    assert end_ep is None


def test_episode_offset_applies_to_episode_zero_with_format():
    """定位模板解析出 E00 时，显式集数偏移不应被丢弃。"""
    parser = FormatParser(eformat="Show.E{ep}.mkv", offset="EP+1")
    meta = SimpleNamespace(begin_episode=None, end_episode=None)

    start_ep, end_ep, _ = parser.split_episode("Show.E00.mkv", meta)

    assert start_ep == 1
    assert end_ep is None


def test_episode_range_detail_matches_numeric_bounds():
    """范围型指定集数应按数值边界过滤模板命中的文件。"""
    parser = FormatParser(eformat="Show - {ep}.mkv", details="1-2")

    assert parser.match("Show - 01.mkv") is True
    assert parser.match("Show - 02.mkv") is True
    assert parser.match("Show - 03.mkv") is False

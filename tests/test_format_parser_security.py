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

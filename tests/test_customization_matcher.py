from unittest.mock import patch

from app.core.meta.customization import CustomizationMatcher


def test_match_uses_latest_customization_setting():
    """自定义占位符修改后，下一次识别应直接使用新配置。"""
    matcher = CustomizationMatcher()
    values = [["GROUP"], ["TEAM"]]

    with patch.object(
        matcher.systemconfig,
        "get",
        side_effect=lambda _: values[0],
    ):
        assert matcher.match("[GROUP][TEAM] Movie") == "GROUP"
        values[0] = ["TEAM"]
        assert matcher.match("[GROUP][TEAM] Movie") == "TEAM"


def test_invalid_customization_regex_does_not_break_recognition():
    """用户写入未闭合等无效占位符时应跳过匹配，不能中断标题识别。"""
    matcher = CustomizationMatcher()

    with patch.object(matcher.systemconfig, "get", return_value=["[broken"]):
        assert matcher.match("test [broken") == ""


def test_invalid_customization_regex_is_cached_per_rule():
    """同一无效规则反复识别时只编译一次，避免高频识别路径重复告警和重复编译。"""
    matcher = CustomizationMatcher()
    compile_calls = []
    real_compile = __import__("regex").compile

    def counting_compile(*args, **kwargs):
        compile_calls.append(args[0])
        return real_compile(*args, **kwargs)

    with patch.object(matcher.systemconfig, "get", return_value=["[broken-cache"]), \
            patch("app.core.meta.customization.re.compile", side_effect=counting_compile):
        assert matcher.match("first [broken-cache") == ""
        assert matcher.match("second [broken-cache") == ""

    assert compile_calls == ["([broken-cache)"]

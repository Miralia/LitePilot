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

from unittest.mock import patch

from tests.cases.groups import release_group_cases
from app.core.meta.releasegroup import ReleaseGroupsMatcher


def test_release_group():
    for info in release_group_cases:
        for item in info.get('groups', []):
            release_group = ReleaseGroupsMatcher().match(item.get("title"))
            assert item.get("group") == release_group


def test_custom_release_group_matches_multiple_adjacent_groups():
    """自定义制作组共用分隔符时，应完整保留所有命中项。"""
    matcher = ReleaseGroupsMatcher()

    with patch.object(
        matcher.systemconfig,
        "get",
        return_value=["re:VCB-Studio|hyakuhuyu|DMG|GM-Team"],
    ):
        release_group = matcher.match(
            "[DMG&VCB-Studio] Youkoso Jitsuryoku Shijou Shugi no Kyoushitsu e"
        )

    assert "DMG&VCB-Studio" == release_group


def test_invalid_custom_group_regex_is_skipped_without_breaking_valid_groups():
    """无效 re: 条目应跳过，不能让其它有效制作组规则整体失效。"""
    matcher = ReleaseGroupsMatcher()

    with patch.object(
        matcher.systemconfig,
        "get",
        return_value=["re:(", "VCB-Studio"],
    ):
        assert matcher.match_list(title="[VCB-Studio] Show [01]") == ["VCB-Studio"]

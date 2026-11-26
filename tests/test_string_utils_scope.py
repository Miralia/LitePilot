"""字符串工具能力边界测试。"""

from pathlib import Path

from app.utils.string import StringUtils


def test_removed_upstream_string_utilities_stay_removed() -> None:
    """字符串工具只保留识别、整理、下载状态展示所需能力。"""
    for method in (
        "num_filesize",
        "str_timelong",
        "is_japanese",
        "is_korean",
        "is_english_word",
        "str_int",
        "str_float",
        "format_size",
        "url_equal",
        "get_url_netloc",
        "get_url_domain",
        "get_url_sld",
        "get_url_host",
        "get_base_url",
        "clear_file_name",
        "generate_random_str",
        "get_time",
        "unify_datetime_str",
        "format_timestamp",
        "str_to_timestamp",
        "to_bool",
        "str_from_cookiejar",
        "get_idlist",
        "str_timehours",
        "str_amount",
        "split_text",
        "escape_markdown",
        "str_series",
        "format_ep",
        "is_number",
        "find_common_prefix",
        "compare_version",
        "diff_time_str",
        "safe_strip",
        "is_valid_html_element",
        "is_link",
        "is_magnet_link",
    ):
        assert not hasattr(StringUtils, method)


def test_active_string_utilities_remain_available() -> None:
    """识别、整理和下载状态展示仍在使用的工具方法不应被误删。"""
    for method in (
        "str_secends",
        "is_chinese",
        "is_all_chinese",
        "clear",
        "clear_upper",
        "str_filesize",
        "md5_hash",
        "count_words",
        "is_media_title_like",
        "get_keyword",
        "str_title",
        "get_domain_address",
        "format_season_episode",
        "natural_sort_key",
    ):
        assert hasattr(StringUtils, method)


def test_dead_date_parsing_dependencies_are_not_required() -> None:
    """dateparser/python-dateutil 只服务已删除的死方法，不应保留为运行依赖。"""
    requirements = Path("requirements.in").read_text()
    assert "dateparser" not in requirements
    assert "python-dateutil" not in requirements

# -*- coding: utf-8 -*-
"""制作组/字幕组识别用例。

重点覆盖两种连接语义：

- `&` 是合作发布，两侧各算一个小组；
- `@` 是从属关系，整体算一个小粗（如 `Baha@SweetSub`）。
"""
import pytest

from app.core.meta.releasegroup import ReleaseGroupsMatcher
from app.db.systemconfig_oper import SystemConfigOper
from app.schemas.types import SystemConfigKey


@pytest.fixture()
def matcher():
    """写入测试组表并返回匹配器实例。"""
    SystemConfigOper().set(
        SystemConfigKey.CustomReleaseGroups,
        ["SweetSub", "VCB-Studio", "ANi", "LoliHouse", "Baha", "喵萌奶茶屋"],
    )
    return ReleaseGroupsMatcher()


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        # & 合作发布：逐个拆开
        ("Show.2024.x264-SweetSub&VCB-Studio", ["SweetSub", "VCB-Studio"]),
        ("[SweetSub&VCB-Studio&ANi] Show [01]", ["SweetSub", "VCB-Studio", "ANi"]),
        (
            "[SweetSub&VCB-Studio&ANi&LoliHouse] Show [01]",
            ["SweetSub", "VCB-Studio", "ANi", "LoliHouse"],
        ),
        ("[喵萌奶茶屋&VCB-Studio] Show [01]", ["喵萌奶茶屋", "VCB-Studio"]),
    ],
)
def test_cooperation_splits_by_ampersand(matcher, title, expected):
    """`&` 连接的多个组应全部识别出来。"""
    assert matcher.match_list(title=title) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        # @ 从属关系：整体算一个，不拆开、也不吞标题前缀
        ("Show.2024.1080p.Baha@SweetSub", ["Baha@SweetSub"]),
        ("[Baha@SweetSub] Show [01]", ["Baha@SweetSub"]),
        ("Show.2024.1080p.Baha@SweetSub@VCB-Studio", ["Baha@SweetSub@VCB-Studio"]),
    ],
)
def test_subordinate_keeps_at_as_single_group(matcher, title, expected):
    """`@` 连接的从属关系应作为一个整体组，且不带标题前缀。"""
    assert matcher.match_list(title=title) == expected


def test_subordinate_plus_cooperation(matcher):
    """从属组与合作伙伴应分别识别。"""
    assert matcher.match_list(title="Show.2024.Baha@SweetSub&VCB-Studio") == [
        "Baha@SweetSub",
        "VCB-Studio",
    ]


def test_single_group_still_works(matcher):
    """普通单组发布保持原有行为。"""
    assert matcher.match_list(title="[ANi] Show - 01 [1080p]") == ["ANi"]


def test_unknown_group_returns_empty(matcher):
    """没有任何已知组时返回空列表。"""
    assert matcher.match_list(title="Show.2024.1080p.WEB-DL.x264") == []


def test_match_joins_groups_with_at(matcher):
    """match 保持以 @ 连接多个组的既有行为。"""
    assert matcher.match(title="x-SweetSub&VCB-Studio") == "SweetSub@VCB-Studio"


def test_custom_group_with_special_chars_is_literal():
    """用户词表中的特殊字符应按字面量匹配，不应被当成正则。"""
    SystemConfigOper().set(
        SystemConfigKey.CustomReleaseGroups, ["SubsPlus+", "VCB-Studio"]
    )
    m = ReleaseGroupsMatcher()

    assert m.match_list(title="Show.2024-SubsPlus+") == ["SubsPlus+"]
    assert m.match_list(title="Show.2024-VCB-Studio") == ["VCB-Studio"]

def test_empty_config_is_seeded_with_builtin_groups():
    """配置为空时用内置表初始化，保证升级后仍能识别常见组。"""
    SystemConfigOper().set(SystemConfigKey.CustomReleaseGroups, None)
    matcher = ReleaseGroupsMatcher()
    setattr(matcher, "_ReleaseGroupsMatcher__seed_applied", False)

    rule = matcher.get_release_groups()
    assert rule
    # 内置表里的正则条目（如 FFAB）应保持正则语义
    assert matcher.match_list(title="Show.2024-FFAB") == ["FFAB"]


def test_user_words_support_literal_special_chars():
    """用户手写的特殊字符组名按字面量匹配。"""
    SystemConfigOper().set(
        SystemConfigKey.CustomReleaseGroups, ["SubsPlus+", "VCB-Studio"]
    )
    m = ReleaseGroupsMatcher()

    assert m.match_list(title="Show.2024-SubsPlus+") == ["SubsPlus+"]
    assert m.match_list(title="Show.2024-VCB-Studio") == ["VCB-Studio"]


def test_regex_prefix_is_honored():
    """显式 re: 前缀的条目按正则处理。"""
    SystemConfigOper().set(SystemConfigKey.CustomReleaseGroups, ["re:ABC-?Sub"])
    m = ReleaseGroupsMatcher()

    assert m.match_list(title="Show.2024-ABCSub") == ["ABCSub"]

@pytest.mark.parametrize(
    ("title", "expected_name", "expected_bit"),
    [
        # 动漫圈常见的 Np 位深写法，且常出现在分辨率之前
        ("[VCB-Studio] Jujutsu Kaisen [Ma10p_1080p][x265_flac].mkv",
         "Jujutsu Kaisen", "10bit"),
        ("[BeanSub&FZSD&VCB-Studio] Gekijouban Jujutsu Kaisen 0 [Ma10p_1080p][x265_flac].mkv",
         "Gekijouban Jujutsu Kaisen 0", "10bit"),
        ("[Nekomoe kissaten&VCB-Studio] Fushigi no Kuni de Alice to [Ma10p_1080p][x265_flac].mkv",
         "Fushigi No Kuni De Alice To", "10bit"),
        # 常规 10bit 写法
        ("[Group] Show [10bit][1080p]", "Show", "10bit"),
        # 8bit 同样适用
        ("[Group] Show [Ma8p][1080p]", "Show", "8bit"),
    ],
)
def test_video_bit_is_stripped_from_name(title, expected_name, expected_bit):
    """位深标记应被识别出来，且不能残留在标题里。"""
    from app.core.meta import MetaVideo

    meta = MetaVideo(title)
    assert meta.video_bit == expected_bit
    assert meta.name == expected_name


def test_resolution_not_confused_with_bit_depth():
    """分辨率里的 p 不能被误判为位深。"""
    from app.core.meta import MetaVideo

    for title in ("Movie.2024.1080p.BluRay.x264", "Movie.2024.2160p.WEB-DL"):
        meta = MetaVideo(title)
        assert meta.video_bit is None


@pytest.mark.parametrize(
    ("title", "expected_name"),
    [
        # 结尾单独的 0 是片名编号，不能当成集数丢弃
        ("Jujutsu Kaisen 0", "Jujutsu Kaisen 0"),
        ("Gekijouban Jujutsu Kaisen 0", "Gekijouban Jujutsu Kaisen 0"),
        (
            "[BeanSub&FZSD&VCB-Studio] Gekijouban Jujutsu Kaisen 0 [Ma10p_1080p]",
            "Gekijouban Jujutsu Kaisen 0",
        ),
    ],
)
def test_trailing_zero_kept_in_title(title, expected_name):
    """片名结尾的编号 0 应保留在标题里。"""
    from app.core.meta import MetaVideo
    from app.core.metainfo import MetaInfo

    assert MetaVideo(title).name == expected_name
    assert MetaInfo(title).name == expected_name


@pytest.mark.parametrize(
    ("title", "expected_episode"),
    [
        # 补零集数仍然要识别为集，不能因为上面的修复而保留进标题
        ("[Group] Show - 01 [1080p]", 1),
        ("[Group] Show - 001 [1080p]", 1),
        ("[Group] Show 02 [1080p]", 2),
    ],
)
def test_zero_padded_episode_still_detected(title, expected_episode):
    """补零集数不能被误当成片名。"""
    from app.core.meta import MetaVideo

    meta = MetaVideo(title)
    assert meta.begin_episode == expected_episode
    assert meta.name == "Show"

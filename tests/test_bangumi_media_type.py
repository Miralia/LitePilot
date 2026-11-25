from typing import Optional

import pytest

from app.chain.media import MediaChain
from app.core.context import MediaInfo
from app.schemas.types import MediaType


@pytest.mark.parametrize(
    ("platform", "expected_type"),
    [
        ("剧场版", MediaType.MOVIE),
        ("Movie", MediaType.MOVIE),
        ("电影", MediaType.MOVIE),
        ("TV", MediaType.TV),
        ("WEB", MediaType.TV),
        ("OVA", MediaType.TV),
        ("未知", MediaType.TV),
        (None, MediaType.TV),
    ],
)
def test_bangumi_platform_maps_to_media_type(
        platform: Optional[str], expected_type: MediaType
) -> None:
    """Bangumi媒介平台应映射为正确的标准媒体类型。"""
    media_info = MediaInfo(bangumi_info={"id": 1, "name": "测试条目", "platform": platform})

    assert media_info.type == expected_type


def test_bangumi_media_type_does_not_override_explicit_type() -> None:
    """显式媒体类型应优先于Bangumi媒介平台。"""
    media_info = MediaInfo(
        type=MediaType.TV,
        bangumi_info={"id": 1, "name": "测试条目", "platform": "剧场版"},
    )

    assert media_info.type == MediaType.TV

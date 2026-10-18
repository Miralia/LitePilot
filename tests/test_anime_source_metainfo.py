from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.metainfo import MetaInfo, MetaInfoPath, find_metainfo
from app.schemas.types import MediaType


@pytest.mark.parametrize(
    ("title", "source", "media_id"),
    [
        ("葬送的芙莉莲 {[bangumiid=400602;type=tv;s=1]}", "bangumi", "400602"),
    ],
)
def test_find_metainfo_supports_anime_source_ids(
    title: str,
    source: str,
    media_id: str,
) -> None:
    """显式动画来源标签应提取统一来源ID并从标题中移除。"""
    parsed_title, metainfo = find_metainfo(title)

    assert metainfo["media_source"] == source
    assert metainfo["media_id"] == media_id
    assert f"{source}id=" not in parsed_title
    assert f"{source}=" not in parsed_title



def test_metainfo_path_inherits_bangumi_id_from_parent() -> None:
    """文件路径识别应从父目录继承Bangumi来源ID。"""
    meta = MetaInfoPath(
        Path("/anime/葬送的芙莉莲 [bangumi=400602]/Frieren.S01E01.mkv")
    )

    assert meta.media_source == "bangumi"
    assert meta.media_id == "400602"
    assert meta.begin_season == 1
    assert meta.begin_episode == 1



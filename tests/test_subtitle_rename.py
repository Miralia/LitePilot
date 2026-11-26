from pathlib import Path

import pytest

from app.core.config import settings
from app.modules.filemanager.transhandler import TransHandler
from app.schemas.file import FileItem


@pytest.fixture(autouse=True)
def restore_default_sub():
    """每个测试结束后恢复全局默认字幕设置。"""
    original = settings.DEFAULT_SUB
    yield
    settings.DEFAULT_SUB = original


def _rename_subtitle(sub_name: str, default_sub: str) -> Path:
    """
    直接调用字幕重命名逻辑，覆盖语言标签识别与默认字幕标记。
    """
    settings.DEFAULT_SUB = default_sub
    sub_item = FileItem(
        storage="local",
        type="file",
        path=f"/source/{sub_name}.srt",
        name=sub_name,
        extension="srt",
    )
    target_file = Path("/target/24 Hours.2001.S02E01.[tmdbid=14064].srt")
    return TransHandler._TransHandler__rename_subtitles(sub_item, target_file)


def test_traditional_chinese_subtitle_is_not_misclassified_as_simplified():
    """
    issue #5703: “繁体中文” 不应命中简中兜底规则，也不应被打上默认简中标签。
    """
    renamed = _rename_subtitle("24.Hours.S02E01.繁体中文", default_sub="zh-cn")
    assert renamed.name == "24 Hours.2001.S02E01.[tmdbid=14064].zh-tw.srt"


def test_traditional_chinese_subtitle_can_be_marked_as_default():
    """
    当默认字幕设置为繁中时，仍应保留正确的繁中语言后缀并追加 default 标记。
    """
    renamed = _rename_subtitle("24.Hours.S02E01.繁体中文", default_sub="zh-tw")
    assert renamed.name == "24 Hours.2001.S02E01.[tmdbid=14064].default.zh-tw.srt"

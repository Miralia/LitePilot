"""仅保留最新版本模式的清理顺序测试。"""

from pathlib import Path
from types import SimpleNamespace

from app.core.context import MediaInfo
from app.core.meta import MetaBase
from app.modules.filemanager.transhandler import TransHandler
from app.schemas import FileItem
from app.schemas.types import MediaType


def _file_item(path: str, item_type: str = "file") -> FileItem:
    """构造整理流程所需的最小文件项。"""
    file_path = Path(path)
    return FileItem(
        storage="local",
        path=file_path.as_posix(),
        type=item_type,
        name=file_path.name,
        basename=file_path.stem,
        extension=file_path.suffix.removeprefix("."),
        size=1024 if item_type == "file" else None,
    )


def _build_input(target_exists=False):
    """构造一次不需要真实重命名模板的剧集整理输入。"""
    source = _file_item("/downloads/Test.Show.S01E01.2160p.WEB-DL.mkv")
    meta = MetaBase(source.name)
    meta.type = MediaType.TV
    meta.name = "Test Show"
    meta.year = "2026"
    meta.begin_season = 1
    meta.begin_episode = 1
    mediainfo = MediaInfo(type=MediaType.TV, title="Test Show", year="2026", tmdb_id=12345)
    target_folder = _file_item("/library", "dir")
    target_item = _file_item("/library/Test.Show.S01E01.2160p.WEB-DL.mkv") if target_exists else None
    target_oper = SimpleNamespace(
        get_folder=lambda path: target_folder,
        get_item_strict=lambda path: target_item,
    )
    return source, meta, mediainfo, target_oper


def _patch_cleanup_and_transfer(monkeypatch, events, transfer_result):
    """拦截删除与传输边界，记录真实执行顺序。"""
    def delete_version_files(storage_oper, path):
        events.append("delete")
        return True

    def transfer_file(self, **kwargs):
        events.append("transfer")
        return transfer_result

    monkeypatch.setattr(
        TransHandler,
        "_TransHandler__delete_version_files",
        staticmethod(delete_version_files),
    )
    monkeypatch.setattr(TransHandler, "_TransHandler__transfer_file", transfer_file)


def _transfer_latest(target_exists=False):
    """执行 latest 模式整理。"""
    source, meta, mediainfo, target_oper = _build_input(target_exists=target_exists)
    return TransHandler().transfer_media(
        fileitem=source,
        in_meta=meta,
        mediainfo=mediainfo,
        target_storage="local",
        target_path=Path("/library"),
        transfer_type="copy",
        source_oper=SimpleNamespace(),
        target_oper=target_oper,
        need_rename=False,
        need_notify=False,
        need_scrape=False,
        overwrite_mode="latest",
    )


def test_latest_mode_does_not_delete_old_versions_when_transfer_fails(monkeypatch) -> None:
    """新版本尚未落盘时不得删除旧版本，否则传输失败会造成媒体缺失。"""
    events = []
    _patch_cleanup_and_transfer(monkeypatch, events, (None, "simulated copy failure"))

    result = _transfer_latest()

    assert result.success is False
    assert events == ["transfer"]


def test_latest_mode_deletes_old_versions_only_after_transfer_success(monkeypatch) -> None:
    """新版本成功落盘后才允许清理同季集旧版本。"""
    events = []
    new_item = _file_item("/library/Test.Show.S01E01.2160p.WEB-DL.mkv")
    _patch_cleanup_and_transfer(monkeypatch, events, (new_item, ""))

    result = _transfer_latest()

    assert result.success is True
    assert events == ["transfer", "delete"]


def test_latest_mode_cleans_other_versions_after_replacing_existing_target(monkeypatch) -> None:
    """同名目标已存在时，覆盖成功后仍应清理分辨率等其它旧版本。"""
    events = []
    new_item = _file_item("/library/Test.Show.S01E01.2160p.WEB-DL.mkv")
    _patch_cleanup_and_transfer(monkeypatch, events, (new_item, ""))

    result = _transfer_latest(target_exists=True)

    assert result.success is True
    assert events == ["transfer", "delete"]

"""仅保留最新版本清理日志语义测试。"""

from pathlib import Path
from types import SimpleNamespace

from app.modules.filemanager.transhandler import TransHandler
from app.schemas import FileItem


def _file_item(path: str, item_type: str = "file") -> FileItem:
    """构造版本清理所需的最小文件项。"""
    file_path = Path(path)
    return FileItem(
        storage="local",
        path=file_path.as_posix(),
        type=item_type,
        name=file_path.name,
        basename=file_path.stem,
        extension=file_path.suffix.removeprefix("."),
    )


def test_version_cleanup_does_not_warn_before_candidates_exist(monkeypatch) -> None:
    """目标目录不存在或没有同季集候选时是正常新入库路径，不应误报正在删除。"""
    warnings = []
    monkeypatch.setattr("app.modules.filemanager.transhandler.logger.warning", warnings.append)
    target = Path("/library/Show/Season 1/Show.S01E01.2160p.WEB-DL.mkv")
    parent = _file_item(target.parent.as_posix(), "dir")
    storage = SimpleNamespace(
        get_item=lambda path: parent,
        list=lambda item: [],
        delete=lambda item: None,
    )

    result = TransHandler._TransHandler__delete_version_files(storage, target)

    assert result is False
    assert not any("正在删除目标目录中其它版本" in message for message in warnings)


def test_version_cleanup_warns_only_when_candidate_is_deleted(monkeypatch) -> None:
    """真正删除同季集旧版本时仍应保留明确的高级别审计日志。"""
    warnings = []
    deleted = []
    monkeypatch.setattr("app.modules.filemanager.transhandler.logger.warning", warnings.append)
    target = Path("/library/Show/Season 1/Show.S01E01.2160p.WEB-DL.mkv")
    parent = _file_item(target.parent.as_posix(), "dir")
    old_version = _file_item("/library/Show/Season 1/Show.S01E01.1080p.WEB-DL.mkv")
    storage = SimpleNamespace(
        get_item=lambda path: parent,
        list=lambda item: [old_version],
        delete=deleted.append,
    )

    result = TransHandler._TransHandler__delete_version_files(storage, target)

    assert result is True
    assert deleted == [old_version]
    assert any("正在删除目标目录中其它版本" in message for message in warnings)


def test_version_cleanup_skips_files_without_extension(monkeypatch) -> None:
    """目录中的无扩展名文件不是媒体版本，不得让成功整理后的清理流程崩溃。"""
    target = Path("/library/Show/Season 1/Show.S01E01.2160p.WEB-DL.mkv")
    extensionless = FileItem(
        storage="local",
        path="/library/Show/Season 1/README",
        type="file",
        name="README",
        extension=None,
    )
    deleted = []
    storage = SimpleNamespace(
        get_item=lambda path: SimpleNamespace(),
        list=lambda item: [extensionless],
        delete=lambda item: deleted.append(item) or True,
    )
    monkeypatch.setattr(
        "app.modules.filemanager.transhandler.MetaInfoPath",
        lambda path: SimpleNamespace(season="S01", episode="E01", part=None),
    )

    result = TransHandler._TransHandler__delete_version_files(storage, target)  # pylint: disable=protected-access

    assert result is True
    assert deleted == []

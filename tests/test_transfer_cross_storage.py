from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.context import MediaInfo
from app.core.meta import MetaBase
from app.modules.filemanager.transhandler import TransHandler
from app.schemas import FileItem, TransferInfo
from app.schemas.types import MediaType


@pytest.mark.parametrize(
    ("source_storage", "target_storage"),
    [("smb", "local"), ("local", "smb")],
)
def test_cross_storage_hard_link_is_rejected_before_io(source_storage, target_storage):
    """跨存储硬链接在后端应被明确拒绝，而不是落到未知错误。"""
    source_item = FileItem(
        storage=source_storage,
        path="/downloads/example.mkv",
        type="file",
        name="example.mkv",
        basename="example",
        extension="mkv",
        size=1024,
    )

    new_item, errmsg = TransHandler._TransHandler__transfer_command(
        fileitem=source_item,
        target_storage=target_storage,
        source_oper=SimpleNamespace(),
        target_oper=SimpleNamespace(),
        target_file=Path("/library/example.mkv"),
        transfer_type="link",
    )

    assert new_item is None
    assert "仅支持复制或移动" in errmsg


def test_remote_to_local_downloads_to_temp_before_final_move(tmp_path, monkeypatch):
    """远程到本地整理应先落到临时目录，完整后再移动到媒体库目标路径。"""
    source_item = FileItem(
        storage="smb",
        path="/downloads/example.mkv",
        type="file",
        name="example.mkv",
        basename="example",
        extension="mkv",
        size=3,
    )
    temp_file = tmp_path / "example.mkv"
    temp_file.write_bytes(b"abc")
    target_file = tmp_path / "library" / "example.mkv"
    calls = {}

    def fake_download(fileitem, path=None):
        calls["download_path"] = path
        return temp_file

    def fake_move(src, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        return 0, ""

    source_oper = SimpleNamespace(
        download=fake_download,
        delete=lambda fileitem: True,
    )
    target_oper = SimpleNamespace(
        get_folder=lambda path: SimpleNamespace(path=path.as_posix()),
    )
    monkeypatch.setattr(
        "app.modules.filemanager.transhandler.SystemUtils.move", fake_move
    )

    new_item, errmsg = TransHandler._TransHandler__transfer_command(
        fileitem=source_item,
        target_storage="local",
        source_oper=source_oper,
        target_oper=target_oper,
        target_file=target_file,
        transfer_type="copy",
    )

    assert errmsg == ""
    assert new_item is not None
    assert calls["download_path"] is None


def test_remote_to_local_move_failure_is_reported_and_temp_is_cleaned(tmp_path, monkeypatch):
    """远程到本地的最终移动失败时不得误报成功，也不得遗留临时文件。"""
    source_item = FileItem(
        storage="smb",
        path="/downloads/example.mkv",
        type="file",
        name="example.mkv",
        basename="example",
        extension="mkv",
        size=3,
    )
    temp_file = tmp_path / "example.mkv"
    temp_file.write_bytes(b"abc")
    target_file = tmp_path / "library" / "example.mkv"
    delete_calls = []

    source_oper = SimpleNamespace(
        download=lambda fileitem: temp_file,
        delete=lambda fileitem: delete_calls.append(fileitem) or True,
    )
    target_oper = SimpleNamespace(
        get_folder=lambda path: SimpleNamespace(path=path.as_posix()),
    )
    monkeypatch.setattr(
        "app.modules.filemanager.transhandler.SystemUtils.move", lambda _src, _dest: (-1, "disk full")
    )

    new_item, errmsg = TransHandler._TransHandler__transfer_command(
        fileitem=source_item,
        target_storage="local",
        source_oper=source_oper,
        target_oper=target_oper,
        target_file=target_file,
        transfer_type="move",
    )

    assert new_item is None
    assert "移动到本地媒体库失败" in errmsg
    assert "disk full" in errmsg
    assert not temp_file.exists()
    assert not target_file.exists()
    assert delete_calls == []


def test_local_to_remote_move_reports_source_delete_failure(tmp_path):
    """本地到远程移动在源文件删除失败时不得静默退化为复制。"""
    source_file = tmp_path / "downloads" / "example.mkv"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"abc")
    source_item = FileItem(
        storage="local",
        path=source_file.as_posix(),
        type="file",
        name=source_file.name,
        basename=source_file.stem,
        extension="mkv",
        size=3,
    )
    uploaded_item = FileItem(
        storage="smb",
        path="/library/example.mkv",
        type="file",
        name="example.mkv",
        basename="example",
        extension="mkv",
        size=3,
    )
    target_oper = SimpleNamespace(
        get_folder=lambda path: SimpleNamespace(path=path.as_posix()),
        upload=lambda folder, path, new_name: uploaded_item,
    )
    source_oper = SimpleNamespace(delete=lambda fileitem: False)

    new_item, errmsg = TransHandler._TransHandler__transfer_command(
        fileitem=source_item,
        target_storage="smb",
        source_oper=source_oper,
        target_oper=target_oper,
        target_file=Path("/library/example.mkv"),
        transfer_type="move",
    )

    assert new_item == uploaded_item
    assert "源文件删除失败" in errmsg
    assert "源文件仍保留" in errmsg
    assert "确认无需保种后手动清理" in errmsg


def test_remote_to_local_move_reports_source_delete_failure(tmp_path, monkeypatch):
    """远程到本地移动在源文件删除失败时不得静默退化为复制。"""
    source_item = FileItem(
        storage="smb",
        path="/downloads/example.mkv",
        type="file",
        name="example.mkv",
        basename="example",
        extension="mkv",
        size=3,
    )
    temp_file = tmp_path / "example.mkv"
    temp_file.write_bytes(b"abc")
    target_file = tmp_path / "library" / "example.mkv"

    def fake_move(src, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        return 0, ""

    monkeypatch.setattr(
        "app.modules.filemanager.transhandler.SystemUtils.move", fake_move
    )
    source_oper = SimpleNamespace(
        download=lambda fileitem: temp_file,
        delete=lambda fileitem: False,
    )
    target_oper = SimpleNamespace(
        get_folder=lambda path: SimpleNamespace(path=path.as_posix()),
    )

    new_item, errmsg = TransHandler._TransHandler__transfer_command(
        fileitem=source_item,
        target_storage="local",
        source_oper=source_oper,
        target_oper=target_oper,
        target_file=target_file,
        transfer_type="move",
    )

    assert new_item is not None
    assert "源文件删除失败" in errmsg
    assert "源文件仍保留" in errmsg
    assert "确认无需保种后手动清理" in errmsg


def test_successful_transfer_warning_is_exposed_in_transferinfo(tmp_path, monkeypatch):
    """整理已落盘但存在后续清理警告时，通知上下文必须能拿到该警告。"""
    source_item = FileItem(
        storage="smb",
        path="/downloads/Test.Show.S01E01.mkv",
        type="file",
        name="Test.Show.S01E01.mkv",
        basename="Test.Show.S01E01",
        extension="mkv",
        size=1024,
    )
    target_item = FileItem(
        storage="local",
        path=(tmp_path / "library" / source_item.name).as_posix(),
        type="file",
        name=source_item.name,
        basename=source_item.basename,
        extension="mkv",
        size=1024,
    )
    meta = MetaBase(source_item.name)
    meta.type = MediaType.TV
    meta.name = "Test Show"
    meta.year = "2026"
    meta.begin_season = 1
    meta.begin_episode = 1
    mediainfo = MediaInfo(type=MediaType.TV, title="Test Show", year="2026", tmdb_id=12345)
    warning = "源文件删除失败，移动未完全完成"
    target_oper = SimpleNamespace(
        get_folder=lambda path: SimpleNamespace(path=path.as_posix()),
        get_item_strict=lambda path: None,
    )
    monkeypatch.setattr(
        TransHandler,
        "_TransHandler__transfer_file",
        lambda self, **kwargs: (target_item, warning),
    )

    result = TransHandler().transfer_media(
        fileitem=source_item,
        in_meta=meta,
        mediainfo=mediainfo,
        target_storage="local",
        target_path=tmp_path / "library",
        transfer_type="move",
        source_oper=SimpleNamespace(),
        target_oper=target_oper,
        need_rename=False,
        need_notify=False,
        need_scrape=False,
    )

    assert result.success is True
    assert result.message == warning



def test_directory_move_aggregates_source_delete_warnings(monkeypatch):
    """目录整理中多个文件的部分完成警告应聚合传递给成功通知。"""
    source_dir = FileItem(
        storage="smb",
        path="/downloads/Example/",
        type="dir",
        name="Example",
    )
    first = FileItem(
        storage="smb",
        path="/downloads/Example/a.mkv",
        type="file",
        name="a.mkv",
    )
    second = FileItem(
        storage="smb",
        path="/downloads/Example/b.mkv",
        type="file",
        name="b.mkv",
    )
    warnings = {
        first.path: "a.mkv 源文件删除失败",
        second.path: "b.mkv 源文件删除失败",
    }

    def fake_command(fileitem, **_kwargs):
        return (
            FileItem(
                storage="local",
                path=f"/library/Example/{fileitem.name}",
                type="file",
                name=fileitem.name,
            ),
            warnings[fileitem.path],
        )

    monkeypatch.setattr(
        TransHandler,
        "_TransHandler__transfer_command",
        staticmethod(fake_command),
    )
    source_oper = SimpleNamespace(list=lambda fileitem: [first, second])

    state, errmsg = TransHandler()._TransHandler__transfer_dir_files(
        fileitem=source_dir,
        target_storage="local",
        source_oper=source_oper,
        target_oper=SimpleNamespace(),
        transfer_type="move",
        target_path=Path("/library/Example"),
        result=TransferInfo(),
    )

    assert state is True
    assert errmsg == "；".join(warnings.values())

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.modules.filemanager.transhandler import TransHandler
from app.schemas import FileItem


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

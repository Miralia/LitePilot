import app.modules.filemanager.storages.local as local_module
from app.modules.filemanager.storages.local import LocalStorage


def test_cancelled_local_copy_removes_partial_target_file(tmp_path, monkeypatch):
    """本地复制取消后不得把未完整的目标文件留在媒体库路径。"""
    source_file = tmp_path / "source.mkv"
    target_file = tmp_path / "target.mkv"
    source_file.write_bytes(b"abc")
    storage = object.__new__(LocalStorage)

    monkeypatch.setattr(local_module, "transfer_process", lambda *_args, **_kwargs: lambda _progress: None)
    stopped = iter([False, True])
    monkeypatch.setattr(local_module.global_vars, "is_transfer_stopped", lambda _path: next(stopped))

    assert storage._copy_with_progress(source_file, target_file) is False
    assert not target_file.exists()


def test_failed_copy_before_start_preserves_existing_target(tmp_path, monkeypatch):
    """复制尚未开始时失败不得删除目标路径已有文件。"""
    source_file = tmp_path / "missing.mkv"
    target_file = tmp_path / "target.mkv"
    target_file.write_bytes(b"original")
    storage = object.__new__(LocalStorage)

    monkeypatch.setattr(local_module, "transfer_process", lambda *_args, **_kwargs: lambda _progress: None)
    monkeypatch.setattr(local_module.global_vars, "is_transfer_stopped", lambda _path: False)

    assert storage._copy_with_progress(source_file, target_file) is False
    assert target_file.read_bytes() == b"original"

import app.modules.filemanager.storages.smb as smb_module
from app import schemas
from app.modules.filemanager.storages.smb import SMB


def make_smb_storage() -> SMB:
    """构造不触发真实网络初始化的 SMB 存储实例。"""
    storage = object.__new__(SMB)
    storage._connected = True
    storage._server_path = "\\\\server\\share"
    return storage


def test_cancelled_download_removes_partial_local_file(tmp_path, monkeypatch):
    """SMB 下载取消后不得把未完整的本地文件留在目标目录。"""
    storage = make_smb_storage()
    fileitem = schemas.FileItem(
        storage="smb",
        path="/downloads/example.mkv",
        type="file",
        name="example.mkv",
        size=6,
    )

    class FakeRemoteReader:
        def __init__(self):
            self.read_count = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _size):
            self.read_count += 1
            return b"abc" if self.read_count == 1 else b""

    monkeypatch.setattr(smb_module.smbclient, "open_file", lambda *_args, **_kwargs: FakeRemoteReader())
    monkeypatch.setattr(smb_module, "transfer_process", lambda *_args, **_kwargs: lambda _progress: None)
    stopped = iter([False, True])
    monkeypatch.setattr(smb_module.global_vars, "is_transfer_stopped", lambda _path: next(stopped))

    result = storage.download(fileitem, tmp_path)

    assert result is None
    assert not (tmp_path / "example.mkv").exists()


def test_cancelled_upload_removes_partial_remote_file(tmp_path, monkeypatch):
    """SMB 上传取消后不得把未完整的远端文件留在共享目录。"""
    storage = make_smb_storage()
    source_file = tmp_path / "example.mkv"
    source_file.write_bytes(b"abc")
    target_folder = schemas.FileItem(
        storage="smb",
        path="/library/",
        type="dir",
        name="library",
    )
    remote_state = {"exists": False, "removed": False, "data": bytearray()}

    class FakeRemoteWriter:
        def __enter__(self):
            remote_state["exists"] = True
            return self

        def __exit__(self, *_args):
            return False

        def write(self, chunk):
            remote_state["data"].extend(chunk)

    def fake_open_file(_path, mode="rb", **_kwargs):
        assert mode == "wb"
        return FakeRemoteWriter()

    def fake_exists(_path):
        return remote_state["exists"]

    def fake_remove(_path):
        remote_state["removed"] = True
        remote_state["exists"] = False

    monkeypatch.setattr(smb_module.smbclient, "open_file", fake_open_file)
    monkeypatch.setattr(smb_module.smbclient.path, "exists", fake_exists)
    monkeypatch.setattr(smb_module.smbclient, "remove", fake_remove)
    monkeypatch.setattr(smb_module, "transfer_process", lambda *_args, **_kwargs: lambda _progress: None)
    stopped = iter([False, True])
    monkeypatch.setattr(smb_module.global_vars, "is_transfer_stopped", lambda _path: next(stopped))

    result = storage.upload(target_folder, source_file, "example.mkv")

    assert result is None
    assert remote_state["removed"] is True
    assert remote_state["exists"] is False
    assert bytes(remote_state["data"]) == b"abc"

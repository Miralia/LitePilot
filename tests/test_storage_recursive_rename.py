from types import SimpleNamespace

from app.api.endpoints.storage import rename
from app.schemas import FileItem


def test_recursive_rename_reads_nested_files_and_uses_full_paths(monkeypatch):
    """批量重命名必须遍历子目录，并用文件项自身的完整路径识别。"""
    root = FileItem(storage="local", type="dir", path="/downloads/Show/", name="Show")
    nested = FileItem(
        storage="local",
        type="file",
        path="/downloads/Show/Season 1/ep1.mkv",
        name="ep1.mkv",
        extension="mkv",
    )
    calls = {"list": [], "recognize": [], "rename": []}

    class FakeStorageChain:
        def list_files(self, fileitem, recursion=False):
            calls["list"].append((fileitem.path, recursion))
            return [nested]

        def rename_file(self, fileitem, new_name):
            calls["rename"].append((fileitem.path, new_name))
            return True

    class FakeMediaChain:
        def recognize_by_path(self, path, obtain_images=False):
            calls["recognize"].append(path.as_posix())
            return SimpleNamespace(media_info=object(), meta_info=object())

    class FakeTransferChain:
        def recommend_name(self, meta, mediainfo):
            return "/library/Show/ep1-renamed.mkv"

    class FakeProgress:
        def start(self):
            return None

        def update(self, **kwargs):
            return None

        def end(self):
            return None

    monkeypatch.setattr("app.api.endpoints.storage.StorageChain", FakeStorageChain)
    monkeypatch.setattr("app.api.endpoints.storage.MediaChain", FakeMediaChain)
    monkeypatch.setattr("app.api.endpoints.storage.TransferChain", FakeTransferChain)
    monkeypatch.setattr("app.api.endpoints.storage.ProgressHelper", lambda key: FakeProgress())

    response = rename(fileitem=root, new_name="Renamed Show", recursive=True, _=object())

    assert response.success is True
    assert calls["list"] == [("/downloads/Show/", True)]
    assert calls["recognize"] == ["/downloads/Show/Season 1/ep1.mkv"]
    assert calls["rename"] == [
        ("/downloads/Show/Season 1/ep1.mkv", "ep1-renamed.mkv"),
        ("/downloads/Show/", "Renamed Show"),
    ]

from pathlib import Path
import pytest

from app import schemas
from app.modules.filemanager.storages.local import LocalStorage






@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("../proof.txt", "proof.txt"),
        ("..\\proof.txt", "proof.txt"),
        ("/tmp/proof.txt", "proof.txt"),
    ],
)
def test_build_download_path_strips_remote_directory_segments(
    tmp_path: Path, name: str, expected: str
) -> None:
    """本地下载路径应剥离远端文件名中的目录片段。"""
    storage = object.__new__(LocalStorage)
    fileitem = schemas.FileItem(path=f"/remote/{expected}", name=name)

    local_path = storage._build_download_path(fileitem, tmp_path)

    assert local_path == tmp_path / expected
    assert local_path.resolve().relative_to(tmp_path.resolve()) == Path(expected)


@pytest.mark.parametrize("name", ["", ".", "..", "subdir/.."])
def test_build_download_path_rejects_unsafe_filename(
    tmp_path: Path, name: str
) -> None:
    """本地下载路径应拒绝无法安全落盘的文件名。"""
    storage = object.__new__(LocalStorage)
    fileitem = schemas.FileItem(path="/remote/proof.txt", name=name)

    assert storage._build_download_path(fileitem, tmp_path) is None




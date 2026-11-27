from unittest.mock import Mock

import pytest

from app.api.endpoints.storage import mkdir, rename
from app.schemas import FileItem


@pytest.mark.parametrize("name", ["../escape", "a/b", "a\\b", ".", "..", "bad\x00name"])
def test_mkdir_rejects_path_segments_instead_of_folder_names(monkeypatch, name):
    """新建目录名称必须是单个路径段，不能把用户输入当作层级路径创建。"""
    storage_chain = Mock()
    monkeypatch.setattr("app.api.endpoints.storage.StorageChain", lambda: storage_chain)

    response = mkdir(
        fileitem=FileItem(storage="local", type="dir", path="/downloads/", name="downloads"),
        name=name,
        _=object(),
    )

    assert response.success is False
    storage_chain.create_folder.assert_not_called()


@pytest.mark.parametrize("name", ["../escape", "a/b", "a\\b", ".", "..", "bad\x00name"])
def test_rename_rejects_path_segments_instead_of_file_names(monkeypatch, name):
    """重命名名称必须是单个路径段，不能把文件意外移动到其它目录。"""
    storage_chain = Mock()
    monkeypatch.setattr("app.api.endpoints.storage.StorageChain", lambda: storage_chain)

    response = rename(
        fileitem=FileItem(storage="local", type="file", path="/downloads/a.mkv", name="a.mkv"),
        new_name=name,
        recursive=False,
        _=object(),
    )

    assert response.success is False
    storage_chain.rename_file.assert_not_called()


def test_mkdir_accepts_unicode_single_segment_name(monkeypatch):
    """常规 Unicode 与空格目录名不应受单段名称校验影响。"""
    storage_chain = Mock()
    storage_chain.create_folder.return_value = object()
    monkeypatch.setattr("app.api.endpoints.storage.StorageChain", lambda: storage_chain)

    response = mkdir(
        fileitem=FileItem(storage="local", type="dir", path="/downloads/", name="downloads"),
        name="Season 01 全",
        _=object(),
    )

    assert response.success is True
    storage_chain.create_folder.assert_called_once()

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.modules.filemanager.storages import StorageBase
from app.modules.filemanager.storages.local import LocalStorage
from app.schemas.exception import StorageQueryError


def _local() -> LocalStorage:
    """
    构造本地存储实例（跳过初始化）。
    """
    return object.__new__(LocalStorage)








def test_local_strict_missing_file_returns_none(tmp_path):
    """
    目标文件确实不存在时应确认为不存在，允许正常整理。
    """
    assert _local().get_item_strict(tmp_path / "missing.mkv") is None


def test_local_strict_existing_file_returns_item(tmp_path):
    """
    目标文件存在时应返回文件项。
    """
    target = tmp_path / "movie.mkv"
    target.write_bytes(b"movie")

    item = _local().get_item_strict(target)

    assert item is not None
    assert item.path == target.as_posix()


def test_local_strict_broken_symlink_returns_none(tmp_path):
    """
    失效软链接视为目标不存在，不应阻断整理。
    """
    target = tmp_path / "movie.mkv"
    target.symlink_to(tmp_path / "gone.mkv")

    assert _local().get_item_strict(target) is None


def test_local_strict_raises_on_stat_error(tmp_path, monkeypatch):
    """
    FUSE 挂载抖动导致 stat 失败时应抛出 StorageQueryError，拒绝覆盖。
    """
    target = tmp_path / "movie.mkv"

    def raise_stat_error(self, *args, **kwargs):
        """
        模拟 CloudDrive FUSE 挂载返回 ENOTRECOVERABLE。
        """
        raise OSError(131, "State not recoverable")

    monkeypatch.setattr(Path, "stat", raise_stat_error)

    with pytest.raises(StorageQueryError):
        _local().get_item_strict(target)
























def test_storage_base_strict_defaults_to_get_item():
    """
    未覆写的存储沿用 get_item 判定，行为不变。
    """
    storage = object.__new__(LocalStorage)
    storage.get_item = MagicMock(return_value=None)

    assert StorageBase.get_item_strict(storage, Path("/movie.mkv")) is None
    storage.get_item.assert_called_once()

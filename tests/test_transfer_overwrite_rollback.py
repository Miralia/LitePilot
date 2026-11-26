"""同名覆盖传输失败时的原文件保护测试。"""

from pathlib import Path
from types import SimpleNamespace

from app.core.context import MediaInfo
from app.modules.filemanager.storages.local import LocalStorage
from app.modules.filemanager.transhandler import TransHandler
from app.schemas import FileItem, TransferInfo
from app.schemas.types import MediaType


def _file_item(path: Path) -> FileItem:
    """构造本地文件项。"""
    return FileItem(
        storage="local",
        path=path.as_posix(),
        type="file",
        name=path.name,
        basename=path.stem,
        extension=path.suffix.removeprefix("."),
        size=path.stat().st_size if path.exists() else None,
    )


class LocalTargetOper:
    """用真实临时目录模拟本地目标存储的 rename/delete 边界。"""

    @staticmethod
    def get_item(path: Path):
        """读取存在的本地文件。"""
        if not path.exists() and not path.is_symlink():
            return None
        return _file_item(path)

    @staticmethod
    def rename(fileitem: FileItem, name: str) -> bool:
        """在同一目录内重命名文件。"""
        path = Path(fileitem.path)
        path.rename(path.parent / name)
        return True

    @staticmethod
    def delete(fileitem: FileItem) -> bool:
        """删除本地文件。"""
        Path(fileitem.path).unlink(missing_ok=True)
        return True


def _invoke_transfer(monkeypatch, tmp_path: Path, transfer_command) -> tuple[FileItem | None, str, Path]:
    """调用私有单文件传输边界。"""
    source = tmp_path / "source.mkv"
    source.write_bytes(b"new source")
    target = tmp_path / "target.mkv"
    target.write_bytes(b"old target")
    monkeypatch.setattr(TransHandler, "_TransHandler__transfer_command", transfer_command)

    return TransHandler()._TransHandler__transfer_file(  # pylint: disable=protected-access
        fileitem=_file_item(source),
        meta=None,
        mediainfo=MediaInfo(type=MediaType.MOVIE, title="Test", year="2026", tmdb_id=1),
        source_oper=SimpleNamespace(),
        target_oper=LocalTargetOper(),
        target_storage="local",
        target_file=target,
        transfer_type="copy",
        result=TransferInfo(),
        over_flag=True,
    ), target


def test_failed_overwrite_restores_original_target(monkeypatch, tmp_path) -> None:
    """覆盖传输失败时不得留下半截新文件或丢失原文件。"""

    def failing_transfer(self, **kwargs):
        target_file = kwargs["target_file"]
        target_file.write_bytes(b"partial new")
        return None, "simulated copy failure"

    (new_item, errmsg), target = _invoke_transfer(monkeypatch, tmp_path, failing_transfer)

    assert new_item is None
    assert "simulated copy failure" in errmsg
    assert target.read_bytes() == b"old target"
    assert not list(tmp_path.glob(f".{target.name}.overwrite-*"))


def test_successful_overwrite_removes_backup_and_uses_new_target(monkeypatch, tmp_path) -> None:
    """覆盖成功后删除临时备份，目标路径使用新内容。"""

    def successful_transfer(self, **kwargs):
        target_file = kwargs["target_file"]
        target_file.write_bytes(b"new target")
        return _file_item(target_file), ""

    (new_item, errmsg), target = _invoke_transfer(monkeypatch, tmp_path, successful_transfer)

    assert new_item is not None
    assert errmsg == ""
    assert target.read_bytes() == b"new target"
    assert not list(tmp_path.glob(f".{target.name}.overwrite-*"))


def test_broken_symlink_overwrite_is_replaced_after_successful_transfer(monkeypatch, tmp_path) -> None:
    """失效软链仍占用目标文件名，覆盖成功后必须替换为新媒体文件。"""
    source = tmp_path / "source.mkv"
    source.write_bytes(b"new source")
    target = tmp_path / "target.mkv"
    target.symlink_to(tmp_path / "missing-target.mkv")
    storage = object.__new__(LocalStorage)

    def successful_transfer(self, **kwargs):
        kwargs["target_file"].write_bytes(b"new target")
        return _file_item(kwargs["target_file"]), ""

    monkeypatch.setattr(TransHandler, "_TransHandler__transfer_command", successful_transfer)

    new_item, errmsg = TransHandler()._TransHandler__transfer_file(  # pylint: disable=protected-access
        fileitem=_file_item(source),
        meta=None,
        mediainfo=MediaInfo(type=MediaType.MOVIE, title="Test", year="2026", tmdb_id=1),
        source_oper=SimpleNamespace(),
        target_oper=storage,
        target_storage="local",
        target_file=target,
        transfer_type="copy",
        result=TransferInfo(),
        over_flag=True,
    )

    assert new_item is not None
    assert errmsg == ""
    assert not target.is_symlink()
    assert target.read_bytes() == b"new target"
    assert not list(tmp_path.glob(f".{target.name}.overwrite-*"))

"""本地软链接目标的覆盖模式测试。"""

from types import SimpleNamespace

from app.core.context import MediaInfo
from app.core.meta import MetaBase
from app.modules.filemanager.storages.local import LocalStorage
from app.modules.filemanager.transhandler import TransHandler
from app.schemas import FileItem
from app.schemas.types import MediaType


def test_valid_relative_symlink_does_not_bypass_never_overwrite(tmp_path, monkeypatch) -> None:
    """相对软链目标必须按链接所在目录解析，有效目标在 never 模式下不得被覆盖。"""
    library = tmp_path / "library"
    library.mkdir()
    (library / "actual.mkv").write_bytes(b"old target")
    link = library / "movie.mkv"
    link.symlink_to("actual.mkv")

    source = tmp_path / "movie.mkv"
    source.write_bytes(b"new source")
    fileitem = FileItem(
        storage="local",
        path=source.as_posix(),
        type="file",
        name=source.name,
        basename=source.stem,
        extension="mkv",
        size=source.stat().st_size,
    )
    meta = MetaBase(source.name)
    meta.type = MediaType.MOVIE
    meta.name = "Test"
    meta.year = "2026"
    transfer_calls = []

    def transfer_file(self, **kwargs):
        transfer_calls.append(kwargs["target_file"])
        return FileItem(
            storage="local",
            path=kwargs["target_file"].as_posix(),
            type="file",
            name=kwargs["target_file"].name,
            basename=kwargs["target_file"].stem,
            extension="mkv",
        ), ""

    monkeypatch.setattr(TransHandler, "_TransHandler__transfer_file", transfer_file)

    result = TransHandler().transfer_media(
        fileitem=fileitem,
        in_meta=meta,
        mediainfo=MediaInfo(type=MediaType.MOVIE, title="Test", year="2026", tmdb_id=1),
        target_storage="local",
        target_path=library,
        transfer_type="copy",
        source_oper=SimpleNamespace(),
        target_oper=object.__new__(LocalStorage),
        need_rename=False,
        need_notify=False,
        need_scrape=False,
        overwrite_mode="never",
    )

    assert result.success is False
    assert "不覆盖" in result.message
    assert transfer_calls == []
    assert link.is_symlink()

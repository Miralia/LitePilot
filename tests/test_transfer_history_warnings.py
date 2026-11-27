from types import SimpleNamespace

from app.core.context import MediaInfo
from app.core.meta import MetaBase
from app.db.transferhistory_oper import TransferHistoryOper
from app.schemas import FileItem, TransferInfo
from app.schemas.types import MediaType


def test_success_history_preserves_partial_completion_warning(monkeypatch):
    """成功入库但源清理失败时，历史记录必须保留部分完成警告。"""
    captured = {}
    oper = object.__new__(TransferHistoryOper)

    def add_force(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(**kwargs)

    monkeypatch.setattr(oper, "add_force", add_force)
    source = FileItem(storage="smb", path="/downloads/example.mkv", type="file", name="example.mkv")
    target = FileItem(storage="local", path="/library/example.mkv", type="file", name="example.mkv")
    meta = MetaBase("example.mkv")
    mediainfo = MediaInfo(type=MediaType.MOVIE, title="Example", year="2026", tmdb_id=1)
    transferinfo = TransferInfo(
        success=True,
        target_item=target,
        transfer_type="move",
        message="源文件删除失败，移动未完全完成",
        file_list=[source.path],
    )

    oper.add_success(
        fileitem=source,
        mode="move",
        meta=meta,
        mediainfo=mediainfo,
        transferinfo=transferinfo,
    )

    assert captured["errmsg"] == transferinfo.message


def test_success_history_preserves_episode_group(monkeypatch):
    """成功历史必须保留剧集组，否则重新整理会回退到默认集数映射。"""
    captured = {}
    oper = object.__new__(TransferHistoryOper)

    def add_force(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(**kwargs)

    monkeypatch.setattr(oper, "add_force", add_force)
    source = FileItem(storage="local", path="/downloads/example.mkv", type="file", name="example.mkv")
    target = FileItem(storage="local", path="/library/example.mkv", type="file", name="example.mkv")
    meta = MetaBase("example.mkv")
    mediainfo = MediaInfo(
        type=MediaType.TV,
        title="Example",
        year="2026",
        tmdb_id=1,
        episode_group="group-id",
    )
    transferinfo = TransferInfo(
        success=True,
        target_item=target,
        transfer_type="copy",
        file_list=[source.path],
    )

    oper.add_success(
        fileitem=source,
        mode="copy",
        meta=meta,
        mediainfo=mediainfo,
        transferinfo=transferinfo,
    )

    assert captured["episode_group"] == "group-id"

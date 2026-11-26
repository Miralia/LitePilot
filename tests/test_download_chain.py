from types import SimpleNamespace

import app.chain.download as download_module
from app.chain.download import DownloadChain
from app.core.context import MediaInfo
from app.schemas import DownloaderTorrent
from app.schemas.types import MediaType, MessageChannel


def test_remote_downloading_does_not_link_removed_downloading_page(monkeypatch):
    """Telegram 下载状态消息不应再指向已删除的 downloading 页面。"""
    chain = DownloadChain.__new__(DownloadChain)
    monkeypatch.setattr(chain, "list_torrents", lambda **_kwargs: [])
    notifications = []
    monkeypatch.setattr(chain, "post_message", lambda notification: notifications.append(notification))

    chain.remote_downloading(channel=MessageChannel.Telegram, userid="10001", source="telegram-test")

    assert len(notifications) == 1
    assert notifications[0].title == "没有正在下载的任务！"
    assert notifications[0].link is None


def test_get_no_exists_info_returns_missing_movie_without_database_write(monkeypatch):
    """电影缺失检查只查询媒体库状态，不依赖已移除的下载候选链。"""
    chain = DownloadChain.__new__(DownloadChain)
    media = MediaInfo(type=MediaType.MOVIE, title="示例电影", year="2024", tmdb_id=1001)
    monkeypatch.setattr(
        download_module,
        "MediaServerOper",
        lambda: SimpleNamespace(get_item_id=lambda **_kwargs: "emby-item-id"),
    )
    monkeypatch.setattr(chain, "media_exists", lambda **_kwargs: None)

    exists, no_exists = chain.get_no_exists_info(meta=SimpleNamespace(), mediainfo=media)

    assert exists is False
    assert no_exists == {}


def test_download_file_deleted_removes_torrent_but_keeps_files(monkeypatch):
    """源文件被删除时只移除下载任务，不级联删除下载器内剩余文件。"""
    chain = DownloadChain.__new__(DownloadChain)
    torrent = DownloaderTorrent(hash="download-hash", title="Demo.Release")
    remove_calls = []
    monkeypatch.setattr(chain, "list_torrents", lambda **_kwargs: [torrent])
    monkeypatch.setattr(
        chain,
        "remove_torrents",
        lambda **kwargs: remove_calls.append(kwargs) or True,
    )

    chain.download_file_deleted(SimpleNamespace(event_data={"hash": "download-hash"}))

    assert remove_calls == [{"hashs": ["download-hash"], "delete_file": False}]

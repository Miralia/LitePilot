from types import SimpleNamespace

import app.chain.download as download_module
from app.chain.download import DownloadChain
from app.core.context import MediaInfo
from app.schemas import DownloaderTorrent
from app.schemas.types import MediaType, MessageChannel


def test_downloading_includes_media_type_and_source_site(monkeypatch):
    """
    正在下载任务应从下载历史回填媒体类型和来源站点。
    """
    torrent = DownloaderTorrent(hash="download-hash", title="Demo.Release")
    history = SimpleNamespace(
        episodes="E02",
        image="https://images.example.com/backdrop.jpg",
        poster="https://images.example.com/poster.jpg",
        seasons="S01",
        title="示例剧集",
        tmdbid=1001,
        torrent_site="示例站点",
        type="电视剧",
        userid="user-1",
        username="tester",
    )
    chain = DownloadChain.__new__(DownloadChain)
    monkeypatch.setattr(chain, "list_torrents", lambda **_kwargs: [torrent])
    monkeypatch.setattr(
        download_module,
        "DownloadHistoryOper",
        lambda: SimpleNamespace(get_by_hashes=lambda _hashes: {torrent.hash: history}),
    )

    result = chain.downloading(name="qb-main")

    assert result == [torrent]
    assert torrent.media["type"] == "电视剧"
    assert torrent.media["image"] == "https://images.example.com/poster.jpg"
    assert torrent.media["poster"] == "https://images.example.com/poster.jpg"
    assert torrent.media["backdrop"] == "https://images.example.com/backdrop.jpg"
    assert torrent.site_name == "示例站点"
    assert torrent.userid == "user-1"
    assert torrent.username == "tester"


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

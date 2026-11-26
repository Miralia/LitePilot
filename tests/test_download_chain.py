from types import SimpleNamespace

from app.chain.download import DownloadChain
from app.schemas import DownloaderTorrent
from app.schemas.types import MessageChannel


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

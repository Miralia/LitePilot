"""下载器任务 schema 边界测试。"""

from app.schemas import DownloaderTorrent


def test_downloader_torrent_drops_unproduced_trackers_field():
    """qBittorrent 统一任务没有 trackers 生产者，不保留永远为空的上游字段。"""
    assert "trackers" not in DownloaderTorrent.model_fields

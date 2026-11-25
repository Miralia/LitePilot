"""下载能力边界回归测试。"""
import importlib.util

import app.core.context as core_context
import app.schemas.context as schema_context
from app.chain import ChainBase
from app.chain.download import DownloadChain
from app.modules.qbittorrent import QbittorrentModule
from app.modules.telegram import TelegramModule
from app.modules.qbittorrent.qbittorrent import Qbittorrent
from app.schemas.types import EventType, SystemConfigKey


def test_torrent_addition_and_subscription_batch_interfaces_are_removed():
    """项目只消费下载器已有任务，不暴露站点搜索、添加下载或订阅批量择优接口。"""
    for chain_method in (
        "download",
        "download_added",
        "search_torrents",
        "async_search_torrents",
        "refresh_torrents",
        "async_refresh_torrents",
        "filter_torrents",
        "search_subtitles",
        "async_search_subtitles",
        "get_search_page_size",
    ):
        assert not hasattr(ChainBase, chain_method)

    for download_method in ("download_torrent", "download_single", "batch_download", "download_subtitle"):
        assert not hasattr(DownloadChain, download_method)

    assert not hasattr(QbittorrentModule, "download")
    assert not hasattr(TelegramModule, "post_medias_message")
    assert not hasattr(TelegramModule, "post_torrents_message")
    assert not hasattr(Qbittorrent, "add_torrent")
    assert importlib.util.find_spec("app.helper.torrent") is None
    assert not hasattr(core_context, "TorrentInfo")
    assert not hasattr(core_context, "SubtitleInfo")
    assert not hasattr(schema_context, "TorrentInfo")
    assert not hasattr(schema_context, "SubtitleInfo")
    assert "torrent_info" not in schema_context.Context.model_fields


def test_download_lifecycle_events_match_supported_downloader_scope():
    """下载事件只保留整理链仍使用的源文件删除通知。"""
    assert not hasattr(EventType, "DownloadAdded")
    assert not hasattr(EventType, "DownloadDeleted")
    assert hasattr(EventType, "DownloadFileDeleted")
    assert not hasattr(SystemConfigKey, "TorrentsPriority")

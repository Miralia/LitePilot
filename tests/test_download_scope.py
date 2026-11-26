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


def test_removed_downloading_page_enrichment_stays_removed():
    """已删除的 downloading 页面不再保留历史站点/用户回填链和空壳模型。"""
    from app import schemas

    assert not hasattr(DownloadChain, "downloading")
    assert not hasattr(schemas, "TransferTorrent")
    assert not hasattr(schemas, "DownloadingTorrent")
    for field in ("site_name", "media", "userid", "username"):
        assert field not in schemas.DownloaderTorrent.model_fields


def test_download_history_management_surface_is_removed():
    """下载历史只服务整理与删种联动，不保留无入口的管理 API 和列表搜索查询层。"""
    from app import schemas
    from app.api.endpoints import history as history_endpoint
    from app.db.downloadhistory_oper import DownloadHistoryOper
    from app.db.models.downloadhistory import DownloadHistory

    routes = {(route.path, tuple(sorted(route.methods or ()))) for route in history_endpoint.router.routes}
    assert ("/download", ("GET",)) not in routes
    assert ("/download", ("DELETE",)) not in routes
    assert not hasattr(history_endpoint, "download_history")
    assert not hasattr(history_endpoint, "delete_download_history")
    assert "download_history" in schemas.TransferTask.model_fields

    for method in (
        "get_by_hashes",
        "get_by_mediaid",
        "list_by_page",
        "async_list_by_page",
        "async_list_by_title",
        "async_count",
        "async_count_by_title",
        "get_last_by",
        "list_by_user_date",
        "list_by_date",
        "list_by_type",
    ):
        assert not hasattr(DownloadHistory, method)

    for method in (
        "get_by_hashes",
        "get_by_mediaid",
        "truncate_files",
        "get_files_by_fullpath",
        "get_hash_by_fullpath",
        "list_by_page",
        "async_delete_history",
        "truncate",
        "get_last_by",
        "list_by_user_date",
        "list_by_date",
        "list_by_type",
        "delete_history",
        "delete_downloadfile",
    ):
        assert not hasattr(DownloadHistoryOper, method)

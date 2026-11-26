"""媒体库缺失探测能力边界测试。"""

from app import schemas
from app.api.endpoints import mediaserver as mediaserver_endpoint
from app.chain import ChainBase
from app.chain.download import DownloadChain
from app.core.config import settings
from app.db.mediaserver_oper import MediaServerOper
from app.db.models.mediaserver import MediaServerItem
from app.modules.emby import EmbyModule
from app.modules.filemanager import FileManagerModule


def test_subscription_missing_media_probe_apis_are_removed():
    """订阅能力移除后，不再保留查询媒体库缺失季集的 API 入口。"""
    routes = {route.path for route in mediaserver_endpoint.router.routes}
    assert "/exists" not in routes
    assert "/exists_remote" not in routes
    assert "/notexists" not in routes


def test_missing_media_probe_internals_are_removed():
    """缺失探测的内部扫描、schema 和配置不随订阅残留继续保留。"""
    assert not hasattr(DownloadChain, "get_no_exists_info")
    assert not hasattr(ChainBase, "media_exists")
    assert not hasattr(ChainBase, "media_files")
    assert not hasattr(FileManagerModule, "media_exists")
    assert not hasattr(FileManagerModule, "media_files")
    assert not hasattr(EmbyModule, "media_exists")
    assert not hasattr(schemas, "ExistMediaInfo")
    assert not hasattr(schemas, "NotExistMediaInfo")
    assert not hasattr(settings, "LOCAL_EXISTS_SEARCH")
    for method in ("exists", "async_exists", "get_item_id", "async_get_item_id"):
        assert not hasattr(MediaServerOper, method)
    for method in (
        "get_by_itemid",
        "async_get_by_itemid",
        "exist_by_tmdbid",
        "exists_by_title",
        "async_exist_by_tmdbid",
        "async_exists_by_title",
    ):
        assert not hasattr(MediaServerItem, method)

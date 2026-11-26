"""媒体服务器播放入口边界测试。"""

from app.api.apiv1 import api_router
from app.chain.mediaserver import MediaServerChain
from app.modules.emby import EmbyModule
from app.modules.emby.emby import Emby


def test_mediaserver_play_proxy_endpoint_is_removed():
    """前端直接使用媒体服务器条目 link，不再保留按 ID 探测播放地址的 API。"""
    paths = {route.path for route in api_router.routes}

    assert "/mediaserver/latest" in paths
    assert "/mediaserver/playing" in paths
    assert "/mediaserver/library" in paths
    assert "/mediaserver/play/{itemid:path}" not in paths


def test_play_url_proxy_chain_is_removed_but_emby_link_builder_stays():
    """只有 Emby 列表直链生成器需要保留，API 专用转发层不应存在。"""
    assert not hasattr(MediaServerChain, "get_play_url")
    assert not hasattr(EmbyModule, "mediaserver_play_url")
    assert hasattr(Emby, "get_play_url")

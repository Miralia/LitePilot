"""媒体服务器 Cookie 图片代理残留边界测试。"""

import inspect

from app import schemas
from app.api.endpoints import system as system_endpoint
from app.chain.mediaserver import MediaServerChain
from app.helper.image import ImageHelper


def test_media_server_schemas_drop_cookie_only_fields():
    """当前唯一 Emby 集成不使用 Cookie 图片鉴权，不保留飞牛时代字段。"""
    assert "use_cookies" not in schemas.MediaServerLibrary.model_fields
    assert "use_cookies" not in schemas.MediaServerPlayItem.model_fields


def test_image_proxy_drops_noop_cookie_parameter():
    """图片代理不保留没有任何模块生产者的 use_cookies 参数。"""
    assert "use_cookies" not in inspect.signature(system_endpoint.proxy_img).parameters
    for method in (
        system_endpoint.fetch_image,
        ImageHelper.fetch_image,
        ImageHelper.fetch_image_with_mime_type,
        ImageHelper.async_fetch_image,
        ImageHelper.async_fetch_image_with_mime_type,
    ):
        assert "cookies" not in inspect.signature(method).parameters


def test_unimplemented_media_server_cookie_chain_is_removed():
    """没有任何模块实现 mediaserver_image_cookies，不保留空调用链。"""
    assert not hasattr(MediaServerChain, "get_image_cookies")

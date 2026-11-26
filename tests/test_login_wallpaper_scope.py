"""登录壁纸接口与调用链边界测试。"""

from app.api.apiv1 import api_router
from app.chain.mediaserver import MediaServerChain
from app.chain.tmdb import TmdbChain
from app.helper.image import WallpaperHelper


def test_login_exposes_wallpaper_list_only():
    """登录页使用列表轮播，不再保留上游单张壁纸接口。"""
    paths = {route.path for route in api_router.routes}

    assert "/login/wallpapers" in paths
    assert "/login/wallpaper" not in paths


def test_wallpaper_helpers_keep_only_list_contract():
    """单张壁纸 helper 只服务已删除的上游端点，不应继续保留。"""
    assert hasattr(WallpaperHelper, "get_wallpapers")
    assert not hasattr(WallpaperHelper, "get_wallpaper")
    assert not hasattr(WallpaperHelper, "get_tmdb_wallpaper")
    assert not hasattr(WallpaperHelper, "get_bing_wallpaper")
    assert not hasattr(WallpaperHelper, "get_mediaserver_wallpaper")
    assert not hasattr(WallpaperHelper, "get_customize_wallpaper")
    assert not hasattr(TmdbChain, "get_random_wallpaper")
    assert not hasattr(MediaServerChain, "get_latest_wallpaper")

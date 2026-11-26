"""媒体查询 API 能力边界测试。"""

from app import schemas
from app.api.endpoints import media as media_endpoint


def test_unreferenced_season_probe_endpoints_are_removed():
    """无入口的季信息探测端点不应继续暴露独立的媒体查询面。"""
    routes = {route.path for route in media_endpoint.router.routes}
    assert "/seasons" not in routes
    assert "/group/seasons/{episode_group}" not in routes


def test_removed_season_probe_schema_is_not_retained():
    """季信息探测端点删除后，不保留仅服务该端点的响应 schema。"""
    assert not hasattr(schemas, "MediaSeason")

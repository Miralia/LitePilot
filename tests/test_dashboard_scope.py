"""仪表板能力边界测试。"""

from app import schemas
from app.api.endpoints import dashboard as dashboard_endpoint
from app.utils.system import SystemUtils


def test_unreferenced_process_enumeration_surface_is_removed():
    """无入口的进程枚举能力不应继续暴露在 API、schema 和系统工具中。"""
    routes = {route.path for route in dashboard_endpoint.router.routes}

    assert "/processes" not in routes
    assert not hasattr(schemas, "ProcessInfo")
    assert not hasattr(SystemUtils, "processes")

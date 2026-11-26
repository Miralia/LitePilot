"""用户接口边界测试。"""

from app.api.apiv1 import api_router
from app import schemas


def _routes() -> set[tuple[str, str]]:
    return {
        (method, route.path)
        for route in api_router.routes
        for method in getattr(route, "methods", set())
    }


def test_user_router_keeps_only_read_and_config_contracts():
    """用户身份由 swizzin 管理，API 不应再暴露本地用户资料或密码修改。"""
    routes = _routes()

    assert ("GET", "/user/current") in routes
    assert ("GET", "/user/config/{key}") in routes
    assert ("POST", "/user/config/{key}") in routes
    assert not any(method == "PUT" and path == "/user/" for method, path in routes)
    assert not hasattr(schemas, "UserUpdate")

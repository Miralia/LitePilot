"""用户接口边界测试。"""

from app.api.apiv1 import api_router
from app import schemas
from app.db.models.user import User
from app.db.user_oper import UserOper


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


def test_swizzin_scope_does_not_keep_local_user_management_operators():
    """账号增删与绑定账号查找由 swizzin 边界接管，本地不再保留上游管理操作。"""
    for name in (
        "get_by_id",
        "async_get_by_id",
        "delete_by_name",
        "async_delete_by_name",
        "delete_by_id",
        "async_delete_by_id",
        "update_otp_by_name",
    ):
        assert not hasattr(User, name)
    assert hasattr(User, "async_update_otp_by_name")

    for name in (
        "list",
        "async_get_by_name",
        "async_get_by_id",
        "get_permissions",
        "get_setting",
        "get_name",
    ):
        assert not hasattr(UserOper, name)

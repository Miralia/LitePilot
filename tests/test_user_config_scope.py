"""用户配置键能力边界测试。"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.endpoints import user as user_endpoint
from app.schemas.types import UserConfigKey


def test_user_config_keys_match_active_dashboard_contract() -> None:
    """用户配置是封闭 UI 契约，不应继续停留在旧 Dashboard 单键状态。"""
    assert {item.value for item in UserConfigKey} == {
        "Dashboard",
        "DashboardOrder",
        "DashboardGridLayout",
        "DashboardGridLayoutTablet",
        "DashboardGridLayoutMobile",
    }


def test_unknown_user_config_key_is_rejected(monkeypatch) -> None:
    """认证用户不能通过通配路径向用户配置表写入任意上游或拼错键。"""
    monkeypatch.setattr(user_endpoint, "UserConfigOper", lambda: object())
    current_user = SimpleNamespace(name="user")

    with pytest.raises(HTTPException) as exc_info:
        user_endpoint.get_config("UnexpectedPluginConfig", current_user)

    assert exc_info.value.status_code == 422


def test_active_user_config_keys_are_accepted(monkeypatch) -> None:
    """当前仪表盘使用的基础、排序和三类设备布局键仍可读写。"""
    written = []

    class FakeUserConfigOper:
        """记录用户配置读写的测试替身。"""

        def get(self, username: str, key: str):
            return {"username": username, "key": key}

        def set(self, username: str, key: str, value):
            written.append((username, key, value))

    monkeypatch.setattr(user_endpoint, "UserConfigOper", FakeUserConfigOper)
    current_user = SimpleNamespace(name="user")

    for key in (
        "Dashboard",
        "DashboardOrder",
        "DashboardGridLayout",
        "DashboardGridLayoutTablet",
        "DashboardGridLayoutMobile",
    ):
        response = user_endpoint.get_config(key, current_user)
        assert response.success is True
        user_endpoint.set_config(key, {"enabled": True}, current_user)

    assert len(written) == 5
    assert {item[1] for item in written} == {item.value for item in UserConfigKey}


def test_falsy_user_config_values_remain_persistent() -> None:
    """false、空对象与空数组是合法 JSON 配置值，不应被当成删除标记。"""
    from app.db.models.userconfig import UserConfig
    from app.db.userconfig_oper import UserConfigOper

    username = "user-config-scope-test"
    key = UserConfigKey.Dashboard.value
    oper = UserConfigOper()
    try:
        for value in (False, {}, []):
            oper.set(username, key, value)
            persisted = UserConfig.get_by_key(db=None, username=username, key=key)
            assert persisted is not None
            assert persisted.value == value

            reloaded = object.__new__(UserConfigOper)
            UserConfigOper.__init__(reloaded)
            assert reloaded.get(username, key) == value

        oper.set(username, key, None)
        assert UserConfig.get_by_key(db=None, username=username, key=key) is None
        assert oper.get(username, key) is None
    finally:
        oper.set(username, key, None)

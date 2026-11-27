"""系统配置 API 的值语义测试。"""
import asyncio
from types import SimpleNamespace

from app.api.endpoints import system as system_endpoint
from app.schemas.types import SystemConfigKey


def _run_set_setting(value):
    """执行系统配置写入并返回捕获结果。"""
    writes = []
    events = []

    class FakeSystemConfigOper:
        """捕获写入值的系统配置测试替身。"""

        async def async_set(self, key, value):
            """记录写入值并返回成功。"""
            writes.append((key, value))
            return True

    class FakeEventManager:
        """捕获配置变更事件的事件测试替身。"""

        async def async_send_event(self, etype, data):
            """记录事件。"""
            events.append((etype, data))

    original_oper = system_endpoint.SystemConfigOper
    original_eventmanager = system_endpoint.eventmanager
    system_endpoint.SystemConfigOper = FakeSystemConfigOper
    system_endpoint.eventmanager = FakeEventManager()
    try:
        response = asyncio.run(
            system_endpoint.set_setting(
                key=SystemConfigKey.CustomReleaseGroups.value,
                value=value,
                _=SimpleNamespace(),
            )
        )
    finally:
        system_endpoint.SystemConfigOper = original_oper
        system_endpoint.eventmanager = original_eventmanager
    return response, writes, events


def test_system_setting_api_preserves_falsy_list_items():
    """配置 API 不得过滤数组中合法的 JSON 假值。"""
    value = [0, False, "", "keep"]

    response, writes, events = _run_set_setting(value)

    assert response.success is True
    assert writes == [(SystemConfigKey.CustomReleaseGroups.value, value)]
    assert len(events) == 1


def test_system_setting_api_preserves_empty_list():
    """空数组是合法配置值，不得被改写成删除标记 None。"""
    response, writes, events = _run_set_setting([])

    assert response.success is True
    assert writes == [(SystemConfigKey.CustomReleaseGroups.value, [])]
    assert len(events) == 1

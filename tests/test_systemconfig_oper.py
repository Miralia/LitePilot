import pytest

from app.db.systemconfig_oper import SystemConfigOper
from app.schemas.types import SystemConfigKey


def test_falsy_system_config_values_remain_persistent() -> None:
    """false、空对象、空数组与 0 是合法 JSON 配置值，不应被当成删除标记。"""
    from app.db.models.systemconfig import SystemConfig

    key = SystemConfigKey.NotificationClearBefore
    oper = SystemConfigOper()
    original_value = oper.get(key)
    try:
        for value in (False, {}, [], 0):
            oper.set(key, value)
            persisted = SystemConfig.get_by_key(db=None, key=key.value)
            assert persisted is not None
            assert persisted.value == value

            reloaded = object.__new__(SystemConfigOper)
            SystemConfigOper.__init__(reloaded)
            assert reloaded.get(key) == value

        oper.set(key, None)
        oper.set(key, None)
        assert SystemConfig.get_by_key(db=None, key=key.value) is None
        assert oper.get(key) is None
        assert key.value not in oper.all()
    finally:
        oper.set(key, original_value)


@pytest.mark.asyncio
async def test_async_falsy_system_config_values_remain_persistent() -> None:
    """异步系统配置写入同样必须持久化合法 JSON 假值。"""
    from app.db.models.systemconfig import SystemConfig

    key = SystemConfigKey.NotificationClearBefore
    oper = SystemConfigOper()
    original_value = oper.get(key)
    try:
        for value in (False, {}, [], 0):
            await oper.async_set(key, value)
            persisted = await SystemConfig.async_get_by_key(db=None, key=key.value)
            assert persisted is not None
            assert persisted.value == value

            reloaded = object.__new__(SystemConfigOper)
            SystemConfigOper.__init__(reloaded)
            assert reloaded.get(key) == value

        await oper.async_set(key, None)
        await oper.async_set(key, None)
        assert await SystemConfig.async_get_by_key(db=None, key=key.value) is None
        assert oper.get(key) is None
        assert key.value not in oper.all()

        legacy_null_row = SystemConfig(key=key.value, value=None)
        await legacy_null_row.async_create(db=None)
        await oper.async_set(key, None)
        assert await SystemConfig.async_get_by_key(db=None, key=key.value) is None
    finally:
        await oper.async_set(key, original_value)

import asyncio
import pickle

import pytest

import app.core.security as security
from app.helper.message import TemplateHelper
from app.helper.redis import AsyncRedisHelper, RedisHelper, deserialize, serialize


def test_redis_serializer_roundtrips_bytes_without_pickle():
    """图片和文件缓存字节应使用显式 bytes 标记，而不是 pickle。"""
    payload = serialize(b"\xff\x00image")

    assert payload.startswith(b"BYTES\x00")
    assert deserialize(payload) == b"\xff\x00image"


def test_redis_serializer_roundtrips_json_values():
    """Redis JSON 序列化应保持活跃缓存使用的标量、列表和字典结构。"""
    value = {"title": "标题", "items": [1, True, None], "nested": {"ok": 2.5}}

    payload = serialize(value)

    assert payload.startswith(b"JSON\x00")
    assert deserialize(payload) == value


def test_redis_serializer_rejects_custom_objects():
    """Redis 缓存不得再通过 pickle 保存任意 Python 对象。"""
    with pytest.raises(TypeError, match="JSON"):
        serialize(object())


def test_redis_deserializer_never_executes_legacy_pickle(tmp_path):
    """旧 PICKLE 标记只能作为过期缓存失败关闭，不能反序列化执行。"""
    marker = tmp_path / "redis-pickle-executed"

    class EvilPayload:
        """构造仅在反序列化执行时才会创建标记文件的测试 payload。"""

        def __reduce__(self):
            import os
            return os.system, (f"touch {marker}",)

    payload = b"PICKLE\x00" + pickle.dumps({"evil": EvilPayload()})

    with pytest.raises(ValueError, match="pickle"):
        deserialize(payload)
    assert not marker.exists()


def test_superuser_payload_does_not_use_shared_redis_cache_decorator():
    """认证身份缓存不得把 TokenPayload 这类自定义对象写入共享 Redis。"""
    func = security.__dict__["__create_superuser_token_payload"]
    assert not hasattr(func, "__wrapped__")


def test_template_helper_dead_context_cache_removed():
    """没有消费者的模板上下文缓存不得继续把原始业务对象写入 Redis。"""
    assert not hasattr(TemplateHelper, "get_cache_context")
    assert not hasattr(TemplateHelper, "set_cache_context")


def test_redis_items_skip_and_delete_legacy_pickle_entry():
    """同步 Redis 遍历应隔离旧 pickle 键，不能中断后续有效缓存。"""
    legacy_key = b"region:test:key:legacy"
    valid_key = b"region:test:key:valid"
    values = {
        legacy_key: b"PICKLE\x00" + pickle.dumps({"legacy": True}),
        valid_key: serialize({"valid": True}),
    }
    deleted = []

    class FakeClient:
        """提供两个 Redis 键的最小同步替身。"""

        def scan_iter(self, pattern):
            assert pattern == "region:test:key:*"
            return iter([legacy_key, valid_key])

        def get(self, key):
            return values[key]

        def delete(self, key):
            deleted.append(key)

    helper = RedisHelper()
    helper.client = FakeClient()
    try:
        items = list(helper.items(region="test"))
    finally:
        helper.client = None

    assert items == [("valid", {"valid": True})]
    assert deleted == [legacy_key]


def test_async_redis_items_skip_and_delete_legacy_pickle_entry():
    """异步 Redis 遍历应与同步路径一样隔离旧 pickle 键。"""
    legacy_key = b"region:test:key:legacy"
    valid_key = b"region:test:key:valid"
    values = {
        legacy_key: b"PICKLE\x00" + pickle.dumps({"legacy": True}),
        valid_key: serialize({"valid": True}),
    }
    deleted = []

    class FakeAsyncClient:
        """提供两个 Redis 键的最小异步替身。"""

        async def scan_iter(self, pattern):
            assert pattern == "region:test:key:*"
            for key in (legacy_key, valid_key):
                yield key

        async def get(self, key):
            return values[key]

        async def delete(self, key):
            deleted.append(key)

    async def collect():
        helper = AsyncRedisHelper()
        helper.client = FakeAsyncClient()
        helper._loop = asyncio.get_running_loop()
        try:
            return [item async for item in helper.items(region="test")]
        finally:
            helper.client = None
            helper._loop = None

    assert asyncio.run(collect()) == [("valid", {"valid": True})]
    assert deleted == [legacy_key]

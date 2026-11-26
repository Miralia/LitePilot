import pickle

import pytest

import app.core.security as security
from app.helper.message import TemplateHelper
from app.helper.redis import deserialize, serialize


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

import json
import pickle

from app.chain import ChainBase


class _FileCacheStub:
    """记录 ChainBase 文件缓存读写的最小替身。"""

    def __init__(self, content: bytes = None):
        """使用预置内容初始化缓存替身。"""
        self.content = content

    def get(self, key: str):
        """返回预置缓存内容。"""
        return self.content

    def set(self, key: str, value: bytes):
        """记录缓存写入内容。"""
        self.content = value

    def delete(self, key: str):
        """清空缓存内容。"""
        self.content = None


def _build_chain(content: bytes = None) -> ChainBase:
    """构造绕过模块管理器初始化的链测试实例。"""
    chain = object.__new__(ChainBase)
    chain.filecache = _FileCacheStub(content)
    return chain


def test_chain_cache_save_and_load_use_json_payload():
    """ChainBase 缓存应使用 JSON 保存简单上下文，不再写入 pickle。"""
    chain = _build_chain()

    chain.save_cache({"channel": "Telegram", "userid": "user-1"}, "restart")

    assert json.loads(chain.filecache.content.decode("utf-8")) == {
        "channel": "Telegram",
        "userid": "user-1",
    }
    assert chain.load_cache("restart") == {"channel": "Telegram", "userid": "user-1"}


def test_chain_cache_migrates_legacy_simple_pickle_payload():
    """旧版简单 dict pickle 重启上下文仍应可读，避免丢失一次重启完成通知。"""
    chain = _build_chain(pickle.dumps({"channel": "Telegram", "userid": "user-1"}))

    assert chain.load_cache("restart") == {"channel": "Telegram", "userid": "user-1"}


def test_chain_cache_legacy_pickle_cannot_execute_payload(tmp_path):
    """旧版 pickle 迁移只允许 plain data，不得执行其中嵌入的恶意 reduce。"""
    marker = tmp_path / "chain-pickle-executed"

    class EvilPayload:
        """构造仅在反序列化执行时才会创建标记文件的测试 payload。"""

        def __reduce__(self):
            import os
            return os.system, (f"touch {marker}",)

    chain = _build_chain(pickle.dumps({"evil": EvilPayload()}))

    assert chain.load_cache("restart") is None
    assert not marker.exists()


def test_chain_cache_dead_async_interfaces_removed():
    """没有消费者的异步通用缓存接口不应继续保留 pickle 攻击面。"""
    assert not hasattr(ChainBase, "async_load_cache")
    assert not hasattr(ChainBase, "async_save_cache")
    assert not hasattr(ChainBase, "async_remove_cache")

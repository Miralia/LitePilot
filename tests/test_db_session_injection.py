"""数据库装饰器自动会话注入的参数保持测试。"""
import asyncio

import app.db as db_module


class _FakeSyncSession:
    """同步数据库会话测试替身。"""

    def __init__(self):
        self.closed = False

    def close(self):
        """记录关闭行为。"""
        self.closed = True


class _FakeAsyncSession:
    """异步数据库会话测试替身。"""

    def __init__(self):
        self.closed = False

    async def close(self):
        """记录关闭行为。"""
        self.closed = True


def test_db_query_created_session_preserves_business_args(monkeypatch):
    """省略数据库会话时，自动注入不得丢弃第一个业务参数。"""
    fake_session = _FakeSyncSession()
    monkeypatch.setattr(db_module, "ScopedSession", lambda: fake_session)

    class Dummy:
        """同步查询测试模型。"""

        @classmethod
        @db_module.db_query
        def read(cls, db, key):
            """返回注入会话与业务键。"""
            return db, key

    db, key = Dummy.read("business-key")

    assert db is fake_session
    assert key == "business-key"
    assert fake_session.closed is True


def test_db_query_replaces_explicit_none_db_placeholder(monkeypatch):
    """显式传入 None 占位时，应替换占位而不是额外插入参数。"""
    fake_session = _FakeSyncSession()
    monkeypatch.setattr(db_module, "ScopedSession", lambda: fake_session)

    class Dummy:
        """同步列表查询测试模型。"""

        @classmethod
        @db_module.db_query
        def list_all(cls, db):
            """返回注入会话。"""
            return db

    assert Dummy.list_all(None) is fake_session
    assert fake_session.closed is True


def test_async_db_query_created_session_preserves_business_args(monkeypatch):
    """异步查询省略会话时，自动注入不得丢弃第一个业务参数。"""
    fake_session = _FakeAsyncSession()
    monkeypatch.setattr(db_module, "AsyncSessionFactory", lambda: fake_session)

    class Dummy:
        """异步查询测试模型。"""

        @classmethod
        @db_module.async_db_query
        async def read(cls, db, key):
            """返回注入会话与业务键。"""
            return db, key

    async def run_read():
        """执行异步查询。"""
        return await Dummy.read("business-key")

    db, key = asyncio.run(run_read())

    assert db is fake_session
    assert key == "business-key"
    assert fake_session.closed is True


def test_async_db_query_replaces_explicit_none_db_placeholder(monkeypatch):
    """异步查询显式传入 None 占位时，应替换占位而不是额外插入参数。"""
    fake_session = _FakeAsyncSession()
    monkeypatch.setattr(db_module, "AsyncSessionFactory", lambda: fake_session)

    class Dummy:
        """异步列表查询测试模型。"""

        @classmethod
        @db_module.async_db_query
        async def list_all(cls, db):
            """返回注入会话。"""
            return db

    async def run_list():
        """执行异步列表查询。"""
        return await Dummy.list_all(None)

    assert asyncio.run(run_list()) is fake_session
    assert fake_session.closed is True

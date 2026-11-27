"""事件总线停止生命周期测试。"""

import asyncio
import threading
import time

from app.core.event import EventManager
from app.schemas.types import EventType


def make_isolated_manager() -> EventManager:
    """创建绕开进程级单例的事件管理器，避免影响全局测试环境。"""
    manager = object.__new__(EventManager)
    manager.__init__()
    return manager


def test_event_stop_wakes_idle_consumer_without_queue_timeout():
    """消费者阻塞等待事件时，停止信号必须立即唤醒线程。"""
    manager = make_isolated_manager()
    manager.start()
    time.sleep(0.05)

    started_at = time.monotonic()
    manager.stop()
    elapsed = time.monotonic() - started_at

    assert elapsed < 0.75


def test_event_consumer_restart_ignores_stop_sentinel_left_by_busy_generation(monkeypatch):
    """停止时正在派发的事件可能让哨兵滞留，下一代消费者不能因此退出。"""
    manager = make_isolated_manager()
    dispatch_started = threading.Event()
    allow_dispatch_return = threading.Event()

    def blocking_dispatch(_event):
        dispatch_started.set()
        allow_dispatch_return.wait(1)

    monkeypatch.setattr(manager, "_EventManager__dispatch_broadcast_event", blocking_dispatch)
    manager.start()
    manager.send_event(EventType.ConfigChanged)
    assert dispatch_started.wait(1)

    stop_thread = threading.Thread(target=manager.stop)
    stop_thread.start()
    allow_dispatch_return.set()
    stop_thread.join(1)
    assert not stop_thread.is_alive()

    manager.start()
    time.sleep(0.1)
    restarted_thread = manager._EventManager__consumer_threads[-1]

    assert restarted_thread.is_alive()
    manager.stop()


def test_async_handler_failure_to_schedule_does_not_kill_consumer(monkeypatch):
    """事件循环不可用只能丢弃该异步处理器调用，不能杀死事件消费者线程。"""
    from app.core.config import global_vars

    manager = make_isolated_manager()

    async def async_handler(_event):
        return None

    closed_loop = asyncio.new_event_loop()
    closed_loop.close()
    monkeypatch.setattr(global_vars, "CURRENT_EVENT_LOOP", closed_loop)
    manager.add_event_listener(EventType.ConfigChanged, async_handler)
    manager.start()
    consumer_thread = manager._EventManager__consumer_threads[-1]

    manager.send_event(EventType.ConfigChanged)
    consumer_thread.join(0.2)

    assert consumer_thread.is_alive()
    manager.stop()


def test_send_event_returns_queued_event_instance():
    """同步发送接口应按类型契约返回已创建的事件对象。"""
    manager = make_isolated_manager()

    event = manager.send_event(EventType.ConfigChanged, {"key": {"a"}}, priority=3)

    assert event is not None
    assert event.event_type is EventType.ConfigChanged
    assert event.event_data == {"key": {"a"}}
    assert event.priority == 3


def test_async_send_event_returns_queued_event_instance():
    """异步发送接口应按类型契约返回已创建的事件对象。"""
    manager = make_isolated_manager()

    event = asyncio.run(manager.async_send_event(EventType.ConfigChanged, {"key": {"a"}}, priority=4))

    assert event is not None
    assert event.event_type is EventType.ConfigChanged
    assert event.event_data == {"key": {"a"}}
    assert event.priority == 4

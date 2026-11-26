import threading
import time

from app.helper.message import MessageQueueManager, TemplateHelper, stop_message
from app.utils.singleton import SingletonClass


def test_message_queue_stop_wakes_idle_monitor(monkeypatch):
    """消息队列停止时应唤醒空闲监控线程，不等待完整检查周期"""
    monkeypatch.setattr(MessageQueueManager, "init_config", lambda self: None)
    manager = object.__new__(MessageQueueManager)
    manager.__init__(check_interval=10)

    started_at = time.monotonic()
    manager.stop()
    elapsed = time.monotonic() - started_at

    assert elapsed < 1
    assert not manager.thread.is_alive()


def test_message_queue_stop_is_bounded_when_send_callback_blocks(monkeypatch):
    """停止消息队列时不能因发送回调网络阻塞而无限等待。"""
    import app.helper.message as message_module

    monkeypatch.setattr(MessageQueueManager, "init_config", lambda self: None)
    monkeypatch.setattr(message_module, "_MESSAGE_QUEUE_STOP_TIMEOUT_SECONDS", 0.1, raising=False)
    send_started = threading.Event()
    release_send = threading.Event()

    def blocked_send(*_args, **_kwargs):
        """模拟进入网络发送后长时间无响应的消息渠道。"""
        send_started.set()
        release_send.wait(5)

    manager = object.__new__(MessageQueueManager)
    manager.__init__(send_callback=blocked_send, check_interval=0.05)
    manager.queue.put({"args": (), "kwargs": {}})
    assert send_started.wait(1)

    stop_thread = threading.Thread(target=manager.stop)
    try:
        stop_thread.start()
        stop_thread.join(0.5)
        assert not stop_thread.is_alive()
    finally:
        release_send.set()
        stop_thread.join(2)
        manager.thread.join(2)

    assert not stop_thread.is_alive()


def test_stop_message_does_not_initialize_absent_services(monkeypatch):
    """消息服务未初始化时，关闭入口不应为了清理而创建后台资源"""
    monkeypatch.setattr(SingletonClass, "_instances", {})

    assert MessageQueueManager.get_existing_instance() is None
    assert TemplateHelper.get_existing_instance() is None
    stop_message()

    assert MessageQueueManager not in SingletonClass._instances
    assert TemplateHelper not in SingletonClass._instances

import queue
import threading
import time

from app.chain.transfer import TransferChain
from app.core.config import GlobalVar


def test_stop_wakes_idle_transfer_worker_without_queue_timeout(monkeypatch):
    """空闲整理线程在停止时应立即唤醒，而不是等待完整队列轮询间隔。"""
    monkeypatch.setattr(GlobalVar, "STOP_EVENT", threading.Event())
    waiting_for_item = threading.Event()

    class ProbeQueue(queue.Queue):
        def get(self, *args, **kwargs):
            waiting_for_item.set()
            return super().get(*args, **kwargs)

    chain = object.__new__(TransferChain)
    chain._queue = ProbeQueue()
    chain.jobview = None
    chain._queue_active = True
    chain._transfer_interval = 1
    chain._threads = []
    worker = threading.Thread(target=chain._TransferChain__start_transfer, daemon=True)
    chain._threads.append(worker)
    worker.start()
    assert waiting_for_item.wait(1)

    started_at = time.monotonic()
    chain._TransferChain__stop()
    elapsed = time.monotonic() - started_at

    assert elapsed < 0.5
    assert not worker.is_alive()

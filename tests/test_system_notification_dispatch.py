import asyncio
from unittest.mock import patch

from app.chain.message import MessageChain
from app.helper.message import MessageQueueManager
from app.schemas import Notification
from app.utils.identity import (
    SYSTEM_INTERNAL_USER_ID,
    is_internal_user_id,
    normalize_internal_user_id,
)


def test_internal_userid_identity_helpers():
    assert is_internal_user_id(SYSTEM_INTERNAL_USER_ID)
    assert is_internal_user_id(" System ")
    assert normalize_internal_user_id(SYSTEM_INTERNAL_USER_ID) is None
    assert normalize_internal_user_id("10001") == "10001"


def test_post_message_normalizes_internal_userid_before_queueing():
    chain = MessageChain()
    message = Notification(
        userid=SYSTEM_INTERNAL_USER_ID,
        username="admin",
        title="后台报告",
        text="任务完成",
    )

    with patch("app.chain.MessageTemplateHelper.render", return_value=message), patch.object(
        chain.messagehelper, "put"
    ), patch.object(chain.messageoper, "add"), patch.object(
        chain.eventmanager, "send_event"
    ) as send_event, patch.object(
        chain.messagequeue, "send_message"
    ) as send_message:
        chain.post_message(message)

    queued_message = send_message.call_args.kwargs["message"]

    send_event.assert_not_called()
    assert queued_message.userid is None
    assert not send_message.call_args.kwargs["immediately"]


def test_async_send_message_uses_executor_for_immediate_send():
    """异步立即发送不能在事件循环里直接执行同步渠道回调。"""

    class _FakeLoop:
        def __init__(self):
            self.called = False

        async def run_in_executor(self, executor, func):
            self.called = True
            func()

    async def _run():
        manager = MessageQueueManager()
        fake_loop = _FakeLoop()
        with patch("asyncio.get_running_loop", return_value=fake_loop), patch.object(
            manager, "_send"
        ) as send:
            await manager.async_send_message("payload", immediately=True)
        assert fake_loop.called
        send.assert_called_once_with("payload")

    asyncio.run(_run())

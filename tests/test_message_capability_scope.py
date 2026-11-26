"""消息渠道能力抽象边界测试。"""

from unittest.mock import patch

from app import schemas
from app.chain.message import MessageChain
from app.schemas.types import MessageChannel


def test_upstream_channel_capability_matrix_is_removed():
    """当前仅 Telegram 支持交互能力，不保留无消费者的能力矩阵。"""
    assert not hasattr(schemas, "ChannelCapability")
    assert not hasattr(schemas, "ChannelCapabilities")
    assert not hasattr(schemas, "ChannelCapabilityManager")


def test_telegram_callback_still_dispatches():
    """裁剪能力矩阵后 Telegram 回调仍进入整理重试分发。"""
    chain = MessageChain()
    with patch.object(chain, "_handle_callback", return_value=True) as callback:
        result = chain._handle_message_core(
            channel=MessageChannel.Telegram,
            source="telegram-test",
            userid="10001",
            username="tester",
            text="CALLBACK:transfer_retry_12",
        )

    assert result is True
    callback.assert_called_once()


def test_web_callback_is_rejected_without_dispatch():
    """Web 通知中心没有回调交互，CALLBACK 文本不能被误当作 Telegram 回调。"""
    chain = MessageChain()
    with patch.object(chain, "_handle_callback", return_value=True) as callback:
        result = chain._handle_message_core(
            channel=MessageChannel.Web,
            source="web",
            userid="10001",
            username="tester",
            text="CALLBACK:transfer_retry_12",
        )

    assert result is False
    callback.assert_not_called()


def test_processing_status_only_runs_for_telegram():
    """处理状态裁剪后仍只对 Telegram 调用模块生命周期。"""
    chain = MessageChain()
    with patch.object(chain, "run_module", return_value={"channel": "Telegram"}) as run_module:
        assert chain.start_message_processing_status(
            channel=MessageChannel.Web,
            source="web",
            userid="10001",
        ) is None
        run_module.assert_not_called()

        status = chain.start_message_processing_status(
            channel=MessageChannel.Telegram,
            source="telegram-test",
            userid="10001",
        )

    assert status == {"channel": "Telegram"}
    run_module.assert_called_once_with(
        "mark_message_processing_started",
        channel=MessageChannel.Telegram,
        source="telegram-test",
        userid="10001",
        message_id=None,
        chat_id=None,
        text=None,
    )

"""消息链路死接口边界测试。"""

from app.chain.message import MessageChain
from app.modules.telegram import TelegramModule
from app.modules.telegram.telegram import Telegram
import app.schemas.message as message_schemas


def test_chain_does_not_keep_unused_message_management_interfaces():
    """没有生产消费者的删除、编辑、直发与收尾 chain 接口不应保留。"""
    for method_name in (
        "delete_message",
        "edit_message",
        "send_direct_message",
        "finalize_message",
    ):
        assert not hasattr(MessageChain, method_name)


def test_telegram_module_does_not_keep_unused_message_management_interfaces():
    """Telegram 模块只保留正常通知、回调与 typing 处理接口。"""
    for method_name in (
        "delete_message",
        "edit_message",
        "send_direct_message",
    ):
        assert not hasattr(TelegramModule, method_name)


def test_telegram_client_does_not_keep_dead_public_delete_edit_wrappers():
    """底层删除与公开编辑包装没有消费者；send_msg 内部编辑路径仍保留。"""
    assert not hasattr(Telegram, "delete_msg")
    assert not hasattr(Telegram, "edit_msg")
    assert hasattr(Telegram, "send_msg")


def test_message_response_schema_has_no_remaining_consumer():
    """直发消息接口删除后，不再保留只服务该接口的响应 schema。"""
    assert not hasattr(message_schemas, "MessageResponse")

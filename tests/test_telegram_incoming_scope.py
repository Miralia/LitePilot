# -*- coding: utf-8 -*-
"""Telegram 传入消息边界测试。"""

from app.modules.telegram import TelegramModule
from app.modules.telegram.telegram import Telegram
from app.schemas import CommingMessage


def test_comming_message_has_no_unconsumed_agent_payload_fields():
    """智能体时代的媒体、附件和原始回调载荷不得重新进入传入消息 schema。"""
    for field in (
        "date",
        "action",
        "is_callback",
        "callback_data",
        "reply_to_message_id",
        "callback_query",
        "images",
        "audio_refs",
        "files",
    ):
        assert field not in CommingMessage.model_fields
    assert not hasattr(CommingMessage, "MessageImage")
    assert not hasattr(CommingMessage, "MessageAttachment")


def test_telegram_has_no_dead_file_download_surface():
    """无消费者的 Telegram 文件下载桥接不得重新出现。"""
    assert not hasattr(TelegramModule, "download_telegram_file_to_base64")
    assert not hasattr(TelegramModule, "download_telegram_file_bytes")
    assert not hasattr(Telegram, "download_file")

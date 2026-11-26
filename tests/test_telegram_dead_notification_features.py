# -*- coding: utf-8 -*-
"""Telegram 死通知能力边界测试。"""

import inspect

from app.modules.telegram.telegram import Telegram
from app.schemas import Notification


def test_notification_has_no_unproduced_telegram_interaction_fields():
    """无生产者的 Telegram 交互覆盖字段不得重新进入通知 schema。"""
    for field in (
        "voice_path",
        "voice_caption",
        "file_path",
        "file_name",
        "force_reply",
        "original_message_id",
        "original_chat_id",
        "disable_web_page_preview",
        "parse_mode",
        "stop_typing",
    ):
        assert field not in Notification.model_fields


def test_telegram_client_has_no_dead_attachment_or_edit_surface():
    """无生产者的附件发送与通知编辑能力不得重新出现。"""
    assert not hasattr(Telegram, "send_voice")
    assert not hasattr(Telegram, "send_file")
    signature = inspect.signature(Telegram.send_msg)
    for parameter in (
        "force_reply",
        "original_message_id",
        "original_chat_id",
        "disable_web_page_preview",
        "parse_mode",
    ):
        assert parameter not in signature.parameters

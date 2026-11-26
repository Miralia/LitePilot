"""事件总线能力边界测试。"""

from app.schemas.types import EVENT_TYPE_NAMES, EventType


def test_event_types_are_limited_to_active_internal_consumers() -> None:
    """只保留同时具有生产者和消费者的内部协调事件。"""
    assert set(EventType.__members__) == {
        "CommandExcute",
        "DownloadFileDeleted",
        "WebhookMessage",
        "ChannelMessageReceived",
        "MetadataScrape",
        "ModuleReload",
        "ConfigChanged",
    }
    assert set(EVENT_TYPE_NAMES) == set(EventType)

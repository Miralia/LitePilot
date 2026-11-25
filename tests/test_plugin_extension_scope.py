"""插件扩展能力移除后的边界回归测试。"""
import sys
from types import ModuleType
from unittest.mock import patch

sys.modules.setdefault("qbittorrentapi", ModuleType("qbittorrentapi"))
setattr(sys.modules["qbittorrentapi"], "TorrentFilesList", list)
sys.modules.setdefault("transmission_rpc", ModuleType("transmission_rpc"))
setattr(sys.modules["transmission_rpc"], "File", object)

import app.schemas.event as event_schema
import app.schemas.types as type_schema
from app.chain.message import MessageChain
from app.schemas.types import MessageChannel


def test_chain_extension_types_are_removed():
    """同步链式扩展事件不再作为可调用边界暴露。"""
    assert not hasattr(type_schema, "ChainEventType")
    for name in (
        "ChainEventData",
        "CommandRegisterEventData",
        "TransferRenameBuildEventData",
        "TransferRenameEventData",
        "ResourceSelectionEventData",
        "ResourceDownloadEventData",
        "TransferInterceptEventData",
        "TransferOverwriteCheckEventData",
        "MediaRecognizeConvertEventData",
        "StorageOperSelectionEventData",
    ):
        assert not hasattr(event_schema, name)


def test_plain_message_does_not_emit_removed_user_message_event():
    """普通文本只记录消息，不再广播给已删除的插件扩展入口。"""
    chain = MessageChain()

    with patch.object(chain.eventmanager, "send_event") as send_event:
        chain._handle_message_core(
            channel=MessageChannel.Telegram,
            source="telegram-test",
            userid="10001",
            username="tester",
            text="普通文本",
        )

    send_event.assert_not_called()

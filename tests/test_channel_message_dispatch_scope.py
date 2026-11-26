"""渠道消息同进程分发边界测试。"""

from types import SimpleNamespace
from unittest.mock import patch

from app.api.apiv1 import api_router
from app.chain.message import MessageChain
from app.core.event import eventmanager
from app.schemas.types import EventType
from app.startup.modules_initializer import _load_event_chain_modules


def test_message_api_only_keeps_notification_center_contracts():
    """Telegram 同进程分发后，不再暴露上游通用用户消息 HTTP 入口。"""
    routes = {
        (method, route.path)
        for route in api_router.routes
        for method in getattr(route, "methods", set())
    }

    assert ("GET", "/message/notification") in routes
    assert ("DELETE", "/message/notification") in routes
    assert not any(method == "POST" and path in {"/message", "/message/"} for method, path in routes)


def test_channel_message_event_invokes_message_chain_process():
    """渠道消息事件应复用消息链现有 parser 与命令处理逻辑。"""
    chain = object.__new__(MessageChain)
    event = SimpleNamespace(
        event_data={
            "body": '{"message":{"text":"/version"}}',
            "form": None,
            "args": {"source": "telegram-test"},
        }
    )

    with patch.object(chain, "process") as process:
        chain.channel_message_event(event)

    process.assert_called_once_with(
        body='{"message":{"text":"/version"}}',
        form=None,
        args={"source": "telegram-test"},
    )


def test_channel_message_event_type_is_registered():
    """内部渠道消息事件应有明确类型，不恢复已删除的插件 UserMessage 语义。"""
    assert EventType.ChannelMessageReceived.value == "channel.message.received"


def test_channel_message_handler_is_registered():
    """消息链事件处理器应在模块导入后注册到广播事件总线。"""
    handlers = eventmanager.visualize_handlers()

    assert any(
        item["event_type"] == "channel.message.received"
        and item["handler_identifier"].endswith("MessageChain.channel_message_event")
        for item in handlers
    )


def test_startup_explicitly_loads_message_chain_event_module():
    """事件装饰器依赖模块导入，启动层必须显式加载消息链。"""
    with patch("app.startup.modules_initializer.importlib.import_module") as import_module:
        _load_event_chain_modules()

    loaded_modules = [call.args[0] for call in import_module.call_args_list]
    assert "app.chain.message" in loaded_modules

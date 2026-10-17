import pytest

from app.testing.bootstrap import ensure_optional_stub

ensure_optional_stub("qbittorrentapi", TorrentFilesList=list)
ensure_optional_stub("transmission_rpc", File=object)
ensure_optional_stub("psutil")
ensure_optional_stub("aioshutil")
ensure_optional_stub("pyquery", PyQuery=object)

from unittest.mock import patch

from app.chain.message import MessageChain
from app.chain.skills import skills_interaction_manager
from app.chain.subscribe import SubscribeChain, subscribe_interaction_manager
from app.schemas.types import MessageChannel


@pytest.fixture(autouse=True)
def _clear_interactions():
    """每个用例前后清空交互会话，避免用例间相互影响。"""
    skills_interaction_manager.clear()
    subscribe_interaction_manager.clear()
    yield
    skills_interaction_manager.clear()
    subscribe_interaction_manager.clear()


def test_message_routes_text_reply_to_latest_subscribes_interaction():
    """最新交互为订阅时，文本回复应交给订阅链处理。"""
    chain = MessageChain()
    skills_interaction_manager.create_or_replace(
        user_id="10001",
        channel=MessageChannel.Wechat,
        source="wechat-test",
        username="tester",
    )
    subscribe_interaction_manager.create_or_replace(
        user_id="10001",
        command="/subscribes",
        channel=MessageChannel.Wechat,
        source="wechat-test",
        username="tester",
    )

    with patch.object(chain, "_record_user_message"), patch(
        "app.chain.message.SubscribeChain.handle_text_interaction",
        return_value=True,
    ) as handle_subscribes, patch(
        "app.chain.message.SkillsChain.handle_text_interaction"
    ) as handle_skills:
        chain.handle_message(
            channel=MessageChannel.Wechat,
            source="wechat-test",
            userid="10001",
            username="tester",
            text="搜索 all",
        )

    handle_subscribes.assert_called_once()
    handle_skills.assert_not_called()


def test_callback_routes_to_subscribes_chain():
    """订阅交互会话的回调应路由到订阅链。"""
    chain = MessageChain()
    request = subscribe_interaction_manager.create_or_replace(
        user_id="10001",
        command="/subscribes",
        channel=MessageChannel.Telegram,
        source="telegram-test",
        username="tester",
    )

    with patch(
        "app.chain.message.SubscribeChain.handle_callback_interaction",
        return_value=True,
    ) as handle_callback:
        chain._handle_callback(
            text=f"CALLBACK:subscribes:{request.request_id}:refresh",
            channel=MessageChannel.Telegram,
            source="telegram-test",
            userid="10001",
            username="tester",
        )

    handle_callback.assert_called_once()


def test_subscribes_text_exit_skips_notification_history():
    """订阅交互退出提示不应写入通知历史。"""
    chain = SubscribeChain()
    subscribe_interaction_manager.create_or_replace(
        user_id="10001",
        command="/subscribes",
        channel=MessageChannel.Telegram,
        source="telegram-test",
        username="tester",
    )

    with patch.object(chain, "post_message") as post_message:
        handled = chain.handle_text_interaction(
            channel=MessageChannel.Telegram,
            source="telegram-test",
            userid="10001",
            username="tester",
            text="退出",
        )

    assert handled is True
    notification = post_message.call_args.args[0]
    assert notification.title == "订阅交互已结束"
    assert notification.save_history is False
    assert subscribe_interaction_manager.get_by_user("10001") is None

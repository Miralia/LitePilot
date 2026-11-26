from unittest.mock import patch

from app.chain.message import MessageChain
from app.chain.transfer import TransferChain
from app.schemas.types import MessageChannel


def test_build_failed_transfer_buttons():
    buttons = TransferChain.build_failed_transfer_buttons(12)

    assert buttons == [
        [
            {"text": "重试", "callback_data": "transfer_retry_12"},
        ]
    ]


def test_remote_transfer_supports_history_only_retry():
    chain = TransferChain()

    with patch.object(chain, "redo_transfer_history", return_value=(True, "")) as redo:
        with patch.object(chain, "post_message") as post_message:
            chain.remote_transfer(
                "12",
                channel=MessageChannel.Telegram,
                userid="10001",
                source="telegram-test",
            )

    redo.assert_called_once_with(12)
    post_message.assert_not_called()


def test_transfer_retry_callback_retries_history():
    chain = MessageChain()

    with patch("app.chain.message.TransferChain") as transfer_cls:
        transfer_cls.return_value.redo_transfer_history.return_value = (True, "")
        with patch.object(chain, "post_message") as post_message:
            chain._handle_callback(
                text="CALLBACK:transfer_retry_12",
                channel=MessageChannel.Telegram,
                source="telegram-test",
                userid="10001",
                username="tester",
            )

    transfer_cls.return_value.redo_transfer_history.assert_called_once_with(12)
    assert post_message.call_count == 2
    assert post_message.call_args_list[0].args[0].title == "开始重新整理记录 #12 ..."
    assert post_message.call_args_list[1].args[0].title == "整理记录 #12 已重新整理"

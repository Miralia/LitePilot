"""原生 systemd 部署的重启能力边界。"""

from unittest.mock import MagicMock

import pytest

from app.chain.system import SystemChain
from app.helper.system import SystemHelper
from app.schemas.types import MessageChannel


def test_systemd_unit_name_is_parsed_from_cgroup():
    """systemd v2 cgroup 中的叶服务单元必须可识别。"""
    cgroup = "0::/system.slice/litepilot.service\n"

    assert SystemHelper._parse_systemd_unit_name(cgroup) == "litepilot.service"


def test_systemd_service_can_restart_when_not_cli_managed(monkeypatch):
    """原生 systemd 服务不是 CLI 管理进程，但仍应支持受控重启。"""
    monkeypatch.setattr(SystemHelper, "_is_local_cli_managed", lambda: False)
    monkeypatch.setattr(SystemHelper, "_systemd_unit_name", lambda: "litepilot.service", raising=False)

    assert SystemHelper.can_restart() is True


def test_systemd_restart_uses_no_block_helper_without_self_kill(monkeypatch):
    """systemd 重启应排队外部重启任务，不能先杀死当前进程导致响应丢失。"""
    spawned = []
    kill = MagicMock()
    monkeypatch.setattr(SystemHelper, "_is_local_cli_managed", lambda: False)
    monkeypatch.setattr(SystemHelper, "_systemd_unit_name", lambda: "litepilot.service", raising=False)
    monkeypatch.setattr(
        SystemHelper,
        "_spawn_systemd_restart_helper",
        lambda unit: spawned.append(unit),
        raising=False,
    )
    monkeypatch.setattr("app.helper.system.os.kill", kill)

    assert SystemHelper.restart() == (True, "")
    assert spawned == ["litepilot.service"]
    kill.assert_not_called()


def test_systemd_restart_helper_uses_standard_no_block_argument_order(monkeypatch):
    """重启 helper 必须以标准 systemctl 参数顺序排队任务。"""
    captured = []
    monkeypatch.setattr(
        SystemHelper,
        "_spawn_restart_helper_process",
        lambda code, description: captured.append((code, description)),
    )

    SystemHelper._spawn_systemd_restart_helper("litepilot.service")

    [(helper_code, _description)] = captured
    assert "'systemctl', '--no-block', 'restart', \"litepilot.service\"" in helper_code
    assert "shell" not in helper_code


@pytest.mark.parametrize(
    "payload",
    [
        False,
        [],
        [1],
        "not-json",
        {},
        {"channel": "Telegram"},
        {"userid": "user-1"},
        {"channel": "Missing", "userid": "user-1"},
        {"channel": "Telegram", "userid": ""},
        {"channel": "Telegram", "userid": {}},
        {"channel": "Telegram", "userid": 1.5},
    ],
)
def test_restart_finish_discards_structurally_invalid_receipt(monkeypatch, payload):
    """无法定位有效接收人的重启收据必须清除，不能每次启动重复失败或误投递。"""
    chain = object.__new__(SystemChain)
    post_message = MagicMock()
    remove_cache = MagicMock()
    chain.load_cache = lambda _filename: payload
    chain.post_message = post_message
    chain.remove_cache = remove_cache

    chain.restart_finish()

    post_message.assert_not_called()
    remove_cache.assert_called_once_with("__system_restart__")


def test_restart_finish_keeps_valid_receipt_when_notification_fails(monkeypatch):
    """结构有效但通知发送失败时保留收据，维持下次启动重试的既有语义。"""
    chain = object.__new__(SystemChain)
    remove_cache = MagicMock()
    chain.load_cache = lambda _filename: {"channel": "Telegram", "userid": "user-1"}
    chain.post_message = MagicMock(side_effect=RuntimeError("notification down"))
    chain.remove_cache = remove_cache

    chain.restart_finish()

    remove_cache.assert_not_called()


def test_command_restart_failure_retracts_receipt_and_notifies(monkeypatch):
    """底层重启失败时必须撤回完成通知收据，并明确告知用户重启失败。"""
    monkeypatch.setattr(SystemHelper, "can_restart", MagicMock(return_value=True))
    monkeypatch.setattr(
        SystemHelper,
        "restart",
        MagicMock(return_value=(False, "restart failed")),
    )
    chain = object.__new__(SystemChain)
    notifications = []
    remove_cache = MagicMock()
    chain.post_message = notifications.append
    chain.save_cache = MagicMock()
    chain.remove_cache = remove_cache

    chain.restart(channel=MessageChannel.Telegram, userid="user-1")

    remove_cache.assert_called_once_with("__system_restart__")
    assert any("重启失败" in notification.title for notification in notifications)

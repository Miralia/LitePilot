"""原生 systemd 部署的重启能力边界。"""

from unittest.mock import MagicMock

from app.helper.system import SystemHelper


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

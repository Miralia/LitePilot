"""CLI 对原生 systemd 部署的重启委托契约。"""

from types import SimpleNamespace

from click.testing import CliRunner

from tests.test_cli_auto_update import load_cli_module


def test_owned_systemd_unit_requires_current_install_root(tmp_path, monkeypatch):
    """只有 WorkingDirectory 指向当前仓库且执行 app.main 的 system unit 才能被委托。"""
    module = load_cli_module()
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(module.settings, "ROOT_PATH", root)
    monkeypatch.setattr(module.shutil, "which", lambda command: "/usr/bin/systemctl" if command == "systemctl" else None)

    values = {
        "LoadState": "loaded",
        "WorkingDirectory": str(root),
        "ExecStart": "{ path=/opt/moviepilot/venv/bin/python ; argv[]=/opt/moviepilot/venv/bin/python -m app.main ; ignore_errors=no }",
    }

    def fake_run(command, **kwargs):
        prop = command[command.index("-p") + 1]
        return SimpleNamespace(returncode=0, stdout=values[prop] + "\n", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module._systemd_unit_for_current_install() == "litepilot.service"

    values["WorkingDirectory"] = str(tmp_path / "other")
    assert module._systemd_unit_for_current_install() is None

    values["WorkingDirectory"] = str(root)
    values["ExecStart"] = "{ path=/usr/bin/python ; argv[]=/usr/bin/python -m other.main ; ignore_errors=no }"
    assert module._systemd_unit_for_current_install() is None


def test_restart_delegates_owned_systemd_unit_instead_of_local_process_control(monkeypatch):
    """原生 systemd 部署执行 CLI restart 时应委托 systemctl，不得误启动第二个本地后端。"""
    module = load_cli_module()
    restarted = []
    monkeypatch.setattr(module, "_systemd_unit_for_current_install", lambda: "litepilot.service", raising=False)
    monkeypatch.setattr(
        module,
        "_restart_systemd_service",
        lambda unit_name, timeout: restarted.append((unit_name, timeout)),
        raising=False,
    )

    def forbidden_local_control(**kwargs):
        raise AssertionError("systemd 实例不得进入本地进程停启路径")

    monkeypatch.setattr(module, "_stop_frontend_service", forbidden_local_control)
    monkeypatch.setattr(module, "_stop_backend_service", forbidden_local_control)
    monkeypatch.setattr(module, "_start_backend_service", forbidden_local_control)
    monkeypatch.setattr(module, "_start_frontend_service", forbidden_local_control)

    result = CliRunner().invoke(module.restart, [])

    assert result.exit_code == 0, result.output
    assert restarted == [("litepilot.service", 60)]
    assert "systemd" in result.output


def test_systemd_restart_uses_systemctl_and_waits_for_backend_health(monkeypatch):
    """委托重启必须调用 systemctl，并等待应用级健康检查而不是只等待进程 fork。"""
    module = load_cli_module()
    commands = []
    monkeypatch.setattr(module.shutil, "which", lambda command: "/usr/bin/systemctl" if command == "systemctl" else None)

    def fake_run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    health_results = iter([(False, None), (True, {"data": {}})])
    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module, "_backend_health", lambda timeout=2.0: next(health_results))
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)

    module._restart_systemd_service("litepilot.service", 5)

    assert commands == [["/usr/bin/systemctl", "restart", "litepilot.service"]]

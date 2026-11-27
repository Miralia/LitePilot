"""原生 systemd 安装归属识别。"""

from types import SimpleNamespace

from app.helper import deploy


def _mock_systemctl_values(monkeypatch, values):
    """按 systemctl 属性名返回测试值。"""
    monkeypatch.setattr(deploy.shutil, "which", lambda command: "/usr/bin/systemctl" if command == "systemctl" else None)

    def fake_run(command, **kwargs):
        prop = command[command.index("-p") + 1]
        return SimpleNamespace(returncode=0, stdout=values[prop] + "\n", stderr="")

    monkeypatch.setattr(deploy.subprocess, "run", fake_run)


def test_owned_systemd_unit_requires_current_install_root(tmp_path, monkeypatch):
    """只有 WorkingDirectory 指向当前仓库且执行 app.main 的 system unit 才归属当前安装。"""
    root = tmp_path / "repo"
    root.mkdir()
    values = {
        "LoadState": "loaded",
        "WorkingDirectory": str(root),
        "ExecStart": "{ path=/opt/moviepilot/venv/bin/python ; argv[]=/opt/moviepilot/venv/bin/python -m app.main ; ignore_errors=no }",
        "ActiveState": "active",
    }
    _mock_systemctl_values(monkeypatch, values)

    assert deploy.owned_systemd_unit(root) == "litepilot.service"

    values["WorkingDirectory"] = str(tmp_path / "other")
    assert deploy.owned_systemd_unit(root) is None

    values["WorkingDirectory"] = str(root)
    values["ExecStart"] = "{ path=/usr/bin/python ; argv[]=/usr/bin/python -m other.main ; ignore_errors=no }"
    assert deploy.owned_systemd_unit(root) is None


def test_owned_active_systemd_unit_ignores_inactive_service(tmp_path, monkeypatch):
    """inactive 或 failed 的所属 unit 不应阻塞更新；运行状态必须拦截。"""
    root = tmp_path / "repo"
    root.mkdir()
    values = {
        "LoadState": "loaded",
        "WorkingDirectory": str(root),
        "ExecStart": "{ path=/opt/moviepilot/venv/bin/python ; argv[]=/opt/moviepilot/venv/bin/python -m app.main ; ignore_errors=no }",
        "ActiveState": "inactive",
    }
    _mock_systemctl_values(monkeypatch, values)

    assert deploy.owned_active_systemd_unit(root) is None

    values["ActiveState"] = "active"
    assert deploy.owned_active_systemd_unit(root) == "litepilot.service"

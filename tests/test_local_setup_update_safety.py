"""本地更新命令的运行实例安全边界。"""

import pytest

from tests.test_local_setup_uninstall import load_local_setup_module


def test_update_safety_blocks_active_owned_systemd_unit(monkeypatch):
    """systemd 生产实例运行时不得更新其代码与虚拟环境。"""
    module = load_local_setup_module()
    monkeypatch.setattr(module, "_services_running", lambda: [])
    monkeypatch.setattr(module, "_owned_active_systemd_unit", lambda: "litepilot.service", raising=False)

    with pytest.raises(RuntimeError, match=r"systemctl stop litepilot\.service"):
        module.ensure_services_stopped()


def test_update_safety_local_process_message_does_not_mention_systemctl(monkeypatch):
    """纯本地 CLI 服务仍运行时，错误文案不得误导用户停止不相关的 systemd unit。"""
    module = load_local_setup_module()
    monkeypatch.setattr(module, "_services_running", lambda: ["backend"])
    monkeypatch.setattr(module, "_owned_active_systemd_unit", lambda: None, raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        module.ensure_services_stopped()

    assert "moviepilot stop" in str(exc_info.value)
    assert "systemctl stop" not in str(exc_info.value)

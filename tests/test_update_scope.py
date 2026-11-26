"""本地更新边界：只保留 CLI 显式更新链。"""

from pathlib import Path

from app.api.endpoints import system
from app.helper.system import SystemHelper


def test_unreachable_web_upgrade_entry_is_removed():
    """systemd/CLI 更新链不经过无入口的 Web upgrade API。"""
    assert not hasattr(system, "upgrade_system")


def test_one_shot_update_marker_residue_is_removed():
    """一次性升级标记只在已删除的 Web upgrade API 中产生，不能保留死状态机。"""
    assert not hasattr(SystemHelper, "upgrade")
    assert not hasattr(SystemHelper, "is_auto_update_enabled")
    assert not hasattr(SystemHelper, "queue_one_shot_update")
    assert not hasattr(SystemHelper, "consume_one_shot_update_mode")
    assert not hasattr(SystemHelper, "clear_one_shot_update_flag")


def test_cli_auto_update_does_not_consume_removed_marker():
    """CLI 启动自动更新只能使用显式配置，不能读取已删除的一次性标记。"""
    source = Path("app/cli.py").read_text(encoding="utf-8")

    assert "consume_one_shot_update_mode" not in source

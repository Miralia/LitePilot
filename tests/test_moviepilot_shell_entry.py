"""POSIX CLI 入口脚本的安装边界测试。"""

from pathlib import Path

import pytest


ENTRYPOINT_SOURCE = (Path(__file__).resolve().parents[1] / "moviepilot").read_text(
    encoding="utf-8"
)


@pytest.mark.parametrize(
    "removed_interface",
    [
        "install resources",
        "install-resources",
        "--skip-resources",
        "--frontend-version",
        "--resources-repo",
        "--resource-dir",
        "MoviePilot-Resources",
        "resources.v2",
    ],
)
def test_shell_entrypoint_removes_upstream_resource_and_release_interfaces(
    removed_interface: str,
) -> None:
    """CLI 入口不得继续路由或展示已移除的上游安装接口。"""
    assert removed_interface not in ENTRYPOINT_SOURCE


def test_shell_entrypoint_uses_current_local_node_runtime() -> None:
    """CLI 帮助中的默认 Node 版本必须与实际安装器一致。"""
    assert "--node-version 24.22.3" in ENTRYPOINT_SOURCE
    assert "20.12.1" not in ENTRYPOINT_SOURCE

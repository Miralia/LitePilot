"""冻结二进制运行时残留边界回归测试。"""

from pathlib import Path

from app import main
from app.chain.system import SystemChain
from app.startup import modules_initializer
from app.utils.system import SystemUtils


def test_frozen_executable_runtime_branches_are_removed() -> None:
    """项目支持源码安装与 systemd/nginx 部署，不再保留无打包管线的 frozen 分支。"""
    assert not hasattr(SystemUtils, "is_frozen")
    assert not hasattr(main, "start_tray")
    assert not hasattr(modules_initializer, "start_frontend")
    assert not hasattr(modules_initializer, "stop_frontend")


def test_frontend_version_always_reads_static_public_version() -> None:
    """前端版本只来自受支持的静态 public 产物，不再探测 frozen nginx 目录。"""
    import inspect

    source = inspect.getsource(SystemChain.get_frontend_version)
    assert "is_frozen" not in source
    assert "nginx" not in source


def test_frozen_only_runtime_assets_and_dependencies_are_removed() -> None:
    """托盘图标、pystray 与二进制专用配置复制逻辑不再随源码安装分发。"""
    assert not Path("app.ico").exists()
    requirements = Path("requirements.in").read_text(encoding="utf-8")
    assert "pystray" not in requirements

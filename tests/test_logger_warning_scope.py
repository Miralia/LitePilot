"""日志警告 API 边界测试。"""

from pathlib import Path

from app.log import logger


def test_application_uses_single_warning_logger_api():
    """应用内部只使用 warning，不再保留 warn 兼容别名调用。"""
    app_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("app").rglob("*.py")
    )

    assert "logger.warn(" not in app_sources


def test_logger_manager_drops_deprecated_warn_alias():
    """日志管理器只暴露标准 warning 方法，不保留重复警告 API。"""
    assert hasattr(logger, "warning")
    assert not hasattr(logger, "warn")

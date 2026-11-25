"""pytest 全局引导：隔离 CONFIG_DIR、建表、装载网络守卫。

引导与网络守卫均复用 ``app/testing`` 的测试 harness，引导逻辑只在 ``app/testing`` 维护一处。
"""
import sys

# 必须早于首个 import app.db（其在 import 期即按 CONFIG_PATH 连库）：prepare_backend 内部
# 先隔离 CONFIG_DIR 再建表。app/testing 仅依赖标准库、import 不连库，故此处先 import
# 再调用是安全的。
from app.testing.bootstrap import prepare_backend

prepare_backend()

# 装载 autouse 网络守卫，确保所有用例默认禁止真实外连
from app.testing.network_guard import block_real_network  # noqa: E402,F401


def _report_session_cleanup_error(session, name: str, err: Exception) -> None:
    """记录收尾错误；原测试绿色时将会话标记为失败。"""
    sys.stderr.write(f"\npytest session cleanup failed: {name}: {err!r}\n")
    if session.exitstatus == 0:
        session.exitstatus = 1


def pytest_sessionfinish(session, exitstatus):
    """释放测试过程中按需创建的全局后台资源，避免解释器退出时等待非 daemon worker。"""
    try:
        from app.helper.thread import ThreadHelper

        helper = ThreadHelper.get_existing_instance()
        if helper:
            helper.shutdown()
    except Exception as err:
        _report_session_cleanup_error(session, "thread helper", err)

    try:
        from app.helper.message import stop_message

        stop_message()
    except Exception as err:
        _report_session_cleanup_error(session, "message service", err)

    try:
        from app.log import LoggerManager

        LoggerManager.shutdown()
    except Exception as err:
        _report_session_cleanup_error(session, "logger manager", err)

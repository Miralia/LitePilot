import os
import setproctitle
import signal
import sys
from pathlib import Path

import uvicorn as uvicorn
from uvicorn import Config

from app.utils.stdio import configure_rotating_stdio

# 禁用输出
stdio_log_file = os.getenv("MOVIEPILOT_STDIO_LOG_FILE")
if stdio_log_file:
    # 本地 CLI 会把 stdout/stderr 切到滚动日志，避免无限追加单独的大文件。
    configure_rotating_stdio(
        log_file=Path(stdio_log_file),
        max_bytes=max(int(os.getenv("MOVIEPILOT_STDIO_LOG_MAX_BYTES", "0") or 0), 1),
        backup_count=max(
            int(os.getenv("MOVIEPILOT_STDIO_LOG_BACKUP_COUNT", "0") or 0),
            0,
        ),
    )

from app.factory import app
from app.core.config import global_vars, settings
from app.db.init import init_db, update_db

# 设置进程名
setproctitle.setproctitle(settings.PROJECT_NAME)


class LitePilotServer(uvicorn.Server):
    """在 Uvicorn 开始优雅退出前发布应用协作停止标志"""

    def handle_exit(self, sig, frame) -> None:
        global_vars.stop_system()
        super().handle_exit(sig, frame)


# uvicorn服务
Server = LitePilotServer(
    Config(
        app,
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEV,
        timeout_graceful_shutdown=60,
    )
)


def request_shutdown() -> None:
    """发布协作停止标志并请求 Uvicorn 退出"""
    global_vars.stop_system()
    Server.should_exit = True


def _validate_launch_arguments(arguments: list[str]) -> None:
    """拒绝被误传到服务入口的 CLI 参数，避免静默启动第二个后端实例。"""
    if not arguments:
        return
    print(
        "app.main 是后端服务入口，不接受命令行参数；管理命令请使用 moviepilot CLI。",
        file=sys.stderr,
    )
    raise SystemExit(2)


def signal_handler(signum, frame):
    """
    信号处理函数，用于优雅停止服务
    """
    print(f"收到信号 {signum}，开始优雅停止服务...")
    request_shutdown()


def run_application() -> None:
    """初始化进程并启动 API 服务"""
    # 注册信号处理器
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # 初始化数据库
    init_db()
    # 更新数据库
    update_db()
    # 启动API服务
    Server.run()


if __name__ == '__main__':
    _validate_launch_arguments(sys.argv[1:])
    run_application()

import inspect
from typing import Callable

from app.helper.redis import RedisHelper, AsyncRedisHelper
from app.utils.system import SystemUtils
from app.log import logger
from app.core.config import settings
from app.core.module import ModuleManager
from app.core.event import EventManager
from app.helper.swizzin import SwizzinUserSync
from app.helper.thread import ThreadHelper
from app.helper.message import stop_message
from app.db import close_database


def start_frontend():
    """
    启动前端服务
    """
    # 仅Windows可执行文件支持内嵌nginx
    if not SystemUtils.is_frozen() \
            or not SystemUtils.is_windows():
        return
    # 临时Nginx目录
    nginx_path = settings.ROOT_PATH / 'nginx'
    if not nginx_path.exists():
        return
    # 配置目录下的Nginx目录
    run_nginx_dir = settings.CONFIG_PATH.with_name('nginx')
    if not run_nginx_dir.exists():
        # 移动到配置目录
        SystemUtils.move(nginx_path, run_nginx_dir)
    # 启动Nginx
    import subprocess
    subprocess.Popen("start nginx.exe",
                     cwd=run_nginx_dir,
                     shell=True)


def stop_frontend():
    """
    停止前端服务
    """
    if not SystemUtils.is_frozen() \
            or not SystemUtils.is_windows():
        return
    import subprocess
    subprocess.Popen(f"taskkill /f /im nginx.exe", shell=True)


def clear_temp():
    """
    清理临时文件和图片缓存
    """
    # 清理临时目录中3天前的文件
    SystemUtils.clear(settings.TEMP_PATH, days=settings.TEMP_FILE_DAYS)
    # 清理图片缓存目录中7天前的文件
    SystemUtils.clear(settings.CACHE_PATH / "images", days=settings.GLOBAL_IMAGE_CACHE_DAYS)
    # 清理 pip/uv 包下载缓存，不接管整个 .cache 目录。
    clear_package_tool_cache()


def clear_package_tool_cache():
    """
    清理 pip/uv 包下载缓存，只处理 MoviePilot 管理的工具子目录。
    """
    days = settings.PACKAGE_CACHE_DAYS
    if days <= 0:
        return
    tool_cache_root = settings.PACKAGE_CACHE_PATH
    for child in ("pip", "uv"):
        cache_path = tool_cache_root / child
        try:
            SystemUtils.clear(cache_path, days=days)
        except Exception as err:
            logger.warning("清理包下载缓存失败：%s - %s", cache_path, err)


async def stop_modules():
    """
    服务关闭
    """
    async def run_step(name: str, callback: Callable[[], object]) -> None:
        """单个模块资源关闭失败时继续执行后续阶段"""
        try:
            result = callback()
            if inspect.isawaitable(result):
                await result
        except Exception as err:
            logger.error(f"关闭{name}失败：{err}")

    await run_step("模块", lambda: ModuleManager().stop())
    await run_step("事件消费", lambda: EventManager().stop())
    await run_step("线程池", lambda: ThreadHelper().shutdown())
    await run_step("消息服务", stop_message)
    await run_step("Redis缓存连接", lambda: RedisHelper().close())
    await run_step("异步Redis缓存连接", lambda: AsyncRedisHelper().close())
    await run_step("数据库连接", close_database)
    await run_step("前端服务", stop_frontend)
    await run_step("临时文件", clear_temp)


def init_modules():
    """
    启动模块
    """
    # 按 swizzin 用户清单同步本地账号（非 swizzin 环境退化为单管理员）
    SwizzinUserSync().sync()
    # 加载模块
    ModuleManager()
    # 启动事件消费
    EventManager().start()
    # 启动前端服务
    start_frontend()

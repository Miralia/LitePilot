import importlib
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


def clear_temp():
    """
    清理临时文件和图片缓存
    """
    cleanup_targets = (
        # 清理临时目录中3天前的文件
        (settings.TEMP_PATH, settings.TEMP_FILE_DAYS),
        # 清理图片缓存目录中7天前的文件
        (settings.CACHE_PATH / "images", settings.GLOBAL_IMAGE_CACHE_DAYS),
    )
    for cache_path, days in cleanup_targets:
        try:
            SystemUtils.clear(cache_path, days=days)
        except Exception as err:
            logger.warning("清理缓存目录失败：%s - %s", cache_path, err)
    # 清理 pip/uv 包下载缓存，不接管整个 .cache 目录。
    clear_package_tool_cache()


def clear_package_tool_cache():
    """
    清理 pip/uv 包下载缓存，只处理 LitePilot 管理的工具子目录。
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
    await run_step("临时文件", clear_temp)


def _load_event_chain_modules():
    """
    导入包含事件处理器的链式模块，确保其装饰器完成注册。
    """
    for module_name in (
        "app.chain.mediaserverdel",
        "app.chain.message",
    ):
        try:
            importlib.import_module(module_name)
        except Exception as err:  # pylint: disable=broad-except
            logger.error(f"加载事件模块 {module_name} 失败：{err}")


def init_modules():
    """
    启动模块
    """
    # 按 swizzin 用户清单同步本地账号（非 swizzin 环境退化为单管理员）
    SwizzinUserSync().sync()
    # 加载模块
    ModuleManager()
    # 加载带事件处理器的链式模块。
    # 事件处理器靠模块导入期的装饰器注册，未被其它代码引用的 chain 模块
    # 需要在这里显式导入，否则其事件永远不触发。
    _load_event_chain_modules()
    # 启动事件消费
    EventManager().start()

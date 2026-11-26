"""进程内存使用读取工具。"""
import os

import psutil

from app.log import logger


def get_memory_usage() -> float:
    """
    获取当前进程的内存使用情况（MB）

    Returns:
        内存使用量（MB）
    """
    try:
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        return memory_info.rss / 1024 / 1024  # 转换为MB
    except Exception as e:
        logger.warning(f"获取内存使用情况失败: {e}")
        return 0.0

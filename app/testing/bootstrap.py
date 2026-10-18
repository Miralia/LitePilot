"""测试引导共享实现。

``tests/conftest.py`` 委托到这里完成「隔离 CONFIG_DIR / 建表 / 退出清理」等引导逻辑，
使引导行为只在主程序维护一处。

本模块只依赖标准库，``import`` 期不连库、不触发 ``app.db``：调用方可安全地「先 import 本模块、
再隔离 CONFIG_DIR」，不破坏「隔离必须早于首个 ``import app.db``」这一硬约束。
"""
from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

# 本进程隔离出的临时 CONFIG_DIR，兼作幂等标记
_isolated_config_dir: Optional[str] = None




def isolate_config_dir() -> str:
    """把 ``CONFIG_DIR`` 指向进程私有临时目录，隔离主程序真实库与配置（幂等）。

    ``import app.db`` / ``import app.chain.*`` 在 import 期即按 ``settings.CONFIG_PATH`` 连接
    ``user.db``，故本函数必须在首个 ``import app.db`` 之前调用。调用方已显式设置 ``CONFIG_DIR``
    （如 CI 指定隔离目录）时尊重之、不覆盖。

    :return: 实际生效的 CONFIG_DIR 绝对路径
    """
    global _isolated_config_dir
    if _isolated_config_dir is not None:
        return _isolated_config_dir
    existing = os.environ.get("CONFIG_DIR")
    if existing:
        _isolated_config_dir = existing
        return existing
    tmp = tempfile.mkdtemp(prefix="mp-test-config-")
    os.environ["CONFIG_DIR"] = tmp
    _isolated_config_dir = tmp

    def _cleanup(path: str = tmp, rmtree=shutil.rmtree, sys_mod=sys) -> None:
        """进程退出时释放 SQLite 连接池再删临时目录。

        默认参数绑定 ``rmtree``/``path``/``sys_mod``：解释器关停期标准库模块可能已被回收为 ``None``，
        绑定后仍可安全调用。先 ``Engine.dispose`` 释放 ``user.db`` 连接，规避 Windows 下
        文件锁导致 ``rmtree`` 静默失败（``ignore_errors``）、残留临时目录。
        """
        try:
            db_mod = sys_mod.modules.get("app.db")
            if db_mod is not None:
                db_mod.Engine.dispose()
        except Exception:
            pass
        rmtree(path, ignore_errors=True)

    atexit.register(_cleanup)
    return tmp


def _prepend_sys_path(path: Path) -> None:
    """把目录前置到 ``sys.path``（去重），使其内顶层包可被导入。"""
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)






def prepare_backend() -> None:
    """隔离 CONFIG_DIR 并建表。

    隔离出的临时库为空，运行期查 ``systemconfig`` 等表会报 no such table，故建表；
    ``init_db`` 仅 import models + create_all，无 alembic/网络、幂等、毫秒级。
    """
    isolate_config_dir()
    from app.db.init import init_db
    init_db()




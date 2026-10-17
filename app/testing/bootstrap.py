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


class _SitesHelperStub:
    """
    测试环境站点资源垫片，用于动态站点资源仓缺失时提供基础只读接口。
    """

    auth_level = 0
    auth_version = ""
    indexer_version = ""

    def get_indexers(self) -> list:
        """返回空站点索引列表。"""
        return []

    async def async_get_indexers(self) -> list:
        """异步返回空站点索引列表。"""
        return []

    def get_indexer(self, *_args: Any, **_kwargs: Any) -> Optional[dict]:
        """返回空站点索引详情。"""
        return None

    async def async_get_indexer(self, *_args: Any, **_kwargs: Any) -> Optional[dict]:
        """异步返回空站点索引详情。"""
        return None

    def get_authsites(self) -> list:
        """返回空认证站点列表。"""
        return []

    def get_indexsites(self) -> list:
        """返回空索引站点列表。"""
        return []

    def check(self, *_args: Any, **_kwargs: Any) -> tuple[bool, str]:
        """返回站点资源不可用的检查结果。"""
        return False, "站点资源未加载"

    def check_user(self, *_args: Any, **_kwargs: Any) -> tuple[bool, str]:
        """返回用户认证站点不可用的检查结果。"""
        return False, "站点资源未加载"


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


def ensure_sites_stub() -> None:
    """为 ``app.helper.sites`` 补最小垫片（仅在缺失时）。

    ``app.helper.sites`` 由独立仓库动态拉取，CI / 全新环境无该模块，而众多 ``app.chain.*`` /
    ``app.modules.*`` 在 import 期依赖它。统一补一个最小垫片，省去各测试文件各自打桩；若真实模块
    已存在（本地已拉取）则用真实模块、不覆盖，不影响真实行为。须在隔离 CONFIG_DIR 之后调用，
    以免试探性 ``import app.helper.sites`` 触发的连库落到真实库。
    """
    if "app.helper.sites" in sys.modules:
        return
    try:
        import app.helper.sites  # noqa: F401  本地已拉取时用真实模块
    except (ModuleNotFoundError, ImportError):
        from types import ModuleType
        stub = ModuleType("app.helper.sites")
        stub.SitesHelper = _SitesHelperStub
        sys.modules["app.helper.sites"] = stub


def ensure_optional_stub(name: str, **attrs) -> None:
    """为可选第三方依赖补占位模块（仅在缺失时），可带属性。

    用例 import 的 app 代码会牵入可选三方库（如 psutil / dateparser / Pinyin2Hanzi /
    qbittorrentapi），CI / 全新环境可能未安装。本函数在该库缺失时补一个带
    指定属性的占位，使 import 不致失败；若已真实安装则保留真实模块、不覆盖。占位为进程级常驻
    （与 import 生命周期一致、不作用域还原），是「让可选 import 不失败」的垫片——与
    :func:`stub_modules`（作用域内打桩并还原）属不同用途，故不收进 stub_modules。

    :param name: 可选依赖的顶层模块名
    :param attrs: 占位模块需暴露的属性（仅在真正创建占位时设置）
    """
    if name in sys.modules:
        return
    try:
        __import__(name)
        return
    except ImportError:
        pass
    from types import ModuleType
    module = ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module


def prepare_backend() -> None:
    """隔离 CONFIG_DIR、补 sites 垫片并建表。

    顺序固定：先隔离 CONFIG_DIR，再补 ``app.helper.sites`` 垫片，最后建表——隔离出的临时库
    为空，运行期查 ``systemconfig`` 等表会报 no such table，故建表；``init_db`` 仅 import
    models + create_all，无 alembic/网络、幂等、毫秒级。
    """
    isolate_config_dir()
    ensure_sites_stub()
    from app.db.init import init_db
    init_db()




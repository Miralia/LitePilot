"""站点资源垫片。

上游把站点认证与站点索引能力放在仓库外的私有动态资源里（``sites.cpython-*.so`` 与
``user.sites.v2.bin``，由 ``app/helper/resource.py`` 从 MoviePilot-Resources 拉取）。
本分支整体删除站点功能，不再加载该资源，但仓库内仍有多处代码在导入期或运行期引用
``SitesHelper``（认证级别、站点索引枚举、资源包版本等）。

这里提供只读的最小实现，用于：

- 保持既有引用点可导入，避免为一个已删除的能力做全仓替换；
- 让 ``auth_level`` 恒为 1，使插件与接口不再依赖站点认证；
- 让站点索引枚举恒为空，使任何遗留调用自然退化为「无站点可用」。
"""
from typing import Any, List, Optional, Tuple

from app.utils.singleton import Singleton


class SitesHelper(metaclass=Singleton):
    """
    站点资源垫片，不提供任何真实站点能力。
    """

    # 认证级别：1 表示所有用户可见，不再要求站点认证
    auth_level: int = 1
    # 站点认证资源版本（本分支不再使用）
    auth_version: str = ""
    # 站点索引资源版本（本分支不再使用）
    indexer_version: str = ""

    def get_indexers(self) -> List[dict]:
        """
        获取所有站点索引器。
        """
        return []

    async def async_get_indexers(self) -> List[dict]:
        """
        异步获取所有站点索引器。
        """
        return []

    def get_indexer(self, domain: Optional[str] = None) -> Optional[dict]:
        """
        获取指定域名的站点索引器。
        """
        return None

    async def async_get_indexer(self, domain: Optional[str] = None) -> Optional[dict]:
        """
        异步获取指定域名的站点索引器。
        """
        return None

    def get_authsites(self) -> List[dict]:
        """
        获取认证站点列表。
        """
        return []

    def get_indexsites(self) -> List[dict]:
        """
        获取索引站点列表。
        """
        return []

    def check(self, domain: Optional[str] = None, *args: Any, **kwargs: Any) -> Tuple[bool, str]:
        """
        检查站点可用性。
        """
        return False, "站点资源未加载"

    def check_user(self, *args: Any, **kwargs: Any) -> Tuple[bool, str]:
        """
        检查用户认证状态。
        """
        return False, "站点资源未加载"

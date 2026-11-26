from typing import Optional

from sqlalchemy.orm import Session

from app.db import DbOper
from app.db.models.mediaserver import MediaServerItem


class MediaServerOper(DbOper):
    """
    媒体服务器数据管理
    """

    def __init__(self, db: Session = None):
        super().__init__(db)

    @staticmethod
    def __prepare_payload(kwargs: dict) -> dict:
        """
        过滤数据库模型不存在或不应由远端覆盖的字段
        """
        return {
            k: v for k, v in kwargs.items()
            if hasattr(MediaServerItem, k) and k != "id"
        }

    def add(self, **kwargs) -> bool:
        """
        新增媒体服务器数据
        """
        kwargs = self.__prepare_payload(kwargs)
        server = kwargs.get("server")
        item_id = kwargs.get("item_id")
        if not server or not item_id:
            return False
        item = MediaServerItem(**kwargs)
        if not item.get_by_server_itemid(self._db, server, item_id):
            item.create(self._db)
            return True
        return False

    def upsert(self, **kwargs) -> bool:
        """
        按媒体服务器和条目ID新增或更新数据
        """
        kwargs = self.__prepare_payload(kwargs)
        server = kwargs.get("server")
        item_id = kwargs.get("item_id")
        if not server or not item_id:
            return False

        item = MediaServerItem.get_by_server_itemid(self._db, server, item_id)
        if item:
            item.update(self._db, kwargs)
            return False

        MediaServerItem(**kwargs).create(self._db)
        return True

    def empty(self, server: Optional[str] = None):
        """
        清空媒体服务器数据
        """
        MediaServerItem.empty(self._db, server)

    def delete_stale(self, server: str, sync_time: str) -> int:
        """
        删除本轮同步未更新的旧数据
        """
        return MediaServerItem.delete_stale(self._db, server, sync_time)

    def delete_excluded_servers(self, servers: list[str]) -> int:
        """
        删除未启用或已移除媒体服务器的数据
        """
        return MediaServerItem.delete_excluded_servers(self._db, servers)

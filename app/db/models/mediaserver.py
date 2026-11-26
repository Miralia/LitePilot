from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, Integer, String, JSON, Index, or_
from sqlalchemy.orm import Session

from app.db import db_query, db_update, get_id_column, Base


class MediaServerItem(Base):
    """
    媒体服务器媒体条目表
    """
    id = get_id_column()
    # 服务器类型
    server = Column(String)
    # 媒体库ID
    library = Column(String)
    # ID
    item_id = Column(String, index=True)
    # 类型
    item_type = Column(String)
    # 标题
    title = Column(String, index=True)
    # 原标题
    original_title = Column(String)
    # 年份
    year = Column(String)
    # TMDBID
    tmdbid = Column(Integer)
    # IMDBID
    imdbid = Column(String, index=True)
    # TVDBID
    tvdbid = Column(String, index=True)
    # 路径
    path = Column(String)
    # 季集
    seasoninfo = Column(JSON, default=dict)
    # 备注
    note = Column(JSON)
    # 同步时间
    lst_mod_date = Column(String, default=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    __table_args__ = (
        Index('ux_mediaserveritem_server_item_id', 'server', 'item_id', unique=True),
        Index('ix_mediaserveritem_tmdbid_item_type', 'tmdbid', 'item_type'),
    )

    @classmethod
    @db_query
    def get_by_server_itemid(cls, db: Session, server: str, item_id: str):
        return db.query(cls).filter(cls.server == server,
                                    cls.item_id == item_id).first()

    @classmethod
    @db_update
    def empty(cls, db: Session, server: Optional[str] = None):
        if server is None:
            db.query(cls).delete(synchronize_session=False)
        else:
            db.query(cls).filter(cls.server == server).delete(synchronize_session=False)

    @classmethod
    @db_update
    def delete_stale(cls, db: Session, server: str, sync_time: str):
        return db.query(cls).filter(cls.server == server,
                                    or_(cls.lst_mod_date.is_(None),
                                        cls.lst_mod_date != sync_time)).delete(synchronize_session=False)

    @classmethod
    @db_update
    def delete_excluded_servers(cls, db: Session, servers: List[str]):
        if not servers:
            return db.query(cls).delete(synchronize_session=False)
        return db.query(cls).filter(or_(cls.server.is_(None),
                                        ~cls.server.in_(servers))).delete(synchronize_session=False)

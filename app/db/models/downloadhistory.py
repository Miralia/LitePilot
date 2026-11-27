import time
from typing import Optional

from sqlalchemy import Column, Integer, String, JSON, Index
from sqlalchemy.orm import Session

from app.db import db_query, db_update, get_id_column, Base


class DownloadHistory(Base):
    """
    下载历史记录
    """

    id = get_id_column()
    # 保存路径
    path = Column(String, nullable=False, index=True)
    # 类型 电影/电视剧
    type = Column(String, nullable=False)
    # 标题
    title = Column(String, nullable=False)
    # 年份
    year = Column(String)
    tmdbid = Column(Integer, index=True)
    imdbid = Column(String)
    tvdbid = Column(Integer)
    doubanid = Column(String)
    bangumiid = Column(Integer, index=True)
    media_source = Column(String, index=True)
    media_id = Column(String, index=True)
    # Sxx
    seasons = Column(String)
    # Exx
    episodes = Column(String)
    # 背景图
    image = Column(String)
    # 海报
    poster = Column(String)
    # 下载器
    downloader = Column(String)
    # 下载任务Hash
    download_hash = Column(String)
    # 种子名称
    torrent_name = Column(String)
    # 种子描述
    torrent_description = Column(String)
    # 种子站点
    torrent_site = Column(String)
    # 下载用户
    userid = Column(String)
    # 下载用户名/插件名
    username = Column(String)
    # 下载渠道
    channel = Column(String)
    # 创建时间
    date = Column(String)
    # 附加信息
    note = Column(JSON)
    # 自定义媒体类别
    media_category = Column(String)
    # 剧集组
    episode_group = Column(String)
    # 自定义识别词（用于整理时应用）
    custom_words = Column(String)

    __table_args__ = (
        Index('ix_downloadhistory_download_hash_date', 'download_hash', 'date'),
        Index('ix_downloadhistory_date_id', 'date', 'id'),
        Index('ix_downloadhistory_media_identity', 'media_source', 'media_id'),
    )

    @classmethod
    @db_query
    def get_by_hash(cls, db: Session, download_hash: str):
        return (
            db.query(DownloadHistory)
            .filter(DownloadHistory.download_hash == download_hash)
            .order_by(DownloadHistory.date.desc())
            .first()
        )

    @classmethod
    @db_query
    def get_by_path(cls, db: Session, path: str):
        return db.query(DownloadHistory).filter(DownloadHistory.path == path).first()

    @classmethod
    @db_update
    def delete_before(
        cls,
        db: Session,
        before_time: str,
        limit: Optional[int] = 500,
    ) -> int:
        """
        分批删除指定时间之前的下载历史。
        """
        ids = [
            row[0]
            for row in db.query(cls.id)
            .filter(cls.date < before_time)
            .order_by(cls.id.asc())
            .limit(limit)
            .all()
        ]
        if not ids:
            return 0
        return (
            db.query(cls)
            .filter(cls.id.in_(ids))
            .delete(synchronize_session=False)
        )


class DownloadFiles(Base):
    """
    下载文件记录
    """

    id = get_id_column()
    # 下载器
    downloader = Column(String)
    # 下载任务Hash
    download_hash = Column(String)
    # 完整路径
    fullpath = Column(String)
    # 保存路径
    savepath = Column(String, index=True)
    # 文件相对路径/名称
    filepath = Column(String)
    # 种子名称
    torrentname = Column(String)
    # 状态 0-已删除 1-正常
    state = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index('ix_downloadfiles_download_hash_state', 'download_hash', 'state'),
        Index('ix_downloadfiles_fullpath_id', 'fullpath', 'id'),
    )

    @classmethod
    @db_query
    def get_by_hash(cls, db: Session, download_hash: str, state: Optional[int] = None):
        if state is not None:
            return (
                db.query(cls)
                .filter(cls.download_hash == download_hash, cls.state == state)
                .all()
            )
        else:
            return db.query(cls).filter(cls.download_hash == download_hash).all()

    @classmethod
    @db_query
    def get_by_fullpath(cls, db: Session, fullpath: str, all_files: bool = False):
        if not all_files:
            return (
                db.query(cls)
                .filter(cls.fullpath == fullpath)
                .order_by(cls.id.desc())
                .first()
            )
        else:
            return (
                db.query(cls)
                .filter(cls.fullpath == fullpath)
                .order_by(cls.id.desc())
                .all()
            )

    @classmethod
    @db_query
    def get_by_savepath(cls, db: Session, savepath: str):
        return db.query(cls).filter(cls.savepath == savepath).all()

    @classmethod
    @db_update
    def delete_by_fullpath(
        cls,
        db: Session,
        fullpath: str,
        download_hash: Optional[str] = None,
    ):
        """
        按完整路径把文件记录标记为已删除。

        早期同步在下载历史缺失时退化成只写相对路径（不带前导斜杠），
        这类记录与调用方传入的绝对路径永远不相等，种子因此一直被判定
        为「仍有文件未删除」，媒体库删除后种子留在下载器里。

        这里把绝对路径逐级裁剪成候选相对路径，与完整路径一起精确匹配：
        不用 LIKE 后缀匹配，避免同名文件被连带标记。

        :param db: 数据库会话
        :param fullpath: 文件完整路径
        :param download_hash: 限定所属种子，进一步收窄匹配范围
        """
        normalized = str(fullpath).replace("\\", "/").strip()
        if not normalized:
            return 0
        candidates = {normalized}
        parts = normalized.strip("/").split("/")
        for index in range(1, len(parts)):
            candidate = "/".join(parts[index:])
            # 仅剩文件名的候选只有在限定种子时才安全，否则同名文件会被连带标记
            if "/" in candidate or download_hash:
                candidates.add(candidate)
        query = db.query(cls).filter(cls.fullpath.in_(candidates), cls.state == 1)
        if download_hash:
            query = query.filter(cls.download_hash == download_hash)
        return query.update({"state": 0}, synchronize_session=False)

    @classmethod
    @db_update
    def backfill_savepath(
        cls,
        db: Session,
        download_hash: str,
        save_path: str,
    ) -> int:
        """
        回填种子的保存根目录，并把相对路径的记录补成绝对路径。

        种子由下载器外部添加时没有下载历史，早期同步因此只写入了相对路径。
        补上 save_path 后既可让后续同步直接拼接绝对路径，也能让按绝对路径
        反查精确命中，不必依赖逐级裁剪的候选匹配。

        :param db: 数据库会话
        :param download_hash: 种子 Hash
        :param save_path: 保存根目录
        :return: 更新的记录数
        """
        normalized = str(save_path or "").replace("\\", "/").rstrip("/")
        if not normalized:
            return 0
        rows = (
            db.query(cls)
            .filter(cls.download_hash == download_hash)
            .all()
        )
        updated = 0
        for row in rows:
            fullpath = str(row.fullpath or "").replace("\\", "/")
            filepath = str(row.filepath or "").replace("\\", "/")
            payload = {}
            if not row.savepath:
                payload["savepath"] = normalized
            # 只补相对路径记录；已是绝对路径的不动，避免拼出错误层级
            if fullpath and not fullpath.startswith("/"):
                relative = filepath or fullpath
                payload["fullpath"] = f"{normalized}/{relative}"
            if not payload:
                continue
            for key, value in payload.items():
                setattr(row, key, value)
            updated += 1
        return updated

    @classmethod
    @db_update
    def delete_missing_for_downloader(
        cls,
        db: Session,
        downloader: str,
        active_hashes: set[str],
        hash_batch_size: int = 200,
    ) -> int:
        """
        删除指定下载器中已不再存在的种子文件记录。

        清理必须限定下载器：不同下载器可能重复使用相同 hash 或保存路径，
        无下载器归属的历史行也不能在没有来源证据时被误删。

        :param db: 数据库会话
        :param downloader: 已成功列出任务的下载器名称
        :param active_hashes: 当前仍存在于该下载器中的种子 Hash
        :param hash_batch_size: 每批删除的 hash 数，避免 SQL 参数过多
        :return: 删除的文件记录数
        """
        normalized_active = {
            str(value).lower()
            for value in active_hashes or set()
            if value
        }
        hash_rows = (
            db.query(cls.download_hash)
            .filter(cls.downloader == downloader)
            .distinct()
            .all()
        )
        missing_hashes = sorted({
            str(row[0])
            for row in hash_rows
            if row[0] and str(row[0]).lower() not in normalized_active
        })
        deleted = 0
        batch_size = max(1, int(hash_batch_size or 200))
        for index in range(0, len(missing_hashes), batch_size):
            batch = missing_hashes[index:index + batch_size]
            deleted += (
                db.query(cls)
                .filter(
                    cls.downloader == downloader,
                    cls.download_hash.in_(batch),
                )
                .delete(synchronize_session=False)
            )
        return deleted

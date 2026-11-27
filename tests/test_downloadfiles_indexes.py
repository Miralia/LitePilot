"""下载文件表索引覆盖测试。"""

from app.db.models.downloadhistory import DownloadFiles


def test_downloadfiles_has_downloader_hash_index() -> None:
    """按下载器清理文件索引时必须能使用复合索引，而不是扫描全部记录。"""
    indexed_columns = {
        tuple(column.name for column in index.columns)
        for index in DownloadFiles.__table__.indexes
    }

    assert ("downloader", "download_hash") in indexed_columns


def test_downloadfiles_downloader_hash_index_migration_is_idempotent(monkeypatch) -> None:
    """迁移必须幂等创建生产数据库中的下载器复合索引。"""
    import importlib

    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    migration = importlib.import_module(
        "database.versions.c8f4a1d7e293_2_2_17"
    )
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table(
        "downloadfiles",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("downloader", sa.String()),
        sa.Column("download_hash", sa.String()),
    )

    with engine.begin() as connection:
        metadata.create_all(connection)
        context = MigrationContext.configure(connection)
        monkeypatch.setattr(migration, "op", Operations(context))

        migration.upgrade()
        migration.upgrade()

        indexes = sa.inspect(connection).get_indexes("downloadfiles")

    assert any(
        index["name"] == "ix_downloadfiles_downloader_hash"
        and index["column_names"] == ["downloader", "download_hash"]
        for index in indexes
    )

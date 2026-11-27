"""整理历史表索引覆盖测试。"""

from app.db.models.transferhistory import TransferHistory


def test_transferhistory_has_dest_index() -> None:
    """按媒体库目标路径反查整理记录时必须能使用索引，而不是扫描全部历史。"""
    indexed_columns = {
        tuple(column.name for column in index.columns)
        for index in TransferHistory.__table__.indexes
    }

    assert ("dest",) in indexed_columns


def test_transferhistory_dest_index_migration_is_idempotent(monkeypatch) -> None:
    """迁移必须幂等创建生产数据库中的目标路径索引。"""
    import importlib

    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    migration = importlib.import_module(
        "database.versions.d9e5a2c4f718_2_2_18"
    )
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table(
        "transferhistory",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dest", sa.String()),
    )

    with engine.begin() as connection:
        metadata.create_all(connection)
        context = MigrationContext.configure(connection)
        monkeypatch.setattr(migration, "op", Operations(context))

        migration.upgrade()
        migration.upgrade()

        indexes = sa.inspect(connection).get_indexes("transferhistory")

    assert any(
        index["name"] == "ix_transferhistory_dest"
        and index["column_names"] == ["dest"]
        for index in indexes
    )

"""系统配置表键唯一性索引覆盖测试。"""

from app.db.models.systemconfig import SystemConfig


def test_systemconfig_key_index_is_unique() -> None:
    """运行时配置键必须数据库级唯一，避免并发或异常写入产生歧义行。"""
    key_indexes = [
        index
        for index in SystemConfig.__table__.indexes
        if tuple(column.name for column in index.columns) == ("key",)
    ]

    assert any(index.unique for index in key_indexes)


def test_systemconfig_unique_index_migration_is_idempotent(monkeypatch) -> None:
    """迁移必须把既有键索引升级为唯一索引，重复执行应保持幂等。"""
    import importlib

    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    migration = importlib.import_module(
        "database.versions.e4f7a1c9d2b5_2_2_19"
    )
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    table = sa.Table(
        "systemconfig",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String()),
        sa.Column("value", sa.JSON()),
    )

    with engine.begin() as connection:
        metadata.create_all(connection)
        sa.Index("ix_systemconfig_key", table.c.key).create(connection)
        connection.execute(
            table.insert().values(key="RuntimeKey", value={"enabled": True})
        )
        context = MigrationContext.configure(connection)
        monkeypatch.setattr(migration, "op", Operations(context))

        migration.upgrade()
        migration.upgrade()

        indexes = sa.inspect(connection).get_indexes("systemconfig")
        row = connection.execute(
            sa.select(table.c.value).where(table.c.key == "RuntimeKey")
        ).first()

    assert row == ({"enabled": True},)
    assert any(
        index["name"] == "ix_systemconfig_key"
        and index["column_names"] == ["key"]
        and index["unique"]
        for index in indexes
    )


def test_systemconfig_unique_index_rejects_duplicate_keys(monkeypatch) -> None:
    """迁移后的数据库必须拒绝相同配置键二次写入。"""
    import importlib

    import pytest
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    migration = importlib.import_module(
        "database.versions.e4f7a1c9d2b5_2_2_19"
    )
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    table = sa.Table(
        "systemconfig",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String()),
        sa.Column("value", sa.JSON()),
    )

    with engine.begin() as connection:
        metadata.create_all(connection)
        sa.Index("ix_systemconfig_key", table.c.key).create(connection)
        context = MigrationContext.configure(connection)
        monkeypatch.setattr(migration, "op", Operations(context))
        migration.upgrade()
        connection.execute(table.insert().values(key="RuntimeKey", value=True))

        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(table.insert().values(key="RuntimeKey", value=False))


def test_systemconfig_unique_migration_preserves_duplicate_rows(monkeypatch) -> None:
    """既有重复键不得被迁移静默删除，必须保留数据并明确要求人工处理。"""
    import importlib

    import pytest
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    migration = importlib.import_module(
        "database.versions.e4f7a1c9d2b5_2_2_19"
    )
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    table = sa.Table(
        "systemconfig",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String()),
        sa.Column("value", sa.JSON()),
    )

    with engine.begin() as connection:
        metadata.create_all(connection)
        sa.Index("ix_systemconfig_key", table.c.key).create(connection)
        connection.execute(
            table.insert(),
            [
                {"key": "RuntimeKey", "value": True},
                {"key": "RuntimeKey", "value": False},
            ],
        )
        context = MigrationContext.configure(connection)
        monkeypatch.setattr(migration, "op", Operations(context))

        with pytest.raises(RuntimeError, match="重复配置键"):
            migration.upgrade()

        row_count = connection.execute(sa.select(sa.func.count()).select_from(table)).scalar()
        indexes = sa.inspect(connection).get_indexes("systemconfig")

    assert row_count == 2
    assert any(
        index["name"] == "ix_systemconfig_key"
        and not index["unique"]
        for index in indexes
    )

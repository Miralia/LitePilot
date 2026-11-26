import importlib

import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory


def test_downloadfiles_dedup_migration_preserves_delete_tombstones(monkeypatch) -> None:
    """迁移应去除重复文件记录，并让已删除墓碑优先于错误复活的正常行。"""
    migration = importlib.import_module(
        "database.versions.b9d6f3a2c1e8_2_2_16"
    )
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    download_files = sa.Table(
        "downloadfiles",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("downloader", sa.String()),
        sa.Column("download_hash", sa.String()),
        sa.Column("fullpath", sa.String()),
        sa.Column("savepath", sa.String()),
        sa.Column("filepath", sa.String()),
        sa.Column("torrentname", sa.String()),
        sa.Column("state", sa.Integer()),
    )

    with engine.begin() as connection:
        metadata.create_all(connection)
        connection.execute(
            download_files.insert(),
            [
                {
                    "id": 1,
                    "downloader": "qBittorrent",
                    "download_hash": "hash-a",
                    "fullpath": "/downloads/Show/ep01.mkv",
                    "savepath": "/downloads",
                    "filepath": "Show/ep01.mkv",
                    "torrentname": "Show",
                    "state": 1,
                },
                {
                    "id": 2,
                    "downloader": "qBittorrent",
                    "download_hash": "hash-a",
                    "fullpath": "/downloads/Show/ep01.mkv",
                    "savepath": "/downloads",
                    "filepath": "Show/ep01.mkv",
                    "torrentname": "Show",
                    "state": 1,
                },
                {
                    "id": 3,
                    "downloader": "qBittorrent",
                    "download_hash": "hash-a",
                    "fullpath": "/downloads/Show/ep01.mkv",
                    "savepath": "/downloads",
                    "filepath": "Show/ep01.mkv",
                    "torrentname": "Show",
                    "state": 0,
                },
                {
                    "id": 4,
                    "downloader": "qBittorrent",
                    "download_hash": "hash-a",
                    "fullpath": "/downloads/Show/ep02.mkv",
                    "savepath": "/downloads",
                    "filepath": "Show/ep02.mkv",
                    "torrentname": "Show",
                    "state": 1,
                },
                {
                    "id": 5,
                    "downloader": "qBittorrent",
                    "download_hash": "hash-a",
                    "fullpath": "/downloads/Show/ep02.mkv",
                    "savepath": "/downloads",
                    "filepath": "Show/ep02.mkv",
                    "torrentname": "Show",
                    "state": 1,
                },
                {
                    "id": 6,
                    "downloader": "Transmission",
                    "download_hash": "hash-a",
                    "fullpath": "/downloads/Show/ep01.mkv",
                    "savepath": "/downloads",
                    "filepath": "Show/ep01.mkv",
                    "torrentname": "Show",
                    "state": 1,
                },
            ],
        )
        context = MigrationContext.configure(connection)
        monkeypatch.setattr(migration, "op", Operations(context))

        migration.upgrade()
        migration.upgrade()

        rows = connection.execute(
            sa.select(download_files).order_by(download_files.c.id)
        ).mappings().all()

    by_id = {row["id"]: row for row in rows}
    assert set(by_id) == {1, 4, 6}
    assert by_id[1]["state"] == 0
    assert by_id[4]["state"] == 1
    assert by_id[6]["downloader"] == "Transmission"


def test_alembic_migrations_have_single_head() -> None:
    """迁移脚本必须保持线性 head，避免生产升级停在分支冲突。"""
    config = Config()
    config.set_main_option("script_location", "database")
    script = ScriptDirectory.from_config(config)

    assert len(script.get_heads()) == 1

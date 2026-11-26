"""2.2.16
清理下载文件重复记录并保留删除墓碑

Revision ID: b9d6f3a2c1e8
Revises: a5d2e8f1c4b7
Create Date: 2026-11-27
"""

from collections.abc import Iterator

from alembic import op
import sqlalchemy as sa


revision = "b9d6f3a2c1e8"
down_revision = "a5d2e8f1c4b7"
branch_labels = None
depends_on = None

_BATCH_SIZE = 500


def _batched(values: list[int]) -> Iterator[list[int]]:
    """把主键集合切成适合 SQL IN 查询的小批次。"""
    for start in range(0, len(values), _BATCH_SIZE):
        yield values[start:start + _BATCH_SIZE]


def _row_identity(row) -> tuple:
    """构造下载文件记录的业务身份。"""
    return (
        row["downloader"],
        row["download_hash"],
        row["fullpath"],
    )


def upgrade() -> None:
    """删除重复下载文件行，并把组内删除墓碑合并到保留行。"""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "downloadfiles" not in inspector.get_table_names():
        return

    download_files = sa.table(
        "downloadfiles",
        sa.column("id", sa.Integer()),
        sa.column("downloader", sa.String()),
        sa.column("download_hash", sa.String()),
        sa.column("fullpath", sa.String()),
        sa.column("state", sa.Integer()),
    )
    rows = connection.execute(
        sa.select(download_files).order_by(download_files.c.id)
    ).mappings().all()

    canonical_ids = {}
    tombstone_keys = set()
    row_keys = {}
    for row in rows:
        key = _row_identity(row)
        if not key[1] or not key[2]:
            continue
        row_keys[row["id"]] = key
        canonical_ids.setdefault(key, row["id"])
        if row["state"] == 0:
            tombstone_keys.add(key)

    delete_ids = []
    tombstone_ids = []
    for row in rows:
        key = row_keys.get(row["id"])
        if key is None:
            continue
        if row["id"] != canonical_ids[key]:
            delete_ids.append(row["id"])
        elif key in tombstone_keys and row["state"] != 0:
            tombstone_ids.append(row["id"])

    for batch in _batched(tombstone_ids):
        connection.execute(
            download_files.update()
            .where(download_files.c.id.in_(batch))
            .values(state=0)
        )
    for batch in _batched(delete_ids):
        connection.execute(
            download_files.delete()
            .where(download_files.c.id.in_(batch))
        )


def downgrade() -> None:
    """重复行属于错误数据，删除后无法按原主键恢复。"""
    return None

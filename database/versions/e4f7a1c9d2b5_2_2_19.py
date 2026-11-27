"""2.2.19
为系统配置键补唯一索引

Revision ID: e4f7a1c9d2b5
Revises: d9e5a2c4f718
Create Date: 2026-11-27
"""

from alembic import op
import sqlalchemy as sa


revision = "e4f7a1c9d2b5"
down_revision = "d9e5a2c4f718"
branch_labels = None
depends_on = None

_TABLE_NAME = "systemconfig"
_INDEX_NAME = "ix_systemconfig_key"


def _key_index(inspector: sa.Inspector):
    """返回系统配置键上的现有索引。"""
    if _TABLE_NAME not in inspector.get_table_names():
        return None
    for index in inspector.get_indexes(_TABLE_NAME):
        if index.get("column_names") == ["key"]:
            return index
    return None


def _assert_no_duplicate_keys() -> None:
    """发现重复配置键时停止迁移，避免在未经确认时删除任何配置。"""
    connection = op.get_bind()
    duplicates = connection.execute(
        sa.text(
            f"SELECT key FROM {_TABLE_NAME} GROUP BY key HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if duplicates:
        raise RuntimeError(
            f"SystemConfig 存在 {len(duplicates)} 个重复配置键，请先人工确认并清理后再升级"
        )


def upgrade() -> None:
    """把系统配置键索引升级为唯一索引。"""
    inspector = sa.inspect(op.get_bind())
    if _TABLE_NAME not in inspector.get_table_names():
        return
    index = _key_index(inspector)
    if index and index.get("unique"):
        return
    _assert_no_duplicate_keys()
    if index:
        op.drop_index(index["name"], table_name=_TABLE_NAME)
    op.create_index(_INDEX_NAME, _TABLE_NAME, ["key"], unique=True)


def downgrade() -> None:
    """恢复系统配置键的普通索引。"""
    inspector = sa.inspect(op.get_bind())
    index = _key_index(inspector)
    if not index:
        return
    op.drop_index(index["name"], table_name=_TABLE_NAME)
    if index.get("unique"):
        op.create_index(_INDEX_NAME, _TABLE_NAME, ["key"])

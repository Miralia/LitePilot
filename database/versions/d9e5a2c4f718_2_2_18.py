"""2.2.18
为整理历史目标路径补索引

Revision ID: d9e5a2c4f718
Revises: c8f4a1d7e293
Create Date: 2026-11-27
"""

from alembic import op
import sqlalchemy as sa


revision = "d9e5a2c4f718"
down_revision = "c8f4a1d7e293"
branch_labels = None
depends_on = None

_INDEX_NAME = "ix_transferhistory_dest"
_TABLE_NAME = "transferhistory"


def _has_index(inspector: sa.Inspector) -> bool:
    """检查整理历史表是否已存在目标路径索引。"""
    if _TABLE_NAME not in inspector.get_table_names():
        return False
    return any(
        index["name"] == _INDEX_NAME
        for index in inspector.get_indexes(_TABLE_NAME)
    )


def upgrade() -> None:
    """创建目标路径索引，避免按媒体库现址反查时扫描全部整理历史。"""
    inspector = sa.inspect(op.get_bind())
    if _TABLE_NAME in inspector.get_table_names() and not _has_index(inspector):
        op.create_index(_INDEX_NAME, _TABLE_NAME, ["dest"])


def downgrade() -> None:
    """删除整理历史目标路径索引。"""
    inspector = sa.inspect(op.get_bind())
    if _has_index(inspector):
        op.drop_index(_INDEX_NAME, table_name=_TABLE_NAME)

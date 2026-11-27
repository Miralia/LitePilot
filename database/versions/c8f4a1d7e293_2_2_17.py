"""2.2.17
为下载文件索引补下载器复合索引

Revision ID: c8f4a1d7e293
Revises: b9d6f3a2c1e8
Create Date: 2026-11-27
"""

from alembic import op
import sqlalchemy as sa


revision = "c8f4a1d7e293"
down_revision = "b9d6f3a2c1e8"
branch_labels = None
depends_on = None

_INDEX_NAME = "ix_downloadfiles_downloader_hash"
_TABLE_NAME = "downloadfiles"


def _has_index(inspector: sa.Inspector) -> bool:
    """检查下载文件表是否已存在下载器复合索引。"""
    if _TABLE_NAME not in inspector.get_table_names():
        return False
    return any(
        index["name"] == _INDEX_NAME
        for index in inspector.get_indexes(_TABLE_NAME)
    )


def upgrade() -> None:
    """创建下载器与种子 Hash 复合索引，避免按下载器清理时扫描全部记录。"""
    inspector = sa.inspect(op.get_bind())
    if _TABLE_NAME in inspector.get_table_names() and not _has_index(inspector):
        op.create_index(
            _INDEX_NAME,
            _TABLE_NAME,
            ["downloader", "download_hash"],
        )


def downgrade() -> None:
    """删除下载器与种子 Hash 复合索引。"""
    inspector = sa.inspect(op.get_bind())
    if _has_index(inspector):
        op.drop_index(_INDEX_NAME, table_name=_TABLE_NAME)

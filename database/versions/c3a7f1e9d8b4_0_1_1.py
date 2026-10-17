"""0.1.1
删除 AniList 相关列

Revision ID: c3a7f1e9d8b4
Revises: b1f7c3d9e5a2
Create Date: 2026-10-18

本分支不再集成 AniList：识别只有 TMDB 与 Bangumi 两个数据源，下载与整理历史中
保存 anilistid 已无任何读写方。升级时直接删列与索引；降级仅重建空列，
历史取值无法恢复，因此降级前应先备份数据库。
"""

from alembic import op
import sqlalchemy as sa


revision = "c3a7f1e9d8b4"
down_revision = "b1f7c3d9e5a2"
branch_labels = None
depends_on = None


# 需要删除 anilistid 列的表与对应的索引名（无索引时索引名为 None）
_ANILIST_COLUMNS = [
    ("downloadhistory", "ix_downloadhistory_anilistid"),
    ("downloadfailure", None),
    ("transferhistory", "ix_transferhistory_anilistid"),
]


def upgrade() -> None:
    """删除 anilistid 列及其索引。"""
    with op.batch_alter_table("downloadhistory") as batch_op:
        batch_op.drop_index("ix_downloadhistory_anilistid")
        batch_op.drop_column("anilistid")

    with op.batch_alter_table("downloadfailure") as batch_op:
        batch_op.drop_column("anilistid")

    with op.batch_alter_table("transferhistory") as batch_op:
        batch_op.drop_index("ix_transferhistory_anilistid")
        batch_op.drop_column("anilistid")


def downgrade() -> None:
    """重建 anilistid 列与索引（历史取值无法恢复）。"""
    for table, index_name in _ANILIST_COLUMNS:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("anilistid", sa.Integer(), nullable=True))
            if index_name:
                batch_op.create_index(index_name, ["anilistid"])
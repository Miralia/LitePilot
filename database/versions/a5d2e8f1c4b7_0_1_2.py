# -*- coding: utf-8 -*-
"""移除 PassKey 相关表

PassKey（通行密钥）功能已整体删除，仅保留用户名密码登录，
因此清理对应的数据表。

Revision ID: a5d2e8f1c4b7
Revises: c3a7f1e9d8b4
Create Date: 2026-10-18
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "a5d2e8f1c4b7"
down_revision = "c3a7f1e9d8b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    删除 PassKey 表及其索引。
    """
    op.execute("DROP INDEX IF EXISTS ix_passkey_id")
    op.execute("DROP INDEX IF EXISTS ix_passkey_user_id")
    op.execute("DROP TABLE IF EXISTS passkey")


def downgrade() -> None:
    """
    恢复 PassKey 表结构。

    仅还原表与索引骨架，历史凭证数据无法恢复——PassKey 记录本身已随功能删除。
    """
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS passkey (
            id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            credential_id VARCHAR NOT NULL,
            public_key TEXT NOT NULL,
            sign_count INTEGER NOT NULL DEFAULT 0,
            transports VARCHAR,
            name VARCHAR,
            created_at DATETIME,
            last_used_at DATETIME,
            PRIMARY KEY (id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_passkey_id ON passkey (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_passkey_user_id ON passkey (user_id)")

"""2.1.1

Revision ID: 279a949d81b6
Revises: ca5461f314f2
Create Date: 2025-02-14 19:02:24.989349

"""

# revision identifiers, used by Alembic.
revision = '279a949d81b6'
down_revision = 'ca5461f314f2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """历史上用于清理种子缓存，种子缓存能力已删除，此处保留空迁移。"""


def downgrade() -> None:
    pass

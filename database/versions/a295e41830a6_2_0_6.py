"""2.0.6

Revision ID: a295e41830a6
Revises: ecf3c693fdf3
Create Date: 2024-11-14 12:49:13.838120

"""

# revision identifiers, used by Alembic.
revision = 'a295e41830a6'
down_revision = 'ecf3c693fdf3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """保留迁移版本号；AList 已移除，全新安装不再初始化该存储。"""
    return


def downgrade() -> None:
    pass

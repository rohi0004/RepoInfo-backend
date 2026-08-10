"""make repository analysis timestamp timezone aware

Revision ID: 4692b487b2b4
Revises: 4e921dfc2cd7
Create Date: 2026-08-09 01:11:41.845804

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '4692b487b2b4'
down_revision: Union[str, None] = '4e921dfc2cd7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "repositories",
        "last_analyzed_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    op.alter_column(
        "repositories",
        "last_analyzed_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=True,
    )
    # ### end Alembic commands ###

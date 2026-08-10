"""fix timezone aware processing timestamps

Revision ID: 4e921dfc2cd7
Revises: 0001_initial_schema
Create Date: 2026-08-09 00:59:16.562916

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '4e921dfc2cd7'
down_revision: Union[str, None] = '0001_initial_schema'
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

def downgrade() -> None:
    op.alter_column(
        "repositories",
        "last_analyzed_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=True,
    )
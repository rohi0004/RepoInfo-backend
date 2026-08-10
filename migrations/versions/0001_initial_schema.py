"""Initial schema.

Creates every table from `Base.metadata`. Native Postgres ENUM types are created
automatically as a side-effect of `metadata.create_all()`, and their identity is
controlled by our `pg_enum(...)` helper. Downgrade drops everything the same way.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

from app.database.base import Base
from app.models import *  # noqa: F401,F403

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)

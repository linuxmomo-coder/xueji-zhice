"""v0.2 security baseline and learning loop.

Revision ID: 0001_v020
Revises:
Create Date: 2026-07-15

This is the initial baseline migration. It may create a fresh schema, but it is
intentionally irreversible because dropping the baseline would destroy all
production data. Later schema changes must use explicit Alembic operations.
"""
from __future__ import annotations

from alembic import op

from app import models  # noqa: F401
from app.db.session import Base

revision = "0001_v020"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    raise RuntimeError(
        "0001_v020 is an irreversible production baseline; restore from backup instead"
    )

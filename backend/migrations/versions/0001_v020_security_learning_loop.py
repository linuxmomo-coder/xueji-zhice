"""v0.2 security baseline and learning loop

Revision ID: 0001_v020
Revises:
Create Date: 2026-07-15
"""
from __future__ import annotations

from alembic import op

from app.db.session import Base
from app import models  # noqa: F401

revision = "0001_v020"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())

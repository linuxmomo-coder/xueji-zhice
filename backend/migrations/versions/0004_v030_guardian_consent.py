"""Add guardian consent records.

Revision ID: 0004_v030_guardian_consent
Revises: 0003_v030_parser_profile
Create Date: 2026-07-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_v030_guardian_consent"
down_revision = "0003_v030_parser_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guardian_consents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("guardian_user_id", sa.String(length=36), nullable=False),
        sa.Column("family_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=True),
        sa.Column("terms_version", sa.String(length=40), nullable=False),
        sa.Column("privacy_version", sa.String(length=40), nullable=False),
        sa.Column("child_policy_version", sa.String(length=40), nullable=False),
        sa.Column("consent_scope", sa.JSON(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["guardian_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_guardian_consents_guardian_user_id", "guardian_consents", ["guardian_user_id"])
    op.create_index("ix_guardian_consents_family_id", "guardian_consents", ["family_id"])
    op.create_index("ix_guardian_consents_student_id", "guardian_consents", ["student_id"])
    op.create_index("ix_guardian_consents_accepted_at", "guardian_consents", ["accepted_at"])
    op.create_index("ix_guardian_consents_revoked_at", "guardian_consents", ["revoked_at"])


def downgrade() -> None:
    op.drop_index("ix_guardian_consents_revoked_at", table_name="guardian_consents")
    op.drop_index("ix_guardian_consents_accepted_at", table_name="guardian_consents")
    op.drop_index("ix_guardian_consents_student_id", table_name="guardian_consents")
    op.drop_index("ix_guardian_consents_family_id", table_name="guardian_consents")
    op.drop_index("ix_guardian_consents_guardian_user_id", table_name="guardian_consents")
    op.drop_table("guardian_consents")

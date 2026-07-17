"""Expand AI reports into auditable asynchronous jobs.

Revision ID: 0008_v030_ai_report_jobs
Revises: 0007_v030_ocr_jobs
Create Date: 2026-07-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_v030_ai_report_jobs"
down_revision = "0007_v030_ocr_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_reports", sa.Column("requested_by_user_id", sa.String(length=36), nullable=True))
    op.add_column("ai_reports", sa.Column("prompt_version", sa.String(length=40), nullable=False, server_default="learning-report-v1"))
    op.add_column("ai_reports", sa.Column("generation_key", sa.String(length=64), nullable=True))
    op.add_column("ai_reports", sa.Column("evidence_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("ai_reports", sa.Column("usage_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("ai_reports", sa.Column("error_code", sa.String(length=80), nullable=True))
    op.add_column("ai_reports", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("ai_reports", sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ai_reports", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ai_reports", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_ai_reports_requested_by_user_id",
        "ai_reports",
        "users",
        ["requested_by_user_id"],
        ["id"],
    )
    op.create_index("ix_ai_reports_requested_by_user_id", "ai_reports", ["requested_by_user_id"])
    op.create_index("ix_ai_reports_report_type", "ai_reports", ["report_type"])
    op.create_index("ix_ai_reports_generation_key", "ai_reports", ["generation_key"], unique=True)
    op.create_index("ix_ai_reports_queued_at", "ai_reports", ["queued_at"])
    op.execute("UPDATE ai_reports SET status = 'completed' WHERE status IS NULL OR status = ''")
    op.execute("UPDATE ai_reports SET provider = 'rules' WHERE provider IS NULL OR provider = ''")
    op.execute("UPDATE ai_reports SET model = 'rules-v1' WHERE model IS NULL OR model = ''")


def downgrade() -> None:
    op.drop_index("ix_ai_reports_queued_at", table_name="ai_reports")
    op.drop_index("ix_ai_reports_generation_key", table_name="ai_reports")
    op.drop_index("ix_ai_reports_report_type", table_name="ai_reports")
    op.drop_index("ix_ai_reports_requested_by_user_id", table_name="ai_reports")
    op.drop_constraint("fk_ai_reports_requested_by_user_id", "ai_reports", type_="foreignkey")
    op.drop_column("ai_reports", "finished_at")
    op.drop_column("ai_reports", "started_at")
    op.drop_column("ai_reports", "queued_at")
    op.drop_column("ai_reports", "error_message")
    op.drop_column("ai_reports", "error_code")
    op.drop_column("ai_reports", "usage_json")
    op.drop_column("ai_reports", "evidence_snapshot")
    op.drop_column("ai_reports", "generation_key")
    op.drop_column("ai_reports", "prompt_version")
    op.drop_column("ai_reports", "requested_by_user_id")

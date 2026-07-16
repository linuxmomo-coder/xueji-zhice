"""Add asynchronous OCR jobs.

Revision ID: 0007_v030_ocr_jobs
Revises: 0006_v030_question_admin
Create Date: 2026-07-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_v030_ocr_jobs"
down_revision = "0006_v030_question_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ocr_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["document_id"], ["learning_documents.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ocr_jobs_document_id", "ocr_jobs", ["document_id"])
    op.create_index("ix_ocr_jobs_provider", "ocr_jobs", ["provider"])
    op.create_index("ix_ocr_jobs_status", "ocr_jobs", ["status"])
    op.create_index("ix_ocr_jobs_queued_at", "ocr_jobs", ["queued_at"])


def downgrade() -> None:
    op.drop_index("ix_ocr_jobs_queued_at", table_name="ocr_jobs")
    op.drop_index("ix_ocr_jobs_status", table_name="ocr_jobs")
    op.drop_index("ix_ocr_jobs_provider", table_name="ocr_jobs")
    op.drop_index("ix_ocr_jobs_document_id", table_name="ocr_jobs")
    op.drop_table("ocr_jobs")

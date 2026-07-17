"""Add question import batches, source records and reviews.

Revision ID: 0006_v030_question_admin
Revises: 0005_v030_account_tokens
Create Date: 2026-07-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_v030_question_admin"
down_revision = "0005_v030_account_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "question_sources",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("source_name", sa.String(length=200), nullable=True),
        sa.Column("source_reference", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("copyright_status", sa.String(length=30), nullable=False),
        sa.Column("license_name", sa.String(length=120), nullable=True),
        sa.Column("authorization_reference", sa.Text(), nullable=True),
        sa.Column("review_status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_question_sources_source_type", "question_sources", ["source_type"])
    op.create_index("ix_question_sources_copyright_status", "question_sources", ["copyright_status"])
    op.create_index("ix_question_sources_review_status", "question_sources", ["review_status"])

    op.add_column("questions", sa.Column("source_id", sa.String(length=36), nullable=True))
    op.create_foreign_key("fk_questions_source_id", "questions", "question_sources", ["source_id"], ["id"])
    op.create_index("ix_questions_source_id", "questions", ["source_id"])

    op.create_table(
        "question_import_batches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("uploaded_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("import_mode", sa.String(length=30), nullable=False, server_default="create_or_version"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="validating"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("committed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"]),
    )
    op.create_index("ix_question_import_batches_uploaded_by_user_id", "question_import_batches", ["uploaded_by_user_id"])
    op.create_index("ix_question_import_batches_file_sha256", "question_import_batches", ["file_sha256"])
    op.create_index("ix_question_import_batches_status", "question_import_batches", ["status"])

    op.create_table(
        "question_import_rows",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("sheet_name", sa.String(length=120), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("question_code", sa.String(length=80), nullable=True),
        sa.Column("raw_data", sa.JSON(), nullable=False),
        sa.Column("normalized_data", sa.JSON(), nullable=True),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("question_id", sa.String(length=36), nullable=True),
        sa.Column("question_version_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["batch_id"], ["question_import_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.ForeignKeyConstraint(["question_version_id"], ["question_versions.id"]),
        sa.UniqueConstraint("batch_id", "sheet_name", "row_number", name="uq_question_import_row"),
    )
    op.create_index("ix_question_import_rows_batch_id", "question_import_rows", ["batch_id"])
    op.create_index("ix_question_import_rows_question_code", "question_import_rows", ["question_code"])
    op.create_index("ix_question_import_rows_status", "question_import_rows", ["status"])

    op.create_table(
        "question_reviews",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("question_version_id", sa.String(length=36), nullable=False),
        sa.Column("review_type", sa.String(length=30), nullable=False, server_default="full"),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("reviewer_user_id", sa.String(length=36), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("findings", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["question_version_id"], ["question_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"]),
    )
    op.create_index("ix_question_reviews_question_version_id", "question_reviews", ["question_version_id"])
    op.create_index("ix_question_reviews_review_type", "question_reviews", ["review_type"])
    op.create_index("ix_question_reviews_decision", "question_reviews", ["decision"])
    op.create_index("ix_question_reviews_reviewer_user_id", "question_reviews", ["reviewer_user_id"])


def downgrade() -> None:
    op.drop_index("ix_question_reviews_reviewer_user_id", table_name="question_reviews")
    op.drop_index("ix_question_reviews_decision", table_name="question_reviews")
    op.drop_index("ix_question_reviews_review_type", table_name="question_reviews")
    op.drop_index("ix_question_reviews_question_version_id", table_name="question_reviews")
    op.drop_table("question_reviews")
    op.drop_index("ix_question_import_rows_status", table_name="question_import_rows")
    op.drop_index("ix_question_import_rows_question_code", table_name="question_import_rows")
    op.drop_index("ix_question_import_rows_batch_id", table_name="question_import_rows")
    op.drop_table("question_import_rows")
    op.drop_index("ix_question_import_batches_status", table_name="question_import_batches")
    op.drop_index("ix_question_import_batches_file_sha256", table_name="question_import_batches")
    op.drop_index("ix_question_import_batches_uploaded_by_user_id", table_name="question_import_batches")
    op.drop_table("question_import_batches")
    op.drop_index("ix_questions_source_id", table_name="questions")
    op.drop_constraint("fk_questions_source_id", "questions", type_="foreignkey")
    op.drop_column("questions", "source_id")
    op.drop_index("ix_question_sources_review_status", table_name="question_sources")
    op.drop_index("ix_question_sources_copyright_status", table_name="question_sources")
    op.drop_index("ix_question_sources_source_type", table_name="question_sources")
    op.drop_table("question_sources")

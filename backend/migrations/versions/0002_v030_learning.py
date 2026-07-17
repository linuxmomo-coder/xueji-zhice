"""v0.3 production assets, practice, evidence and audit.

Revision ID: 0002_v030_learning
Revises: 0001_v030_core
Create Date: 2026-07-16
"""
from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    ]


def _guard_production_downgrade() -> None:
    if os.getenv("APP_ENV", "").strip().lower() == "production":
        raise RuntimeError("生产环境禁止直接降级初始基线；请使用向前修复迁移或已验证备份恢复")


revision = "0002_v030_learning"
down_revision = "0001_v030_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "question_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("storage_provider", sa.String(20), nullable=False),
        sa.Column("bucket", sa.String(100), nullable=False),
        sa.Column("object_key", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("alt_text", sa.String(500)),
        sa.Column("source_url", sa.Text()),
        sa.Column("source_metadata", sa.JSON()),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        *_timestamps(),
        sa.UniqueConstraint("object_key", name="uq_question_assets_object_key"),
        sa.UniqueConstraint("sha256", name="uq_question_assets_sha256"),
    )
    op.create_index("ix_question_assets_sha256", "question_assets", ["sha256"], unique=True)
    op.create_index("ix_question_assets_status", "question_assets", ["status"])

    op.create_table(
        "question_version_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("question_version_id", sa.String(36), sa.ForeignKey("question_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("question_assets.id"), nullable=False),
        sa.Column("asset_role", sa.String(40), nullable=False),
        sa.Column("option_key", sa.String(20)),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("display_config", sa.JSON()),
        *_timestamps(),
    )
    op.create_index("ix_question_version_assets_version", "question_version_assets", ["question_version_id"])
    op.create_index("ix_question_version_assets_asset", "question_version_assets", ["asset_id"])

    op.create_table(
        "practice_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("family_id", sa.String(36), sa.ForeignKey("families.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("practice_type", sa.String(40), nullable=False, server_default="subject_drill"),
        sa.Column("subject", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="in_progress"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
    )
    op.create_index("ix_practice_sessions_family", "practice_sessions", ["family_id"])
    op.create_index("ix_practice_sessions_student", "practice_sessions", ["student_id"])
    op.create_index("ix_practice_sessions_subject", "practice_sessions", ["subject"])
    op.create_index("ix_practice_sessions_status", "practice_sessions", ["status"])

    op.create_table(
        "practice_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("practice_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.String(36), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("question_version_id", sa.String(36), sa.ForeignKey("question_versions.id"), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("question_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        *_timestamps(),
        sa.UniqueConstraint("session_id", "sequence_no", name="uq_practice_item_sequence"),
    )
    op.create_index("ix_practice_items_session", "practice_items", ["session_id"])
    op.create_index("ix_practice_items_question", "practice_items", ["question_id"])
    op.create_index("ix_practice_items_version", "practice_items", ["question_version_id"])
    op.create_index("ix_practice_items_status", "practice_items", ["status"])

    op.create_table(
        "attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("practice_item_id", sa.String(36), sa.ForeignKey("practice_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("answer_raw", sa.JSON(), nullable=False),
        sa.Column("answer_normalized", sa.JSON(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hint_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evaluation", sa.JSON(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        *_timestamps(),
        sa.UniqueConstraint("practice_item_id", "attempt_no", name="uq_attempt_number"),
    )
    op.create_index("ix_attempts_item", "attempts", ["practice_item_id"])
    op.create_index("ix_attempts_student", "attempts", ["student_id"])
    op.create_index("ix_attempts_correct", "attempts", ["is_correct"])

    op.create_table(
        "wrong_questions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.String(36), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("first_wrong_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_wrong_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("wrong_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("state", sa.String(40), nullable=False, server_default="new"),
        sa.Column("next_review_at", sa.DateTime(timezone=True)),
        sa.Column("latest_attempt_id", sa.String(36), sa.ForeignKey("attempts.id")),
        *_timestamps(),
        sa.UniqueConstraint("student_id", "question_id", name="uq_student_wrong_question"),
    )
    op.create_index("ix_wrong_questions_student", "wrong_questions", ["student_id"])
    op.create_index("ix_wrong_questions_question", "wrong_questions", ["question_id"])
    op.create_index("ix_wrong_questions_state", "wrong_questions", ["state"])

    op.create_table(
        "learning_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("family_id", sa.String(36), sa.ForeignKey("families.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("file_name", sa.String(240), nullable=False),
        sa.Column("storage_provider", sa.String(30), nullable=False, server_default="local"),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="uploaded"),
        sa.Column("structured_data", sa.JSON()),
        sa.Column("confirmed_data", sa.JSON()),
        sa.Column("confirmed_by_user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.String(500)),
        *_timestamps(),
        sa.UniqueConstraint("student_id", "file_sha256", name="uq_student_document_hash"),
        sa.UniqueConstraint("storage_key", name="uq_learning_documents_storage_key"),
    )
    op.create_index("ix_learning_documents_family", "learning_documents", ["family_id"])
    op.create_index("ix_learning_documents_student", "learning_documents", ["student_id"])
    op.create_index("ix_learning_documents_status", "learning_documents", ["status"])
    op.create_index("ix_learning_documents_hash", "learning_documents", ["file_sha256"])

    op.create_table(
        "ai_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("family_id", sa.String(36), sa.ForeignKey("families.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="completed"),
        sa.Column("provider", sa.String(40), nullable=False, server_default="rules"),
        sa.Column("model", sa.String(80), nullable=False, server_default="rules-v1"),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("output_json", sa.JSON(), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_ai_reports_family", "ai_reports", ["family_id"])
    op.create_index("ix_ai_reports_student", "ai_reports", ["student_id"])
    op.create_index("ix_ai_reports_status", "ai_reports", ["status"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("family_id", sa.String(36), sa.ForeignKey("families.id")),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(36)),
        sa.Column("before_data", sa.JSON()),
        sa.Column("after_data", sa.JSON()),
        sa.Column("request_id", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_audit_actor", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_family", "audit_events", ["family_id"])
    op.create_index("ix_audit_action", "audit_events", ["action"])
    op.create_index("ix_audit_resource", "audit_events", ["resource_type", "resource_id"])
    op.create_index("ix_audit_request", "audit_events", ["request_id"])


def downgrade() -> None:
    _guard_production_downgrade()
    for table in [
        "audit_events", "ai_reports", "learning_documents", "wrong_questions",
        "attempts", "practice_items", "practice_sessions",
        "question_version_assets", "question_assets",
    ]:
        op.drop_table(table)

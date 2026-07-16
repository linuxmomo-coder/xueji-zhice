"""v0.3 production identity and question-bank core.

Revision ID: 0001_v030_core
Revises:
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


revision = "0001_v030_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_status", "users", ["status"])

    op.create_table(
        "families",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("primary_guardian_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        *_timestamps(),
    )
    op.create_index("ix_families_primary_guardian", "families", ["primary_guardian_user_id"])
    op.create_index("ix_families_status", "families", ["status"])

    op.create_table(
        "family_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("family_id", sa.String(36), sa.ForeignKey("families.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relation_type", sa.String(30), nullable=False, server_default="guardian"),
        sa.Column("is_primary_guardian", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("permissions", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("family_id", "user_id", name="uq_family_member"),
    )
    op.create_index("ix_family_members_family_id", "family_members", ["family_id"])
    op.create_index("ix_family_members_user_id", "family_members", ["user_id"])

    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_jti", sa.String(36), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("user_agent", sa.String(300)),
        *_timestamps(),
        sa.UniqueConstraint("token_jti", name="uq_refresh_sessions_jti"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_sessions_hash"),
    )
    op.create_index("ix_refresh_sessions_user_id", "refresh_sessions", ["user_id"])
    op.create_index("ix_refresh_sessions_expires_at", "refresh_sessions", ["expires_at"])

    op.create_table(
        "students",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("family_id", sa.String(36), sa.ForeignKey("families.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), unique=True),
        sa.Column("nickname", sa.String(80), nullable=False),
        sa.Column("birth_date", sa.Date()),
        sa.Column("school_system", sa.String(20), nullable=False, server_default="6-3"),
        sa.Column("current_grade", sa.Integer(), nullable=False),
        sa.Column("current_term", sa.String(60), nullable=False, server_default="第一学期"),
        sa.Column("region", sa.String(80)),
        sa.Column("daily_minutes_limit", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_students_family_id", "students", ["family_id"])
    op.create_index("ix_students_status", "students", ["status"])

    op.create_table(
        "questions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("question_code", sa.String(80), nullable=False),
        sa.Column("subject", sa.String(40), nullable=False),
        sa.Column("base_grade", sa.Integer(), nullable=False),
        sa.Column("lifecycle_status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("current_version_id", sa.String(36)),
        sa.Column("source_type", sa.String(30), nullable=False, server_default="self_built"),
        sa.Column("copyright_status", sa.String(30), nullable=False, server_default="owned"),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("first_published_at", sa.DateTime(timezone=True)),
        sa.Column("suspended_reason", sa.String(200)),
        *_timestamps(),
        sa.UniqueConstraint("question_code", name="uq_questions_code"),
    )
    op.create_index("ix_questions_code", "questions", ["question_code"], unique=True)
    op.create_index("ix_questions_subject_grade", "questions", ["subject", "base_grade"])
    op.create_index("ix_questions_lifecycle", "questions", ["lifecycle_status"])
    op.create_index("ix_questions_current_version", "questions", ["current_version_id"])

    op.create_table(
        "question_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("question_id", sa.String(36), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("display_type", sa.String(40), nullable=False),
        sa.Column("stem_content", sa.JSON(), nullable=False),
        sa.Column("explanation_content", sa.JSON()),
        sa.Column("difficulty", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("cognitive_level", sa.String(30), nullable=False, server_default="application"),
        sa.Column("estimated_seconds", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("scoring_mode", sa.String(30), nullable=False, server_default="rule"),
        sa.Column("total_score", sa.Numeric(8, 2), nullable=False, server_default="1.00"),
        sa.Column("common_errors", sa.JSON()),
        sa.Column("answer_summary", sa.String(500)),
        sa.Column("content_checksum", sa.String(64), nullable=False),
        sa.Column("review_status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("publication_status", sa.String(30), nullable=False, server_default="unpublished"),
        sa.Column("change_summary", sa.Text()),
        sa.Column("reviewed_by_user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint("question_id", "version_no", name="uq_question_version"),
    )
    op.create_index("ix_question_versions_question", "question_versions", ["question_id"])
    op.create_index("ix_question_versions_status", "question_versions", ["review_status", "publication_status"])
    op.create_index("ix_question_versions_checksum", "question_versions", ["content_checksum"])

    op.create_table(
        "question_options",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("question_version_id", sa.String(36), sa.ForeignKey("question_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("option_key", sa.String(20), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_fixed_position", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metadata", sa.JSON()),
        *_timestamps(),
        sa.UniqueConstraint("question_version_id", "option_key", name="uq_question_option"),
    )
    op.create_index("ix_question_options_version", "question_options", ["question_version_id"])

    op.create_table(
        "question_response_fields",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("question_version_id", sa.String(36), sa.ForeignKey("question_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_key", sa.String(40), nullable=False),
        sa.Column("field_type", sa.String(40), nullable=False),
        sa.Column("prompt", sa.String(300)),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("score_weight", sa.Numeric(8, 2), nullable=False, server_default="1.00"),
        sa.Column("input_config", sa.JSON()),
        *_timestamps(),
        sa.UniqueConstraint("question_version_id", "field_key", name="uq_response_field"),
    )
    op.create_index("ix_response_fields_version", "question_response_fields", ["question_version_id"])

    op.create_table(
        "question_answer_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("response_field_id", sa.String(36), sa.ForeignKey("question_response_fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_type", sa.String(40), nullable=False),
        sa.Column("accepted_values", sa.JSON()),
        sa.Column("normalization_profile", sa.String(40)),
        sa.Column("case_sensitive", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("order_sensitive", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_fullwidth_equivalent", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_fraction_decimal_equivalent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("unit", sa.String(40)),
        sa.Column("unit_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("absolute_tolerance", sa.Numeric(20, 10)),
        sa.Column("relative_tolerance", sa.Numeric(20, 10)),
        sa.Column("parser_profile", sa.String(40)),
        sa.Column("parse_failure_action", sa.String(30), nullable=False, server_default="incorrect"),
        sa.Column("rule_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata", sa.JSON()),
        *_timestamps(),
    )
    op.create_index("ix_answer_rules_field", "question_answer_rules", ["response_field_id"])
    op.create_index("ix_answer_rules_type", "question_answer_rules", ["rule_type"])


def downgrade() -> None:
    _guard_production_downgrade()
    for table in [
        "question_answer_rules", "question_response_fields", "question_options",
        "question_versions", "questions", "students", "refresh_sessions",
        "family_members", "families", "users",
    ]:
        op.drop_table(table)

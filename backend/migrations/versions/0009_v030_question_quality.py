"""Add correction, regrade, taxonomy, recommendation and notification tables.

Revision ID: 0009_v030_question_quality
Revises: 0008_v030_ai_report_jobs
Create Date: 2026-07-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_v030_question_quality"
down_revision = "0008_v030_ai_report_jobs"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    ]


def upgrade() -> None:
    op.create_table(
        "question_error_reports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("question_version_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=True),
        sa.Column("reported_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("report_type", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("suggested_answer", sa.Text(), nullable=True),
        sa.Column("affects_scoring_claim", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="submitted"),
        sa.Column("submitted_context", sa.JSON(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.ForeignKeyConstraint(["question_version_id"], ["question_versions.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["reported_by_user_id"], ["users.id"]),
    )
    for name in ("question_id", "question_version_id", "student_id", "reported_by_user_id", "report_type", "status"):
        op.create_index(f"ix_question_error_reports_{name}", "question_error_reports", [name])

    op.create_table(
        "question_correction_reviews",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("reviewer_user_id", sa.String(length=36), nullable=False),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=True),
        sa.Column("correction_payload", sa.JSON(), nullable=True),
        sa.Column("affects_scoring", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("corrected_version_id", sa.String(length=36), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["report_id"], ["question_error_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["corrected_version_id"], ["question_versions.id"]),
    )
    for name in ("report_id", "reviewer_user_id", "decision", "corrected_version_id"):
        op.create_index(f"ix_question_correction_reviews_{name}", "question_correction_reviews", [name])

    op.create_table(
        "answer_regrade_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("old_version_id", sa.String(length=36), nullable=False),
        sa.Column("new_version_id", sa.String(length=36), nullable=False),
        sa.Column("triggered_by_review_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("total_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("changed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("affected_students", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.ForeignKeyConstraint(["old_version_id"], ["question_versions.id"]),
        sa.ForeignKeyConstraint(["new_version_id"], ["question_versions.id"]),
        sa.ForeignKeyConstraint(["triggered_by_review_id"], ["question_correction_reviews.id"]),
    )
    for name in ("question_id", "old_version_id", "new_version_id", "triggered_by_review_id", "status", "queued_at"):
        op.create_index(f"ix_answer_regrade_jobs_{name}", "answer_regrade_jobs", [name])

    op.create_table(
        "question_taxonomy_nodes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("node_type", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("subject", sa.String(length=40), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["parent_id"], ["question_taxonomy_nodes.id"]),
        sa.UniqueConstraint("code", name="uq_question_taxonomy_nodes_code"),
    )
    op.create_index("ix_question_taxonomy_nodes_code", "question_taxonomy_nodes", ["code"], unique=True)
    for name in ("node_type", "name", "parent_id", "subject", "status"):
        op.create_index(f"ix_question_taxonomy_nodes_{name}", "question_taxonomy_nodes", [name])

    op.create_table(
        "question_taxonomy_mappings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("question_version_id", sa.String(length=36), nullable=False),
        sa.Column("taxonomy_node_id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="manual"),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("review_status", sa.String(length=30), nullable=False, server_default="approved"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["question_version_id"], ["question_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["taxonomy_node_id"], ["question_taxonomy_nodes.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("question_version_id", "taxonomy_node_id", name="uq_question_taxonomy_mapping"),
    )
    for name in ("question_version_id", "taxonomy_node_id", "review_status"):
        op.create_index(f"ix_question_taxonomy_mappings_{name}", "question_taxonomy_mappings", [name])

    op.create_table(
        "student_error_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("taxonomy_node_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("incorrect_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consecutive_incorrect", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consecutive_correct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("state", sa.String(length=30), nullable=False, server_default="insufficient_evidence"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_summary", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["taxonomy_node_id"], ["question_taxonomy_nodes.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("student_id", "taxonomy_node_id", name="uq_student_error_profile"),
    )
    for name in ("student_id", "taxonomy_node_id", "state"):
        op.create_index(f"ix_student_error_profiles_{name}", "student_error_profiles", [name])

    op.create_table(
        "question_relations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_question_id", sa.String(length=36), nullable=False),
        sa.Column("target_question_id", sa.String(length=36), nullable=False),
        sa.Column("relation_type", sa.String(length=40), nullable=False),
        sa.Column("strength", sa.Numeric(5, 4), nullable=False, server_default="1.0000"),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="manual"),
        sa.Column("review_status", sa.String(length=30), nullable=False, server_default="approved"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["source_question_id"], ["questions.id"]),
        sa.ForeignKeyConstraint(["target_question_id"], ["questions.id"]),
        sa.UniqueConstraint("source_question_id", "target_question_id", "relation_type", name="uq_question_relation"),
    )
    for name in ("source_question_id", "target_question_id", "relation_type", "review_status"):
        op.create_index(f"ix_question_relations_{name}", "question_relations", [name])

    op.create_table(
        "recommendation_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("source_wrong_question_id", sa.String(length=36), nullable=True),
        sa.Column("recommended_question_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False, server_default="shown"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_wrong_question_id"], ["wrong_questions.id"]),
        sa.ForeignKeyConstraint(["recommended_question_id"], ["questions.id"]),
    )
    for name in ("student_id", "source_wrong_question_id", "recommended_question_id", "state"):
        op.create_index(f"ix_recommendation_events_{name}", "recommendation_events", [name])

    op.create_table(
        "user_notifications",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("family_id", sa.String(length=36), nullable=True),
        sa.Column("notification_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=True),
        sa.Column("resource_id", sa.String(length=36), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"]),
    )
    for name in ("user_id", "family_id", "notification_type", "read_at"):
        op.create_index(f"ix_user_notifications_{name}", "user_notifications", [name])


def downgrade() -> None:
    for table, indexes in [
        ("user_notifications", ("user_id", "family_id", "notification_type", "read_at")),
        ("recommendation_events", ("student_id", "source_wrong_question_id", "recommended_question_id", "state")),
        ("question_relations", ("source_question_id", "target_question_id", "relation_type", "review_status")),
        ("student_error_profiles", ("student_id", "taxonomy_node_id", "state")),
        ("question_taxonomy_mappings", ("question_version_id", "taxonomy_node_id", "review_status")),
        ("question_taxonomy_nodes", ("node_type", "name", "parent_id", "subject", "status")),
        ("answer_regrade_jobs", ("question_id", "old_version_id", "new_version_id", "triggered_by_review_id", "status", "queued_at")),
        ("question_correction_reviews", ("report_id", "reviewer_user_id", "decision", "corrected_version_id")),
        ("question_error_reports", ("question_id", "question_version_id", "student_id", "reported_by_user_id", "report_type", "status")),
    ]:
        for name in reversed(indexes):
            op.drop_index(f"ix_{table}_{name}", table_name=table)
        if table == "question_taxonomy_nodes":
            op.drop_index("ix_question_taxonomy_nodes_code", table_name=table)
        op.drop_table(table)

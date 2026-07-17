from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin, uuid_str


class QuestionErrorReport(Base, TimestampMixin):
    __tablename__ = "question_error_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    question_version_id: Mapped[str] = mapped_column(ForeignKey("question_versions.id"), index=True)
    student_id: Mapped[str | None] = mapped_column(ForeignKey("students.id"), nullable=True, index=True)
    reported_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    report_type: Mapped[str] = mapped_column(String(40), index=True)
    description: Mapped[str] = mapped_column(Text)
    suggested_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    affects_scoring_claim: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(30), default="submitted", index=True)
    submitted_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class QuestionCorrectionReview(Base, TimestampMixin):
    __tablename__ = "question_correction_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    report_id: Mapped[str] = mapped_column(
        ForeignKey("question_error_reports.id", ondelete="CASCADE"), index=True
    )
    reviewer_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    decision: Mapped[str] = mapped_column(String(30), index=True)
    findings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    correction_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    affects_scoring: Mapped[bool] = mapped_column(Boolean, default=False)
    corrected_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("question_versions.id"), nullable=True, index=True
    )


class AnswerRegradeJob(Base, TimestampMixin):
    __tablename__ = "answer_regrade_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    old_version_id: Mapped[str] = mapped_column(ForeignKey("question_versions.id"), index=True)
    new_version_id: Mapped[str] = mapped_column(ForeignKey("question_versions.id"), index=True)
    triggered_by_review_id: Mapped[str | None] = mapped_column(
        ForeignKey("question_correction_reviews.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    total_attempts: Mapped[int] = mapped_column(Integer, default=0)
    processed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    changed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    affected_students: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QuestionTaxonomyNode(Base, TimestampMixin):
    __tablename__ = "question_taxonomy_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    node_type: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("question_taxonomy_nodes.id"), nullable=True, index=True
    )
    subject: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)


class QuestionTaxonomyMapping(Base, TimestampMixin):
    __tablename__ = "question_taxonomy_mappings"
    __table_args__ = (
        UniqueConstraint("question_version_id", "taxonomy_node_id", name="uq_question_taxonomy_mapping"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    question_version_id: Mapped[str] = mapped_column(
        ForeignKey("question_versions.id", ondelete="CASCADE"), index=True
    )
    taxonomy_node_id: Mapped[str] = mapped_column(
        ForeignKey("question_taxonomy_nodes.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(30), default="manual")
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    review_status: Mapped[str] = mapped_column(String(30), default="approved", index=True)


class StudentErrorProfile(Base, TimestampMixin):
    __tablename__ = "student_error_profiles"
    __table_args__ = (
        UniqueConstraint("student_id", "taxonomy_node_id", name="uq_student_error_profile"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    taxonomy_node_id: Mapped[str] = mapped_column(
        ForeignKey("question_taxonomy_nodes.id", ondelete="CASCADE"), index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    incorrect_count: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_incorrect: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_correct: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(30), default="insufficient_evidence", index=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_summary: Mapped[dict] = mapped_column(JSON, default=dict)


class QuestionRelation(Base, TimestampMixin):
    __tablename__ = "question_relations"
    __table_args__ = (
        UniqueConstraint(
            "source_question_id",
            "target_question_id",
            "relation_type",
            name="uq_question_relation",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    source_question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    target_question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    relation_type: Mapped[str] = mapped_column(String(40), index=True)
    strength: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("1.0000"))
    source: Mapped[str] = mapped_column(String(30), default="manual")
    review_status: Mapped[str] = mapped_column(String(30), default="approved", index=True)


class RecommendationEvent(Base, TimestampMixin):
    __tablename__ = "recommendation_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    source_wrong_question_id: Mapped[str | None] = mapped_column(
        ForeignKey("wrong_questions.id"), nullable=True, index=True
    )
    recommended_question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    reason: Mapped[dict] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(30), default="shown", index=True)


class UserNotification(Base, TimestampMixin):
    __tablename__ = "user_notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[str | None] = mapped_column(ForeignKey("families.id"), nullable=True, index=True)
    notification_type: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    resource_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

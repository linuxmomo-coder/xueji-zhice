from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, uuid_str


class Question(Base, TimestampMixin):
    __tablename__ = "questions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    question_code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    subject: Mapped[str] = mapped_column(String(40), index=True)
    base_grade: Mapped[int] = mapped_column(Integer, index=True)
    lifecycle_status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    current_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(30), default="self_built")
    copyright_status: Mapped[str] = mapped_column(String(30), default="owned")
    source_id: Mapped[str | None] = mapped_column(ForeignKey("question_sources.id"), nullable=True, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    first_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    versions: Mapped[list["QuestionVersion"]] = relationship(back_populates="question", cascade="all, delete-orphan")


class QuestionVersion(Base, TimestampMixin):
    __tablename__ = "question_versions"
    __table_args__ = (UniqueConstraint("question_id", "version_no", name="uq_question_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    display_type: Mapped[str] = mapped_column(String(40), index=True)
    stem_content: Mapped[dict] = mapped_column(JSON)
    explanation_content: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    difficulty: Mapped[int] = mapped_column(Integer, default=2, index=True)
    cognitive_level: Mapped[str] = mapped_column(String(30), default="application")
    estimated_seconds: Mapped[int] = mapped_column(Integer, default=120)
    scoring_mode: Mapped[str] = mapped_column(String(30), default="rule")
    total_score: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("1.00"))
    common_errors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    answer_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_checksum: Mapped[str] = mapped_column(String(64), index=True)
    review_status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    publication_status: Mapped[str] = mapped_column(String(30), default="unpublished", index=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    question: Mapped[Question] = relationship(back_populates="versions")
    options: Mapped[list["QuestionOption"]] = relationship(cascade="all, delete-orphan")
    response_fields: Mapped[list["QuestionResponseField"]] = relationship(cascade="all, delete-orphan")


class QuestionOption(Base, TimestampMixin):
    __tablename__ = "question_options"
    __table_args__ = (UniqueConstraint("question_version_id", "option_key", name="uq_question_option"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    question_version_id: Mapped[str] = mapped_column(ForeignKey("question_versions.id", ondelete="CASCADE"), index=True)
    option_key: Mapped[str] = mapped_column(String(20))
    content: Mapped[dict] = mapped_column(JSON)
    sort_order: Mapped[int] = mapped_column(Integer)
    is_fixed_position: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


class QuestionResponseField(Base, TimestampMixin):
    __tablename__ = "question_response_fields"
    __table_args__ = (UniqueConstraint("question_version_id", "field_key", name="uq_response_field"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    question_version_id: Mapped[str] = mapped_column(ForeignKey("question_versions.id", ondelete="CASCADE"), index=True)
    field_key: Mapped[str] = mapped_column(String(40))
    field_type: Mapped[str] = mapped_column(String(40))
    prompt: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    score_weight: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("1.00"))
    input_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rules: Mapped[list["QuestionAnswerRule"]] = relationship(cascade="all, delete-orphan")


class QuestionAnswerRule(Base, TimestampMixin):
    __tablename__ = "question_answer_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    response_field_id: Mapped[str] = mapped_column(ForeignKey("question_response_fields.id", ondelete="CASCADE"), index=True)
    rule_type: Mapped[str] = mapped_column(String(40), index=True)
    accepted_values: Mapped[list | None] = mapped_column(JSON, nullable=True)
    normalization_profile: Mapped[str | None] = mapped_column(String(40), nullable=True)
    case_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    order_sensitive: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_fullwidth_equivalent: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_fraction_decimal_equivalent: Mapped[bool] = mapped_column(Boolean, default=False)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    unit_required: Mapped[bool] = mapped_column(Boolean, default=False)
    absolute_tolerance: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    relative_tolerance: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    parser_profile: Mapped[str | None] = mapped_column(String(40), nullable=True)
    parse_failure_action: Mapped[str] = mapped_column(String(30), default="incorrect")
    rule_version: Mapped[int] = mapped_column(Integer, default=1)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


class QuestionAsset(Base, TimestampMixin):
    __tablename__ = "question_assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    storage_provider: Mapped[str] = mapped_column(String(20))
    bucket: Mapped[str] = mapped_column(String(100))
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    alt_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)


class QuestionVersionAsset(Base, TimestampMixin):
    __tablename__ = "question_version_assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    question_version_id: Mapped[str] = mapped_column(ForeignKey("question_versions.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("question_assets.id"), index=True)
    asset_role: Mapped[str] = mapped_column(String(40))
    option_key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    display_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

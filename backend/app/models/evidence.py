from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin, utc_now, uuid_str


class LearningDocument(Base, TimestampMixin):
    __tablename__ = "learning_documents"
    __table_args__ = (UniqueConstraint("student_id", "file_sha256", name="uq_student_document_hash"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    family_id: Mapped[str] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    uploaded_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(40), index=True)
    file_name: Mapped[str] = mapped_column(String(240))
    storage_provider: Mapped[str] = mapped_column(String(30), default="local")
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    file_sha256: Mapped[str] = mapped_column(String(64), index=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(40), default="uploaded", index=True)
    structured_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confirmed_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confirmed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class AIReport(Base, TimestampMixin):
    __tablename__ = "ai_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    family_id: Mapped[str] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    requested_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    report_type: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    provider: Mapped[str] = mapped_column(String(40), default="pending")
    model: Mapped[str] = mapped_column(String(120), default="pending")
    prompt_version: Mapped[str] = mapped_column(String(40), default="learning-report-v1")
    generation_key: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    usage_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    family_id: Mapped[str | None] = mapped_column(ForeignKey("families.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    resource_type: Mapped[str] = mapped_column(String(80), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    before_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

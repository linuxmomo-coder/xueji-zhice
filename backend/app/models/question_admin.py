from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, uuid_str


class QuestionSource(Base, TimestampMixin):
    __tablename__ = "question_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    source_type: Mapped[str] = mapped_column(String(30), index=True)
    source_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    copyright_status: Mapped[str] = mapped_column(String(30), index=True)
    license_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    authorization_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


class QuestionImportBatch(Base, TimestampMixin):
    __tablename__ = "question_import_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    uploaded_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    file_sha256: Mapped[str] = mapped_column(String(64), index=True)
    import_mode: Mapped[str] = mapped_column(String(30), default="create_or_version")
    status: Mapped[str] = mapped_column(String(30), default="validating", index=True)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    warning_rows: Mapped[int] = mapped_column(Integer, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, default=0)
    committed_rows: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rows: Mapped[list["QuestionImportRow"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class QuestionImportRow(Base, TimestampMixin):
    __tablename__ = "question_import_rows"
    __table_args__ = (
        UniqueConstraint("batch_id", "sheet_name", "row_number", name="uq_question_import_row"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("question_import_batches.id", ondelete="CASCADE"), index=True
    )
    sheet_name: Mapped[str] = mapped_column(String(120))
    row_number: Mapped[int] = mapped_column(Integer)
    question_code: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    raw_data: Mapped[dict] = mapped_column(JSON)
    normalized_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    question_id: Mapped[str | None] = mapped_column(ForeignKey("questions.id"), nullable=True)
    question_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("question_versions.id"), nullable=True
    )
    batch: Mapped[QuestionImportBatch] = relationship(back_populates="rows")


class QuestionReview(Base, TimestampMixin):
    __tablename__ = "question_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    question_version_id: Mapped[str] = mapped_column(
        ForeignKey("question_versions.id", ondelete="CASCADE"), index=True
    )
    review_type: Mapped[str] = mapped_column(String(30), default="full", index=True)
    decision: Mapped[str] = mapped_column(String(30), index=True)
    reviewer_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings: Mapped[dict | None] = mapped_column(JSON, nullable=True)

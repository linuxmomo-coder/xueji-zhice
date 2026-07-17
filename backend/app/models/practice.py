from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, utc_now, uuid_str


class PracticeSession(Base, TimestampMixin):
    __tablename__ = "practice_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    family_id: Mapped[str] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    practice_type: Mapped[str] = mapped_column(String(40), default="targeted")
    subject: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(40), default="in_progress", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    items: Mapped[list["PracticeItem"]] = relationship(cascade="all, delete-orphan")


class PracticeItem(Base, TimestampMixin):
    __tablename__ = "practice_items"
    __table_args__ = (UniqueConstraint("session_id", "sequence_no", name="uq_practice_item_sequence"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    session_id: Mapped[str] = mapped_column(ForeignKey("practice_sessions.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    question_version_id: Mapped[str] = mapped_column(ForeignKey("question_versions.id"), index=True)
    sequence_no: Mapped[int] = mapped_column(Integer)
    question_snapshot: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    attempts: Mapped[list["Attempt"]] = relationship(cascade="all, delete-orphan")


class Attempt(Base, TimestampMixin):
    __tablename__ = "attempts"
    __table_args__ = (UniqueConstraint("practice_item_id", "attempt_no", name="uq_attempt_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    practice_item_id: Mapped[str] = mapped_column(ForeignKey("practice_items.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    answer_raw: Mapped[dict] = mapped_column(JSON)
    answer_normalized: Mapped[dict] = mapped_column(JSON)
    is_correct: Mapped[bool] = mapped_column(Boolean, index=True)
    score: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"))
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    hint_count: Mapped[int] = mapped_column(Integer, default=0)
    evaluation: Mapped[dict] = mapped_column(JSON, default=dict)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WrongQuestion(Base, TimestampMixin):
    __tablename__ = "wrong_questions"
    __table_args__ = (UniqueConstraint("student_id", "question_id", name="uq_student_wrong_question"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    first_wrong_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_wrong_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    wrong_count: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[str] = mapped_column(String(40), default="new", index=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latest_attempt_id: Mapped[str | None] = mapped_column(ForeignKey("attempts.id"), nullable=True)

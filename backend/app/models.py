from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def uuid_str() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Student(Base, TimestampMixin):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    family_id: Mapped[str] = mapped_column(String(36), index=True, default="demo-family")
    nickname: Mapped[str] = mapped_column(String(80))
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    school_system: Mapped[str] = mapped_column(String(20), default="6-3")
    current_grade: Mapped[int] = mapped_column(Integer)
    current_term: Mapped[str] = mapped_column(String(40), default="第一学期")
    region: Mapped[str | None] = mapped_column(String(80), nullable=True)
    daily_minutes_limit: Mapped[int] = mapped_column(Integer, default=50)

    textbooks: Mapped[list[StudentTextbook]] = relationship(back_populates="student", cascade="all, delete-orphan")


class Textbook(Base, TimestampMixin):
    __tablename__ = "textbooks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    subject: Mapped[str] = mapped_column(String(40), index=True)
    publisher: Mapped[str] = mapped_column(String(120))
    version_name: Mapped[str] = mapped_column(String(120))
    revision_year: Mapped[int] = mapped_column(Integer)
    curriculum_standard_version: Mapped[str] = mapped_column(String(80), default="2022版课程标准")
    grade: Mapped[int] = mapped_column(Integer, index=True)
    volume: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default="active")


class StudentTextbook(Base, TimestampMixin):
    __tablename__ = "student_textbooks"
    __table_args__ = (UniqueConstraint("student_id", "subject", "is_active", name="uq_student_subject_active"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    textbook_id: Mapped[str] = mapped_column(ForeignKey("textbooks.id"), index=True)
    subject: Mapped[str] = mapped_column(String(40), index=True)
    current_unit: Mapped[str | None] = mapped_column(String(120), nullable=True)
    current_chapter: Mapped[str | None] = mapped_column(String(160), nullable=True)
    progress_source: Mapped[str] = mapped_column(String(40), default="parent_confirmed")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    student: Mapped[Student] = relationship(back_populates="textbooks")
    textbook: Mapped[Textbook] = relationship()


class Question(Base, TimestampMixin):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    question_code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    subject: Mapped[str] = mapped_column(String(40), index=True)
    grade: Mapped[int] = mapped_column(Integer, index=True)
    knowledge_point: Mapped[str] = mapped_column(String(160), index=True)
    question_type: Mapped[str] = mapped_column(String(40), default="single_choice")
    difficulty: Mapped[int] = mapped_column(Integer, default=2)
    cognitive_level: Mapped[str] = mapped_column(String(40), default="application")
    stem: Mapped[str] = mapped_column(Text)
    options: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    answer: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(Text)
    hints: Mapped[list | None] = mapped_column(JSON, nullable=True)
    source_type: Mapped[str] = mapped_column(String(40), default="self_built")
    copyright_status: Mapped[str] = mapped_column(String(40), default="owned")
    review_status: Mapped[str] = mapped_column(String(40), default="active", index=True)
    estimated_seconds: Mapped[int] = mapped_column(Integer, default=120)


class LearningDocument(Base, TimestampMixin):
    __tablename__ = "learning_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    uploaded_by_role: Mapped[str] = mapped_column(String(20), default="parent")
    document_type: Mapped[str] = mapped_column(String(40))
    file_name: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(40), default="awaiting_confirmation", index=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ocr_raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confirmed_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PracticeSession(Base, TimestampMixin):
    __tablename__ = "practice_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    practice_type: Mapped[str] = mapped_column(String(40), default="targeted")
    subject: Mapped[str] = mapped_column(String(40))
    knowledge_point: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(40), default="in_progress")
    question_ids: Mapped[list] = mapped_column(JSON, default=list)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    total_count: Mapped[int] = mapped_column(Integer, default=0)


class AIReport(Base, TimestampMixin):
    __tablename__ = "ai_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    report_type: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="completed")
    provider: Mapped[str] = mapped_column(String(40), default="mock")
    model: Mapped[str] = mapped_column(String(80), default="mock-v1")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)

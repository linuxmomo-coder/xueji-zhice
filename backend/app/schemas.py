from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StudentCreate(BaseModel):
    nickname: str = Field(min_length=1, max_length=80)
    birth_date: date | None = None
    school_system: str = "6-3"
    current_grade: int = Field(ge=1, le=12)
    current_term: str = "第一学期"
    region: str | None = None
    daily_minutes_limit: int = Field(default=50, ge=5, le=240)


class StudentRead(ORMModel):
    id: str
    family_id: str
    nickname: str
    birth_date: date | None
    school_system: str
    current_grade: int
    current_term: str
    region: str | None
    daily_minutes_limit: int
    created_at: datetime


class TextbookRead(ORMModel):
    id: str
    subject: str
    publisher: str
    version_name: str
    revision_year: int
    curriculum_standard_version: str
    grade: int
    volume: str
    status: str


class QuestionRead(ORMModel):
    id: str
    question_code: str
    subject: str
    grade: int
    knowledge_point: str
    question_type: str
    difficulty: int
    cognitive_level: str
    stem: str
    options: dict[str, str] | None
    explanation: str
    hints: list[str] | None
    estimated_seconds: int


class OCRDemoRequest(BaseModel):
    student_id: str
    document_type: Literal["score", "comment", "evaluation", "textbook_catalog"] = "score"
    uploaded_by_role: Literal["student", "parent"] = "parent"
    file_name: str = "demo-score.jpg"


class DocumentConfirmRequest(BaseModel):
    confirmed_data: dict[str, Any]


class PracticeDemoRequest(BaseModel):
    student_id: str
    subject: str = "数学"
    knowledge_point: str = "分数应用题"
    question_count: int = Field(default=4, ge=1, le=20)


class ReportDemoRequest(BaseModel):
    student_id: str
    report_type: Literal["student", "parent"] = "parent"


class DashboardResponse(BaseModel):
    role: str
    profile: dict[str, Any]
    metrics: list[dict[str, Any]]
    tasks: list[dict[str, Any]]
    notices: list[dict[str, Any]]

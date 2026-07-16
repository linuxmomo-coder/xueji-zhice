from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class UserRead(ORMModel):
    id: str
    email: str
    role: str
    display_name: str
    status: str


class RegisterParentRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)
    family_name: str = Field(default="我的家庭", min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    role: Literal["parent", "student", "admin"]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
    family_id: str | None


class StudentCreate(BaseModel):
    nickname: str = Field(min_length=1, max_length=80)
    birth_date: date | None = None
    school_system: str = Field(default="6-3", max_length=20)
    current_grade: int = Field(ge=1, le=12)
    current_term: str = Field(default="第一学期", max_length=60)
    region: str | None = Field(default=None, max_length=80)
    daily_minutes_limit: int = Field(default=50, ge=5, le=240)


class StudentRead(ORMModel):
    id: str
    family_id: str
    user_id: str | None
    nickname: str
    birth_date: date | None
    school_system: str
    current_grade: int
    current_term: str
    region: str | None
    daily_minutes_limit: int
    status: str
    created_at: datetime


class StudentAccountCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, min_length=1, max_length=80)


class StudentAccountRead(BaseModel):
    student: StudentRead
    user: UserRead


class QuestionAssetRead(BaseModel):
    id: str
    role: str
    option_key: str | None
    alt_text: str | None
    url: str


class QuestionSummary(BaseModel):
    id: str
    question_code: str
    subject: str
    grade: int
    display_type: str
    difficulty: int
    cognitive_level: str
    stem: dict[str, Any]
    options: list[dict[str, Any]]
    assets: list[QuestionAssetRead] = []
    estimated_seconds: int


class PracticeCreateRequest(BaseModel):
    student_id: str
    subject: str
    practice_type: Literal["diagnostic", "daily", "subject_drill", "targeted", "retest"] = "subject_drill"
    question_count: int = Field(default=3, ge=1, le=20)


class PracticeRead(ORMModel):
    id: str
    student_id: str
    subject: str
    practice_type: str
    status: str
    correct_count: int
    total_count: int
    started_at: datetime
    finished_at: datetime | None


class PracticeItemRead(BaseModel):
    id: str
    sequence_no: int
    status: str
    question: QuestionSummary


class AnswerSubmitRequest(BaseModel):
    practice_item_id: str
    answer: dict[str, Any]
    duration_seconds: int = Field(default=0, ge=0, le=86_400)
    hint_count: int = Field(default=0, ge=0, le=100)


class AnswerResult(BaseModel):
    attempt_id: str
    is_correct: bool
    score: Decimal
    normalized_answer: dict[str, Any]
    feedback: str
    wrong_question_state: str | None = None


class WrongQuestionRead(ORMModel):
    id: str
    student_id: str
    question_id: str
    wrong_count: int
    state: str
    first_wrong_at: datetime
    last_wrong_at: datetime
    next_review_at: datetime | None


class WrongQuestionDetail(BaseModel):
    wrong_question: WrongQuestionRead
    question: QuestionSummary


class DocumentConfirmRequest(BaseModel):
    confirmed_data: dict[str, Any]


class DocumentRead(ORMModel):
    id: str
    family_id: str
    student_id: str
    document_type: str
    file_name: str
    storage_provider: str
    file_sha256: str
    mime_type: str
    status: str
    structured_data: dict[str, Any] | None
    confirmed_data: dict[str, Any] | None
    confirmed_at: datetime | None
    created_at: datetime


class DashboardResponse(BaseModel):
    role: str
    identity: dict[str, Any]
    metrics: list[dict[str, Any]]
    actions: list[dict[str, Any]]
    notices: list[dict[str, Any]]
    generated_at: datetime
    environment: str


class ApiData(BaseModel):
    data: Any
    meta: dict[str, Any] | None = None

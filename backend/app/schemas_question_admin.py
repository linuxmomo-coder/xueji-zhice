from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class QuestionImportBatchRead(ORMModel):
    id: str
    file_name: str
    file_sha256: str
    import_mode: str
    status: str
    total_rows: int
    valid_rows: int
    warning_rows: int
    failed_rows: int
    committed_rows: int
    summary: dict | None
    committed_at: datetime | None
    created_at: datetime


class QuestionImportRowRead(ORMModel):
    id: str
    sheet_name: str
    row_number: int
    question_code: str | None
    normalized_data: dict | None
    errors: list
    warnings: list
    status: str
    question_id: str | None
    question_version_id: str | None


class QuestionReviewRequest(BaseModel):
    decision: Literal["approved", "rejected", "changes_requested"]
    review_type: Literal["full", "content", "answer", "copyright", "technical"] = "full"
    comment: str | None = Field(default=None, max_length=2000)
    findings: dict[str, Any] | None = None
    source_review_status: Literal["approved", "rejected", "pending"] | None = None


class QuestionPublishRequest(BaseModel):
    change_summary: str | None = Field(default=None, max_length=2000)


class QuestionAssetLinkRequest(BaseModel):
    asset_id: str
    asset_role: Literal["stem", "explanation", "option", "attachment"] = "stem"
    option_key: str | None = Field(default=None, max_length=20)
    sort_order: int = Field(default=0, ge=0, le=1000)
    is_required: bool = True
    display_config: dict[str, Any] | None = None

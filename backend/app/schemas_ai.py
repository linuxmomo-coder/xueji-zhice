from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AIReportCreate(BaseModel):
    student_id: str
    report_type: Literal["student_report", "parent_report"]


class AIReportRead(ORMModel):
    id: str
    family_id: str
    student_id: str
    requested_by_user_id: str | None
    report_type: str
    status: str
    provider: str
    model: str
    prompt_version: str
    metrics: dict
    evidence_snapshot: dict
    output_json: dict
    evidence_ids: list
    usage_json: dict
    error_code: str | None
    error_message: str | None
    queued_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

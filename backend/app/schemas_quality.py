from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class QuestionErrorReportCreate(BaseModel):
    student_id: str | None = None
    question_version_id: str | None = None
    report_type: Literal[
        "stem",
        "condition",
        "option",
        "answer",
        "explanation",
        "image",
        "formula",
        "unit",
        "knowledge_mapping",
        "copyright",
        "other",
    ]
    description: str = Field(min_length=5, max_length=3000)
    suggested_answer: str | None = Field(default=None, max_length=2000)
    affects_scoring_claim: bool = False
    submitted_context: dict[str, Any] | None = None


class CorrectionReviewRequest(BaseModel):
    decision: Literal["valid", "invalid", "uncertain"]
    findings: dict[str, Any] | None = None
    correction_payload: dict[str, Any] | None = None
    affects_scoring: bool = False


class TaxonomyNodeCreate(BaseModel):
    code: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    node_type: Literal["family", "template", "skill", "error_pattern", "representation", "prerequisite"]
    name: str = Field(min_length=2, max_length=200)
    parent_id: str | None = None
    subject: str | None = Field(default=None, max_length=40)
    description: str | None = Field(default=None, max_length=2000)


class TaxonomyMappingCreate(BaseModel):
    taxonomy_node_id: str
    source: Literal["manual", "import", "ai"] = "manual"
    confidence: float | None = Field(default=None, ge=0, le=1)
    review_status: Literal["approved", "pending", "rejected"] = "approved"


class QuestionRelationCreate(BaseModel):
    source_question_id: str
    target_question_id: str
    relation_type: Literal["similar", "variant", "easier", "harder", "prerequisite"]
    strength: float = Field(default=1.0, ge=0, le=1)
    source: Literal["manual", "ai", "import"] = "manual"
    review_status: Literal["approved", "pending", "rejected"] = "approved"

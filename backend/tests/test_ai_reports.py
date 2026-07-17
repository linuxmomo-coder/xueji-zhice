from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.errors import ApiError
from app.db.session import SessionLocal
from app.models import AIReport, Student
from app.services.ai_reports import (
    AIOutputError,
    AIProviderError,
    ProviderResult,
    create_report_job,
    process_report_job,
    validate_report_output,
)


class FailingProvider:
    name = "bailian_openai"
    model = "qwen-plus"

    def generate(self, *, system_prompt: str, user_prompt: str) -> ProviderResult:
        assert "只能依据" in system_prompt
        assert "evidence_snapshot" in user_prompt
        raise AIProviderError("主模型暂时不可用")


class ValidProvider:
    name = "hunyuan_openai"
    model = "hunyuan-turbos-latest"

    def __init__(self, evidence_id: str):
        self.evidence_id = evidence_id

    def generate(self, *, system_prompt: str, user_prompt: str) -> ProviderResult:
        assert "不得与其他学生比较" in system_prompt
        assert self.evidence_id in user_prompt
        payload = {
            "summary": "最近一次练习提供了可核验的学习证据，建议继续完成复测。",
            "evidence_overview": [
                {
                    "statement": "已完成至少一次练习。",
                    "confidence": "fact",
                    "evidence_ids": [self.evidence_id],
                }
            ],
            "strengths": [
                {
                    "statement": "能够完成当前练习流程。",
                    "confidence": "possible",
                    "evidence_ids": [self.evidence_id],
                }
            ],
            "improvements": [
                {
                    "statement": "需要结合后续练习确认稳定性。",
                    "confidence": "possible",
                    "evidence_ids": [self.evidence_id],
                }
            ],
            "actions": [
                {
                    "title": "安排一次同科目复测",
                    "reason": "当前证据量较少，需要新增可比较的练习记录。",
                    "priority": "high",
                    "evidence_ids": [self.evidence_id],
                }
            ],
            "limitations": ["当前仅有少量练习证据，不能形成长期趋势结论。"],
        }
        return ProviderResult(
            content=json.dumps(payload, ensure_ascii=False),
            provider=self.name,
            model=self.model,
            usage={"prompt_tokens": 800, "completion_tokens": 260, "total_tokens": 1060},
        )


def _login_parent(client) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "parent@example.com", "password": "Parent123!", "role": "parent"},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _enable_ai_consent_and_complete_practice(client, access_token: str) -> str:
    headers = {"Authorization": f"Bearer {access_token}"}
    policy = client.get("/api/v1/legal/current").json()["data"]
    scope = dict(policy["required_scope"])
    scope["automated_analysis"] = True
    consent = client.post(
        "/api/v1/legal/consents",
        headers=headers,
        json={
            "terms_version": policy["terms_version"],
            "privacy_version": policy["privacy_version"],
            "child_policy_version": policy["child_policy_version"],
            "consent_scope": scope,
        },
    )
    assert consent.status_code == 201, consent.text
    student_id = client.get("/api/v1/students", headers=headers).json()["data"][0]["id"]
    session = client.post(
        "/api/v1/practice-sessions",
        headers=headers,
        json={"student_id": student_id, "subject": "数学", "question_count": 1},
    )
    assert session.status_code == 201, session.text
    session_id = session.json()["data"]["id"]
    item = client.get(f"/api/v1/practice-sessions/{session_id}/next", headers=headers)
    assert item.status_code == 200, item.text
    practice_item = item.json()["data"]
    answer = client.post(
        f"/api/v1/practice-sessions/{session_id}/answers",
        headers=headers,
        json={"practice_item_id": practice_item["id"], "answer": {"selected": ["B"]}},
    )
    assert answer.status_code == 200, answer.text
    return student_id


def test_report_validator_rejects_unknown_evidence() -> None:
    payload = {
        "summary": "测试",
        "evidence_overview": [
            {"statement": "无依据结论", "confidence": "fact", "evidence_ids": ["unknown:1"]}
        ],
        "strengths": [],
        "improvements": [],
        "actions": [],
        "limitations": [],
    }
    with pytest.raises(AIOutputError):
        validate_report_output(payload, ["practice_session:known"])


def test_report_requires_automated_analysis_consent(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_enabled", True)
    auth = _login_parent(client)
    with SessionLocal() as db:
        student = db.scalar(select(Student).limit(1))
        assert student
        with pytest.raises(ApiError) as error:
            create_report_job(
                db,
                student=student,
                requested_by_user_id=auth["user"]["id"],
                report_type="parent_report",
            )
        assert error.value.code == "AI_003"


def test_primary_failure_uses_fallback_and_preserves_evidence(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_enabled", True)
    auth = _login_parent(client)
    student_id = _enable_ai_consent_and_complete_practice(client, auth["access_token"])
    with SessionLocal() as db:
        student = db.get(Student, student_id)
        assert student
        report = create_report_job(
            db,
            student=student,
            requested_by_user_id=auth["user"]["id"],
            report_type="parent_report",
        )
        db.commit()
        report_id = report.id
        practice_evidence = next(
            evidence_id
            for evidence_id in report.evidence_ids
            if evidence_id.startswith("practice_session:")
        )

    result = process_report_job(
        report_id,
        providers=[FailingProvider(), ValidProvider(practice_evidence)],
    )
    assert result == "completed"

    with SessionLocal() as db:
        report = db.get(AIReport, report_id)
        assert report
        assert report.status == "completed"
        assert report.provider == "hunyuan_openai"
        assert report.model == "hunyuan-turbos-latest"
        assert report.usage_json["total_tokens"] == 1060
        assert practice_evidence in report.evidence_ids
        assert report.output_json["actions"][0]["evidence_ids"] == [practice_evidence]
        assert report.evidence_snapshot["student"]["id"] == student_id
        assert report.finished_at is not None

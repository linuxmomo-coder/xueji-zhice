from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal

from app.db.session import SessionLocal
from app.models import Question, QuestionAnswerRule, QuestionResponseField, QuestionVersion, User
from app.services.grading import grade_answer


def _login(client, email="parent@example.com", password="Parent123!", role="parent") -> dict:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password, "role": role})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_practice_creates_snapshot_wrong_record_and_retest(client) -> None:
    auth = _login(client)
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    student_id = client.get("/api/v1/students", headers=headers).json()["data"][0]["id"]
    created = client.post(
        "/api/v1/practice-sessions",
        headers=headers,
        json={"student_id": student_id, "subject": "数学", "question_count": 1, "practice_type": "subject_drill"},
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["data"]["id"]
    item = client.get(f"/api/v1/practice-sessions/{session_id}/next", headers=headers).json()["data"]
    assert item["question"]["grade"] == 8
    answer = client.post(
        f"/api/v1/practice-sessions/{session_id}/answers",
        headers=headers,
        json={"practice_item_id": item["id"], "answer": {"selected": ["A"]}},
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["data"]["is_correct"] is False
    wrong = client.get(f"/api/v1/students/{student_id}/wrong-questions", headers=headers)
    assert wrong.status_code == 200
    wrong_rows = wrong.json()["data"]
    assert len(wrong_rows) == 1
    assert wrong_rows[0]["question"]["question_code"] == item["question"]["question_code"]

    retest = client.post(
        f"/api/v1/students/{student_id}/wrong-questions/{wrong_rows[0]['wrong_question']['id']}/retest",
        headers=headers,
    )
    assert retest.status_code == 201, retest.text
    assert retest.json()["data"]["practice_type"] == "retest"


def test_practice_filters_candidates_by_student_grade(client) -> None:
    with SessionLocal() as db:
        admin = db.query(User).filter(User.role == "admin").first()
        question = Question(
            question_code="MATH-G7-0000",
            subject="数学",
            base_grade=7,
            lifecycle_status="active",
            source_type="self_built",
            copyright_status="owned",
            created_by_user_id=admin.id,
            first_published_at=datetime.now(timezone.utc),
        )
        db.add(question)
        db.flush()
        version = QuestionVersion(
            question_id=question.id,
            version_no=1,
            display_type="fill_blank",
            stem_content={"blocks": [{"type": "text", "value": "七年级专用题"}]},
            difficulty=1,
            cognitive_level="remember",
            estimated_seconds=30,
            scoring_mode="rule",
            total_score=Decimal("1"),
            answer_summary="1",
            content_checksum=hashlib.sha256(b"g7").hexdigest(),
            review_status="approved",
            publication_status="published",
            reviewed_by_user_id=admin.id,
            published_at=datetime.now(timezone.utc),
        )
        db.add(version)
        db.flush()
        question.current_version_id = version.id
        db.commit()

    auth = _login(client)
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    student_id = client.get("/api/v1/students", headers=headers).json()["data"][0]["id"]
    created = client.post(
        "/api/v1/practice-sessions",
        headers=headers,
        json={"student_id": student_id, "subject": "数学", "question_count": 2, "practice_type": "subject_drill"},
    )
    assert created.status_code == 201, created.text
    item = client.get(
        f"/api/v1/practice-sessions/{created.json()['data']['id']}/next",
        headers=headers,
    ).json()["data"]
    assert item["question"]["grade"] == 8
    assert item["question"]["question_code"] != "MATH-G7-0000"


def test_symbolic_equivalence_accepts_root_forms(client) -> None:
    auth = _login(client)
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    student_id = client.get("/api/v1/students", headers=headers).json()["data"][0]["id"]
    created = client.post(
        "/api/v1/practice-sessions",
        headers=headers,
        json={"student_id": student_id, "subject": "数学", "question_count": 2, "practice_type": "subject_drill"},
    ).json()["data"]
    session_id = created["id"]
    first = client.get(f"/api/v1/practice-sessions/{session_id}/next", headers=headers).json()["data"]
    client.post(
        f"/api/v1/practice-sessions/{session_id}/answers",
        headers=headers,
        json={"practice_item_id": first["id"], "answer": {"selected": ["B"]}},
    )
    second = client.get(f"/api/v1/practice-sessions/{session_id}/next", headers=headers).json()["data"]
    response = client.post(
        f"/api/v1/practice-sessions/{session_id}/answers",
        headers=headers,
        json={"practice_item_id": second["id"], "answer": {"value": "sqrt(27)"}},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["is_correct"] is True


def test_numeric_rule_handles_fullwidth_fraction_and_required_unit() -> None:
    field = QuestionResponseField(
        question_version_id="v",
        field_key="answer",
        field_type="number",
        sort_order=1,
        score_weight=Decimal("1"),
    )
    field.rules = [
        QuestionAnswerRule(
            response_field_id="f",
            rule_type="numeric_tolerance",
            accepted_values=["0.5°"],
            allow_fullwidth_equivalent=True,
            allow_fraction_decimal_equivalent=True,
            unit="°",
            unit_required=True,
            absolute_tolerance=Decimal("0"),
            relative_tolerance=Decimal("0"),
        )
    ]
    outcome = grade_answer({"value": "１/２°"}, [field], Decimal("1"))
    assert outcome.correct is True
    missing_unit = grade_answer({"value": "1/2"}, [field], Decimal("1"))
    assert missing_unit.correct is False

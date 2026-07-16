from __future__ import annotations

from app.db.session import SessionLocal
from app.models import Student


def _login(
    client,
    email="parent@example.com",
    password="Parent123!",
    role="parent",
) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "role": role},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_practice_creates_snapshot_and_wrong_record(client) -> None:
    auth = _login(client)
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    students = client.get("/api/v1/students", headers=headers).json()["data"]
    student_id = students[0]["id"]
    created = client.post(
        "/api/v1/practice-sessions",
        headers=headers,
        json={"student_id": student_id, "subject": "数学", "question_count": 1},
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["data"]["id"]
    item = client.get(f"/api/v1/practice-sessions/{session_id}/next", headers=headers).json()["data"]
    answer = client.post(
        f"/api/v1/practice-sessions/{session_id}/answers",
        headers=headers,
        json={"practice_item_id": item["id"], "answer": {"selected": ["A"]}},
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["data"]["is_correct"] is False
    wrong = client.get(f"/api/v1/students/{student_id}/wrong-questions", headers=headers)
    assert wrong.status_code == 200
    assert len(wrong.json()["data"]) == 1


def test_practice_never_uses_questions_from_another_grade(client) -> None:
    auth = _login(client)
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    student_id = client.get("/api/v1/students", headers=headers).json()["data"][0]["id"]
    with SessionLocal() as db:
        student = db.get(Student, student_id)
        assert student is not None
        student.current_grade = 7
        db.commit()

    available = client.get("/api/v1/questions/subjects?grade=7", headers=headers)
    assert available.status_code == 200
    assert available.json()["data"] == []

    created = client.post(
        "/api/v1/practice-sessions",
        headers=headers,
        json={"student_id": student_id, "subject": "数学", "question_count": 1},
    )
    assert created.status_code == 404
    assert created.json()["error"]["code"] == "PRACTICE_002"


def test_symbolic_equivalence_accepts_root_forms(client) -> None:
    auth = _login(client)
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    student_id = client.get("/api/v1/students", headers=headers).json()["data"][0]["id"]
    created = client.post(
        "/api/v1/practice-sessions",
        headers=headers,
        json={"student_id": student_id, "subject": "数学", "question_count": 2},
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

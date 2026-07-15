from __future__ import annotations


def login(client, email: str, password: str, role: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "role": role},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_register_parent_and_create_student(client) -> None:
    response = client.post(
        "/api/v1/auth/register/parent",
        json={
            "email": "new-parent@example.com",
            "password": "StrongPass123!",
            "display_name": "新家长",
            "family_name": "新家庭",
        },
    )
    assert response.status_code == 201
    token = response.json()["data"]["access_token"]
    create = client.post(
        "/api/v1/students",
        headers={"Authorization": f"Bearer {token}"},
        json={"nickname": "小新", "current_grade": 8},
    )
    assert create.status_code == 201
    assert create.json()["data"]["family_id"] == response.json()["data"]["family_id"]


def test_cross_family_access_is_forbidden(client) -> None:
    first = client.post(
        "/api/v1/auth/register/parent",
        json={
            "email": "a@example.com",
            "password": "StrongPass123!",
            "display_name": "A",
            "family_name": "A家",
        },
    ).json()["data"]
    second = client.post(
        "/api/v1/auth/register/parent",
        json={
            "email": "b@example.com",
            "password": "StrongPass123!",
            "display_name": "B",
            "family_name": "B家",
        },
    ).json()["data"]
    student = client.post(
        "/api/v1/students",
        headers={"Authorization": f"Bearer {first['access_token']}"},
        json={"nickname": "A学生", "current_grade": 8},
    ).json()["data"]
    forbidden = client.get(
        f"/api/v1/students/{student['id']}",
        headers={"Authorization": f"Bearer {second['access_token']}"},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FAMILY_001"


def test_login_role_must_match_account(client) -> None:
    success = login(client, "parent@example.com", "Parent123!", "parent")
    assert success["user"]["role"] == "parent"

    mismatch = client.post(
        "/api/v1/auth/login",
        json={
            "email": "parent@example.com",
            "password": "Parent123!",
            "role": "admin",
        },
    )
    assert mismatch.status_code == 401
    assert mismatch.json()["error"]["code"] == "AUTH_004"


def test_dashboard_uses_database_counts(client) -> None:
    registered = client.post(
        "/api/v1/auth/register/parent",
        json={
            "email": "dashboard@example.com",
            "password": "StrongPass123!",
            "display_name": "数据家长",
            "family_name": "数据家庭",
        },
    ).json()["data"]
    headers = {"Authorization": f"Bearer {registered['access_token']}"}

    empty_dashboard = client.get("/api/v1/dashboard", headers=headers)
    assert empty_dashboard.status_code == 200
    empty_metrics = {
        item["label"]: item["value"]
        for item in empty_dashboard.json()["data"]["metrics"]
    }
    assert empty_metrics["家庭学生档案"] == 0
    assert empty_metrics["已完成练习"] == 0

    client.post(
        "/api/v1/students",
        headers=headers,
        json={"nickname": "真实学生", "current_grade": 8},
    )
    updated_dashboard = client.get("/api/v1/dashboard", headers=headers)
    updated_metrics = {
        item["label"]: item["value"]
        for item in updated_dashboard.json()["data"]["metrics"]
    }
    assert updated_metrics["家庭学生档案"] == 1
    assert updated_dashboard.json()["data"]["generated_at"]

from __future__ import annotations


def login(client, email: str, password: str, role: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "role": role},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def accept_guardian_consent(client, access_token: str) -> dict:
    policy = client.get("/api/v1/legal/current")
    assert policy.status_code == 200, policy.text
    current = policy.json()["data"]
    response = client.post(
        "/api/v1/legal/consents",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "terms_version": current["terms_version"],
            "privacy_version": current["privacy_version"],
            "child_policy_version": current["child_policy_version"],
            "consent_scope": current["required_scope"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_student_creation_requires_explicit_guardian_consent(client) -> None:
    registered = client.post(
        "/api/v1/auth/register/parent",
        json={
            "email": "consent-parent@example.com",
            "password": "StrongPass123!",
            "display_name": "授权家长",
            "family_name": "授权家庭",
        },
    ).json()["data"]
    headers = {"Authorization": f"Bearer {registered['access_token']}"}

    blocked = client.post(
        "/api/v1/students",
        headers=headers,
        json={"nickname": "未授权学生", "current_grade": 8},
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "LEGAL_005"

    consent = accept_guardian_consent(client, registered["access_token"])
    assert consent["revoked_at"] is None
    created = client.post(
        "/api/v1/students",
        headers=headers,
        json={"nickname": "已授权学生", "current_grade": 8},
    )
    assert created.status_code == 201, created.text


def test_register_parent_create_student_and_student_account(client) -> None:
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
    assert "refresh_token" not in response.json()["data"]
    assert response.cookies.get("xueji_refresh")
    token = response.json()["data"]["access_token"]
    accept_guardian_consent(client, token)
    headers = {"Authorization": f"Bearer {token}"}
    create = client.post(
        "/api/v1/students",
        headers=headers,
        json={"nickname": "小新", "current_grade": 8},
    )
    assert create.status_code == 201
    student = create.json()["data"]
    assert student["family_id"] == response.json()["data"]["family_id"]

    account = client.post(
        f"/api/v1/students/{student['id']}/account",
        headers=headers,
        json={"email": "new-student@example.com", "password": "StudentPass123!"},
    )
    assert account.status_code == 201, account.text
    assert account.json()["data"]["student"]["user_id"]

    student_login = login(client, "new-student@example.com", "StudentPass123!", "student")
    own_rows = client.get(
        "/api/v1/students",
        headers={"Authorization": f"Bearer {student_login['access_token']}"},
    )
    assert own_rows.status_code == 200
    assert [row["id"] for row in own_rows.json()["data"]] == [student["id"]]


def test_refresh_cookie_rotation_and_logout(client) -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "parent@example.com", "password": "Parent123!", "role": "parent"},
    )
    assert login_response.status_code == 200
    original_cookie = login_response.cookies.get("xueji_refresh")
    assert original_cookie
    refreshed = client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["data"]["access_token"]
    rotated_cookie = refreshed.cookies.get("xueji_refresh")
    assert rotated_cookie and rotated_cookie != original_cookie
    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 204


def test_password_change_and_session_management(client) -> None:
    auth = login(client, "student@example.com", "Student123!", "student")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    sessions = client.get("/api/v1/account/sessions", headers=headers)
    assert sessions.status_code == 200, sessions.text
    assert sessions.json()["meta"]["total"] >= 1

    changed = client.post(
        "/api/v1/account/password",
        headers=headers,
        json={
            "current_password": "Student123!",
            "new_password": "StudentPassword456!",
            "revoke_other_sessions": True,
        },
    )
    assert changed.status_code == 204, changed.text

    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": "student@example.com", "password": "Student123!", "role": "student"},
    )
    assert old_login.status_code == 401
    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": "student@example.com", "password": "StudentPassword456!", "role": "student"},
    )
    assert new_login.status_code == 200, new_login.text


def test_cross_family_access_is_forbidden(client) -> None:
    first = client.post(
        "/api/v1/auth/register/parent",
        json={"email": "a@example.com", "password": "StrongPass123!", "display_name": "A", "family_name": "A家"},
    ).json()["data"]
    second = client.post(
        "/api/v1/auth/register/parent",
        json={"email": "b@example.com", "password": "StrongPass123!", "display_name": "B", "family_name": "B家"},
    ).json()["data"]
    accept_guardian_consent(client, first["access_token"])
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
        json={"email": "parent@example.com", "password": "Parent123!", "role": "admin"},
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
    empty_metrics = {item["label"]: item["value"] for item in empty_dashboard.json()["data"]["metrics"]}
    assert empty_metrics["家庭学生档案"] == 0
    assert empty_metrics["已完成练习"] == 0
    assert empty_dashboard.json()["data"]["environment"] == "test"

    accept_guardian_consent(client, registered["access_token"])
    client.post("/api/v1/students", headers=headers, json={"nickname": "真实学生", "current_grade": 8})
    updated_dashboard = client.get("/api/v1/dashboard", headers=headers)
    updated_metrics = {item["label"]: item["value"] for item in updated_dashboard.json()["data"]["metrics"]}
    assert updated_metrics["家庭学生档案"] == 1
    assert updated_dashboard.json()["data"]["generated_at"]

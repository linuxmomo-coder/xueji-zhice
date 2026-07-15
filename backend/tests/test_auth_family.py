from __future__ import annotations


def test_register_parent_and_create_student(client) -> None:
    response = client.post("/api/v1/auth/register/parent", json={
        "email": "new-parent@example.com", "password": "StrongPass123!",
        "display_name": "新家长", "family_name": "新家庭",
    })
    assert response.status_code == 201
    token = response.json()["data"]["access_token"]
    create = client.post("/api/v1/students", headers={"Authorization": f"Bearer {token}"},
                         json={"nickname": "小新", "current_grade": 8})
    assert create.status_code == 201
    assert create.json()["data"]["family_id"] == response.json()["data"]["family_id"]


def test_cross_family_access_is_forbidden(client) -> None:
    first = client.post("/api/v1/auth/register/parent", json={
        "email": "a@example.com", "password": "StrongPass123!", "display_name": "A", "family_name": "A家",
    }).json()["data"]
    second = client.post("/api/v1/auth/register/parent", json={
        "email": "b@example.com", "password": "StrongPass123!", "display_name": "B", "family_name": "B家",
    }).json()["data"]
    student = client.post("/api/v1/students", headers={"Authorization": f"Bearer {first['access_token']}"},
                          json={"nickname": "A学生", "current_grade": 8}).json()["data"]
    forbidden = client.get(f"/api/v1/students/{student['id']}",
                           headers={"Authorization": f"Bearer {second['access_token']}"})
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FAMILY_001"

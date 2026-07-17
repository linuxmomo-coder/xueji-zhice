from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from app.core.config import settings
from app.services import recovery


def _extract_query_token(text: str, key: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("http://") or line.startswith("https://"):
            values = parse_qs(urlparse(line).query).get(key)
            if values:
                return values[0]
    raise AssertionError(f"邮件正文中未找到 {key}")


def test_email_verification_is_single_use_and_unlocks_protected_actions(client, monkeypatch) -> None:
    delivered: list[dict[str, str]] = []

    def fake_send_email(*, recipient: str, subject: str, text: str) -> bool:
        delivered.append({"recipient": recipient, "subject": subject, "text": text})
        return True

    monkeypatch.setattr(recovery, "send_email", fake_send_email)
    monkeypatch.setattr(settings, "require_email_verification", True)
    monkeypatch.setattr(settings, "frontend_public_url", "https://learn.example.test")

    registered = client.post(
        "/api/v1/auth/register/parent",
        json={
            "email": "verify-parent@example.com",
            "password": "StrongPass123!",
            "display_name": "验证家长",
            "family_name": "验证家庭",
        },
    )
    assert registered.status_code == 201, registered.text
    assert registered.json()["data"]["email_verification"]["delivery"] == "sent"
    assert delivered and delivered[-1]["recipient"] == "verify-parent@example.com"
    access_token = registered.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    blocked = client.post(
        "/api/v1/students",
        headers=headers,
        json={"nickname": "未验证学生", "current_grade": 8},
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "AUTH_006"

    raw_token = _extract_query_token(delivered[-1]["text"], "verify_email_token")
    confirmed = client.post(
        "/api/v1/auth/email-verification/confirm",
        json={"token": raw_token},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["verified"] is True

    reused = client.post(
        "/api/v1/auth/email-verification/confirm",
        json={"token": raw_token},
    )
    assert reused.status_code == 400
    assert reused.json()["error"]["code"] == "AUTH_007"

    policy = client.get("/api/v1/legal/current").json()["data"]
    consent = client.post(
        "/api/v1/legal/consents",
        headers=headers,
        json={
            "terms_version": policy["terms_version"],
            "privacy_version": policy["privacy_version"],
            "child_policy_version": policy["child_policy_version"],
            "consent_scope": policy["required_scope"],
        },
    )
    assert consent.status_code == 201, consent.text
    created = client.post(
        "/api/v1/students",
        headers=headers,
        json={"nickname": "已验证学生", "current_grade": 8},
    )
    assert created.status_code == 201, created.text


def test_password_reset_is_generic_single_use_and_revokes_old_password(client, monkeypatch) -> None:
    delivered: list[dict[str, str]] = []

    def fake_send_email(*, recipient: str, subject: str, text: str) -> bool:
        delivered.append({"recipient": recipient, "subject": subject, "text": text})
        return True

    monkeypatch.setattr(recovery, "send_email", fake_send_email)
    monkeypatch.setattr(settings, "frontend_public_url", "https://learn.example.test")

    unknown = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "missing-user@example.com"},
    )
    assert unknown.status_code == 202
    assert unknown.json()["data"] == {"accepted": True}

    existing = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "student@example.com"},
    )
    assert existing.status_code == 202
    assert existing.json()["data"] == {"accepted": True}
    assert delivered and delivered[-1]["recipient"] == "student@example.com"

    raw_token = _extract_query_token(delivered[-1]["text"], "password_reset_token")
    reset = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": raw_token, "new_password": "RecoveredStudent456!"},
    )
    assert reset.status_code == 200, reset.text

    reused = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": raw_token, "new_password": "AnotherPassword789!"},
    )
    assert reused.status_code == 400
    assert reused.json()["error"]["code"] == "AUTH_008"

    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": "student@example.com", "password": "Student123!", "role": "student"},
    )
    assert old_login.status_code == 401
    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": "student@example.com", "password": "RecoveredStudent456!", "role": "student"},
    )
    assert new_login.status_code == 200, new_login.text

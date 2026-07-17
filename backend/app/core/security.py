from __future__ import annotations

import base64
import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt import InvalidTokenError

from app.core.config import Settings, settings

PBKDF2_ITERATIONS = 390_000


class TokenError(ValueError):
    pass


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("密码至少8位")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(expected, actual)
    except (ValueError, TypeError):
        return False


def _create_token(
    *,
    subject: str,
    role: str,
    family_id: str | None,
    token_type: str,
    expires_delta: timedelta,
    config: Settings = settings,
) -> tuple[str, str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + expires_delta
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "family_id": family_id,
        "type": token_type,
        "jti": jti,
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, config.secret_key, algorithm=config.jwt_algorithm)
    return token, jti, expires_at


def create_access_token(subject: str, role: str, family_id: str | None, config: Settings = settings) -> str:
    token, _, _ = _create_token(
        subject=subject,
        role=role,
        family_id=family_id,
        token_type="access",
        expires_delta=timedelta(minutes=config.access_token_minutes),
        config=config,
    )
    return token


def create_refresh_token(
    subject: str, role: str, family_id: str | None, config: Settings = settings
) -> tuple[str, str, datetime]:
    return _create_token(
        subject=subject,
        role=role,
        family_id=family_id,
        token_type="refresh",
        expires_delta=timedelta(days=config.refresh_token_days),
        config=config,
    )


def decode_token(token: str, expected_type: str, config: Settings = settings) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, config.secret_key, algorithms=[config.jwt_algorithm])
    except InvalidTokenError as exc:
        raise TokenError("令牌无效或已过期") from exc
    if payload.get("type") != expected_type:
        raise TokenError("令牌类型错误")
    if not payload.get("sub") or not payload.get("jti"):
        raise TokenError("令牌载荷不完整")
    return payload


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

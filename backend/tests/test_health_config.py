from __future__ import annotations

import pytest

from app.core.config import Settings


def test_health(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["version"] == "0.3.0"


def test_production_fails_with_insecure_defaults() -> None:
    config = Settings(
        app_env="production",
        secret_key="change-me-in-production",
        database_url="sqlite:///prod.db",
        cors_origins="*",
        enable_demo=True,
        auto_create_schema=True,
        enable_api_docs=True,
        storage_provider="local",
        file_storage_path="/tmp/xueji-prod-test",
    )
    with pytest.raises(RuntimeError):
        config.validate_runtime()


def test_production_rejects_incomplete_ai_ocr_configuration() -> None:
    config = Settings(
        app_env="production",
        secret_key="a" * 48,
        database_url="postgresql+psycopg://x:y@db/app",
        postgres_password="strong-db-password",
        cors_origins="https://example.com",
        enable_api_docs=False,
        enable_demo=False,
        seed_demo_data=False,
        auto_create_schema=False,
        storage_provider="s3",
        storage_bucket="private",
        storage_access_key="key",
        storage_secret_key="secret",
        require_email_verification=True,
        email_provider="smtp",
        smtp_host="smtp.example.com",
        smtp_from_email="noreply@example.com",
        frontend_public_url="https://example.com",
        ocr_enabled=True,
        ocr_provider="paddle_http",
        ai_enabled=True,
        ai_primary_provider="bailian_openai",
    )
    with pytest.raises(RuntimeError) as error:
        config.validate_runtime()
    message = str(error.value)
    assert "OCR_SERVICE_URL" in message
    assert "OCR_SERVICE_TOKEN" in message
    assert "DASHSCOPE_API_KEY" in message


def test_production_accepts_complete_ai_ocr_configuration() -> None:
    config = Settings(
        app_env="production",
        secret_key="a" * 48,
        database_url="postgresql+psycopg://x:y@db/app",
        postgres_password="strong-db-password",
        cors_origins="https://example.com",
        enable_api_docs=False,
        enable_demo=False,
        seed_demo_data=False,
        auto_create_schema=False,
        storage_provider="s3",
        storage_bucket="private",
        storage_endpoint_url="https://cos.example.com",
        storage_region="ap-singapore",
        storage_access_key="key",
        storage_secret_key="secret",
        require_email_verification=True,
        email_provider="smtp",
        smtp_host="smtp.example.com",
        smtp_from_email="noreply@example.com",
        frontend_public_url="https://example.com",
        redis_url="redis://redis:6379/0",
        ocr_enabled=True,
        ocr_provider="paddle_http",
        ocr_service_url="https://ocr.example.com/v1/recognize",
        ocr_service_token="ocr-token",
        ai_enabled=True,
        ai_primary_provider="bailian_openai",
        ai_fallback_provider="hunyuan_openai",
        dashscope_api_key="dashscope-token",
        hunyuan_api_key="hunyuan-token",
    )
    config.validate_runtime()


def test_demo_router_is_registered_only_by_explicit_flag(client) -> None:
    response = client.get("/api/v1/demo/accounts")
    assert response.status_code == 200
    assert response.json()["data"]["warning"].startswith("仅用于本地开发")

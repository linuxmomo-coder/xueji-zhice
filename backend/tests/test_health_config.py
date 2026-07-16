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


def test_production_rejects_unimplemented_ai_ocr() -> None:
    config = Settings(
        app_env="production",
        secret_key="a" * 48,
        database_url="postgresql+psycopg://x:y@db/app",
        postgres_password="strong-db-password",
        cors_origins="https://example.com",
        enable_api_docs=False,
        storage_provider="s3",
        storage_bucket="private",
        storage_access_key="key",
        storage_secret_key="secret",
        ocr_enabled=True,
        ai_enabled=True,
    )
    with pytest.raises(RuntimeError, match="尚未交付"):
        config.validate_runtime()


def test_demo_router_is_registered_only_by_explicit_flag(client) -> None:
    response = client.get("/api/v1/demo/accounts")
    assert response.status_code == 200
    assert response.json()["data"]["warning"].startswith("仅用于本地开发")

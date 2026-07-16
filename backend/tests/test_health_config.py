from __future__ import annotations

import pytest

from app.core.config import Settings


def test_health(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["version"] == "0.2.2"


def test_production_fails_with_insecure_defaults() -> None:
    config = Settings(
        app_env="production",
        secret_key="change-me-in-production",
        database_url="sqlite:///prod.db",
        cors_origins="*",
        enable_demo=True,
        auto_create_schema=True,
        file_storage_path="/tmp/xueji-prod-test",
    )
    with pytest.raises(RuntimeError):
        config.validate_runtime()


def test_demo_router_is_registered_only_by_explicit_flag(client) -> None:
    response = client.get("/api/v1/demo/accounts")
    assert response.status_code == 200
    assert response.json()["data"]["warning"].startswith("仅用于本地开发")

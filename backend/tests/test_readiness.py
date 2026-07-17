from __future__ import annotations

import app.main as main_module


class DummyConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, statement):
        assert str(statement) == "SELECT 1"
        return 1


class DummyRedis:
    def ping(self) -> bool:
        return True


def test_readiness_checks_database_and_redis(client, monkeypatch) -> None:
    monkeypatch.setattr(main_module.engine, "connect", lambda: DummyConnection())
    monkeypatch.setattr(main_module.Redis, "from_url", lambda *args, **kwargs: DummyRedis())

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["dependencies"] == "ready"


def test_liveness_does_not_require_dependencies(client) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

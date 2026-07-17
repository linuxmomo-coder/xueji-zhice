from __future__ import annotations

import os

os.environ.update({
    "APP_ENV": "test",
    "DATABASE_URL": "sqlite+pysqlite:///:memory:",
    "SECRET_KEY": "test-secret-key-that-is-long-enough-for-tests",
    "ENABLE_DEMO": "true",
    "AUTO_CREATE_SCHEMA": "true",
    "SEED_DEMO_DATA": "true",
    "FILE_STORAGE_PATH": "/tmp/xueji-test-uploads",
})

import pytest
from fastapi.testclient import TestClient

from app.db.session import Base, engine
from app.main import app


@pytest.fixture()
def client() -> TestClient:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client

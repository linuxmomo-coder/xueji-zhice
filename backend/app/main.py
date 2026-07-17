from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api import (
    account,
    ai_reports,
    auth,
    dashboard,
    demo,
    documents,
    legal,
    practice,
    question_admin,
    question_quality,
    questions,
    students,
)
from app.core.config import settings
from app.core.errors import ApiError, install_error_handlers
from app.core.middleware import RequestContextMiddleware
from app.db.session import Base, SessionLocal, engine
from app.seed import seed_demo_data


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_runtime()
    if settings.auto_create_schema and not settings.is_production:
        Base.metadata.create_all(bind=engine)
    if settings.seed_demo_data and settings.enable_demo and not settings.is_production:
        with SessionLocal() as db:
            seed_demo_data(db)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="学迹智评 v0.3.0：题库质量、勘误重判、OCR与证据化AI学习报告闭环。",
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
    lifespan=lifespan,
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
)
install_error_handlers(app)


def _health_payload() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "xueji-zhice-api",
        "version": settings.app_version,
        "environment": settings.app_env,
    }


@app.get("/health")
@app.get("/health/live")
def health() -> dict[str, str]:
    return _health_payload()


@app.get("/health/ready")
def readiness() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=2,
            socket_timeout=2,
        ).ping()
    except (SQLAlchemyError, RedisError, OSError) as exc:
        raise ApiError(503, "HEALTH_001", "数据库或任务队列尚未就绪") from exc
    return {**_health_payload(), "dependencies": "ready"}


for router in [
    auth.router,
    account.router,
    legal.router,
    dashboard.router,
    students.router,
    questions.router,
    question_admin.router,
    question_quality.router,
    practice.router,
    documents.router,
    ai_reports.router,
]:
    app.include_router(router, prefix=settings.api_prefix)
if settings.enable_demo and not settings.is_production:
    app.include_router(demo.router, prefix=settings.api_prefix)

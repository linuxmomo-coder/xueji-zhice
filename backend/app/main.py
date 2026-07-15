from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, dashboard, demo, documents, practice, questions, students
from app.core.config import settings
from app.core.errors import install_error_handlers
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
    description="学迹智评 v0.2：真实身份与家庭隔离、题库版本、可审计练习判题闭环。",
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


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "xueji-zhice-api",
        "version": settings.app_version,
        "environment": settings.app_env,
    }


for router in [auth.router, dashboard.router, students.router, questions.router, practice.router, documents.router]:
    app.include_router(router, prefix=settings.api_prefix)
if settings.enable_demo and not settings.is_production:
    app.include_router(demo.router, prefix=settings.api_prefix)

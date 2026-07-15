from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


INSECURE_SECRET_VALUES = {
    "change-me",
    "change-me-in-production",
    "replace-with-a-long-random-value",
    "local-development-secret-change-before-production",
}
INSECURE_PASSWORD_VALUES = {"change-me", "password", "123456", "local-dev-password"}


class Settings(BaseSettings):
    app_name: str = "学迹智评 API"
    app_version: str = "0.2.1"
    app_env: str = "development"
    api_prefix: str = "/api/v1"

    secret_key: str = "local-development-secret-change-before-production"
    access_token_minutes: int = Field(default=30, ge=5, le=1440)
    refresh_token_days: int = Field(default=14, ge=1, le=90)
    jwt_algorithm: str = "HS256"

    database_url: str = "sqlite:///./xueji_zhice.db"
    redis_url: str = "redis://redis:6379/0"
    cors_origins: str = "http://localhost:5173,http://localhost"
    file_storage_path: str = "./data/uploads"
    max_upload_mb: int = Field(default=10, ge=1, le=50)

    enable_demo: bool = False
    auto_create_schema: bool = False
    seed_demo_data: bool = False

    postgres_password: str | None = None
    ocr_provider: str = "mock"
    ai_primary_provider: str = "mock"
    ai_fallback_provider: str = "mock"
    dashscope_api_key: str | None = None
    bailian_model: str = "qwen-plus"
    hunyuan_secret_id: str | None = None
    hunyuan_secret_key: str | None = None
    hunyuan_model: str = "hunyuan-turbos-latest"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("app_env")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"development", "test", "staging", "production"}:
            raise ValueError("APP_ENV 必须为 development/test/staging/production")
        return normalized

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    def validate_runtime(self) -> None:
        errors: list[str] = []
        if self.is_production:
            if self.secret_key in INSECURE_SECRET_VALUES or len(self.secret_key) < 32:
                errors.append("生产环境 SECRET_KEY 必须使用长度不少于32位的随机值")
            if self.enable_demo or self.seed_demo_data:
                errors.append("生产环境禁止 ENABLE_DEMO/SEED_DEMO_DATA")
            if self.auto_create_schema:
                errors.append("生产环境禁止 AUTO_CREATE_SCHEMA，必须使用 Alembic")
            if not self.cors_origin_list or "*" in self.cors_origin_list:
                errors.append("生产环境 CORS_ORIGINS 必须填写明确域名，禁止通配符")
            if self.database_url.startswith("sqlite"):
                errors.append("生产环境必须使用 PostgreSQL，禁止 SQLite")
            if self.postgres_password in INSECURE_PASSWORD_VALUES:
                errors.append("生产数据库密码仍为不安全默认值")
        if errors:
            raise RuntimeError("；".join(errors))

        Path(self.file_storage_path).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

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
INSECURE_PASSWORD_VALUES = {"change-me", "password", "123456", "local-dev-password", "CHANGE_ME"}


class Settings(BaseSettings):
    app_name: str = "学迹智评 API"
    app_version: str = "0.3.0"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    enable_api_docs: bool = True

    secret_key: str = "local-development-secret-change-before-production"
    access_token_minutes: int = Field(default=30, ge=5, le=1440)
    refresh_token_days: int = Field(default=14, ge=1, le=90)
    jwt_algorithm: str = "HS256"
    refresh_cookie_name: str = "xueji_refresh"
    cookie_domain: str | None = None
    cookie_samesite: str = "lax"

    database_url: str = "sqlite:///./xueji_zhice.db"
    redis_url: str = "redis://redis:6379/0"
    cors_origins: str = "http://localhost:5173,http://localhost"
    max_upload_mb: int = Field(default=10, ge=1, le=50)

    storage_provider: str = "local"
    file_storage_path: str = "./data/uploads"
    storage_bucket: str | None = None
    storage_endpoint_url: str | None = None
    storage_region: str | None = None
    storage_access_key: str | None = None
    storage_secret_key: str | None = None
    storage_presign_seconds: int = Field(default=300, ge=60, le=3600)

    require_email_verification: bool = False
    email_provider: str = "disabled"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_starttls: bool = True
    frontend_public_url: str = "http://localhost"
    email_verification_hours: int = Field(default=24, ge=1, le=168)
    password_reset_minutes: int = Field(default=30, ge=5, le=120)

    enable_demo: bool = False
    auto_create_schema: bool = False
    seed_demo_data: bool = False

    postgres_password: str | None = None
    ocr_enabled: bool = False
    ocr_provider: str = "disabled"
    ocr_service_url: str | None = None
    ocr_service_token: str | None = None
    ocr_timeout_seconds: int = Field(default=60, ge=5, le=300)
    ocr_queue_name: str = "xueji:ocr:jobs"
    ocr_max_attempts: int = Field(default=3, ge=1, le=10)

    ai_enabled: bool = False
    ai_primary_provider: str = "disabled"
    ai_fallback_provider: str = "disabled"
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

    @field_validator("storage_provider")
    @classmethod
    def normalize_storage_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"local", "s3"}:
            raise ValueError("STORAGE_PROVIDER 必须为 local 或 s3")
        return normalized

    @field_validator("email_provider")
    @classmethod
    def normalize_email_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"disabled", "smtp"}:
            raise ValueError("EMAIL_PROVIDER 必须为 disabled 或 smtp")
        return normalized

    @field_validator("ocr_provider")
    @classmethod
    def normalize_ocr_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"disabled", "paddle_http"}:
            raise ValueError("OCR_PROVIDER 必须为 disabled 或 paddle_http")
        return normalized

    @field_validator("cookie_samesite")
    @classmethod
    def normalize_cookie_samesite(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError("COOKIE_SAMESITE 必须为 lax/strict/none")
        return normalized

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def secure_cookies(self) -> bool:
        return self.app_env in {"staging", "production"}

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
            if self.enable_api_docs:
                errors.append("生产环境必须关闭 ENABLE_API_DOCS")
            if not self.cors_origin_list or "*" in self.cors_origin_list:
                errors.append("生产环境 CORS_ORIGINS 必须填写明确域名，禁止通配符")
            if self.database_url.startswith("sqlite"):
                errors.append("生产环境必须使用 PostgreSQL，禁止 SQLite")
            if not self.postgres_password or self.postgres_password in INSECURE_PASSWORD_VALUES:
                errors.append("生产数据库密码未配置或仍为不安全默认值")
            if self.storage_provider != "s3":
                errors.append("生产环境必须使用 S3 兼容对象存储，禁止本地磁盘存储")
            required_storage = {
                "STORAGE_BUCKET": self.storage_bucket,
                "STORAGE_ACCESS_KEY": self.storage_access_key,
                "STORAGE_SECRET_KEY": self.storage_secret_key,
            }
            missing_storage = [name for name, value in required_storage.items() if not value]
            if missing_storage:
                errors.append(f"对象存储缺少配置：{', '.join(missing_storage)}")
            if not self.require_email_verification:
                errors.append("生产环境必须开启 REQUIRE_EMAIL_VERIFICATION")
            if self.email_provider != "smtp":
                errors.append("生产环境必须配置 SMTP 邮件服务")
            required_email = {
                "SMTP_HOST": self.smtp_host,
                "SMTP_FROM_EMAIL": self.smtp_from_email,
            }
            if self.smtp_username and not self.smtp_password:
                required_email["SMTP_PASSWORD"] = self.smtp_password
            missing_email = [name for name, value in required_email.items() if not value]
            if missing_email:
                errors.append(f"邮件服务缺少配置：{', '.join(missing_email)}")
            if not self.frontend_public_url.startswith("https://"):
                errors.append("生产环境 FRONTEND_PUBLIC_URL 必须使用 HTTPS")
            if self.ocr_enabled:
                if self.ocr_provider != "paddle_http":
                    errors.append("启用OCR时必须配置 OCR_PROVIDER=paddle_http")
                if not self.ocr_service_url or not self.ocr_service_url.startswith("https://"):
                    errors.append("生产OCR服务必须配置HTTPS OCR_SERVICE_URL")
                if not self.ocr_service_token:
                    errors.append("生产OCR服务必须配置 OCR_SERVICE_TOKEN")
                if not self.redis_url:
                    errors.append("启用OCR时必须配置 Redis 队列")
            elif self.ocr_provider != "disabled":
                errors.append("OCR_ENABLED=false 时 OCR_PROVIDER 必须为 disabled")
            if self.ai_enabled:
                errors.append("v0.3.0尚未交付真实AI报告适配器，生产环境必须关闭 AI_ENABLED")

        if errors:
            raise RuntimeError("；".join(errors))

        if self.storage_provider == "local":
            Path(self.file_storage_path).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

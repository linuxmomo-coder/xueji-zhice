from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "学迹智评 API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    secret_key: str = "change-me-in-production"
    database_url: str = "sqlite:///./xueji_zhice.db"
    redis_url: str = "redis://redis:6379/0"
    cors_origins: str = "http://localhost:5173,http://localhost"
    file_storage_path: str = "/data/uploads"
    ocr_provider: str = "mock"
    ai_primary_provider: str = "mock"
    ai_fallback_provider: str = "mock"
    dashscope_api_key: str | None = None
    bailian_model: str = "qwen-plus"
    hunyuan_secret_id: str | None = None
    hunyuan_secret_key: str | None = None
    hunyuan_model: str = "hunyuan-turbos-latest"
    max_upload_mb: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

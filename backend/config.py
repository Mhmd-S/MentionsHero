"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Supabase
    supabase_url: str
    supabase_service_key: str

    # Gemini API
    gemini_api_key: str = ""

    # Replicate API
    replicate_api_token: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8001

    # CORS — set CORS_ORIGINS env var as comma-separated list in production
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

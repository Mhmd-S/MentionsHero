"""Application configuration using pydantic-settings."""

import json
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""

    # Auto-transcription scheduler
    auto_transcription_enabled: bool = True

    # Server
    host: str = "0.0.0.0"
    port: int = 8001

    # Frontend URL — set FRONTEND_URL env var in production
    frontend_url: str = "http://localhost:3000"

    # CORS — set CORS_ORIGINS env var in production, either as a comma-separated
    # list or a JSON array. NoDecode is required: without it pydantic-settings
    # json.loads() the raw env var before the validator below runs, so a
    # comma-separated value raises SettingsError at import and the app never boots.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        """Parse a JSON array or a comma-separated string into a list."""
        if isinstance(v, str):
            text = v.strip()
            if text.startswith("["):
                try:
                    return [str(o).strip() for o in json.loads(text) if str(o).strip()]
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in text.split(",") if origin.strip()]
        return v  # type: ignore[return-value]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

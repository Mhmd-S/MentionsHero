"""Application configuration using pydantic-settings."""

import json
import logging
import re
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

logger = logging.getLogger(__name__)

# https://<project-ref>.supabase.co — Supabase project URLs have no path or port.
_SUPABASE_URL_RE = re.compile(r"https://[a-z0-9-]+\.supabase\.(?:co|in|red)", re.I)


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
    # Only needed on projects still using the legacy symmetric JWT secret
    # (Settings > API > JWT Secret). Projects on asymmetric signing keys verify
    # against the public JWKS endpoint and need nothing here.
    supabase_jwt_secret: str = ""

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

    @field_validator("supabase_url", mode="after")
    @classmethod
    def normalise_supabase_url(cls, v: str) -> str:
        """Repair a SUPABASE_URL that has extra characters glued onto it.

        A deployment once had ~77 stray characters appended to the project URL with no
        separator. Nothing validated it, so the app started happily and then failed at
        the DNS layer on the first query with

            'idna' codec can't encode characters in position 30-108: label too long

        — an error that names neither the setting nor the service, on a request stack
        far away from the cause. Every /api/** route 500'd while /health stayed green,
        because /health is the one endpoint that never touches the database.

        Rather than raise (which would kill the container and put it in a restart
        loop), recover the canonical URL and log loudly enough to be actioned.
        """
        raw = (v or "").strip().strip('"').strip("'")
        if not raw:
            return raw

        match = _SUPABASE_URL_RE.match(raw)
        if match and match.group(0) == raw:
            return raw

        if match:
            logger.error(
                "SUPABASE_URL has %d unexpected trailing characters and would fail DNS "
                "resolution; using %r. Fix the variable on the service.",
                len(raw) - len(match.group(0)),
                match.group(0),
            )
            return match.group(0)

        # Not a recognisable Supabase URL. Say which label is the problem without
        # echoing the value, which may be a secret pasted into the wrong variable.
        host = raw.split("://", 1)[-1].split("/", 1)[0]
        long_labels = [len(part) for part in host.split(".") if len(part) > 63]
        detail = f"; DNS label(s) of length {long_labels} exceed the 63-char limit" if long_labels else ""
        logger.error(
            "SUPABASE_URL is not a valid Supabase project URL (length %d)%s. "
            "Expected https://<project-ref>.supabase.co",
            len(raw),
            detail,
        )
        return raw

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

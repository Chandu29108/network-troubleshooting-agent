"""
Centralised configuration.

Why pydantic-settings: it validates env vars at startup (fail fast if
GOOGLE_API_KEY is missing) instead of failing deep inside a LangGraph node
where it's harder to debug.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    google_api_key: str
    gemini_model: str = "gemini-1.5-flash"
    # Used only when the primary model is down long enough to exhaust its own
    # retry budget (see app/core/resilience.py: invoke_with_retry_and_fallback).
    # A smaller/cheaper tier tends to sit on a separate capacity pool from the
    # main flash model, so it can still be up during a "high demand" 503
    # streak on gemini-1.5-flash -- confirmed against a real production log
    # showing 4 straight retries (~15s) all hitting 503 before giving up.
    gemini_fallback_model: str = "gemini-1.5-flash-8b"

    # Your Clerk instance's issuer URL, e.g. https://your-app-name.clerk.accounts.dev
    # (dev instance) or https://clerk.yourdomain.com (prod, custom domain).
    # Find it in the Clerk dashboard under Configure -> API Keys -> Advanced,
    # or it's the domain embedded in your publishable key.
    clerk_issuer: str

    database_url: str = "sqlite+aiosqlite:///./data/netagent.db"

    chroma_persist_dir: str = "./chroma_store"
    # Gemini's embedding API (not a local model -- see app/rag/ingest.py for why).
    # NOTE: "models/text-embedding-004" (the older naming) 404s against the
    # Gemini Developer API's embedContent endpoint -- confirmed against a real
    # deploy. "gemini-embedding-001" is the current stable model name for this
    # API path (langchain_google_genai's own docs/tests use this or the
    # "-2-preview" variant, never the old "models/..." embedding-004 name).
    embedding_model_name: str = "gemini-embedding-001"

    # Comma-separated in .env, e.g. FRONTEND_ORIGINS=http://localhost:3000,https://app.example.com
    frontend_origins: str = "http://localhost:3000"

    # Empty by default = Sentry disabled (used for local dev / tests, so
    # neither needs a Sentry account). Get a DSN by creating a free project
    # at sentry.io -> Settings -> Projects -> <project> -> Client Keys (DSN).
    sentry_dsn: str = ""
    # Tags errors by environment in the Sentry UI (dev/staging/production)
    # so a local traceback doesn't get mixed in with real production ones.
    environment: str = "development"

    @property
    def frontend_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    # lru_cache => settings are parsed once and reused (cheap, and avoids
    # re-reading .env on every request).
    return Settings()

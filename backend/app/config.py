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

    database_url: str = "sqlite+aiosqlite:///./data/netagent.db"

    chroma_persist_dir: str = "./chroma_store"
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Comma-separated in .env, e.g. FRONTEND_ORIGINS=http://localhost:3000,https://app.example.com
    frontend_origins: str = "http://localhost:3000"

    @property
    def frontend_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    # lru_cache => settings are parsed once and reused (cheap, and avoids
    # re-reading .env on every request).
    return Settings()

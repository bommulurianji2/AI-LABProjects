from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PPSDLC_", extra="ignore")

    database_url: str = f"sqlite:///{BACKEND_DIR / 'pp_sdlc.db'}"
    agent_skills_dir: Path = REPO_ROOT / "03_Agent_Skills"
    templates_dir: Path = REPO_ROOT / "04_Templates"
    generated_artefacts_dir: Path = REPO_ROOT / "05_Generated_Artefacts"
    cors_allowed_origins: list[str] = ["http://localhost:3000"]

    # LLM provider (OpenRouter, OpenAI-compatible) - only required for agents
    # whose manifest declares `runtime: llm`. Set PPSDLC_OPENROUTER_API_KEY in
    # backend/.env; never commit a real key.
    openrouter_api_key: str | None = None
    openrouter_model: str = "anthropic/claude-sonnet-4.5"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    # 기본 설정
    app_name: str = "Health Checkup AI Assistant"
    app_version: str = "0.1.0"
    port: int = 8000

    # Ollama 설정
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout_seconds: float = 120.0

    # 데이터 설정
    data_dir: Path = ROOT / "data" / "patients"


@lru_cache
def get_settings() -> Settings:
    return Settings()

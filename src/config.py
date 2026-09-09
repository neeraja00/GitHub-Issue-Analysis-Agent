"""Application Configuration module using Pydantic Settings."""

import os
from pathlib import Path
from typing import Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # GitHub Settings
    github_token: Optional[str] = Field(default=None, alias="GITHUB_TOKEN")
    github_api_base: str = Field(default="https://api.github.com", alias="GITHUB_API_BASE")
    github_timeout_seconds: float = Field(default=30.0, alias="GITHUB_TIMEOUT_SECONDS")
    github_max_retries: int = Field(default=3, alias="GITHUB_MAX_RETRIES")

    # LLM Provider Configuration
    default_llm_provider: Literal["mock", "gemini", "anthropic", "openai"] = Field(
        default="mock", alias="DEFAULT_LLM_PROVIDER"
    )
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")

    # Default Models
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    claude_model: str = Field(default="claude-3-5-sonnet-20241022", alias="CLAUDE_MODEL")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    # Agent Pipeline Parameters
    default_max_issues: int = Field(default=30, alias="DEFAULT_MAX_ISSUES")
    default_dry_run: bool = Field(default=True, alias="DEFAULT_DRY_RUN")
    similarity_threshold: float = Field(default=0.72, alias="SIMILARITY_THRESHOLD")

    # Paths & Logging
    logs_dir: Path = Field(default_factory=lambda: BASE_DIR / "logs")
    reports_dir: Path = Field(default_factory=lambda: BASE_DIR / "reports")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    def ensure_directories(self) -> None:
        """Ensure necessary output directories exist."""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

# Global settings instance
settings = Settings()
settings.ensure_directories()

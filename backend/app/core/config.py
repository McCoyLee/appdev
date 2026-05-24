from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_log_level: str = "INFO"
    app_env: Literal["dev", "prod"] = "dev"
    cors_origins: str = "*"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    github_token: str = ""
    github_api_base: str = "https://api.github.com"
    test_repo: str = Field(default="", description="owner/name for M0 e2e")

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

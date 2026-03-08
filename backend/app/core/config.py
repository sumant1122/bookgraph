from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="BookGraph API")
    app_env: str = Field(default="development")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)

    openlibrary_base_url: str = Field(default="https://openlibrary.org")

    neo4j_uri: str = Field(default="bolt://neo4j:7687")
    neo4j_username: str = Field(default="neo4j")
    neo4j_password: str = Field(default="bookgraph")

    model_provider: str = Field(default="auto")

    openrouter_api_key: str | None = None
    openrouter_model: str = Field(default="openai/gpt-4o-mini")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")

    ollama_api_key: str | None = None
    ollama_model: str = Field(default="llama3.1:8b")
    ollama_base_url: str = Field(default="http://localhost:11434/v1")

    openai_api_key: str | None = None
    openai_model: str = Field(default="gpt-4o-mini")

    relationship_scan_limit: int = Field(default=20)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator(
        "openrouter_api_key",
        "ollama_api_key",
        "openai_api_key",
        mode="before",
    )
    @classmethod
    def _empty_string_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

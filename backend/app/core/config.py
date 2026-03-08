from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BookGraph API"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    openlibrary_base_url: str = "https://openlibrary.org"

    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "bookgraph"

    llm_provider: str = "openai"
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None

    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    ollama_model: str = "llama3.1:8b"
    ollama_base_url: str = "http://localhost:11434/v1"

    # Backward-compatible aliases
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    relationship_scan_limit: int = 20

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

"""
Central application settings powered by pydantic-settings.

All config is read from environment variables (or a .env file).
Import the singleton `settings` anywhere in the app.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # LLM provider selection: "openai" | "anthropic" | "ollama"
    llm_provider: str = Field("openai", alias="LLM_PROVIDER")

    # OpenAI
    openai_api_key: str = Field("", alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", alias="OPENAI_MODEL")
    openai_model_fallback: str = Field("gpt-4o", alias="OPENAI_MODEL_FALLBACK")

    # Anthropic
    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field("claude-3-5-haiku-20241022", alias="ANTHROPIC_MODEL")

    # Ollama
    ollama_model: str = Field("qwen2.5:0.5b", alias="OLLAMA_MODEL")
    ollama_base_url: str = Field("http://ollama:11434", alias="OLLAMA_BASE_URL")

    # LLM call behaviour
    max_retries: int = Field(3, alias="MAX_RETRIES")
    request_timeout: int = Field(300, alias="REQUEST_TIMEOUT")

    # Feature flags
    demo_mode: bool = Field(True, alias="DEMO_MODE")

    # Session storage
    session_ttl_seconds: int = Field(3600, alias="SESSION_TTL_SECONDS")
    redis_url: str = Field("redis://localhost:6379", alias="REDIS_URL")
    use_redis: bool = Field(True, alias="USE_REDIS")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name": True,
        "extra": "ignore",
    }


settings = Settings()

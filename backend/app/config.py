"""
Central application settings powered by pydantic-settings.

All config is read from environment variables (or a .env file).
Import the singleton `settings` anywhere in the app.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM provider selection: "openai" | "anthropic" | "deepseek" | "ollama"
    llm_provider: str = Field("openai", alias="LLM_PROVIDER")

    # OpenAI
    openai_api_key: str = Field("", alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", alias="OPENAI_MODEL")
    openai_model_fallback: str = Field("gpt-4o", alias="OPENAI_MODEL_FALLBACK")

    # Anthropic
    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field("claude-3-5-haiku-20241022", alias="ANTHROPIC_MODEL")

    # DeepSeek (OpenAI-compatible API)
    deepseek_api_key: str = Field("", alias="DEEPSEEK_API_KEY")
    deepseek_model: str = Field("deepseek-chat", alias="DEEPSEEK_MODEL")
    deepseek_base_url: str = Field("https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")

    # Ollama
    ollama_model: str = Field("qwen2.5:0.5b", alias="OLLAMA_MODEL")
    ollama_base_url: str = Field("http://ollama:11434", alias="OLLAMA_BASE_URL")

    # LLM call behaviour
    max_retries: int = Field(3, alias="MAX_RETRIES")
    request_timeout: int = Field(300, alias="REQUEST_TIMEOUT")

    # Feature flags
    demo_mode: bool = Field(True, alias="DEMO_MODE")

    # Largest number of rows fed to the agent pipeline. The agents compute
    # summary statistics and aggregated charts, so past this point extra
    # rows cost time and memory without changing the conclusions. Set to 0
    # to disable the cap.
    max_analysis_rows: int = Field(250_000, alias="MAX_ANALYSIS_ROWS")

    # Session storage
    session_ttl_seconds: int = Field(3600, alias="SESSION_TTL_SECONDS")
    redis_url: str = Field("redis://localhost:6379", alias="REDIS_URL")
    use_redis: bool = Field(True, alias="USE_REDIS")

    # DB connection metadata store (see connection_store.py): how long a
    # connected-but-idle database connection's metadata stays valid before
    # the user has to reconnect.
    db_connection_ttl_seconds: int = Field(600, alias="DB_CONNECTION_TTL_SECONDS")

    # How long an unused dataset (upload, materialized DB table, BigQuery
    # result, demo data) is kept before the retention sweep deletes it and
    # its file. Sliding: touched every time the dataset is resolved, so a
    # workspace someone keeps reopening is never reaped. Default 30 days —
    # long enough that "I'll get back to this analysis next week" still
    # works. 0 disables age-based reaping (orphan cleanup still runs).
    dataset_ttl_seconds: int = Field(30 * 24 * 3600, alias="DATASET_TTL_SECONDS")

    # How often the retention sweep runs. It does two cheap, idempotent
    # things — reap expired datasets, delete orphaned files — so a modest
    # cadence is fine even on a small deployment.
    retention_sweep_interval_seconds: int = Field(3600, alias="RETENTION_SWEEP_INTERVAL_SECONDS")

    # CORS: comma-separated allowed origins (use "*" to allow all, dev only)
    allowed_origins: str = Field(
        "http://localhost:8501,http://localhost:3000", alias="ALLOWED_ORIGINS"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name": True,
        "extra": "ignore",
    }


settings = Settings()  # type: ignore[call-arg]

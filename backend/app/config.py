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
    anthropic_model: str = Field("claude-haiku-4-5-20251001", alias="ANTHROPIC_MODEL")

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

    # Overall wall-clock ceiling for the whole /process and /nlq requests
    # (not just a single LLM call — the full multi-stage pipeline). Set well
    # above `request_timeout` since /process alone can chain several
    # LLM-backed stages. Past this, the request fails with a clean 504
    # instead of hanging until the client's own timeout gives up silently.
    process_timeout_seconds: int = Field(600, alias="PROCESS_TIMEOUT_SECONDS")
    nlq_timeout_seconds: int = Field(180, alias="NLQ_TIMEOUT_SECONDS")

    # Root logger level for the structured JSON logs (see logging_config.py).
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    # Feature flags
    demo_mode: bool = Field(True, alias="DEMO_MODE")

    # Rate limiting (in-memory, per-client-IP fixed window). Safe as
    # in-memory because the backend always runs as a single uvicorn worker
    # (see backend/Dockerfile) — move to Redis if that ever changes.
    rate_limit_enabled: bool = Field(True, alias="RATE_LIMIT_ENABLED")
    rate_limit_default_per_minute: int = Field(120, alias="RATE_LIMIT_DEFAULT_PER_MINUTE")
    rate_limit_process_per_minute: int = Field(10, alias="RATE_LIMIT_PROCESS_PER_MINUTE")
    rate_limit_nlq_per_minute: int = Field(20, alias="RATE_LIMIT_NLQ_PER_MINUTE")

    # /nlq answer cache — same dataset + question + provider/model + prior
    # conversation skips regenerating and re-executing the query.
    query_cache_enabled: bool = Field(True, alias="QUERY_CACHE_ENABLED")
    query_cache_ttl_seconds: int = Field(3600, alias="QUERY_CACHE_TTL_SECONDS")

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

    # Auth is off by default — the app stays single-tenant/no-auth exactly as
    # documented until an operator explicitly sets AUTH_ENABLED=true. Once on,
    # ADMIN_EMAIL + ADMIN_PASSWORD bootstrap the first account (admin role) on
    # startup; leave them unset for an OIDC-only deployment with no local admin.
    auth_enabled: bool = Field(False, alias="AUTH_ENABLED")
    admin_email: str = Field("", alias="ADMIN_EMAIL")
    admin_password: str = Field("", alias="ADMIN_PASSWORD")
    auth_session_ttl_seconds: int = Field(30 * 24 * 3600, alias="AUTH_SESSION_TTL_SECONDS")

    # SSO (OIDC). SAML is intentionally not supported yet — see PLAN.md.
    oidc_issuer: str = Field("", alias="OIDC_ISSUER")
    oidc_client_id: str = Field("", alias="OIDC_CLIENT_ID")
    oidc_client_secret: str = Field("", alias="OIDC_CLIENT_SECRET")
    oidc_redirect_uri: str = Field("", alias="OIDC_REDIRECT_URI")

    # API keys for headless (non-browser) callers, once auth is enabled.
    api_key_ttl_seconds: int = Field(0, alias="API_KEY_TTL_SECONDS")  # 0 = no expiry

    # Audit log retention (entries beyond this count are dropped, oldest first).
    audit_log_max_entries: int = Field(50_000, alias="AUDIT_LOG_MAX_ENTRIES")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name": True,
        "extra": "ignore",
    }


settings = Settings()  # type: ignore[call-arg]

"""
Runtime-overridable LLM provider/model.

Lets the UI switch provider (DeepSeek / Ollama / OpenAI / Anthropic) live without
editing .env or restarting. Falls back to the env defaults when nothing is set.
"""

import threading

from app.config import settings

_lock = threading.Lock()
_override: dict[str, str | None] = {"provider": None, "model": None}

PROVIDERS = ["ollama", "deepseek", "openai", "anthropic"]


def get_provider() -> str:
    return _override["provider"] or settings.llm_provider


def get_model_override() -> str | None:
    return _override["model"]


def _default_model(provider: str) -> str:
    return {
        "openai": settings.openai_model,
        "anthropic": settings.anthropic_model,
        "deepseek": settings.deepseek_model,
        "ollama": settings.ollama_model,
    }.get(provider, settings.ollama_model)


def set_override(provider: str | None, model: str | None) -> None:
    with _lock:
        if provider is not None:
            _override["provider"] = provider
            # A new provider invalidates a model pinned to the old one.
            _override["model"] = model
        elif model is not None:
            _override["model"] = model


def current() -> dict[str, str]:
    provider = get_provider()
    model = _override["model"] or _default_model(provider)
    return {"provider": provider, "model": model}

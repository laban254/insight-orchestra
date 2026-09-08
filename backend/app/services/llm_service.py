import json
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import requests
from openai import OpenAI

from app.config import settings

try:
    import anthropic as _anthropic_sdk

    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

logger = logging.getLogger(__name__)


class LLMProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"


@dataclass
class LLMConfig:
    provider: LLMProvider = LLMProvider.OPENAI
    api_key: str = ""
    model: str = "gpt-4o-mini"
    fallback_model: str = "gpt-4o"
    base_url: str = ""
    max_retries: int = 3
    request_timeout: int = 60
    temperature: float = 0.1


@dataclass
class LLMResponse:
    content: str
    model: str
    tokens_used: int = 0
    cost_usd: float = 0.0
    raw_response: dict[str, Any] = field(default_factory=dict)


class LLMService:
    PRICING = {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 5.00, "output": 15.00},
        "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
        "claude-opus-4-5": {"input": 15.00, "output": 75.00},
        "deepseek-chat": {"input": 0.27, "output": 1.10},
        "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    }

    def __init__(self, config: LLMConfig | None = None):
        if config is None:
            from app import runtime_config

            try:
                provider = LLMProvider(runtime_config.get_provider().lower())
            except ValueError:
                provider = LLMProvider.OPENAI

            if provider == LLMProvider.OPENAI:
                api_key = settings.openai_api_key
                model = settings.openai_model
                fallback_model = settings.openai_model_fallback
                base_url = ""
            elif provider == LLMProvider.ANTHROPIC:
                api_key = settings.anthropic_api_key
                model = settings.anthropic_model
                fallback_model = model
                base_url = ""
            elif provider == LLMProvider.DEEPSEEK:
                api_key = settings.deepseek_api_key
                model = settings.deepseek_model
                fallback_model = model
                base_url = settings.deepseek_base_url
            else:  # OLLAMA
                api_key = ""
                model = settings.ollama_model
                fallback_model = model
                base_url = settings.ollama_base_url

            # A live model override (set via POST /config) wins over env defaults.
            override_model = runtime_config.get_model_override()
            if override_model:
                model = override_model
                if provider != LLMProvider.OPENAI:
                    fallback_model = override_model

            config = LLMConfig(
                provider=provider,
                api_key=api_key,
                model=model,
                fallback_model=fallback_model,
                base_url=base_url,
                max_retries=settings.max_retries,
                request_timeout=settings.request_timeout,
            )

        self.config = config
        self.total_cost = 0.0
        self.total_tokens = 0
        self._client = None
        self._client_lock = threading.Lock()  # guards lazy client initialisation

        if self.config.provider == LLMProvider.OPENAI and not config.api_key:
            raise ValueError("OPENAI_API_KEY not set")
        if self.config.provider == LLMProvider.ANTHROPIC and not config.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        if self.config.provider == LLMProvider.DEEPSEEK and not config.api_key:
            raise ValueError("DEEPSEEK_API_KEY not set")

    # ------------------------------------------------------------------
    # Client initialisation (thread-safe lazy singleton per provider)
    # ------------------------------------------------------------------

    @property
    def client(self):
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    if self.config.provider == LLMProvider.OPENAI:
                        self._client = OpenAI(api_key=self.config.api_key)
                    elif self.config.provider == LLMProvider.DEEPSEEK:
                        # DeepSeek ships an OpenAI-compatible API; reuse the SDK
                        # with its base URL.
                        self._client = OpenAI(
                            api_key=self.config.api_key,
                            base_url=self.config.base_url,
                        )
                    elif self.config.provider == LLMProvider.ANTHROPIC:
                        if not _ANTHROPIC_AVAILABLE:
                            raise ImportError(
                                "anthropic package not installed. Run: pip install anthropic"
                            )
                        self._client = _anthropic_sdk.Anthropic(api_key=self.config.api_key)
        return self._client

    # ------------------------------------------------------------------
    # Cost helpers
    # ------------------------------------------------------------------

    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        if self.config.provider == LLMProvider.OLLAMA:
            return 0.0
        pricing = self.PRICING.get(model, {"input": 0.15, "output": 0.60})
        return (
            prompt_tokens / 1_000_000 * pricing["input"]
            + completion_tokens / 1_000_000 * pricing["output"]
        )

    def _record_usage(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        cost = self._calculate_cost(model, prompt_tokens, completion_tokens)
        self.total_cost += cost
        self.total_tokens += prompt_tokens + completion_tokens
        logger.info(
            '{"event":"llm_call","model":"%s","prompt_tokens":%d,'
            '"completion_tokens":%d,"cost_usd":%.6f}',
            model,
            prompt_tokens,
            completion_tokens,
            cost,
        )
        return cost

    def _exponential_backoff(self, attempt: int) -> float:
        return float(min(2**attempt + (attempt * 0.1), 60))

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """Whether retrying `exc` could plausibly succeed.

        Auth/permission/bad-request errors (401/403/400/404) fail the same
        way every time — retrying just burns `max_retries` attempts and the
        user's wait time before failing anyway. Detected by `status_code`
        (set by both the OpenAI and Anthropic SDKs' error classes, and by
        `requests.HTTPError.response`) rather than importing SDK-specific
        exception types, so this covers every provider uniformly.
        """
        status: int | None = getattr(exc, "status_code", None)
        if status is None and isinstance(exc, requests.exceptions.HTTPError):
            status = exc.response.status_code if exc.response is not None else None
        if status is not None:
            return bool(status == 429 or status >= 500)
        if isinstance(exc, requests.exceptions.RequestException):
            # Timeouts/connection errors are transient; any other requests
            # exception without a status code (e.g. a malformed response) is not.
            return isinstance(
                exc, requests.exceptions.Timeout | requests.exceptions.ConnectionError
            )
        return True  # unknown shape — keep the previous always-retry behaviour

    # ------------------------------------------------------------------
    # Provider-specific callers
    # ------------------------------------------------------------------

    def _call_ollama(self, messages: list[dict[str, str]], model: str) -> LLMResponse:
        needs_json = any(
            m.get("role") == "system" and "valid json" in m.get("content", "").lower()
            for m in messages
        )
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.config.temperature},
        }
        if needs_json:
            payload["format"] = "json"

        llm_timeout = max(self.config.request_timeout, 300)
        logger.info(f"Calling Ollama model={model} timeout={llm_timeout}s")
        response = requests.post(
            f"{self.config.base_url}/api/chat", json=payload, timeout=llm_timeout
        )
        response.raise_for_status()
        data = response.json()
        tokens = data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
        self.total_tokens += tokens
        return LLMResponse(
            content=data["message"]["content"],
            model=model,
            tokens_used=tokens,
            cost_usd=0.0,
            raw_response=data,
        )

    def _call_openai(self, messages: list[dict[str, str]], model: str) -> LLMResponse:
        needs_json = any(
            m.get("role") == "system" and "valid json" in m.get("content", "").lower()
            for m in messages
        )
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=4096,
            timeout=self.config.request_timeout,
            response_format={"type": "json_object"} if needs_json else None,
        )
        cost = self._record_usage(
            model,
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
        )
        return LLMResponse(
            content=response.choices[0].message.content,
            model=model,
            tokens_used=response.usage.prompt_tokens + response.usage.completion_tokens,
            cost_usd=cost,
            raw_response=response.model_dump(),
        )

    def _call_anthropic(self, messages: list[dict[str, str]], model: str) -> LLMResponse:
        system_content = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_messages = [m for m in messages if m["role"] != "system"]
        response = self.client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_content,
            messages=user_messages,
            temperature=self.config.temperature,
        )
        cost = self._record_usage(model, response.usage.input_tokens, response.usage.output_tokens)
        return LLMResponse(
            content=response.content[0].text,
            model=model,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            cost_usd=cost,
            raw_response={"id": response.id, "model": response.model},
        )

    def _call_llm(self, messages: list[dict[str, str]], model: str) -> LLMResponse:
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                if self.config.provider == LLMProvider.OLLAMA:
                    return self._call_ollama(messages, model)
                elif self.config.provider in (LLMProvider.OPENAI, LLMProvider.DEEPSEEK):
                    return self._call_openai(messages, model)
                elif self.config.provider == LLMProvider.ANTHROPIC:
                    return self._call_anthropic(messages, model)
                else:
                    raise NotImplementedError(f"Provider {self.config.provider} not implemented")
            except Exception as e:
                last_error = e
                logger.error(f"LLM call failed (attempt {attempt + 1}): {e}")
                if not self._is_retryable(e):
                    logger.info(f"Not retrying — {type(e).__name__} won't succeed on retry.")
                    raise
            if attempt < self.config.max_retries:
                delay = self._exponential_backoff(attempt)
                logger.info(f"Retrying in {delay:.1f}s…")
                time.sleep(delay)
        raise last_error or Exception(
            f"LLM call failed after {self.config.max_retries + 1} attempts"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def complete(
        self, system_prompt: str, user_prompt: str, use_fallback: bool = False
    ) -> LLMResponse:
        model = (
            self.config.fallback_model
            if use_fallback and self.config.provider == LLMProvider.OPENAI
            else self.config.model
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self._call_llm(messages, model)

    def complete_json(
        self, system_prompt: str, user_prompt: str, use_fallback: bool = False
    ) -> dict[str, Any]:
        json_system = (
            f"{system_prompt}\n\n"
            "IMPORTANT: You must respond with valid JSON only. "
            "No markdown formatting. Do not include ```json``` code blocks. Just raw JSON."
        )
        response = self.complete(json_system, user_prompt, use_fallback)
        content = response.content.strip()

        # Strip accidental markdown fences (handles ```json, ```python, ``` variants)
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```python"):
            # Small models often ignore JSON instructions and return code blocks.
            # Extract the code and wrap it in the expected JSON structure.
            inner = content[9:]
            if inner.endswith("```"):
                inner = inner[:-3]
            inner = inner.strip()
            # Remove import lines so the extracted code is ready for the sandbox
            code_lines = [
                ln for ln in inner.splitlines() if not ln.strip().startswith(("import ", "from "))
            ]
            return {
                "reasoning": "extracted from markdown code block",
                "code": "\n".join(code_lines).strip(),
                "needs_clarification": False,
                "clarification_question": None,
            }
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            return json.loads(content)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            # Last-ditch: if the entire response looks like Python code, wrap it
            stripped = content.strip()
            if stripped and not stripped.startswith("{"):
                code_lines = [
                    ln
                    for ln in stripped.splitlines()
                    if not ln.strip().startswith(("import ", "from "))
                ]
                code = "\n".join(code_lines).strip()
                if code:
                    logger.warning(
                        f"LLM returned raw code instead of JSON "
                        f"({len(code)} chars); wrapping automatically"
                    )
                    return {
                        "reasoning": "raw code response from model",
                        "code": code,
                        "needs_clarification": False,
                        "clarification_question": None,
                    }
            logger.error(f"JSON parse failed. Raw ({len(content)} chars): {content[:200]!r}")
            raise ValueError("Invalid JSON from LLM") from None

    def stream_complete(self, system_prompt: str, user_prompt: str):
        """Yield the response text incrementally as the provider generates it.

        For user-facing prose only (narration) — JSON-mode responses can't
        be shown mid-stream (partial JSON reads as broken text), so this has
        no `use_fallback`/JSON variant; callers needing structured output
        still use `complete_json()`. No retry loop: a failure partway
        through has already shown the caller partial text, so retrying
        would duplicate or contradict what's already been displayed. The
        caller (a chunk-consuming agent) is expected to fall back to a
        non-streamed heuristic on any exception here, same as a `complete()`
        failure.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        model = self.config.model
        if self.config.provider == LLMProvider.OLLAMA:
            yield from self._stream_ollama(messages, model)
        elif self.config.provider in (LLMProvider.OPENAI, LLMProvider.DEEPSEEK):
            yield from self._stream_openai(messages, model)
        elif self.config.provider == LLMProvider.ANTHROPIC:
            yield from self._stream_anthropic(messages, model)
        else:
            raise NotImplementedError(f"Provider {self.config.provider} not implemented")

    def _stream_ollama(self, messages: list[dict[str, str]], model: str):
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": self.config.temperature},
        }
        llm_timeout = max(self.config.request_timeout, 300)
        response = requests.post(
            f"{self.config.base_url}/api/chat", json=payload, timeout=llm_timeout, stream=True
        )
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            chunk = data.get("message", {}).get("content", "")
            if chunk:
                yield chunk
            if data.get("done"):
                self.total_tokens += data.get("prompt_eval_count", 0) + data.get("eval_count", 0)

    def _stream_openai(self, messages: list[dict[str, str]], model: str):
        stream = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=4096,
            timeout=self.config.request_timeout,
            stream=True,
            stream_options={"include_usage": True},
        )
        for chunk in stream:
            if chunk.usage is not None:
                self._record_usage(model, chunk.usage.prompt_tokens, chunk.usage.completion_tokens)
                continue
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta

    def _stream_anthropic(self, messages: list[dict[str, str]], model: str):
        system_content = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_messages = [m for m in messages if m["role"] != "system"]
        with self.client.messages.stream(
            model=model,
            max_tokens=4096,
            system=system_content,
            messages=user_messages,
            temperature=self.config.temperature,
        ) as stream:
            yield from stream.text_stream
            final = stream.get_final_message()
            self._record_usage(model, final.usage.input_tokens, final.usage.output_tokens)

    def get_cost_summary(self) -> dict[str, Any]:
        return {
            "total_cost_usd": round(self.total_cost, 4),
            "total_tokens": self.total_tokens,
        }


def friendly_llm_error(e: Exception, llm: LLMService) -> str:
    """Map a raw LLM provider exception to an actionable, user-facing message.

    Shared between /nlq and /process — both call through `llm` and both need
    to turn "APIConnectionError" or a urllib3 retry trace into something a
    user can act on. Auth/timeout are detected by shape (a `status_code` of
    401, or "timeout"/"authenticationerror" in the exception's class name)
    rather than importing any specific SDK's error types, so this covers
    every cloud provider — including ones added later — without an update
    here. Ollama is the one provider called over plain HTTP instead of an
    SDK, so a dead/unreachable container surfaces as a
    `requests.exceptions.ConnectionError` instead — checked separately since
    neither signal above would catch it.
    """
    is_auth_error = (
        getattr(e, "status_code", None) == 401 or "authenticationerror" in type(e).__name__.lower()
    )
    if is_auth_error:
        provider = llm.config.provider
        env_var = {
            LLMProvider.OPENAI: "OPENAI_API_KEY",
            LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
            LLMProvider.DEEPSEEK: "DEEPSEEK_API_KEY",
        }.get(provider)
        if env_var:
            return (
                f"Your {provider.value} API key is missing or invalid. "
                f"Add it to backend/.env ({env_var}=...) and restart the backend "
                "(docker compose up -d --build backend)."
            )

    if (
        isinstance(e, requests.exceptions.ConnectionError)
        and llm.config.provider == LLMProvider.OLLAMA
    ):
        return (
            f"Can't reach Ollama at {llm.config.base_url}. Make sure the ollama "
            "container is running (docker compose up -d ollama) and the model is pulled "
            f"(docker compose exec ollama ollama pull {llm.config.model})."
        )

    is_timeout = isinstance(e, requests.exceptions.Timeout) or "timeout" in type(e).__name__.lower()
    if is_timeout:
        return (
            f"The {llm.config.provider.value} request took too long and was stopped. "
            "Try a smaller dataset, a simpler question, or a faster model."
        )

    return f"Error: {str(e)}"


class DataFrameSchema:
    @staticmethod
    def from_dataframe(df, max_columns: int = 50) -> dict[str, Any]:
        """Build a schema dict from a DataFrame, capped at max_columns."""
        cols = list(df.columns[:max_columns])
        omitted = max(0, len(df.columns) - max_columns)
        schema: dict[str, Any] = {
            "columns": [],
            "shape": list(df.shape),
            "null_counts": {},
            "omitted_columns": omitted,
        }
        for col in cols:
            samples = df[col].dropna().head(3).tolist()
            schema["columns"].append(
                {
                    "name": col,
                    "dtype": str(df[col].dtype),
                    "sample_values": samples,
                }
            )
            schema["null_counts"][col] = int(df[col].isnull().sum())
        return schema

    @staticmethod
    def to_prompt(schema: dict[str, Any]) -> str:
        total_cols = schema["shape"][1]
        shown = len(schema["columns"])
        omitted = schema.get("omitted_columns", 0)
        header = f"DataFrame: {schema['shape'][0]} rows × {total_cols} columns" + (
            f" (showing first {shown}; {omitted} omitted)" if omitted else ""
        )
        lines = [header, "Columns:"]
        for col in schema["columns"]:
            nulls = schema["null_counts"].get(col["name"], 0)
            lines.append(
                f"  - {col['name']}: {col['dtype']} "
                f"(nulls: {nulls}, samples: {col['sample_values']})"
            )
        return "\n".join(lines)

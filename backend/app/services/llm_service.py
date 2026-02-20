import os
import json
import time
import logging
import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from openai import OpenAI, RateLimitError, APIError, APITimeoutError

logger = logging.getLogger(__name__)

class LLMProvider(str, Enum):
    OPENAI    = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA    = "ollama"

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
    raw_response: Dict[str, Any] = field(default_factory=dict)

class LLMService:
    PRICING = {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 5.00, "output": 15.00},
    }
    
    def __init__(self, config: Optional[LLMConfig] = None):
        if config is None:
            provider_str = os.getenv("LLM_PROVIDER", "openai").lower()
            try:
                provider = LLMProvider(provider_str)
            except ValueError:
                provider = LLMProvider.OPENAI
            
            api_key = os.getenv(f"{provider.name}_API_KEY", os.getenv("OPENAI_API_KEY", ""))
            model = os.getenv(f"{provider.name}_MODEL", "gpt-4o-mini" if provider == LLMProvider.OPENAI else "llama3.1:8b")
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") if provider == LLMProvider.OLLAMA else ""
            
            config = LLMConfig(
                provider=provider,
                api_key=api_key,
                model=model,
                fallback_model=os.getenv("OPENAI_MODEL_FALLBACK", "gpt-4o"),
                base_url=base_url,
                max_retries=int(os.getenv("MAX_RETRIES", 3)),
                request_timeout=int(os.getenv("REQUEST_TIMEOUT", 60)),
            )
        
        self.config = config
        self.total_cost = 0.0
        self.total_tokens = 0

        if self.config.provider == LLMProvider.OPENAI:
            self.client = OpenAI(api_key=config.api_key)
            
    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        if self.config.provider == LLMProvider.OLLAMA:
            return 0.0
        pricing = self.PRICING.get(model, {"input": 0.15, "output": 0.60})
        cost = (prompt_tokens / 1_000_000 * pricing["input"] +
                completion_tokens / 1_000_000 * pricing["output"])
        return cost
        
    def _exponential_backoff(self, attempt: int) -> float:
        return min(2 ** attempt + (attempt * 0.1), 60)
        
    def _call_ollama(self, messages: List[Dict[str, str]], model: str) -> LLMResponse:
        url = f"{self.config.base_url}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.config.temperature
            }
        }
        response = requests.post(url, json=payload, timeout=self.config.request_timeout)
        response.raise_for_status()
        data = response.json()
        
        return LLMResponse(
            content=data["message"]["content"],
            model=model,
            tokens_used=data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            cost_usd=0.0,
            raw_response=data
        )

    def _call_openai(self, messages: List[Dict[str, str]], model: str) -> LLMResponse:
        # Check if the prompt explicitly requires json format
        needs_json = any(msg.get("role") == "system" and "valid json" in msg.get("content", "").lower() for msg in messages)
        
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=4096,
            timeout=self.config.request_timeout,
            response_format={"type": "json_object"} if needs_json else None,
        )
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = prompt_tokens + completion_tokens
        
        cost = self._calculate_cost(model, prompt_tokens, completion_tokens)
        self.total_cost += cost
        self.total_tokens += total_tokens
        
        return LLMResponse(
            content=response.choices[0].message.content,
            model=model,
            tokens_used=total_tokens,
            cost_usd=cost,
            raw_response=response.model_dump(),
        )

    def _call_llm(self, messages: List[Dict[str, str]], model: str) -> LLMResponse:
        last_error = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                if self.config.provider == LLMProvider.OLLAMA:
                    return self._call_ollama(messages, model)
                elif self.config.provider == LLMProvider.OPENAI:
                    return self._call_openai(messages, model)
                else:
                    raise NotImplementedError(f"Provider {self.config.provider} not implemented")
            except Exception as e:
                last_error = e
                logger.error(f"Error calling LLM (attempt {attempt + 1}): {e}")
                
            if attempt < self.config.max_retries:
                delay = self._exponential_backoff(attempt)
                logger.info(f"Retrying in {delay:.1f}s...")
                time.sleep(delay)
                
        raise last_error or Exception(f"LLM call failed after {self.config.max_retries + 1} attempts")

    def complete(self, system_prompt: str, user_prompt: str, 
                 use_fallback: bool = False) -> LLMResponse:
        model = self.config.fallback_model if use_fallback and self.config.provider == LLMProvider.OPENAI else self.config.model
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self._call_llm(messages, model)

    def complete_json(self, system_prompt: str, user_prompt: str,
                       use_fallback: bool = False) -> Dict[str, Any]:
        json_prompt = f"{system_prompt}\n\nIMPORTANT: You must respond with valid JSON only. No markdown formatting. Do not include ```json``` code blocks. Just raw JSON."
        response = self.complete(json_prompt, user_prompt, use_fallback)
        
        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")

    def get_cost_summary(self) -> Dict[str, Any]:
        return {
            "total_cost_usd": round(self.total_cost, 4),
            "total_tokens": self.total_tokens,
            "avg_cost_per_call": round(self.total_cost / max(1, self.total_tokens), 6) if self.total_tokens else 0,
        }

class DataFrameSchema:
    @staticmethod
    def from_dataframe(df) -> Dict[str, Any]:
        schema = {
            "columns": [],
            "shape": list(df.shape),
            "null_counts": {},
        }
        for col in df.columns:
            col_info = {
                "name": col,
                "dtype": str(df[col].dtype),
                "sample_values": df[col].dropna().head(5).tolist(),
            }
            schema["columns"].append(col_info)
            schema["null_counts"][col] = int(df[col].isnull().sum())
        return schema
    
    @staticmethod
    def to_prompt(schema: Dict[str, Any]) -> str:
        lines = [f"DataFrame Shape: {schema['shape'][0]} rows × {schema['shape'][1]} columns\n"]
        lines.append("Columns:")
        for col in schema["columns"]:
            nulls = schema['null_counts'].get(col['name'], 0)
            lines.append(
                f"  - {col['name']}: {col['dtype']} "
                f"(nulls: {nulls}, samples: {col['sample_values']})"
            )
        return "\n".join(lines)

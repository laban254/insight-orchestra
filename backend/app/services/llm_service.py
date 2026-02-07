"""
LLM Service - OpenAI wrapper with retry logic and structured output.

This service handles:
- OpenAI API communication
- Retry with exponential backoff
- Cost tracking
- Structured JSON output
"""

import os
import json
import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from openai import OpenAI, RateLimitError, APIError, APITimeoutError
from pydantic import BaseModel

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """Configuration for LLM Service."""
    api_key: str = ""
    model: str = "gpt-4o-mini"
    fallback_model: str = "gpt-4o"
    max_retries: int = 3
    request_timeout: int = 60
    temperature: float = 0.1


@dataclass
class LLMResponse:
    """Response from LLM Service."""
    content: str
    model: str
    tokens_used: int
    cost_usd: float
    raw_response: Dict[str, Any] = field(default_factory=dict)


class LLMService:
    """
    LLM Service for Insight Orchestra.
    
    Features:
    - OpenAI API wrapper
    - Automatic retry with exponential backoff
    - Cost tracking
    - Structured JSON output
    - Model fallback for complex queries
    """
    
    # Pricing per 1M tokens (as of 2024)
    PRICING = {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 5.00, "output": 15.00},
    }
    
    def __init__(self, config: Optional[LLMConfig] = None):
        """
        Initialize LLM Service.
        
        Args:
            config: Optional LLMConfig. If not provided, loads from environment.
        """
        if config is None:
            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set. Add it to .env file.")
            
            config = LLMConfig(
                api_key=api_key,
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                fallback_model=os.getenv("OPENAI_MODEL_FALLBACK", "gpt-4o"),
                max_retries=int(os.getenv("MAX_RETRIES", 3)),
                request_timeout=int(os.getenv("REQUEST_TIMEOUT", 60)),
            )
        
        self.config = config
        self.client = OpenAI(api_key=config.api_key)
        self.total_cost = 0.0
        self.total_tokens = 0
    
    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost in USD based on model pricing."""
        pricing = self.PRICING.get(model, {"input": 0.15, "output": 0.60})
        cost = (prompt_tokens / 1_000_000 * pricing["input"] +
                completion_tokens / 1_000_000 * pricing["output"])
        return cost
    
    def _exponential_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        return min(2 ** attempt + (attempt * 0.1), 60)
    
    def _call_llm(self, messages: List[Dict[str, str]], model: str) -> LLMResponse:
        """
        Call LLM API with retry logic.
        
        Args:
            messages: List of chat messages
            model: Model to use
            
        Returns:
            LLMResponse object
        """
        last_error = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=self.config.temperature,
                    max_tokens=4096,
                    timeout=self.config.request_timeout,
                    response_format={"type": "json_object"},
                )
                
                # Extract token usage
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens
                total_tokens = prompt_tokens + completion_tokens
                
                # Calculate cost
                cost = self._calculate_cost(model, prompt_tokens, completion_tokens)
                self.total_cost += cost
                self.total_tokens += total_tokens
                
                logger.info(
                    f"LLM Response - Model: {model}, Tokens: {total_tokens}, "
                    f"Cost: ${cost:.4f}, Total: ${self.total_cost:.4f}"
                )
                
                return LLMResponse(
                    content=response.choices[0].message.content,
                    model=model,
                    tokens_used=total_tokens,
                    cost_usd=cost,
                    raw_response=response.model_dump(),
                )
                
            except APITimeoutError as e:
                last_error = e
                logger.warning(f"LLM timeout (attempt {attempt + 1}): {e}")
                
            except RateLimitError as e:
                last_error = e
                logger.warning(f"Rate limit (attempt {attempt + 1}): {e}")
                
            except APIError as e:
                last_error = e
                logger.error(f"API error (attempt {attempt + 1}): {e}")
                
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error (attempt {attempt + 1}): {e}")
            
            # Exponential backoff
            if attempt < self.config.max_retries:
                delay = self._exponential_backoff(attempt)
                logger.info(f"Retrying in {delay:.1f}s...")
                time.sleep(delay)
        
        raise last_error or Exception(f"LLM call failed after {self.config.max_retries + 1} attempts")
    
    def complete(self, system_prompt: str, user_prompt: str, 
                 use_fallback: bool = False) -> LLMResponse:
        """
        Get completion from LLM.
        
        Args:
            system_prompt: System instruction
            user_prompt: User question/task
            use_fallback: Use fallback model for complex queries
            
        Returns:
            LLMResponse object
        """
        model = self.config.fallback_model if use_fallback else self.config.model
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        return self._call_llm(messages, model)
    
    def complete_json(self, system_prompt: str, user_prompt: str,
                       use_fallback: bool = False) -> Dict[str, Any]:
        """
        Get JSON completion from LLM.
        
        Args:
            system_prompt: System instruction
            user_prompt: User question/task
            use_fallback: Use fallback model
            
        Returns:
            Parsed JSON dictionary
        """
        # Ensure JSON mode in system prompt
        json_prompt = f"""{system_prompt}

IMPORTANT: You must respond with valid JSON only. No markdown formatting.
Do not include ```json``` code blocks. Just raw JSON."""
        
        response = self.complete(json_prompt, user_prompt, use_fallback)
        
        # Parse JSON
        try:
            content = response.content.strip()
            # Remove any markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Raw response: {response.content}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost tracking summary."""
        return {
            "total_cost_usd": round(self.total_cost, 4),
            "total_tokens": self.total_tokens,
            "avg_cost_per_call": round(self.total_cost / max(1, self.total_tokens), 6) if self.total_tokens else 0,
        }


class DataFrameSchema:
    """Helper to create DataFrame schema for LLM prompts."""
    
    @staticmethod
    def from_dataframe(df) -> Dict[str, Any]:
        """
        Create schema from pandas DataFrame.
        
        Args:
            df: pandas DataFrame
            
        Returns:
            Dictionary with column info
        """
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
        """Convert schema to LLM-friendly prompt."""
        lines = [f"DataFrame Shape: {schema['shape'][0]} rows × {schema['shape'][1]} columns\n"]
        lines.append("Columns:")
        
        for col in schema["columns"]:
            nulls = schema['null_counts'].get(col['name'], 0)
            lines.append(
                f"  - {col['name']}: {col['dtype']} "
                f"(nulls: {nulls}, samples: {col['sample_values']})"
            )
        
        return "\n".join(lines)


# Example usage
if __name__ == "__main__":
    import pandas as pd
    
    # Test with sample data
    df = pd.DataFrame({
        "name": ["Alice", "Bob", "Charlie"],
        "age": [25, 30, 35],
        "city": ["NYC", "LA", "Chicago"],
    })
    
    schema = DataFrameSchema.from_dataframe(df)
    print("Schema:")
    print(DataFrameSchema.to_prompt(schema))
    
    # Test LLM Service (requires API key)
    try:
        llm = LLMService()
        response = llm.complete(
            system_prompt="You are a helpful data analyst.",
            user_prompt="What can you tell me about this DataFrame?",
        )
        print(f"\nLLM Response: {response.content}")
        print(f"Cost: ${response.cost_usd:.4f}")
    except ValueError as e:
        print(f"\nNote: {e}")
        print("Add OPENAI_API_KEY to .env to test LLM integration.")

"""
Unit tests for LLM Service.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests
from app.services.llm_service import (
    DataFrameSchema,
    LLMConfig,
    LLMProvider,
    LLMResponse,
    LLMService,
    friendly_llm_error,
)


class TestLLMConfig:
    """Test cases for LLMConfig."""

    def test_default_config(self):
        """Test default LLM configuration."""
        config = LLMConfig()

        assert config.model == "gpt-4o-mini"
        assert config.fallback_model == "gpt-4o"
        assert config.max_retries == 3
        assert config.temperature == 0.1

    def test_custom_config(self):
        """Test custom LLM configuration."""
        config = LLMConfig(
            api_key="test-key",
            model="gpt-4",
            fallback_model="gpt-4-turbo",
            max_retries=5,
            temperature=0.5,
        )

        assert config.api_key == "test-key"
        assert config.model == "gpt-4"
        assert config.fallback_model == "gpt-4-turbo"
        assert config.max_retries == 5
        assert config.temperature == 0.5


class TestLLMResponse:
    """Test cases for LLMResponse."""

    def test_create_response(self):
        """Test creating an LLMResponse."""
        response = LLMResponse(
            content='{"answer": "test"}',
            model="gpt-4o-mini",
            tokens_used=100,
            cost_usd=0.001,
        )

        assert response.content == '{"answer": "test"}'
        assert response.model == "gpt-4o-mini"
        assert response.tokens_used == 100
        assert response.cost_usd == 0.001

    def test_response_with_raw(self):
        """Test response with raw API response."""
        raw = {"id": "chat-123", "object": "chat.completion"}
        response = LLMResponse(
            content='{"result": "test"}',
            model="gpt-4o-mini",
            tokens_used=50,
            cost_usd=0.0005,
            raw_response=raw,
        )

        assert response.raw_response["id"] == "chat-123"


class TestDataFrameSchema:
    """Test cases for DataFrameSchema helper."""

    def test_from_dataframe(self, sample_dataframe):
        """Test creating schema from DataFrame."""
        schema = DataFrameSchema.from_dataframe(sample_dataframe)

        assert "columns" in schema
        assert "shape" in schema
        assert "null_counts" in schema
        assert schema["shape"] == [4, 4]  # 4 rows, 4 columns
        assert len(schema["columns"]) == 4

    def test_column_info(self, sample_dataframe):
        """Test column information in schema."""
        schema = DataFrameSchema.from_dataframe(sample_dataframe)

        for col in schema["columns"]:
            assert "name" in col
            assert "dtype" in col
            assert "sample_values" in col
            assert 1 <= len(col["sample_values"]) <= 5

    def test_null_counts(self, sample_dataframe):
        """Test null counts in schema."""
        schema = DataFrameSchema.from_dataframe(sample_dataframe)

        for col_name, null_count in schema["null_counts"].items():
            assert null_count == 0  # No nulls in sample data

    def test_to_prompt(self, sample_dataframe):
        """Test converting schema to prompt string."""
        schema = DataFrameSchema.from_dataframe(sample_dataframe)
        prompt = DataFrameSchema.to_prompt(schema)

        assert "DataFrame:" in prompt
        assert "Columns:" in prompt
        assert "name:" in prompt
        assert "age:" in prompt


class TestLLMService:
    """Test cases for LLMService."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        with patch("app.services.llm_service.OpenAI") as mock_client:
            yield mock_client

    @pytest.fixture
    def llm_service(self, mock_openai_client):
        """Create an LLMService with mocked client."""
        config = LLMConfig(api_key="test-key")
        return LLMService(config)

    def test_calculate_cost_gpt4o_mini(self, llm_service):
        """Test cost calculation for gpt-4o-mini."""
        cost = llm_service._calculate_cost(
            "gpt-4o-mini",
            prompt_tokens=1000,
            completion_tokens=500,
        )

        # gpt-4o-mini: $0.15/M input, $0.60/M output
        expected = (1000 / 1_000_000 * 0.15) + (500 / 1_000_000 * 0.60)
        assert cost == expected

    def test_calculate_cost_gpt4o(self, llm_service):
        """Test cost calculation for gpt-4o."""
        cost = llm_service._calculate_cost(
            "gpt-4o",
            prompt_tokens=1000,
            completion_tokens=500,
        )

        # gpt-4o: $5.00/M input, $15.00/M output
        expected = (1000 / 1_000_000 * 5.00) + (500 / 1_000_000 * 15.00)
        assert cost == expected

    def test_exponential_backoff(self, llm_service):
        """Test exponential backoff calculation."""
        delays = [
            llm_service._exponential_backoff(0),
            llm_service._exponential_backoff(1),
            llm_service._exponential_backoff(2),
        ]

        # Should increase exponentially
        assert delays[0] < delays[1] < delays[2]
        # Should not exceed 60 seconds
        assert all(d <= 60 for d in delays)

    def test_complete_requires_api_key(self):
        """Test that complete method fails without API key."""
        # This would require actually setting up the test with no API key
        # In practice, we'd mock this
        pass

    def test_complete_json_parses_valid_json(self, llm_service, mock_openai_client):
        """Test that complete_json correctly parses JSON."""
        # Mock the OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"answer": "test"}'
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.model_dump.return_value = {}

        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_openai_client.return_value = mock_client_instance

        result = llm_service.complete_json(
            system_prompt="You are a helpful assistant.",
            user_prompt="Say hello.",
        )

        assert result["answer"] == "test"

    def test_complete_json_strips_markdown(self, llm_service, mock_openai_client):
        """Test that complete_json strips markdown code blocks."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '```json\n{"answer": "test"}\n```'
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.model_dump.return_value = {}

        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_openai_client.return_value = mock_client_instance

        result = llm_service.complete_json(
            system_prompt="You are a helpful assistant.",
            user_prompt="Say hello.",
        )

        assert result["answer"] == "test"

    def test_get_cost_summary(self, llm_service):
        """Test cost summary generation."""
        # Manually set some costs
        llm_service.total_cost = 0.05
        llm_service.total_tokens = 1000

        summary = llm_service.get_cost_summary()

        assert summary["total_cost_usd"] == 0.05
        assert summary["total_tokens"] == 1000


class TestIsRetryable:
    """Auth/bad-request errors shouldn't burn retries; timeouts/5xx/429 should."""

    def test_auth_error_status_401_not_retryable(self):
        exc = Exception("unauthorized")
        exc.status_code = 401
        assert LLMService._is_retryable(exc) is False

    def test_bad_request_status_400_not_retryable(self):
        exc = Exception("bad request")
        exc.status_code = 400
        assert LLMService._is_retryable(exc) is False

    def test_not_found_status_404_not_retryable(self):
        exc = Exception("not found")
        exc.status_code = 404
        assert LLMService._is_retryable(exc) is False

    def test_rate_limit_status_429_is_retryable(self):
        exc = Exception("rate limited")
        exc.status_code = 429
        assert LLMService._is_retryable(exc) is True

    def test_server_error_status_500_is_retryable(self):
        exc = Exception("server error")
        exc.status_code = 500
        assert LLMService._is_retryable(exc) is True

    def test_requests_timeout_is_retryable(self):
        assert LLMService._is_retryable(requests.exceptions.Timeout("timed out")) is True

    def test_requests_connection_error_is_retryable(self):
        assert LLMService._is_retryable(requests.exceptions.ConnectionError("unreachable")) is True

    def test_requests_http_error_without_status_uses_response_status(self):
        response = MagicMock(status_code=401)
        exc = requests.exceptions.HTTPError("unauthorized", response=response)
        assert LLMService._is_retryable(exc) is False

    def test_unknown_exception_shape_defaults_to_retryable(self):
        # No status_code, not a requests exception — preserves the old
        # always-retry behaviour rather than risking a false "don't retry".
        assert LLMService._is_retryable(ValueError("something odd")) is True


class TestCallLlmRetryDiscrimination:
    """_call_llm should stop immediately on a non-retryable error instead of
    burning through every retry attempt first."""

    @pytest.fixture
    def llm_service(self):
        config = LLMConfig(api_key="test-key", max_retries=3)
        with patch("app.services.llm_service.OpenAI"):
            return LLMService(config)

    def test_non_retryable_error_fails_after_one_attempt(self, llm_service):
        auth_error = Exception("invalid api key")
        auth_error.status_code = 401
        with (
            patch.object(llm_service, "_call_openai", side_effect=auth_error) as mock_call,
            patch("app.services.llm_service.time.sleep") as mock_sleep,
        ):
            with pytest.raises(Exception, match="invalid api key"):
                llm_service._call_llm([{"role": "user", "content": "hi"}], "gpt-4o-mini")
        assert mock_call.call_count == 1
        mock_sleep.assert_not_called()

    def test_retryable_error_retries_up_to_max(self, llm_service):
        timeout_error = requests.exceptions.Timeout("timed out")
        with (
            patch.object(llm_service, "_call_openai", side_effect=timeout_error) as mock_call,
            patch("app.services.llm_service.time.sleep"),
        ):
            with pytest.raises(requests.exceptions.Timeout):
                llm_service._call_llm([{"role": "user", "content": "hi"}], "gpt-4o-mini")
        assert mock_call.call_count == llm_service.config.max_retries + 1

    def test_retryable_error_recovers_on_a_later_attempt(self, llm_service):
        timeout_error = requests.exceptions.Timeout("timed out")
        success = LLMResponse(content="ok", model="gpt-4o-mini")
        with (
            patch.object(
                llm_service, "_call_openai", side_effect=[timeout_error, success]
            ) as mock_call,
            patch("app.services.llm_service.time.sleep"),
        ):
            result = llm_service._call_llm([{"role": "user", "content": "hi"}], "gpt-4o-mini")
        assert result is success
        assert mock_call.call_count == 2


class TestFriendlyLlmError:
    """friendly_llm_error() maps raw provider exceptions to actionable text."""

    def _llm(self, provider=LLMProvider.OPENAI, **overrides):
        config = LLMConfig(provider=provider, api_key="test-key", **overrides)
        with patch("app.services.llm_service.OpenAI"):
            return LLMService(config)

    def test_auth_error_names_the_env_var(self):
        llm = self._llm(LLMProvider.OPENAI)
        exc = Exception("unauthorized")
        exc.status_code = 401
        msg = friendly_llm_error(exc, llm)
        assert "OPENAI_API_KEY" in msg

    def test_authenticationerror_by_class_name_also_detected(self):
        llm = self._llm(LLMProvider.ANTHROPIC)

        class AuthenticationError(Exception):
            pass

        msg = friendly_llm_error(AuthenticationError("nope"), llm)
        assert "ANTHROPIC_API_KEY" in msg

    def test_ollama_connection_error_names_the_container(self):
        llm = self._llm(LLMProvider.OLLAMA, base_url="http://ollama:11434")
        msg = friendly_llm_error(requests.exceptions.ConnectionError("refused"), llm)
        assert "ollama" in msg.lower()

    def test_timeout_error_is_actionable(self):
        llm = self._llm(LLMProvider.OPENAI)
        msg = friendly_llm_error(requests.exceptions.Timeout("timed out"), llm)
        assert "too long" in msg.lower()

    def test_unrecognized_error_falls_back_to_raw_message(self):
        llm = self._llm(LLMProvider.OPENAI)
        msg = friendly_llm_error(ValueError("weird failure"), llm)
        assert "weird failure" in msg


class TestLLMServiceIntegration:
    """Integration-style tests for LLMService."""

    def test_service_initialization_without_api_key_raises(self):
        """Test that initializing without API key raises ValueError."""
        from app.services.llm_service import LLMConfig, LLMProvider

        config = LLMConfig(provider=LLMProvider.OPENAI, api_key="")
        with pytest.raises(ValueError, match="OPENAI_API_KEY not set"):
            LLMService(config=config)


class TestStreamComplete:
    """stream_complete() yields prose incrementally instead of returning it
    all at once — one implementation per provider, since each has its own
    streaming wire format."""

    def _make_chunk(self, content):
        chunk = MagicMock()
        chunk.usage = None
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = content
        return chunk

    def test_openai_streams_deltas_and_records_usage_from_final_chunk(self):
        config = LLMConfig(provider=LLMProvider.OPENAI, api_key="test-key")
        with patch("app.services.llm_service.OpenAI") as mock_openai:
            service = LLMService(config)
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            usage_chunk = MagicMock()
            usage_chunk.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
            usage_chunk.choices = []

            mock_client.chat.completions.create.return_value = [
                self._make_chunk("Hello"),
                self._make_chunk(" world"),
                self._make_chunk(None),  # a chunk with no text delta is skipped
                usage_chunk,
            ]

            chunks = list(service.stream_complete("system", "user"))

        assert chunks == ["Hello", " world"]
        assert service.total_tokens == 15
        assert service.total_cost > 0

        _, kwargs = mock_client.chat.completions.create.call_args
        assert kwargs["stream"] is True
        assert kwargs["stream_options"] == {"include_usage": True}

    def test_deepseek_uses_the_openai_streaming_path(self):
        config = LLMConfig(
            provider=LLMProvider.DEEPSEEK, api_key="test-key", base_url="https://api.deepseek.com"
        )
        with patch("app.services.llm_service.OpenAI") as mock_openai:
            service = LLMService(config)
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = [self._make_chunk("hi")]

            chunks = list(service.stream_complete("system", "user"))
        assert chunks == ["hi"]

    def test_ollama_streams_json_lines_and_records_usage_on_done(self):
        config = LLMConfig(provider=LLMProvider.OLLAMA, base_url="http://ollama:11434")
        service = LLMService(config)

        lines = [
            b'{"message": {"content": "Hel"}, "done": false}',
            b'{"message": {"content": "lo"}, "done": false}',
            b'{"done": true, "prompt_eval_count": 8, "eval_count": 3}',
        ]
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = lines

        with patch("app.services.llm_service.requests.post", return_value=mock_response) as post:
            chunks = list(service.stream_complete("system", "user"))

        assert chunks == ["Hel", "lo"]
        assert service.total_tokens == 11
        _, kwargs = post.call_args
        assert kwargs["json"]["stream"] is True
        assert kwargs["stream"] is True

    def test_anthropic_streams_text_and_records_usage_from_final_message(self):
        config = LLMConfig(provider=LLMProvider.ANTHROPIC, api_key="test-key")
        with (
            patch("app.services.llm_service._ANTHROPIC_AVAILABLE", True),
            patch("app.services.llm_service._anthropic_sdk") as mock_sdk,
        ):
            service = LLMService(config)
            mock_client = MagicMock()
            mock_sdk.Anthropic.return_value = mock_client

            mock_stream = MagicMock()
            mock_stream.text_stream = iter(["Hel", "lo"])
            mock_stream.get_final_message.return_value = MagicMock(
                usage=MagicMock(input_tokens=7, output_tokens=2)
            )
            mock_client.messages.stream.return_value.__enter__.return_value = mock_stream

            chunks = list(service.stream_complete("system", "user"))

        assert chunks == ["Hel", "lo"]
        assert service.total_tokens == 9

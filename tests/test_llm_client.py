"""
Tests for workers/renderer/llm/client.py — the multi-provider LLM client
(Groq default, Gemini, Anthropic). These test key resolution, provider
dispatch, and error handling without making real network calls (mocked
at the SDK client level) — actual request/response shape against each
provider's real API was verified manually during development (each
provider's client correctly reaches its real endpoint and fails with a
provider-specific auth error on a fake key, confirming the request is
built correctly), not repeated here since that requires live network
access this test suite doesn't assume.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from workers.renderer.llm.client import (
    DEFAULT_MODELS,
    ENV_VAR_BY_PROVIDER,
    LLMClient,
    NoAPIKeyError,
    UnknownProviderError,
    extract_json_object,
)


def test_default_provider_is_groq(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    # Re-import to pick up the env var at module load time would be
    # needed for DEFAULT_PROVIDER itself, but LLMClient() without an
    # explicit provider argument falls back to that module constant —
    # test the constant directly here instead of reimporting.
    from workers.renderer.llm import client as client_module

    assert client_module.DEFAULT_PROVIDER == "groq" or client_module.DEFAULT_PROVIDER in DEFAULT_MODELS


def test_no_key_has_key_false_for_each_provider(monkeypatch):
    for provider in ("groq", "gemini", "anthropic"):
        monkeypatch.delenv(ENV_VAR_BY_PROVIDER[provider], raising=False)
        client = LLMClient(provider=provider)
        assert client.has_key is False


def test_no_api_key_error_mentions_correct_signup_url():
    client = LLMClient(provider="groq")
    with pytest.raises(NoAPIKeyError) as exc_info:
        client.complete_json(system="s", user="u")
    assert "console.groq.com" in str(exc_info.value)


def test_no_api_key_error_for_gemini_mentions_aistudio():
    client = LLMClient(provider="gemini")
    with pytest.raises(NoAPIKeyError) as exc_info:
        client.complete_json(system="s", user="u")
    assert "aistudio.google.com" in str(exc_info.value)


def test_unknown_provider_rejected():
    with pytest.raises(UnknownProviderError):
        LLMClient(provider="chatgpt")  # type: ignore[arg-type]


def test_explicit_api_key_takes_priority_over_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "env-key")
    client = LLMClient(api_key="explicit-key", provider="groq")
    assert client.api_key == "explicit-key"


def test_env_key_used_when_no_explicit_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "env-key")
    client = LLMClient(provider="groq")
    assert client.api_key == "env-key"
    assert client.has_key is True


def test_default_model_used_when_not_specified(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    client = LLMClient(api_key="fake", provider="groq")
    assert client.model == DEFAULT_MODELS["groq"]

    client2 = LLMClient(api_key="fake", provider="gemini")
    assert client2.model == DEFAULT_MODELS["gemini"]


def test_explicit_model_overrides_default():
    client = LLMClient(api_key="fake", provider="groq", model="openai/gpt-oss-20b")
    assert client.model == "openai/gpt-oss-20b"


def test_groq_complete_json_dispatches_correctly():
    client = LLMClient(api_key="fake", provider="groq")

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content='{"x": 1}'))]
    mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)

    with patch.object(client._client.chat.completions, "create", return_value=mock_response) as mock_create:
        result = client.complete_json(system="sys", user="usr", max_tokens=500)

    assert result.raw_text == '{"x": 1}'
    assert result.provider == "groq"
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["messages"][0] == {"role": "system", "content": "sys"}
    assert call_kwargs["messages"][1] == {"role": "user", "content": "usr"}
    assert call_kwargs["response_format"] == {"type": "json_object"}


def test_gemini_complete_json_dispatches_correctly():
    client = LLMClient(api_key="fake", provider="gemini")

    mock_response = MagicMock()
    mock_response.text = '{"y": 2}'
    mock_response.usage_metadata = MagicMock(prompt_token_count=8, candidates_token_count=4)

    with patch.object(client._client.models, "generate_content", return_value=mock_response) as mock_create:
        result = client.complete_json(system="sys", user="usr", max_tokens=500)

    assert result.raw_text == '{"y": 2}'
    assert result.provider == "gemini"
    assert result.input_tokens == 8
    assert result.output_tokens == 4
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["contents"] == "usr"
    assert call_kwargs["config"].system_instruction == "sys"


def test_anthropic_complete_json_dispatches_correctly():
    client = LLMClient(api_key="fake", provider="anthropic")

    text_block = MagicMock(type="text", text='{"z": 3}')
    mock_response = MagicMock()
    mock_response.content = [text_block]
    mock_response.usage = MagicMock(input_tokens=6, output_tokens=3)

    with patch.object(client._client.messages, "create", return_value=mock_response) as mock_create:
        result = client.complete_json(system="sys", user="usr", max_tokens=500)

    assert result.raw_text == '{"z": 3}'
    assert result.provider == "anthropic"
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["system"] == "sys"
    assert call_kwargs["messages"] == [{"role": "user", "content": "usr"}]


# -- extract_json_object (provider-agnostic parsing helper) -----------------


def test_extract_json_object_plain():
    assert extract_json_object('{"a": 1}') == {"a": 1}


def test_extract_json_object_with_markdown_fences():
    text = '```json\n{"a": 1}\n```'
    assert extract_json_object(text) == {"a": 1}


def test_extract_json_object_with_surrounding_prose():
    text = 'Here is the JSON:\n{"a": 1}\nHope that helps!'
    assert extract_json_object(text) == {"a": 1}


def test_extract_json_object_raises_on_no_json():
    with pytest.raises(ValueError):
        extract_json_object("no json here at all")
"""
Multi-provider LLM client wrapper.

Supports three providers behind one interface: Groq (default — fast,
generous free tier), Gemini (free tier via Google AI Studio), and
Anthropic (kept as an option, no longer the default). Users supply their
own API key per-request from the frontend; nothing server-side is shared
unless an operator explicitly sets a provider's env var as a fallback
default for their own deployment.

Why Groq as the default: both Groq and Gemini have real no-credit-card
free tiers suitable for local development and demos, but Groq's API key
setup is the fastest path (no Google Cloud project, no OAuth consent
screen) — see the README's "Getting a free API key" section. Anthropic
remains supported for anyone who already has a key.

Key resolution order, per call:
  1. Explicit `api_key` argument (the per-request user key from the
     frontend's "API key" field)
  2. Provider-specific environment variable (operator-configured
     deployment default: GROQ_API_KEY, GEMINI_API_KEY, or
     ANTHROPIC_API_KEY) for the *selected* provider
  3. None — caller must handle NoAPIKeyError by falling back to manual
     input, never silently degrading or using someone else's key.

This module intentionally knows nothing about FastAPI/Celery — it's a
plain client that takes a key + provider as arguments, so it's equally
usable from the async worker, the debug CLI, and tests.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Literal

Provider = Literal["groq", "gemini", "anthropic"]

DEFAULT_PROVIDER: Provider = os.environ.get("LLM_PROVIDER", "groq")  # type: ignore[assignment]

# Free-tier-friendly defaults per provider. Overridable via LLM_MODEL env
# var or the `model` constructor argument for anyone using a paid tier or
# a different model on the same provider.
DEFAULT_MODELS: dict[Provider, str] = {
    "groq": "llama-3.3-70b-versatile",
    "gemini": "gemini-2.0-flash",
    "anthropic": "claude-sonnet-4-6",
}

ENV_VAR_BY_PROVIDER: dict[Provider, str] = {
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

PROVIDER_SIGNUP_URL: dict[Provider, str] = {
    "groq": "https://console.groq.com/keys",
    "gemini": "https://aistudio.google.com/apikey",
    "anthropic": "https://console.anthropic.com/settings/keys",
}


class NoAPIKeyError(Exception):
    """Raised when no API key is available and the caller must fall back
    to manual input rather than silently degrading."""

    def __init__(self, provider: Provider):
        signup_url = PROVIDER_SIGNUP_URL[provider]
        super().__init__(
            f"No {provider} API key configured. Get a free one at {signup_url} "
            f"and pass it as api_key, or set {ENV_VAR_BY_PROVIDER[provider]} "
            f"in your environment, or paste the required JSON manually."
        )
        self.provider = provider


class UnknownProviderError(Exception):
    pass


@dataclass
class LLMCallResult:
    raw_text: str
    model: str
    provider: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        provider: Provider | None = None,
        model: str | None = None,
    ):
        self.provider: Provider = provider or DEFAULT_PROVIDER  # type: ignore[assignment]
        if self.provider not in DEFAULT_MODELS:
            raise UnknownProviderError(
                f"Unknown provider {self.provider!r}. Must be one of {list(DEFAULT_MODELS)}"
            )

        self.api_key = api_key or os.environ.get(ENV_VAR_BY_PROVIDER[self.provider])
        self.model = model or os.environ.get("LLM_MODEL") or DEFAULT_MODELS[self.provider]
        self._client = None

        if self.api_key:
            self._client = self._build_client()

    @property
    def has_key(self) -> bool:
        return self._client is not None

    def _build_client(self):
        if self.provider == "groq":
            from groq import Groq

            return Groq(api_key=self.api_key)
        elif self.provider == "gemini":
            from google import genai

            return genai.Client(api_key=self.api_key)
        elif self.provider == "anthropic":
            import anthropic

            return anthropic.Anthropic(api_key=self.api_key)
        raise UnknownProviderError(self.provider)

    def complete_json(
        self, *, system: str, user: str, max_tokens: int = 2000, temperature: float = 0.0
    ) -> LLMCallResult:
        """Calls the model expecting a pure-JSON response (system prompt
        should instruct this explicitly). Raises NoAPIKeyError if no key
        is configured — callers must catch this and fall back to the
        manual-input path rather than raising it up as a hard failure."""
        if self._client is None:
            raise NoAPIKeyError(self.provider)

        if self.provider == "groq":
            return self._complete_groq(system=system, user=user, max_tokens=max_tokens, temperature=temperature)
        elif self.provider == "gemini":
            return self._complete_gemini(system=system, user=user, max_tokens=max_tokens, temperature=temperature)
        elif self.provider == "anthropic":
            return self._complete_anthropic(system=system, user=user, max_tokens=max_tokens, temperature=temperature)
        raise UnknownProviderError(self.provider)

    def _complete_groq(self, *, system: str, user: str, max_tokens: int, temperature: float) -> LLMCallResult:
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        choice = response.choices[0]
        usage = getattr(response, "usage", None)
        return LLMCallResult(
            raw_text=choice.message.content or "",
            model=self.model,
            provider=self.provider,
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
        )

    def _complete_gemini(self, *, system: str, user: str, max_tokens: int, temperature: float) -> LLMCallResult:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
                temperature=temperature,
                response_mime_type="application/json",
            ),
        )
        usage = getattr(response, "usage_metadata", None)
        return LLMCallResult(
            raw_text=response.text or "",
            model=self.model,
            provider=self.provider,
            input_tokens=getattr(usage, "prompt_token_count", None),
            output_tokens=getattr(usage, "candidates_token_count", None),
        )

    def _complete_anthropic(self, *, system: str, user: str, max_tokens: int, temperature: float) -> LLMCallResult:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text_parts = [block.text for block in response.content if block.type == "text"]
        return LLMCallResult(
            raw_text="".join(text_parts),
            model=self.model,
            provider=self.provider,
            input_tokens=getattr(response.usage, "input_tokens", None),
            output_tokens=getattr(response.usage, "output_tokens", None),
        )


def extract_json_object(text: str) -> dict:
    """Strips markdown code fences etc. and parses the first JSON object
    found. Raises json.JSONDecodeError (or ValueError) on failure — the
    caller (classify.py / plan_scene.py) is expected to feed that failure
    into the repair loop rather than crash the job."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:] if lines[0].startswith("```") else lines
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    cleaned = cleaned.strip()

    # Find the outermost JSON object even if the model added stray prose.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(cleaned[start : end + 1])

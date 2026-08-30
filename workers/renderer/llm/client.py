"""
LLM client wrapper.

Per project decision: users supply their own Anthropic API key (stored
only for the duration of the request — never persisted server-side in
plaintext, see apps/api/deps_/llm_key.py for how the API layer handles
this). If no key is supplied/configured, the pipeline falls back to
asking the user to paste the classification/scene-plan JSON manually
(see workers/renderer/pipeline/classify.py and plan_scene.py for the
fallback branches) rather than silently failing or using a shared key.

This module intentionally knows nothing about FastAPI/Celery — it's a
plain client that takes a key as an argument, so it's equally usable from
the async worker, the debug CLI, and tests.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

import anthropic

DEFAULT_MODEL = "claude-sonnet-4-6"


class NoAPIKeyError(Exception):
    """Raised when no API key is available and the caller must fall back
    to manual input rather than silently degrading."""


@dataclass
class LLMCallResult:
    raw_text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMClient:
    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL):
        # Resolution order: explicit argument (per-request user key) >
        # environment variable (operator-configured deployment default,
        # e.g. an operator who wants to run this without per-user keys) >
        # none (caller must handle NoAPIKeyError by falling back to
        # manual input).
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self._client: anthropic.Anthropic | None = None
        if self.api_key:
            self._client = anthropic.Anthropic(api_key=self.api_key)

    @property
    def has_key(self) -> bool:
        return self._client is not None

    def complete_json(
        self, *, system: str, user: str, max_tokens: int = 2000, temperature: float = 0.0
    ) -> LLMCallResult:
        """Calls the model expecting a pure-JSON response (system prompt
        should instruct this explicitly). Raises NoAPIKeyError if no key
        is configured — callers must catch this and fall back to the
        manual-input path rather than raising it up as a hard failure."""
        if self._client is None:
            raise NoAPIKeyError(
                "No Anthropic API key configured. Supply one for this request "
                "or paste the required JSON manually."
            )

        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text_parts = [block.text for block in response.content if block.type == "text"]
        raw_text = "".join(text_parts)
        return LLMCallResult(
            raw_text=raw_text,
            model=self.model,
            input_tokens=getattr(response.usage, "input_tokens", None),
            output_tokens=getattr(response.usage, "output_tokens", None),
        )


def extract_json_object(text: str) -> dict:
    """Strips markdown code fences etc. and parses the first JSON object
    found. Raises json.JSONDecodeError (or ValueError) on failure — the
    caller (classify.py / plan_scene.py) is expected to feed that failure
    into the repair loop (§14) rather than crash the job."""
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

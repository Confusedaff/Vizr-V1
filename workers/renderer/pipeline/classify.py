"""
classify.py — Pipeline stage 1: turn a natural-language prompt into a
`visualization_type` + extracted input parameters.

Two paths:
  - LLM path: if an API key is available (per-request user key, or an
    operator-configured provider env var — GROQ_API_KEY, GEMINI_API_KEY,
    or ANTHROPIC_API_KEY depending on LLM_PROVIDER), ask the model to
    classify + extract in one structured-JSON call.
  - Manual fallback: if no key is available, raise `NeedsManualInput` so
    the caller (CLI or API layer) can prompt the user to directly supply
    `visualization_type` + `input` themselves instead of free-text.

This stage NEVER returns a `Scene` — only classification + raw input
params. Scene *construction* (with the full step list) is plan_scene.py's
job. Keeping these separate mirrors §12: small, single-purpose LLM calls
are easier to validate, retry, and debug than one big "do everything" call.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from packages.scene_schema import VISUALIZATION_TYPES
from workers.renderer.llm.client import LLMClient, NoAPIKeyError, extract_json_object

CLASSIFY_SYSTEM_PROMPT = f"""You are a classifier for an algorithm-visualization tool.
Given a natural-language prompt describing an algorithm or data-structure
question, respond with ONLY a JSON object (no prose, no markdown fences):

{{
  "visualization_type": one of {VISUALIZATION_TYPES},
  "confidence": float between 0 and 1,
  "input": {{
    "array": [list of ints] or null,
    "target": int or null,
    "tree_values": [list of ints or null, level-order] or null,
    "graph_nodes": [list of ints] or null,
    "graph_edges": [[int,int], ...] or null
  }},
  "title": short human-readable title for the visualization
}}

Extract concrete values mentioned in the prompt. If the prompt gives no
concrete array/tree/graph, invent a small, reasonable canonical example
appropriate to the visualization_type (e.g. a 6-8 element sorted array for
binary_search). Never invent an array longer than 12 elements or a tree/graph
larger than 10 nodes for illustrative purposes unless the prompt explicitly
provides more.
"""


class NeedsManualInput(Exception):
    """Raised when no LLM key is available — caller must collect
    visualization_type + input from the user directly."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass
class ClassificationResult:
    visualization_type: str
    confidence: float
    input_params: dict = field(default_factory=dict)
    title: str = "Visualization"
    raw_llm_response: str | None = None


def classify_prompt(prompt: str, *, llm_client: LLMClient | None = None) -> ClassificationResult:
    client = llm_client or LLMClient()

    if not client.has_key:
        raise NeedsManualInput(
            "No LLM API key configured. Please provide visualization_type "
            "and input parameters manually (see manual classification form)."
        )

    result = client.complete_json(system=CLASSIFY_SYSTEM_PROMPT, user=prompt, max_tokens=800)

    try:
        parsed = extract_json_object(result.raw_text)
    except (ValueError, json.JSONDecodeError) as e:
        raise ValueError(f"Classifier returned unparseable JSON: {e}") from e

    viz_type = parsed.get("visualization_type")
    if viz_type not in VISUALIZATION_TYPES:
        raise ValueError(
            f"Classifier returned unknown visualization_type={viz_type!r}. "
            f"Must be one of {VISUALIZATION_TYPES}"
        )

    return ClassificationResult(
        visualization_type=viz_type,
        confidence=float(parsed.get("confidence", 0.5)),
        input_params=parsed.get("input", {}) or {},
        title=parsed.get("title", "Visualization"),
        raw_llm_response=result.raw_text,
    )


def classify_from_manual_input(
    visualization_type: str, input_params: dict, title: str = "Visualization"
) -> ClassificationResult:
    """Used by the manual-fallback path — same return shape as the LLM
    path so downstream code (plan_scene.py) doesn't need to know which
    path produced it."""
    if visualization_type not in VISUALIZATION_TYPES:
        raise ValueError(
            f"Unknown visualization_type={visualization_type!r}. "
            f"Must be one of {VISUALIZATION_TYPES}"
        )
    return ClassificationResult(
        visualization_type=visualization_type,
        confidence=1.0,
        input_params=input_params,
        title=title,
        raw_llm_response=None,
    )

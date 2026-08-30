"""
plan_scene.py — Pipeline stage 2: given a classification result, produce
the full Scene JSON (steps + narration) that the deterministic renderer
will execute.

Same two-path structure as classify.py: LLM-driven if a key is available,
manual-paste fallback otherwise. The manual fallback is genuinely usable
standalone — a user (or this Claude session, when helping someone
without an API key) can hand-write the steps list directly, since it's
plain JSON following the schema in packages/scene_schema.

The JSON Schema shown to the LLM is generated directly from the Pydantic
models (model_json_schema()) rather than hand-maintained separately —
this is what "single source of truth" (§9/§25) means in practice: the
schema the LLM sees and the schema that validates its output are
guaranteed to be the same schema, because they're the same Python object.
"""
from __future__ import annotations

import json

from packages.scene_schema import ACTION_TO_MODEL, Scene, SceneInput
from packages.scene_schema.errors import SceneValidationError
from pydantic import ValidationError
from workers.renderer.llm.client import LLMClient, extract_json_object
from workers.renderer.pipeline.classify import ClassificationResult, NeedsManualInput


def _build_plan_system_prompt(visualization_type: str) -> str:
    action_names = sorted(ACTION_TO_MODEL.keys())
    action_schemas = {
        name: model.model_json_schema() for name, model in ACTION_TO_MODEL.items()
    }
    return f"""You are a scene planner for an algorithm-visualization tool.
The visualization_type is: {visualization_type}

Produce ONLY a JSON object (no prose, no markdown fences) matching this shape:
{{
  "steps": [ ...list of step objects, each with an "action" field... ],
  "narration": [ ...list of short caption strings, roughly one per step... ]
}}

Every step's "action" MUST be one of: {action_names}
Here are the exact fields each action requires (JSON Schema per action):
{json.dumps(action_schemas, indent=2)}

Rules:
- Only reference indices/nodes that exist in the given input.
- A pointer name used in remove_pointer or advance_pointer_node must have
  been set_pointer'd earlier in the steps list.
- Keep steps between 4 and 30 for a clear, well-paced video.
- narration entries should be short (under 80 characters), plain-language
  captions describing what's happening at that step — not a repeat of the
  action's raw parameters.
"""


def plan_scene(
    classification: ClassificationResult, *, llm_client: LLMClient | None = None
) -> Scene:
    client = llm_client or LLMClient()

    if not client.has_key:
        raise NeedsManualInput(
            "No LLM API key configured. Please provide the scene 'steps' "
            "and 'narration' manually as JSON (see manual scene-plan form)."
        )

    system = _build_plan_system_prompt(classification.visualization_type)
    user = (
        f"input: {json.dumps(classification.input_params)}\n"
        f"title: {classification.title}\n"
        "Produce the steps/narration JSON now."
    )
    result = client.complete_json(system=system, user=user, max_tokens=3000)

    try:
        parsed = extract_json_object(result.raw_text)
    except (ValueError, json.JSONDecodeError) as e:
        raise ValueError(f"Scene planner returned unparseable JSON: {e}") from e

    return assemble_and_validate_scene(
        visualization_type=classification.visualization_type,
        title=classification.title,
        input_params=classification.input_params,
        steps=parsed.get("steps", []),
        narration=parsed.get("narration", []),
    )


def assemble_and_validate_scene(
    *,
    visualization_type: str,
    title: str,
    input_params: dict,
    steps: list[dict],
    narration: list[str],
) -> Scene:
    """Shared by both the LLM path and the manual-fallback path (and by
    the debug CLI, which lets a developer hand-write a scene JSON file
    and validate it directly) — this is THE validation chokepoint. Every
    Scene that ever reaches the renderer passed through here."""
    try:
        return Scene(
            version="1.0",
            visualization_type=visualization_type,
            title=title[:100],
            input=SceneInput(**input_params),
            steps=steps,
            narration=narration,
        )
    except ValidationError as e:
        raise SceneValidationError.from_pydantic(e) from e


def plan_scene_from_manual_input(
    classification: ClassificationResult, steps: list[dict], narration: list[str]
) -> Scene:
    return assemble_and_validate_scene(
        visualization_type=classification.visualization_type,
        title=classification.title,
        input_params=classification.input_params,
        steps=steps,
        narration=narration,
    )

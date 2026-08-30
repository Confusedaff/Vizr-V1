"""
repair.py — Pipeline stage: given a Scene that failed validation (schema
validation, AST safety, or render-quality validation), ask the LLM to fix
it, re-validate, and repeat up to `max_attempts`.

This is application-level repair (fixing content the LLM got wrong),
distinct from Celery/infra-level retry (fixing transient failures like a
dropped connection) — see §14 vs §21 in the original spec. Infra retry is
handled at the Celery task level (workers/renderer/tasks.py); this module
only ever re-invokes the LLM with specific, structured error context.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from packages.scene_schema import Scene
from packages.scene_schema.errors import SceneValidationError
from workers.renderer.llm.client import LLMClient, extract_json_object
from workers.renderer.pipeline.plan_scene import assemble_and_validate_scene

MAX_REPAIR_ATTEMPTS = 3

REPAIR_SYSTEM_PROMPT = """You previously produced a scene plan (steps + narration)
for an algorithm visualization, but it failed validation. You will be given
the original input parameters, the JSON you produced, and the specific
validation error(s). Fix ONLY what's needed to pass validation, preserving
the original intent as closely as possible. Respond with ONLY the corrected
JSON object (same shape as before: {"steps": [...], "narration": [...]}),
no prose, no markdown fences.
"""


@dataclass
class RepairAttemptLog:
    attempt: int
    error_before: str
    success: bool
    raw_llm_response: str | None = None


@dataclass
class RepairResult:
    scene: Scene | None
    attempts: list[RepairAttemptLog] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return self.scene is not None

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)


def repair_scene(
    *,
    visualization_type: str,
    title: str,
    input_params: dict,
    broken_steps: list[dict],
    broken_narration: list[str],
    error: SceneValidationError | Exception,
    llm_client: LLMClient | None = None,
    max_attempts: int = MAX_REPAIR_ATTEMPTS,
) -> RepairResult:
    client = llm_client or LLMClient()
    result = RepairResult(scene=None)

    current_steps = broken_steps
    current_narration = broken_narration
    current_error: Exception = error

    for attempt in range(1, max_attempts + 1):
        error_context = (
            current_error.as_repair_context()
            if isinstance(current_error, SceneValidationError)
            else str(current_error)
        )

        if not client.has_key:
            result.attempts.append(
                RepairAttemptLog(attempt=attempt, error_before=error_context, success=False)
            )
            break

        user_msg = (
            f"input: {json.dumps(input_params)}\n"
            f"broken JSON: {json.dumps({'steps': current_steps, 'narration': current_narration})}\n"
            f"validation error: {error_context}\n"
            "Produce corrected JSON now."
        )

        candidate_steps = current_steps
        candidate_narration = current_narration
        llm_raw_text = None

        try:
            llm_result = client.complete_json(
                system=REPAIR_SYSTEM_PROMPT, user=user_msg, max_tokens=3000
            )
            llm_raw_text = llm_result.raw_text
            parsed = extract_json_object(llm_result.raw_text)
            candidate_steps = parsed.get("steps", [])
            candidate_narration = parsed.get("narration", [])

            scene = assemble_and_validate_scene(
                visualization_type=visualization_type,
                title=title,
                input_params=input_params,
                steps=candidate_steps,
                narration=candidate_narration,
            )
            result.scene = scene
            result.attempts.append(
                RepairAttemptLog(
                    attempt=attempt,
                    error_before=error_context,
                    success=True,
                    raw_llm_response=llm_raw_text,
                )
            )
            return result

        except Exception as e:  # noqa: BLE001 — repair loop must catch anything and keep retrying
            result.attempts.append(
                RepairAttemptLog(
                    attempt=attempt,
                    error_before=error_context,
                    success=False,
                    raw_llm_response=llm_raw_text,
                )
            )
            current_steps = candidate_steps
            current_narration = candidate_narration
            current_error = e
            continue

    return result

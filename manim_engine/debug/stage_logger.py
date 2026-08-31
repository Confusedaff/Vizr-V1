"""
Granular per-stage debuggability.

Every pipeline stage (classify -> plan_scene -> validate_scene ->
generate_code -> validate_code -> render -> validate_render -> upload)
writes its inputs, outputs, timing, and any error through a StageLogger
into a per-job debug directory:

    debug_runs/{job_id}/
      00_classify/{input.json, output.json, meta.json}
      01_plan_scene/{input.json, output.json, meta.json}
      02_validate_scene/{input.json, output.json, meta.json}
      03_generate_code/{input.json, output.py, meta.json}
      04_validate_code/{input.json, output.json, meta.json}
      05_render/{scene.py, stdout.log, stderr.log, meta.json, video.mp4}
      06_validate_render/{report.json, worst_frames/*.png, meta.json}
      07_upload/{meta.json}
      manifest.json                 <- RenderManifest, see manifest.py
      pipeline.log                  <- structured JSON lines, all stages

This means: "the frame quality is low" is never a dead end. You can go to
debug_runs/{job_id}/06_validate_render/report.json, see exactly which
frames failed which checks, open worst_frames/*.png, then go to
05_render/scene.py to see the exact generated Manim code that produced
them, and 02_validate_scene/output.json to see the scene graph that code
was generated from. Every layer is independently inspectable.

This module has zero dependency on FastAPI/Celery/Postgres — it works
identically whether called from the real async worker or from the
standalone debug CLI (debug_cli/run_stage.py), which is the point: the
same code path is exercised in both, so debugging via the CLI is
debugging the real thing, not a simulation of it.
"""
from __future__ import annotations

import json
import logging
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEBUG_RUNS_ROOT = Path("debug_runs")

STAGE_DIR_NAMES = {
    "classify": "00_classify",
    "plan_scene": "01_plan_scene",
    "validate_scene": "02_validate_scene",
    "generate_code": "03_generate_code",
    "validate_code": "04_validate_code",
    "render": "05_render",
    "validate_render": "06_validate_render",
    "upload": "07_upload",
}


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return str(obj)


@dataclass
class StageArtifact:
    """Handle returned by StageLogger.stage(), used to write outputs and
    mark success/failure for a single stage's directory."""

    stage_name: str
    stage_dir: Path
    started_at: float = field(default_factory=time.time)

    def write_input(self, data: Any, filename: str = "input.json") -> None:
        self._write_json(filename, data)

    def write_output(self, data: Any, filename: str = "output.json") -> None:
        self._write_json(filename, data)

    def write_text(self, filename: str, text: str) -> None:
        (self.stage_dir / filename).write_text(text)

    def write_bytes(self, filename: str, data: bytes) -> None:
        (self.stage_dir / filename).write_bytes(data)

    def copy_file(self, src: str | Path, filename: str | None = None) -> Path:
        src = Path(src)
        dest = self.stage_dir / (filename or src.name)
        shutil.copy2(src, dest)
        return dest

    def _write_json(self, filename: str, data: Any) -> None:
        path = self.stage_dir / filename
        path.write_text(json.dumps(data, indent=2, default=_json_default))

    def finalize(self, *, success: bool, error: str | None = None, extra: dict | None = None) -> None:
        meta = {
            "stage": self.stage_name,
            "success": success,
            "duration_seconds": round(time.time() - self.started_at, 4),
            "error": error,
            **(extra or {}),
        }
        self._write_json("meta.json", meta)


class StageLogger:
    """One StageLogger per job. Owns debug_runs/{job_id}/ and the
    structured pipeline.log stream."""

    def __init__(self, job_id: str, *, root: Path | None = None, echo_to_console: bool = True):
        self.job_id = job_id
        self.root = (root or DEBUG_RUNS_ROOT) / job_id
        self.root.mkdir(parents=True, exist_ok=True)
        self.echo_to_console = echo_to_console

        self._logger = logging.getLogger(f"vizr.job.{job_id}")
        self._logger.setLevel(logging.DEBUG)
        self._logger.handlers.clear()

        file_handler = logging.FileHandler(self.root / "pipeline.log")
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(file_handler)

        if echo_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(console_handler)

    def log_event(self, event: str, **fields: Any) -> None:
        record = {"job_id": self.job_id, "ts": time.time(), "event": event, **fields}
        self._logger.info(json.dumps(record, default=_json_default))

    def stage(self, stage_name: str) -> StageArtifact:
        dir_name = STAGE_DIR_NAMES.get(stage_name, stage_name)
        stage_dir = self.root / dir_name
        stage_dir.mkdir(parents=True, exist_ok=True)
        self.log_event("stage_started", stage=stage_name)
        return StageArtifact(stage_name=stage_name, stage_dir=stage_dir)

    def stage_finished(self, stage_name: str, *, success: bool, error: str | None = None) -> None:
        self.log_event("stage_finished", stage=stage_name, success=success, error=error)

    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

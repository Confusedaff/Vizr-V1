"""
RenderManifest: a single JSON document summarizing an entire job's
pipeline run end-to-end — the "start here" file for debugging any job.

Written incrementally as stages complete, finalized at job end (success
or failure). This is intentionally a plain dataclass (not a DB model) so
it works identically for a Postgres-backed job or a bare debug-CLI run
with no database at all.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class StageTiming:
    stage: str
    started_at: float
    finished_at: float | None = None
    success: bool | None = None
    error: str | None = None
    attempt: int = 1

    @property
    def duration_seconds(self) -> float | None:
        if self.finished_at is None:
            return None
        return round(self.finished_at - self.started_at, 4)


@dataclass
class RenderManifest:
    job_id: str
    prompt: str | None = None
    visualization_type: str | None = None
    architecture_path: str | None = None  # "structured" | "fallback"
    created_at: float = field(default_factory=time.time)
    stages: list[StageTiming] = field(default_factory=list)
    final_status: str | None = None
    video_path: str | None = None
    video_duration_seconds: float | None = None
    quality_passed: bool | None = None
    quality_error_count: int = 0
    quality_warning_count: int = 0
    repair_attempts: int = 0
    cache_hit: bool = False
    renderer_version: str | None = None
    notes: list[str] = field(default_factory=list)

    def start_stage(self, stage: str, attempt: int = 1) -> StageTiming:
        timing = StageTiming(stage=stage, started_at=time.time(), attempt=attempt)
        self.stages.append(timing)
        return timing

    def finish_stage(self, timing: StageTiming, *, success: bool, error: str | None = None) -> None:
        timing.finished_at = time.time()
        timing.success = success
        timing.error = error

    def add_note(self, note: str) -> None:
        self.notes.append(f"[{time.strftime('%H:%M:%S')}] {note}")

    def total_duration_seconds(self) -> float:
        if not self.stages:
            return 0.0
        finished = [s.finished_at for s in self.stages if s.finished_at]
        if not finished:
            return round(time.time() - self.created_at, 4)
        return round(max(finished) - self.created_at, 4)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["total_duration_seconds"] = self.total_duration_seconds()
        for s in d["stages"]:
            started = s["started_at"]
            finished = s["finished_at"]
            s["duration_seconds"] = round(finished - started, 4) if finished else None
        return d

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "RenderManifest":
        data = json.loads(Path(path).read_text())
        stages = [StageTiming(**{k: v for k, v in s.items() if k != "duration_seconds"})
                  for s in data.pop("stages", [])]
        data.pop("total_duration_seconds", None)
        manifest = cls(**{k: v for k, v in data.items()})
        manifest.stages = stages
        return manifest

    def print_summary(self) -> str:
        lines = [
            f"Job {self.job_id}  [{self.final_status or 'in progress'}]",
            f"  type: {self.visualization_type}  path: {self.architecture_path}  "
            f"cache_hit: {self.cache_hit}  repairs: {self.repair_attempts}",
        ]
        for s in self.stages:
            status = "OK" if s.success else ("FAIL" if s.success is False else "...")
            dur = f"{s.duration_seconds:.2f}s" if s.duration_seconds is not None else "?"
            lines.append(f"  [{status:4s}] {s.stage:20s} attempt={s.attempt} {dur}")
        if self.quality_passed is not None:
            lines.append(
                f"  quality: {'PASS' if self.quality_passed else 'FAIL'} "
                f"(errors={self.quality_error_count}, warnings={self.quality_warning_count})"
            )
        if self.video_path:
            lines.append(f"  video: {self.video_path} ({self.video_duration_seconds}s)")
        for n in self.notes:
            lines.append(f"  note: {n}")
        return "\n".join(lines)

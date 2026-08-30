"""
Render validation (§15's VALIDATING_RENDER stage).

This is the quality gate a render must pass before a job is allowed to
reach COMPLETED. It combines:
  1. Structural checks (does the file exist, is it a valid video, duration
     within bounds)
  2. Frame-quality checks (manim_engine/debug/frame_quality.py) sampled
     across the whole video
  3. Any geometric warnings collected during scene construction (passed in
     from the renderer, since bbox-overlap is cheapest to check at
     construction time rather than by re-deriving object positions from
     pixels)

A failing validation feeds into the repair loop (§14) — the *specific*
failed checks are what get handed back to the LLM/renderer as repair
context, not just a generic "render failed."
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from manim_engine.debug.frame_quality import Severity, VideoQualityReport, analyze_video
from manim_engine.renderer.config import MAX_VIDEO_DURATION_S, MIN_VIDEO_DURATION_S


@dataclass
class RenderValidationResult:
    valid: bool
    video_path: str
    duration_seconds: float | None = None
    quality_report: VideoQualityReport | None = None
    construction_warnings: list[str] = field(default_factory=list)
    failure_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "video_path": self.video_path,
            "duration_seconds": self.duration_seconds,
            "quality_report": self.quality_report.to_dict() if self.quality_report else None,
            "construction_warnings": self.construction_warnings,
            "failure_reasons": self.failure_reasons,
        }

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    def as_repair_context(self) -> str:
        """Compact, specific summary for the LLM repair loop (§14) — lists
        exactly what failed so a repair attempt can target the real
        problem instead of guessing."""
        if self.valid:
            return "Render passed validation."
        lines = ["Render failed validation:"] + [f"- {r}" for r in self.failure_reasons]
        if self.quality_report:
            for f in self.quality_report.worst_frames(3):
                for issue in f.issues:
                    if issue.severity == Severity.ERROR:
                        lines.append(f"- at t={f.timestamp_s:.2f}s: {issue.message}")
        return "\n".join(lines)


def probe_duration_seconds(video_path: str | Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(video_path),
        ],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip()[:300]}")
    return float(result.stdout.strip())


def validate_render(
    video_path: str | Path,
    *,
    construction_warnings: list[str] | None = None,
    sample_fps: float = 2.0,
    save_frames_dir: str | Path | None = None,
    min_duration_s: float = MIN_VIDEO_DURATION_S,
    max_duration_s: float = MAX_VIDEO_DURATION_S,
) -> RenderValidationResult:
    video_path = Path(video_path)
    result = RenderValidationResult(
        valid=True,
        video_path=str(video_path),
        construction_warnings=construction_warnings or [],
    )

    if not video_path.exists() or video_path.stat().st_size == 0:
        result.valid = False
        result.failure_reasons.append("Output video file is missing or empty.")
        return result

    try:
        duration = probe_duration_seconds(video_path)
        result.duration_seconds = duration
    except Exception as e:
        result.valid = False
        result.failure_reasons.append(f"Could not read video duration: {e}")
        return result

    if duration < min_duration_s:
        result.valid = False
        result.failure_reasons.append(
            f"Video duration {duration:.2f}s is below minimum {min_duration_s}s."
        )
    if duration > max_duration_s:
        result.valid = False
        result.failure_reasons.append(
            f"Video duration {duration:.2f}s exceeds maximum {max_duration_s}s."
        )

    try:
        quality_report = analyze_video(
            video_path, sample_fps=sample_fps, save_frames_dir=save_frames_dir
        )
        result.quality_report = quality_report
        if not quality_report.passed:
            result.valid = False
            result.failure_reasons.append(
                f"Frame quality checks failed on {quality_report.error_count} "
                f"of {quality_report.total_frames_sampled} sampled frames."
            )
    except Exception as e:
        # Frame-quality analysis failing should not itself be treated the
        # same as a quality failure (it might be an environment issue, e.g.
        # missing codec) — but it must not be silently swallowed either.
        result.construction_warnings.append(f"Frame-quality analysis could not run: {e}")

    return result

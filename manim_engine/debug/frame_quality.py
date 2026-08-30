"""
Frame quality inspector.

This is the core of "make it debuggable if frame quality is low." It
operates on actual rendered pixels — not on the Manim object graph — so it
catches problems that only manifest post-render (anti-aliasing artifacts,
actual off-screen clipping, actual overlap/occlusion, actual low contrast)
rather than problems we merely *believe* the layout math prevents.

Two ways to use this:
  1. Automated quality gate: `analyze_frame()` / `analyze_video()` run as
     part of render validation (§15's VALIDATING_RENDER stage) and can
     fail a render before it ever reaches the user.
  2. Manual debugging: the frame inspector CLI (debug_cli/inspect_frames.py)
     dumps every issue found, with the offending frame(s) saved as PNGs
     and an HTML report, for a human to look at.

Design principle: every check returns a structured `FrameIssue` with a
`severity`, a human-readable `message`, and — wherever a location makes
sense — pixel coordinates, so the report can literally draw a box around
the problem area on the saved frame.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import numpy as np
from PIL import Image


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class FrameIssue:
    check: str
    severity: Severity
    message: str
    bbox: tuple[int, int, int, int] | None = None  # x0,y0,x1,y1 in pixels

    def to_dict(self) -> dict:
        return {
            "check": self.check,
            "severity": self.severity.value,
            "message": self.message,
            "bbox": list(self.bbox) if self.bbox else None,
        }


@dataclass
class FrameReport:
    frame_index: int
    timestamp_s: float
    width: int
    height: int
    issues: list[FrameIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == Severity.ERROR for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == Severity.WARNING for i in self.issues)

    def to_dict(self) -> dict:
        return {
            "frame_index": self.frame_index,
            "timestamp_s": round(self.timestamp_s, 3),
            "width": self.width,
            "height": self.height,
            "issues": [i.to_dict() for i in self.issues],
        }


@dataclass
class VideoQualityReport:
    """Aggregate report across all sampled frames of a render."""

    video_path: str
    total_frames_sampled: int
    frame_reports: list[FrameReport] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.frame_reports if f.has_errors)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.frame_reports if f.has_warnings)

    @property
    def passed(self) -> bool:
        return self.error_count == 0

    def worst_frames(self, n: int = 5) -> list[FrameReport]:
        def score(f: FrameReport) -> int:
            return sum(
                3 if i.severity == Severity.ERROR else 1 for i in f.issues
            )

        return sorted(
            [f for f in self.frame_reports if f.issues], key=score, reverse=True
        )[:n]

    def to_dict(self) -> dict:
        return {
            "video_path": self.video_path,
            "total_frames_sampled": self.total_frames_sampled,
            "passed": self.passed,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "frames": [f.to_dict() for f in self.frame_reports],
        }

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))


# --------------------------------------------------------------------------
# Individual checks. Each takes a numpy RGB(A) array (H, W, C) and returns
# a list of FrameIssue. Keep each check narrow and independently testable —
# same philosophy as the LLM pipeline stages (§12): small, diagnosable units.
# --------------------------------------------------------------------------


def check_blank_frame(
    arr: np.ndarray, *, bg_tolerance: int = 6, min_nonbg_fraction: float = 0.002
) -> list[FrameIssue]:
    """Flags frames that are (near-)entirely a single flat color — usually
    means nothing rendered (e.g. an empty VGroup, a crashed animation that
    left a blank hold frame, or a scene that starts before content exists)."""
    issues = []
    h, w = arr.shape[:2]
    rgb = arr[:, :, :3].astype(np.int16)

    # Most common pixel value, sampled from corners (background is
    # virtually always what touches the frame edges).
    corner_px = np.concatenate(
        [rgb[0, 0:5], rgb[0, -5:], rgb[-1, 0:5], rgb[-1, -5:]]
    )
    bg_estimate = np.median(corner_px, axis=0)

    diff = np.abs(rgb - bg_estimate).sum(axis=2)
    nonbg_mask = diff > bg_tolerance
    nonbg_fraction = nonbg_mask.sum() / (h * w)

    if nonbg_fraction < min_nonbg_fraction:
        issues.append(
            FrameIssue(
                check="blank_frame",
                severity=Severity.ERROR,
                message=(
                    f"Frame is {100 * (1 - nonbg_fraction):.2f}% flat background "
                    f"color — likely no content rendered on this frame."
                ),
            )
        )
    return issues


def check_offscreen_clipping(
    arr: np.ndarray, *, edge_px: int = 2, bg_tolerance: int = 6
) -> list[FrameIssue]:
    """Flags non-background pixels touching the true frame edge — a strong
    signal that a mobject is clipped/cut off rather than properly
    contained within the safe frame (the boundary-protection math in
    layout.py *should* prevent this; this check verifies it actually did,
    on real pixels, not just in theory)."""
    issues = []
    h, w = arr.shape[:2]
    rgb = arr[:, :, :3].astype(np.int16)
    corner_px = np.concatenate(
        [rgb[0, 0:5], rgb[0, -5:], rgb[-1, 0:5], rgb[-1, -5:]]
    )
    bg_estimate = np.median(corner_px, axis=0)

    edges = {
        "top": rgb[0:edge_px, :, :],
        "bottom": rgb[h - edge_px : h, :, :],
        "left": rgb[:, 0:edge_px, :],
        "right": rgb[:, w - edge_px : w, :],
    }
    for edge_name, region in edges.items():
        diff = np.abs(region.astype(np.int16) - bg_estimate).sum(axis=2)
        nonbg = diff > bg_tolerance
        if nonbg.sum() > 0:
            ys, xs = np.where(nonbg.any(axis=-1) if nonbg.ndim > 2 else nonbg)
            frac = nonbg.sum() / nonbg.size
            if frac > 0.003:  # ignore a handful of anti-aliased stray pixels
                issues.append(
                    FrameIssue(
                        check="offscreen_clipping",
                        severity=Severity.ERROR,
                        message=(
                            f"Content appears clipped at the {edge_name} edge "
                            f"({frac * 100:.1f}% of edge pixels are non-background)."
                        ),
                    )
                )
    return issues


def check_low_contrast_text_regions(
    arr: np.ndarray, *, min_local_contrast: float = 25.0
) -> list[FrameIssue]:
    """Approximate low-contrast detection: samples local patches and flags
    ones with very low standard deviation *and* non-background mean
    (i.e. "something is drawn here but it's nearly invisible against its
    surroundings"). This is a heuristic proxy for illegible text/thin
    strokes, not a text detector — cheap enough to run on every sampled
    frame."""
    issues = []
    gray = np.asarray(Image.fromarray(arr[:, :, :3]).convert("L"))
    h, w = gray.shape
    patch = 24
    bg_val = float(np.median(np.concatenate([gray[0, :20], gray[-1, :20]])))

    low_contrast_patches = 0
    total_content_patches = 0
    for y in range(0, h - patch, patch):
        for x in range(0, w - patch, patch):
            block = gray[y : y + patch, x : x + patch].astype(np.float32)
            mean_diff_from_bg = abs(float(block.mean()) - bg_val)
            if mean_diff_from_bg > 8:  # patch has *some* content, not pure bg
                total_content_patches += 1
                if float(block.std()) < min_local_contrast and mean_diff_from_bg < 18:
                    low_contrast_patches += 1

    if total_content_patches > 0:
        ratio = low_contrast_patches / total_content_patches
        if ratio > 0.35:
            issues.append(
                FrameIssue(
                    check="low_contrast",
                    severity=Severity.WARNING,
                    message=(
                        f"{ratio * 100:.0f}% of content-bearing regions have low "
                        f"local contrast — text or thin strokes may be hard to read."
                    ),
                )
            )
    return issues


def check_overlap_density(
    arr: np.ndarray, *, dense_edge_threshold: float = 0.30
) -> list[FrameIssue]:
    """Flags frames with an unusually dense concentration of EDGES
    (contours/outlines) in a small region — a signature of overlapping
    distinct shapes (e.g. two array cells' borders stacked because a
    layout bug placed them at the same coordinate).

    Deliberately edge-density rather than raw-fill-density: a single
    solid-filled rectangle is expected to be 100% "filled" in its own
    window and must NOT trigger this check. What's abnormal is many
    *edges* (multiple distinct borders/strokes) crammed into one small
    area — that only happens when shapes actually overlap each other.

    KNOWN LIMITATION: this is a coarse, pixel-statistical signal. Thin
    strokes (e.g. 2-4px borders) from two overlapping shapes produce a
    surprisingly small increase in local edge density, so this check is
    tuned toward catching moderate-to-severe overlap and will miss subtle
    cases. For exact overlap detection, prefer
    `check_mobject_bbox_overlap()` in this module, which operates on
    Manim's own bounding-box geometry at scene-construction time rather
    than inferring from rendered pixels — use that as the authoritative
    check and this one as a secondary post-render sanity signal.
    """
    issues = []
    gray = np.asarray(Image.fromarray(arr[:, :, :3]).convert("L"))
    h, w = gray.shape
    if h < 48 or w < 48:
        return issues

    try:
        import cv2

        edges = cv2.Canny(gray, 40, 120)
    except ImportError:
        # Dependency-free fallback: simple gradient-magnitude edge proxy.
        gy, gx = np.gradient(gray.astype(np.float32))
        grad = np.sqrt(gx**2 + gy**2)
        edges = (grad > 40).astype(np.uint8) * 255

    win = 40
    kernel = np.ones((win, win), dtype=np.float32) / (win * win)
    try:
        import cv2

        edge_density = cv2.filter2D((edges > 0).astype(np.float32), -1, kernel)
    except ImportError:
        edge_density = np.zeros((h, w), dtype=np.float32)
        binmask = (edges > 0).astype(np.float32)
        for y in range(0, h - win, win // 2):
            for x in range(0, w - win, win // 2):
                edge_density[y : y + win, x : x + win] = binmask[y : y + win, x : x + win].mean()

    max_density = float(edge_density.max())
    if max_density > dense_edge_threshold:
        y, x = np.unravel_index(np.argmax(edge_density), edge_density.shape)
        issues.append(
            FrameIssue(
                check="overlap_density",
                severity=Severity.WARNING,
                message=(
                    f"Unusually dense edge/outline cluster detected "
                    f"({max_density * 100:.0f}% edge coverage in a {win}px window) — "
                    f"possible overlapping shapes."
                ),
                bbox=(
                    max(0, int(x) - win // 2),
                    max(0, int(y) - win // 2),
                    min(w, int(x) + win // 2),
                    min(h, int(y) + win // 2),
                ),
            )
        )
    return issues


ALL_CHECKS = [
    check_blank_frame,
    check_offscreen_clipping,
    check_low_contrast_text_regions,
    check_overlap_density,
]


def check_mobject_bbox_overlap(
    mobjects: list, *, min_overlap_fraction: float = 0.25
) -> list[FrameIssue]:
    """
    Authoritative overlap check, run against live Manim mobjects (e.g. all
    cells in an ArrayVisualizer, or all node circles in a TreeVisualizer) —
    NOT against rendered pixels. This is exact axis-aligned-bounding-box
    intersection math on Manim's own coordinate data, so unlike
    `check_overlap_density` it has no false-positive/false-negative
    trade-off from thin strokes or tight-but-legitimate adjacency.

    Intended call site: component `_build()` methods can call this on
    their own children right after layout, so a layout bug is caught at
    construction time — before a single frame is ever rendered — and
    reported with the exact pair of mobjects involved. Also callable from
    tests (manim_engine/tests/test_components/) for the boundary tests
    the spec calls for (§30).
    """
    issues: list[FrameIssue] = []
    n = len(mobjects)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = mobjects[i], mobjects[j]
            try:
                ax0, ay0 = a.get_left()[0], a.get_bottom()[1]
                ax1, ay1 = a.get_right()[0], a.get_top()[1]
                bx0, by0 = b.get_left()[0], b.get_bottom()[1]
                bx1, by1 = b.get_right()[0], b.get_top()[1]
            except Exception:
                continue

            ix0, iy0 = max(ax0, bx0), max(ay0, by0)
            ix1, iy1 = min(ax1, bx1), min(ay1, by1)
            if ix1 <= ix0 or iy1 <= iy0:
                continue  # no intersection

            inter_area = (ix1 - ix0) * (iy1 - iy0)
            a_area = max((ax1 - ax0) * (ay1 - ay0), 1e-9)
            b_area = max((bx1 - bx0) * (by1 - by0), 1e-9)
            smaller_area = min(a_area, b_area)
            overlap_fraction = inter_area / smaller_area

            if overlap_fraction >= min_overlap_fraction:
                issues.append(
                    FrameIssue(
                        check="mobject_bbox_overlap",
                        severity=Severity.ERROR,
                        message=(
                            f"Mobjects at index {i} and {j} overlap by "
                            f"{overlap_fraction * 100:.0f}% of the smaller "
                            f"object's area — likely a layout bug."
                        ),
                    )
                )
    return issues


def analyze_frame(
    arr: np.ndarray, *, frame_index: int = 0, timestamp_s: float = 0.0
) -> FrameReport:
    h, w = arr.shape[:2]
    report = FrameReport(frame_index=frame_index, timestamp_s=timestamp_s, width=w, height=h)
    for check_fn in ALL_CHECKS:
        report.issues.extend(check_fn(arr))
    return report


def analyze_image_file(path: str | Path) -> FrameReport:
    arr = np.asarray(Image.open(path).convert("RGB"))
    return analyze_frame(arr)


def analyze_video(
    video_path: str | Path, *, sample_fps: float = 2.0, save_frames_dir: str | Path | None = None
) -> VideoQualityReport:
    """Samples frames from the rendered MP4 at `sample_fps` and runs the
    full quality-check suite on each. This is what VALIDATING_RENDER (§15)
    calls before a job is allowed to reach COMPLETED, and what the debug
    CLI calls for a full manual report."""
    import cv2

    video_path = Path(video_path)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, int(round(video_fps / sample_fps)))

    if save_frames_dir:
        save_frames_dir = Path(save_frames_dir)
        save_frames_dir.mkdir(parents=True, exist_ok=True)

    report = VideoQualityReport(video_path=str(video_path), total_frames_sampled=0)

    idx = 0
    sampled = 0
    while True:
        ok, frame_bgr = cap.read()
        if not ok:
            break
        if idx % step == 0:
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            ts = idx / video_fps
            frame_report = analyze_frame(frame_rgb, frame_index=idx, timestamp_s=ts)
            report.frame_reports.append(frame_report)
            sampled += 1
            if save_frames_dir and frame_report.issues:
                out_path = save_frames_dir / f"frame_{idx:06d}_t{ts:.2f}s.png"
                Image.fromarray(frame_rgb).save(out_path)
        idx += 1
    cap.release()

    report.total_frames_sampled = sampled
    return report

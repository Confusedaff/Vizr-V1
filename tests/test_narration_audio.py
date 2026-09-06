"""Tests for workers/renderer/pipeline/audio.py.

Deliberately avoids any real edge-tts/network calls — CI and most dev
environments shouldn't depend on an external service being reachable.
`collect_narratable_text` is pure logic and tested directly;
`generate_narration_audio`'s network-touching path is exercised only via
its documented non-fatal-failure behavior (TTS_ENABLED=False, and a
mocked edge_tts that raises), which is exactly the behavior a real
network outage would trigger too.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from packages.scene_schema import Scene, SceneInput
from workers.renderer.pipeline.audio import collect_narratable_text, generate_narration_audio


def make_scene(**overrides):
    defaults = dict(
        version="1.0",
        visualization_type="binary_search",
        title="Test",
        input=SceneInput(array=[1, 2, 3, 4, 5]),
        steps=[{"action": "show_array", "data": [1, 2, 3, 4, 5]}],
        narration=[],
    )
    defaults.update(overrides)
    return Scene(**defaults)


def test_collect_narratable_text_pulls_from_narration_list():
    scene = make_scene(narration=["Starting search", "Checking the midpoint"])
    assert collect_narratable_text(scene) == ["Starting search", "Checking the midpoint"]


def test_collect_narratable_text_includes_step_messages():
    scene = make_scene(
        narration=["Starting search"],
        steps=[
            {"action": "show_array", "data": [1, 2, 3]},
            {"action": "show_result", "indices": [1], "message": "Found it!"},
        ],
    )
    result = collect_narratable_text(scene)
    assert "Starting search" in result
    assert "Found it!" in result


def test_collect_narratable_text_deduplicates_preserving_order():
    scene = make_scene(
        narration=["Same line", "Same line", "Different line"],
        steps=[
            {"action": "show_result", "indices": [0], "message": "Same line"},
        ],
    )
    assert collect_narratable_text(scene) == ["Same line", "Different line"]


def test_collect_narratable_text_empty_when_no_narration():
    scene = make_scene()
    assert collect_narratable_text(scene) == []


def test_generate_narration_audio_disabled_returns_empty_map(tmp_path):
    scene = make_scene(narration=["Some line"])
    result = generate_narration_audio(scene, output_dir=tmp_path, enabled=False)
    assert result.audio_map == {}
    assert result.errors == []


def test_generate_narration_audio_no_narration_skips_synthesis(tmp_path):
    scene = make_scene(narration=[])
    result = generate_narration_audio(scene, output_dir=tmp_path, enabled=True)
    assert result.audio_map == {}
    assert result.errors == []
    # Nothing to synthesize — the output dir shouldn't even be created.
    assert not tmp_path.exists() or not any(tmp_path.iterdir())


def test_generate_narration_audio_degrades_gracefully_on_tts_failure(tmp_path):
    """Simulates the real-world case (no network, edge-tts endpoint
    unreachable): the pipeline stage must never raise — it should report
    the failure per-line and hand back an empty-enough map so the render
    step downstream falls back to captions-only, exactly as it did before
    this feature existed."""
    scene = make_scene(narration=["Line one", "Line two"])

    class _FakeCommunicate:
        def __init__(self, *_args, **_kwargs):
            pass

        async def save(self, *_args, **_kwargs):
            raise RuntimeError("simulated network failure")

    with patch.dict("sys.modules", {"edge_tts": type("_M", (), {"Communicate": _FakeCommunicate})()}):
        result = generate_narration_audio(scene, output_dir=tmp_path, enabled=True)

    assert result.audio_map == {}
    assert len(result.errors) == 2

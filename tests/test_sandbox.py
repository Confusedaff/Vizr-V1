"""
Tests for manim_engine/renderer/sandbox.py. Since this development
environment has no Docker daemon, these tests validate the parts that
don't require one: the exact `docker run` argument construction (the
security-relevant part) and the result-parsing/error-handling logic,
using a mocked subprocess.run. See sandbox.py's module docstring for
what still needs live-Docker verification before production use.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from manim_engine.renderer.sandbox import (
    RESULT_MARKER,
    SandboxUnavailableError,
    build_docker_run_args,
    check_sandbox_available,
    render_scene_sandboxed,
)


def test_docker_run_args_include_network_none():
    args = build_docker_run_args(
        input_dir=Path("/tmp/in"), output_dir=Path("/tmp/out"), container_name="test1"
    )
    assert "--network" in args
    assert args[args.index("--network") + 1] == "none"


def test_docker_run_args_include_read_only_root():
    args = build_docker_run_args(
        input_dir=Path("/tmp/in"), output_dir=Path("/tmp/out"), container_name="test2"
    )
    assert "--read-only" in args


def test_docker_run_args_drop_all_capabilities():
    args = build_docker_run_args(
        input_dir=Path("/tmp/in"), output_dir=Path("/tmp/out"), container_name="test3"
    )
    assert "--cap-drop" in args
    assert args[args.index("--cap-drop") + 1] == "ALL"


def test_docker_run_args_no_new_privileges():
    args = build_docker_run_args(
        input_dir=Path("/tmp/in"), output_dir=Path("/tmp/out"), container_name="test4"
    )
    assert "no-new-privileges" in args


def test_docker_run_args_non_root_user():
    args = build_docker_run_args(
        input_dir=Path("/tmp/in"), output_dir=Path("/tmp/out"), container_name="test5"
    )
    assert "--user" in args
    assert args[args.index("--user") + 1] == "sandboxuser"


def test_docker_run_args_resource_limits_applied():
    args = build_docker_run_args(
        input_dir=Path("/tmp/in"), output_dir=Path("/tmp/out"), container_name="test6",
        cpu_limit="1", memory_limit="1g", pids_limit="64",
    )
    assert "--cpus=1" in args
    assert "--memory=1g" in args
    assert "--pids-limit=64" in args


def test_docker_run_args_mounts_input_readonly_output_readwrite():
    args = build_docker_run_args(
        input_dir=Path("/tmp/in"), output_dir=Path("/tmp/out"), container_name="test7"
    )
    joined = " ".join(args)
    assert "/tmp/in:/input:ro" in joined
    assert "/tmp/out:/output:rw" in joined


def test_check_sandbox_available_false_when_docker_missing():
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        assert check_sandbox_available() is False


def test_check_sandbox_available_true_when_image_present():
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result):
        assert check_sandbox_available() is True


def test_render_scene_sandboxed_raises_when_unavailable(tmp_path):
    with patch("manim_engine.renderer.sandbox.check_sandbox_available", return_value=False):
        with pytest.raises(SandboxUnavailableError):
            render_scene_sandboxed({"visualization_type": "binary_search"}, output_dir=tmp_path)


def test_render_scene_sandboxed_parses_success_result(tmp_path):
    fake_result = {
        "success": True,
        "video_path": "/output/media/videos/test/1080p30/Scene.mp4",
        "construction_warnings": [],
    }
    mock_proc = MagicMock(
        returncode=0,
        stdout=f"some manim log output\n{RESULT_MARKER}{json.dumps(fake_result)}\n",
        stderr="",
    )
    with patch("manim_engine.renderer.sandbox.check_sandbox_available", return_value=True), \
         patch("subprocess.run", return_value=mock_proc):
        result = render_scene_sandboxed({"visualization_type": "binary_search"}, output_dir=tmp_path)

    assert result.success
    assert result.video_path == str(tmp_path / "media/videos/test/1080p30/Scene.mp4")


def test_render_scene_sandboxed_parses_failure_result(tmp_path):
    fake_result = {"success": False, "error": "IndexError: list index out of range", "traceback": "..."}
    mock_proc = MagicMock(
        returncode=1,
        stdout=f"{RESULT_MARKER}{json.dumps(fake_result)}\n",
        stderr="",
    )
    with patch("manim_engine.renderer.sandbox.check_sandbox_available", return_value=True), \
         patch("subprocess.run", return_value=mock_proc):
        result = render_scene_sandboxed({"visualization_type": "binary_search"}, output_dir=tmp_path)

    assert not result.success
    assert "IndexError" in result.error


def test_render_scene_sandboxed_handles_missing_result_marker(tmp_path):
    mock_proc = MagicMock(returncode=0, stdout="no marker here", stderr="some error")
    with patch("manim_engine.renderer.sandbox.check_sandbox_available", return_value=True), \
         patch("subprocess.run", return_value=mock_proc):
        result = render_scene_sandboxed({"visualization_type": "binary_search"}, output_dir=tmp_path)

    assert not result.success
    assert result.error == "NO_RESULT_MARKER"


def test_render_scene_sandboxed_handles_unexpected_container_exit(tmp_path):
    mock_proc = MagicMock(returncode=137, stdout="", stderr="OOM killed")  # e.g. OOM-killed
    with patch("manim_engine.renderer.sandbox.check_sandbox_available", return_value=True), \
         patch("subprocess.run", return_value=mock_proc):
        result = render_scene_sandboxed({"visualization_type": "binary_search"}, output_dir=tmp_path)

    assert not result.success
    assert "137" in result.error

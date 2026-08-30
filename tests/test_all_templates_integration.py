"""
Integration test: render every one of the 10 templates end-to-end at low
resolution and run them through the frame-quality gate. This is the
highest-value test in the suite — it's the only one that exercises the
real Manim render path for every template, not just the ones spot-checked
manually during development (binary_search and two_sum).

Runs are slow (real Manim renders) — marked so CI can run them in a
separate, longer-timeout job from the fast unit tests.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from packages.scene_schema import Scene, SceneInput
from manim_engine.renderer.validate_render import validate_render
from workers.renderer.pipeline.render import render_scene

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_OUTPUT = Path("/tmp/aiviz_integration_test_output")

SCENES: dict[str, dict] = {
    "array_traversal": dict(
        input=SceneInput(array=[4, 8, 15, 16, 23, 42]),
        steps=[
            {"action": "show_array", "data": [4, 8, 15, 16, 23, 42]},
            {"action": "set_pointer", "name": "i", "index": 0},
            {"action": "highlight_pair", "indices": [0, 0], "color": "highlight"},
            {"action": "set_pointer", "name": "i", "index": 3},
            {"action": "highlight_pair", "indices": [3, 3], "color": "highlight"},
            {"action": "show_result", "indices": [3], "message": "Done traversing"},
        ],
    ),
    "two_sum": dict(
        input=SceneInput(array=[2, 7, 11, 15], target=9),
        steps=[
            {"action": "show_array", "data": [2, 7, 11, 15]},
            {"action": "set_pointer", "name": "i", "index": 0},
            {"action": "hashmap_insert", "key": 2, "value": 0},
            {"action": "set_pointer", "name": "i", "index": 1},
            {"action": "hashmap_lookup", "key": 2, "found": True},
            {"action": "show_result", "indices": [0, 1], "message": "2 + 7 = 9"},
        ],
    ),
    "two_pointers": dict(
        input=SceneInput(array=[1, 2, 4, 7, 11, 15], target=9),
        steps=[
            {"action": "show_array", "data": [1, 2, 4, 7, 11, 15]},
            {"action": "set_pointer", "name": "left", "index": 0},
            {"action": "set_pointer", "name": "right", "index": 5},
            {"action": "highlight_pair", "indices": [0, 5], "color": "highlight"},
            {"action": "set_pointer", "name": "right", "index": 4},
            {"action": "highlight_pair", "indices": [0, 4], "color": "success"},
            {"action": "show_result", "indices": [0, 4], "message": "Found: 1 + 11 = 12"},
        ],
    ),
    "binary_search": dict(
        input=SceneInput(array=[1, 3, 5, 7, 9, 11, 13], target=9),
        steps=[
            {"action": "show_array", "data": [1, 3, 5, 7, 9, 11, 13]},
            {"action": "highlight_range", "start": 0, "end": 6},
            {"action": "set_pointer", "name": "mid", "index": 3},
            {"action": "highlight_range", "start": 4, "end": 6},
            {"action": "set_pointer", "name": "mid", "index": 5},
            {"action": "show_result", "indices": [4], "message": "Found 9"},
        ],
    ),
    "sliding_window": dict(
        input=SceneInput(array=[2, 1, 5, 1, 3, 2]),
        steps=[
            {"action": "show_array", "data": [2, 1, 5, 1, 3, 2]},
            {"action": "highlight_range", "start": 0, "end": 2},
            {"action": "highlight_range", "start": 1, "end": 3},
            {"action": "highlight_range", "start": 2, "end": 4},
            {"action": "show_result", "indices": [2, 3, 4], "message": "Max window sum found"},
        ],
    ),
    "bubble_sort": dict(
        input=SceneInput(array=[5, 2, 4, 1]),
        steps=[
            {"action": "show_array", "data": [5, 2, 4, 1]},
            {"action": "highlight_pair", "indices": [0, 1], "color": "highlight"},
            {"action": "swap", "indices": [0, 1]},
            {"action": "highlight_pair", "indices": [1, 2], "color": "highlight"},
            {"action": "swap", "indices": [1, 2]},
            {"action": "clear_highlight"},
        ],
    ),
    "merge_sort": dict(
        input=SceneInput(array=[5, 2, 4, 1]),
        steps=[
            {"action": "show_array", "data": [5, 2, 4, 1]},
            {"action": "split_array", "start": 0, "mid": 1, "end": 3},
            {"action": "merge_array", "start": 0, "end": 3, "result": [1, 2, 4, 5]},
            {"action": "show_result", "indices": [0, 1, 2, 3], "message": "Sorted"},
        ],
    ),
    "binary_tree_traversal": dict(
        input=SceneInput(tree_values=[5, 3, 8, 1, 4, None, 9]),
        steps=[
            {"action": "build_tree", "values": [5, 3, 8, 1, 4, None, 9]},
            {"action": "visit_node", "index": 0, "order_label": "1st"},
            {"action": "visit_node", "index": 1, "order_label": "2nd"},
            {"action": "visit_node", "index": 3, "order_label": "3rd"},
        ],
    ),
    "graph_bfs_dfs": dict(
        input=SceneInput(graph_nodes=[0, 1, 2, 3], graph_edges=[[0, 1], [1, 2], [2, 3]]),
        steps=[
            {"action": "build_graph", "nodes": [0, 1, 2, 3], "edges": [[0, 1], [1, 2], [2, 3]]},
            {"action": "visit_graph_node", "node": 0, "order_label": "1st"},
            {"action": "traverse_edge", "from_node": 0, "to_node": 1},
            {"action": "visit_graph_node", "node": 1, "order_label": "2nd"},
        ],
    ),
    "hashmap_ops": dict(
        input=SceneInput(),
        steps=[
            {"action": "hashmap_insert", "key": 1, "value": 100},
            {"action": "hashmap_insert", "key": 2, "value": 200},
            {"action": "hashmap_lookup", "key": 1, "found": True},
            {"action": "hashmap_lookup", "key": 5, "found": False},
        ],
    ),
    "quicksort": dict(
        input=SceneInput(array=[5, 2, 8, 1, 9]),
        steps=[
            {"action": "show_array", "data": [5, 2, 8, 1, 9]},
            {"action": "set_pivot", "index": 4},
            {"action": "highlight_pair", "indices": [0, 4], "color": "highlight"},
            {"action": "swap", "indices": [0, 4]},
            {"action": "partition_complete", "index": 0},
            {"action": "show_result", "indices": [], "message": "Partition done"},
        ],
    ),
    "linked_list_reversal": dict(
        input=SceneInput(),
        steps=[
            {"action": "build_linked_list", "values": [1, 2, 3, 4]},
            {"action": "set_pointer", "name": "prev", "index": 0},
            {"action": "reverse_link", "node_index": 0},
            {"action": "advance_pointer_node", "name": "prev", "node_index": 1},
            {"action": "reverse_link", "node_index": 1},
            {"action": "show_result", "indices": [], "message": "List reversed"},
        ],
    ),
    "valid_parentheses": dict(
        input=SceneInput(),
        steps=[
            {"action": "push_stack", "value": "("},
            {"action": "push_stack", "value": "["},
            {"action": "pop_stack", "matched": True},
            {"action": "pop_stack", "matched": True},
            {"action": "show_result", "indices": [], "message": "Valid!"},
        ],
    ),
    "dynamic_programming_1d": dict(
        input=SceneInput(array=[0, 0, 0, 0, 0]),
        steps=[
            {"action": "fill_dp_cell", "index": 0, "value": 1, "depends_on": []},
            {"action": "fill_dp_cell", "index": 1, "value": 1, "depends_on": [0]},
            {"action": "fill_dp_cell", "index": 2, "value": 2, "depends_on": [0, 1]},
            {"action": "fill_dp_cell", "index": 3, "value": 3, "depends_on": [1, 2]},
            {"action": "fill_dp_cell", "index": 4, "value": 5, "depends_on": [2, 3]},
            {"action": "show_result", "indices": [4], "message": "5 ways to climb"},
        ],
    ),
}


@pytest.fixture(scope="module", autouse=True)
def cleanup_output_dir():
    yield
    shutil.rmtree(TMP_OUTPUT, ignore_errors=True)


@pytest.mark.slow
@pytest.mark.parametrize("visualization_type", list(SCENES.keys()))
def test_template_renders_and_passes_quality_gate(visualization_type):
    spec = SCENES[visualization_type]
    scene = Scene(
        version="1.0",
        visualization_type=visualization_type,
        title=f"Test: {visualization_type}",
        input=spec["input"],
        steps=spec["steps"],
        narration=[],
    )

    output_dir = TMP_OUTPUT / visualization_type
    result = render_scene(
        scene,
        output_dir=output_dir,
        project_root=PROJECT_ROOT,
        resolution=(640, 360),
        fps=15,
        timeout_seconds=120,
    )

    assert result.success, (
        f"[{visualization_type}] render failed: {result.error}\n"
        f"stderr tail:\n{result.stderr[-1500:]}"
    )

    validation = validate_render(
        result.video_path,
        construction_warnings=result.construction_warnings,
        sample_fps=3.0,
    )

    assert not result.construction_warnings, (
        f"[{visualization_type}] construction warnings (layout bugs): "
        f"{result.construction_warnings}"
    )
    assert validation.valid, (
        f"[{visualization_type}] failed quality gate:\n{validation.as_repair_context()}"
    )

"""Tests for packages/scene_schema — the closed action vocabulary and
semantic bounds-checking that is the system's primary safety boundary."""
import pytest
from pydantic import ValidationError

from packages.scene_schema import Scene, SceneInput


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


def test_valid_scene_parses():
    scene = make_scene()
    assert scene.visualization_type == "binary_search"
    assert len(scene.steps) == 1


def test_unknown_visualization_type_rejected():
    with pytest.raises(ValidationError):
        make_scene(visualization_type="quantum_bogosort")


def test_unknown_action_rejected():
    with pytest.raises(ValidationError):
        make_scene(steps=[{"action": "eval_code", "code": "import os"}])


def test_out_of_bounds_index_rejected():
    with pytest.raises(ValidationError):
        make_scene(
            input=SceneInput(array=[1, 2, 3]),
            steps=[{"action": "set_pointer", "name": "i", "index": 99}],
        )


def test_out_of_bounds_highlight_pair_rejected():
    with pytest.raises(ValidationError):
        make_scene(
            input=SceneInput(array=[1, 2, 3]),
            steps=[{"action": "highlight_pair", "indices": [0, 10]}],
        )


def test_highlight_range_start_after_end_rejected():
    with pytest.raises(ValidationError):
        make_scene(
            steps=[{"action": "highlight_range", "start": 5, "end": 2}],
        )


def test_remove_pointer_before_set_rejected():
    with pytest.raises(ValidationError):
        make_scene(
            steps=[
                {"action": "show_array", "data": [1, 2, 3]},
                {"action": "remove_pointer", "name": "ghost"},
            ]
        )


def test_advance_pointer_before_set_rejected():
    with pytest.raises(ValidationError):
        make_scene(
            visualization_type="two_pointers",
            steps=[
                {"action": "show_array", "data": [1, 2, 3]},
                {"action": "advance_pointer_node", "name": "ghost", "node_index": 0},
            ],
        )


def test_set_then_remove_pointer_accepted():
    scene = make_scene(
        steps=[
            {"action": "show_array", "data": [1, 2, 3]},
            {"action": "set_pointer", "name": "i", "index": 0},
            {"action": "remove_pointer", "name": "i"},
        ]
    )
    assert len(scene.steps) == 3


def test_graph_node_reference_validated():
    with pytest.raises(ValidationError):
        make_scene(
            visualization_type="graph_bfs_dfs",
            input=SceneInput(graph_nodes=[0, 1, 2], graph_edges=[[0, 1]]),
            steps=[{"action": "visit_graph_node", "node": 99}],
        )


def test_graph_edge_reference_validated():
    with pytest.raises(ValidationError):
        make_scene(
            visualization_type="graph_bfs_dfs",
            input=SceneInput(graph_nodes=[0, 1, 2], graph_edges=[[0, 1]]),
            steps=[{"action": "traverse_edge", "from_node": 0, "to_node": 99}],
        )


def test_tree_index_bounds_validated():
    with pytest.raises(ValidationError):
        make_scene(
            visualization_type="binary_tree_traversal",
            input=SceneInput(tree_values=[5, 3, 8]),
            steps=[{"action": "visit_node", "index": 50}],
        )


def test_empty_steps_rejected():
    with pytest.raises(ValidationError):
        make_scene(steps=[])


def test_too_many_steps_rejected():
    with pytest.raises(ValidationError):
        make_scene(steps=[{"action": "clear_highlight"}] * 100)


def test_array_max_length_enforced():
    with pytest.raises(ValidationError):
        make_scene(input=SceneInput(array=list(range(100))))


def test_pointer_name_pattern_enforced():
    with pytest.raises(ValidationError):
        make_scene(
            steps=[{"action": "set_pointer", "name": "invalid name!", "index": 0}]
        )

"""
scene_to_manim: the deterministic compiler from a validated Scene (Pydantic
model) to a runnable Manim Scene subclass instance.

This function is the load-bearing wall of the "no LLM writes animation
code" architecture (§10, §13). It performs a pure lookup + attribute
assignment — there is no code generation, no eval, no exec, no template
string formatting into Python source. Every visualization_type maps to a
hand-written, hand-tested template class; the Scene JSON only ever
supplies *data* to that class's build_visualization() method.
"""
from __future__ import annotations

from packages.scene_schema import Scene
from manim_engine.templates.array_traversal import ArrayTraversalScene
from manim_engine.templates.binary_search import BinarySearchScene
from manim_engine.templates.binary_tree_traversal import BinaryTreeTraversalScene
from manim_engine.templates.bubble_sort import BubbleSortScene
from manim_engine.templates.dynamic_programming_1d import DynamicProgramming1DScene
from manim_engine.templates.graph_bfs_dfs import GraphBfsDfsScene
from manim_engine.templates.hashmap_ops import HashMapOpsScene
from manim_engine.templates.linked_list_reversal import LinkedListReversalScene
from manim_engine.templates.merge_sort import MergeSortScene
from manim_engine.templates.quicksort import QuicksortScene
from manim_engine.templates.sliding_window import SlidingWindowScene
from manim_engine.templates.two_pointers import TwoPointersScene
from manim_engine.templates.two_sum import TwoSumScene
from manim_engine.templates.valid_parentheses import ValidParenthesesScene

TEMPLATE_REGISTRY: dict[str, type] = {
    "array_traversal": ArrayTraversalScene,
    "two_sum": TwoSumScene,
    "two_pointers": TwoPointersScene,
    "binary_search": BinarySearchScene,
    "sliding_window": SlidingWindowScene,
    "bubble_sort": BubbleSortScene,
    "merge_sort": MergeSortScene,
    "binary_tree_traversal": BinaryTreeTraversalScene,
    "graph_bfs_dfs": GraphBfsDfsScene,
    "hashmap_ops": HashMapOpsScene,
    "quicksort": QuicksortScene,
    "linked_list_reversal": LinkedListReversalScene,
    "valid_parentheses": ValidParenthesesScene,
    "dynamic_programming_1d": DynamicProgramming1DScene,
}


class UnknownVisualizationTypeError(Exception):
    pass


def scene_to_manim(scene: Scene):
    """Returns an *instance* of the appropriate Manim Scene subclass, with
    `scene_data` already attached, ready to `.render()`.

    Note: we attach scene_data to the *class* via a per-call dynamic
    subclass rather than the instance, because Manim's CLI/renderer
    machinery in some code paths re-reads class-level state. Using a
    fresh dynamic subclass per call also means concurrent renders (e.g.
    two workers rendering different jobs in the same process during
    tests) never share mutable class state.
    """
    template_cls = TEMPLATE_REGISTRY.get(scene.visualization_type)
    if template_cls is None:
        raise UnknownVisualizationTypeError(
            f"No template registered for visualization_type={scene.visualization_type!r}. "
            f"Known types: {sorted(TEMPLATE_REGISTRY)}"
        )

    dynamic_cls = type(
        f"{template_cls.__name__}_Bound",
        (template_cls,),
        {"scene_data": scene},
    )
    return dynamic_cls()

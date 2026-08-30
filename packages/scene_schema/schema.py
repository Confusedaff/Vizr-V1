"""
Scene JSON Schema — the contract between "what the LLM is allowed to decide"
and "what the deterministic renderer executes."

Design constraint: the schema makes it structurally impossible to embed
arbitrary code. Every field is data (arrays, indices, labels, enum-typed
actions) — never a code string, never a Python expression to eval.

This is the single source of truth. TypeScript types (apps/web) and the
JSON Schema shown to the LLM (workers/renderer/pipeline/plan_scene.py) are
both derived from these models, never hand-duplicated.
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator

# --------------------------------------------------------------------------
# Visualization types supported in v1 (§11 of spec)
# --------------------------------------------------------------------------

VISUALIZATION_TYPES: list[str] = [
    "array_traversal",
    "two_sum",
    "two_pointers",
    "binary_search",
    "sliding_window",
    "bubble_sort",
    "merge_sort",
    "binary_tree_traversal",
    "graph_bfs_dfs",
    "hashmap_ops",
    "quicksort",
    "linked_list_reversal",
    "valid_parentheses",
    "dynamic_programming_1d",
]

NAME_PATTERN = r"^[a-zA-Z_][a-zA-Z0-9_]*$"
PointerName = Annotated[str, Field(max_length=12, pattern=NAME_PATTERN)]


# --------------------------------------------------------------------------
# Step vocabulary — one Pydantic model per action. This IS the closed
# action vocabulary. Adding a new action means adding a new model here,
# never opening the schema up to free-form fields.
# --------------------------------------------------------------------------


class ShowArrayStep(BaseModel):
    action: Literal["show_array"]
    data: list[int] = Field(min_length=1, max_length=50)


class SetPointerStep(BaseModel):
    action: Literal["set_pointer"]
    name: PointerName
    index: int = Field(ge=0)
    label: str | None = Field(default=None, max_length=16)


class RemovePointerStep(BaseModel):
    action: Literal["remove_pointer"]
    name: PointerName


class HighlightPairStep(BaseModel):
    action: Literal["highlight_pair"]
    indices: list[int] = Field(min_length=2, max_length=2)
    color: Literal["highlight", "success", "danger", "neutral"] = "highlight"


class HighlightRangeStep(BaseModel):
    action: Literal["highlight_range"]
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    label: str | None = Field(default=None, max_length=24)

    @model_validator(mode="after")
    def start_le_end(self) -> "HighlightRangeStep":
        if self.start > self.end:
            raise ValueError("highlight_range: start must be <= end")
        return self


class ClearHighlightStep(BaseModel):
    action: Literal["clear_highlight"]


class ShowResultStep(BaseModel):
    action: Literal["show_result"]
    indices: list[int] = Field(min_length=0, max_length=10)
    message: str | None = Field(default=None, max_length=80)


class SwapStep(BaseModel):
    action: Literal["swap"]
    indices: list[int] = Field(min_length=2, max_length=2)


class HashMapInsertStep(BaseModel):
    action: Literal["hashmap_insert"]
    key: int
    value: int


class HashMapLookupStep(BaseModel):
    action: Literal["hashmap_lookup"]
    key: int
    found: bool


class BuildTreeStep(BaseModel):
    action: Literal["build_tree"]
    # level-order array with nulls for missing children, e.g. [5,3,8,1,4,null,9]
    values: list[int | None] = Field(min_length=1, max_length=31)


class VisitNodeStep(BaseModel):
    action: Literal["visit_node"]
    index: int = Field(ge=0)
    order_label: str | None = Field(default=None, max_length=8)


class BuildGraphStep(BaseModel):
    action: Literal["build_graph"]
    nodes: list[int] = Field(min_length=1, max_length=20)
    edges: list[list[int]] = Field(max_length=60)


class VisitGraphNodeStep(BaseModel):
    action: Literal["visit_graph_node"]
    node: int
    order_label: str | None = Field(default=None, max_length=8)


class TraverseEdgeStep(BaseModel):
    action: Literal["traverse_edge"]
    from_node: int
    to_node: int


class BuildLinkedListStep(BaseModel):
    action: Literal["build_linked_list"]
    values: list[int] = Field(min_length=1, max_length=20)


class AdvancePointerNodeStep(BaseModel):
    action: Literal["advance_pointer_node"]
    name: PointerName
    node_index: int = Field(ge=0)


class ShowCodeStep(BaseModel):
    action: Literal["show_code"]
    lines: list[str] = Field(min_length=1, max_length=25)
    language: str = "python"


class HighlightCodeLineStep(BaseModel):
    action: Literal["highlight_code_line"]
    line: int = Field(ge=0)


class SplitArrayStep(BaseModel):
    action: Literal["split_array"]
    start: int = Field(ge=0)
    mid: int = Field(ge=0)
    end: int = Field(ge=0)


class MergeArrayStep(BaseModel):
    action: Literal["merge_array"]
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    result: list[int] = Field(max_length=50)


class SetPivotStep(BaseModel):
    """quicksort: marks an index as the current pivot, distinct from a
    generic highlight so templates can render it with dedicated styling
    (e.g. a persistent marker that survives partition swaps)."""

    action: Literal["set_pivot"]
    index: int = Field(ge=0)


class PartitionCompleteStep(BaseModel):
    """quicksort: signals the pivot has settled into its final sorted
    position at `index` — distinct from show_result so a template can
    render a running tally of "settled" cells across multiple recursive
    partition calls rather than only a single final result."""

    action: Literal["partition_complete"]
    index: int = Field(ge=0)


class ReverseLinkStep(BaseModel):
    """linked_list_reversal: reverses the direction of the arrow between
    node_index and node_index + 1 (or removes it, if reversal severs a
    forward link outright, per reverse_type)."""

    action: Literal["reverse_link"]
    node_index: int = Field(ge=0)


class PushStackStep(BaseModel):
    action: Literal["push_stack"]
    value: str = Field(max_length=8)


class PopStackStep(BaseModel):
    action: Literal["pop_stack"]
    matched: bool | None = Field(
        default=None,
        description="For validation-style stack use (e.g. valid_parentheses): "
        "whether the popped value correctly matched what triggered the pop.",
    )


class FillDpCellStep(BaseModel):
    """dynamic_programming_1d: fills a single cell of a 1D DP table with
    its computed value, optionally citing which earlier cell(s) it was
    derived from so the template can draw a dependency arrow."""

    action: Literal["fill_dp_cell"]
    index: int = Field(ge=0)
    value: int
    depends_on: list[int] = Field(default_factory=list, max_length=4)


# Discriminated union — this IS the closed action vocabulary.
Step = Annotated[
    Union[
        ShowArrayStep,
        SetPointerStep,
        RemovePointerStep,
        HighlightPairStep,
        HighlightRangeStep,
        ClearHighlightStep,
        ShowResultStep,
        SwapStep,
        HashMapInsertStep,
        HashMapLookupStep,
        BuildTreeStep,
        VisitNodeStep,
        BuildGraphStep,
        VisitGraphNodeStep,
        TraverseEdgeStep,
        BuildLinkedListStep,
        AdvancePointerNodeStep,
        ShowCodeStep,
        HighlightCodeLineStep,
        SplitArrayStep,
        MergeArrayStep,
        SetPivotStep,
        PartitionCompleteStep,
        ReverseLinkStep,
        PushStackStep,
        PopStackStep,
        FillDpCellStep,
    ],
    Field(discriminator="action"),
]

# Maps action string -> model class. Used by the debug CLI and by
# codegen tooling that needs the concrete type, not just the union.
ACTION_TO_MODEL: dict[str, type[BaseModel]] = {
    "show_array": ShowArrayStep,
    "set_pointer": SetPointerStep,
    "remove_pointer": RemovePointerStep,
    "highlight_pair": HighlightPairStep,
    "highlight_range": HighlightRangeStep,
    "clear_highlight": ClearHighlightStep,
    "show_result": ShowResultStep,
    "swap": SwapStep,
    "hashmap_insert": HashMapInsertStep,
    "hashmap_lookup": HashMapLookupStep,
    "build_tree": BuildTreeStep,
    "visit_node": VisitNodeStep,
    "build_graph": BuildGraphStep,
    "visit_graph_node": VisitGraphNodeStep,
    "traverse_edge": TraverseEdgeStep,
    "build_linked_list": BuildLinkedListStep,
    "advance_pointer_node": AdvancePointerNodeStep,
    "show_code": ShowCodeStep,
    "highlight_code_line": HighlightCodeLineStep,
    "split_array": SplitArrayStep,
    "merge_array": MergeArrayStep,
    "set_pivot": SetPivotStep,
    "partition_complete": PartitionCompleteStep,
    "reverse_link": ReverseLinkStep,
    "push_stack": PushStackStep,
    "pop_stack": PopStackStep,
    "fill_dp_cell": FillDpCellStep,
}


class SceneInput(BaseModel):
    array: list[int] | None = Field(default=None, max_length=50)
    target: int | None = None
    tree_values: list[int | None] | None = Field(default=None, max_length=31)
    graph_nodes: list[int] | None = Field(default=None, max_length=20)
    graph_edges: list[list[int]] | None = Field(default=None, max_length=60)


class Scene(BaseModel):
    """Top-level envelope, shared across all visualization types."""

    version: Literal["1.0"] = "1.0"
    visualization_type: str
    title: str = Field(max_length=100)
    input: SceneInput = Field(default_factory=SceneInput)
    steps: list[Step] = Field(min_length=1, max_length=40)
    narration: list[str] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def visualization_type_known(self) -> "Scene":
        if self.visualization_type not in VISUALIZATION_TYPES:
            raise ValueError(
                f"unknown visualization_type '{self.visualization_type}'. "
                f"Must be one of {VISUALIZATION_TYPES}"
            )
        return self

    @model_validator(mode="after")
    def indices_in_bounds(self) -> "Scene":
        """
        Semantic validation beyond structure: referenced indices must exist
        in the declared array/tree/graph. Catches LLM hallucination (e.g.
        "highlight index 12" on a 4-element array) before it ever reaches
        the renderer and produces an out-of-bounds crash.
        """
        array_len = len(self.input.array or [])
        tree_len = len(self.input.tree_values or [])
        graph_node_ids = set(self.input.graph_nodes or [])
        # linked_list_reversal doesn't have a dedicated SceneInput field —
        # its node count comes from the build_linked_list step itself
        # (found by scanning steps below), since a linked list is
        # constructed by the scene rather than declared in `input`.
        linked_list_len = next(
            (len(s.values) for s in self.steps if s.action == "build_linked_list"), 0
        )

        for i, step in enumerate(self.steps):
            action = step.action

            # Array-indexed actions
            if action in {
                "set_pointer",
                "highlight_pair",
                "highlight_range",
                "show_result",
                "swap",
                "split_array",
                "merge_array",
                "set_pivot",
                "partition_complete",
                "fill_dp_cell",
            }:
                for field_name in ("index", "indices", "start", "end", "depends_on"):
                    if hasattr(step, field_name):
                        val = getattr(step, field_name)
                        idxs = val if isinstance(val, list) else [val]
                        for idx in idxs:
                            if isinstance(idx, int) and array_len and idx >= array_len:
                                raise ValueError(
                                    f"step[{i}] ({action}): index {idx} out of bounds "
                                    f"for array of length {array_len}"
                                )

            if action == "reverse_link" and linked_list_len:
                if step.node_index >= linked_list_len - 1:
                    raise ValueError(
                        f"step[{i}] (reverse_link): node_index {step.node_index} has no "
                        f"following node in a list of length {linked_list_len}"
                    )
            if action == "advance_pointer_node" and linked_list_len:
                if step.node_index >= linked_list_len:
                    raise ValueError(
                        f"step[{i}] (advance_pointer_node): node_index {step.node_index} "
                        f"out of bounds for a list of length {linked_list_len}"
                    )

            # Tree-indexed actions
            if action == "visit_node" and tree_len:
                if step.index >= tree_len:
                    raise ValueError(
                        f"step[{i}] (visit_node): index {step.index} out of bounds "
                        f"for tree of length {tree_len}"
                    )

            # Graph node actions
            if action == "visit_graph_node" and graph_node_ids:
                if step.node not in graph_node_ids:
                    raise ValueError(
                        f"step[{i}] (visit_graph_node): node {step.node} not declared "
                        f"in input.graph_nodes"
                    )
            if action == "traverse_edge" and graph_node_ids:
                if step.from_node not in graph_node_ids or step.to_node not in graph_node_ids:
                    raise ValueError(
                        f"step[{i}] (traverse_edge): edge ({step.from_node},{step.to_node}) "
                        f"references undeclared node"
                    )

        return self

    @model_validator(mode="after")
    def pointer_names_defined_before_use(self) -> "Scene":
        """A pointer must be set_pointer'd before it's referenced by
        remove_pointer or advance_pointer_node — catches planning bugs
        that would otherwise surface as a confusing renderer KeyError."""
        active: set[str] = set()
        for i, step in enumerate(self.steps):
            if step.action == "set_pointer":
                active.add(step.name)
            elif step.action == "remove_pointer":
                if step.name not in active:
                    raise ValueError(
                        f"step[{i}] (remove_pointer): pointer '{step.name}' "
                        f"was never set"
                    )
                active.discard(step.name)
            elif step.action == "advance_pointer_node":
                if step.name not in active:
                    raise ValueError(
                        f"step[{i}] (advance_pointer_node): pointer '{step.name}' "
                        f"was never set"
                    )
        return self

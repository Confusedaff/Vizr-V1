"""array_traversal: walk through an array left-to-right (or per explicit
steps), highlighting the current element as we go. The simplest template —
also serves as the reference implementation other templates pattern-match
against."""
from __future__ import annotations

from manim_engine.components.arrays.array_visualizer import ArrayVisualizer
from manim_engine.components.pointers.pointer_group import PointerGroup
from manim_engine.renderer.config import PAUSE_SHORT
from manim_engine.templates.base_scene import BaseVisualizationScene


class ArrayTraversalScene(BaseVisualizationScene):
    def build_visualization(self) -> None:
        data = self.scene_data
        arr_values = data.input.array or []
        array_viz = ArrayVisualizer(arr_values)
        pointers = PointerGroup()

        self.play(array_viz.build_in())
        self.add(pointers)

        narration_iter = iter(data.narration)

        for step in data.steps:
            action = step.action

            if action == "show_array":
                continue  # already built above from input.array

            elif action == "set_pointer":
                target = array_viz.cell_center(step.index)
                self.play(pointers.set_pointer(step.name, target, step.label))

            elif action == "remove_pointer":
                anim = pointers.remove_pointer(step.name)
                if anim is not None:
                    self.play(anim)

            elif action == "highlight_pair":
                self.safe_play(*array_viz.highlight(step.indices, step.color))

            elif action == "highlight_range":
                self.safe_play(*array_viz.highlight(list(range(step.start, step.end + 1)), "highlight"))

            elif action == "clear_highlight":
                self.safe_play(*array_viz.clear_highlight())

            elif action == "show_result":
                self.safe_play(*array_viz.highlight(step.indices, "success"))
                if step.message:
                    self.play(self.narrate(step.message))

            else:
                # Unknown-for-this-template action: skip gracefully rather
                # than crash — the scene schema already guarantees the
                # action is *valid* globally, just not meaningful here.
                continue

            try:
                cap = next(narration_iter)
                self.play(self.narrate(cap))
            except StopIteration:
                pass

            self.wait(PAUSE_SHORT)

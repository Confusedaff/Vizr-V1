"""binary_search: array with a shrinking active range (highlight_range)
and a 'mid' pointer, eliminating half the search space each step."""
from __future__ import annotations

from manim_engine.components.arrays.array_visualizer import ArrayVisualizer
from manim_engine.components.pointers.pointer_group import PointerGroup
from manim_engine.renderer.config import PAUSE_SHORT
from manim_engine.templates.base_scene import BaseVisualizationScene


class BinarySearchScene(BaseVisualizationScene):
    def build_visualization(self) -> None:
        data = self.scene_data
        arr_values = data.input.array or []
        n = len(arr_values)

        array_viz = ArrayVisualizer(arr_values)
        pointers = PointerGroup()

        self.play(array_viz.build_in())
        self.add(pointers)

        narration_iter = iter(data.narration)
        active_range = set(range(n))

        for step in data.steps:
            action = step.action

            if action == "show_array":
                continue

            elif action == "set_pointer":
                target = array_viz.cell_center(step.index)
                self.play(pointers.set_pointer(step.name, target, step.label))

            elif action == "remove_pointer":
                anim = pointers.remove_pointer(step.name)
                if anim is not None:
                    self.play(anim)

            elif action == "highlight_range":
                new_range = set(range(step.start, step.end + 1))
                to_dim = active_range - new_range
                anims = []
                if to_dim:
                    anims += array_viz.highlight(sorted(to_dim), "neutral")
                anims += array_viz.highlight(sorted(new_range), "highlight")
                self.safe_play(*anims)
                active_range = new_range

            elif action == "highlight_pair":
                self.safe_play(*array_viz.highlight(step.indices, step.color))

            elif action == "clear_highlight":
                self.safe_play(*array_viz.clear_highlight())

            elif action == "show_result":
                self.safe_play(*array_viz.highlight(step.indices, "success"))
                if step.message:
                    self.play(self.narrate(step.message))

            else:
                continue

            try:
                cap = next(narration_iter)
                self.play(self.narrate(cap))
            except StopIteration:
                pass

            self.wait(PAUSE_SHORT)

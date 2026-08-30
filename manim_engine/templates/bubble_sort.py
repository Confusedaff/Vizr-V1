"""bubble_sort: repeated highlight_pair (comparison) + swap steps."""
from __future__ import annotations

from manim_engine.components.arrays.array_visualizer import ArrayVisualizer
from manim_engine.renderer.config import PAUSE_SHORT
from manim_engine.templates.base_scene import BaseVisualizationScene


class BubbleSortScene(BaseVisualizationScene):
    def build_visualization(self) -> None:
        data = self.scene_data
        arr_values = data.input.array or []

        array_viz = ArrayVisualizer(arr_values)
        self.play(array_viz.build_in())

        narration_iter = iter(data.narration)

        for step in data.steps:
            action = step.action

            if action == "show_array":
                continue

            elif action == "highlight_pair":
                self.safe_play(*array_viz.highlight(step.indices, step.color))

            elif action == "clear_highlight":
                self.safe_play(*array_viz.clear_highlight())

            elif action == "swap":
                self.safe_play(*array_viz.swap_cells(*step.indices))

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

        # Final flourish: sorted array fully highlighted green if the scene
        # didn't already end with an explicit show_result covering everything.
        if not any(s.action == "show_result" and len(s.indices) == len(arr_values) for s in data.steps):
            self.safe_play(*array_viz.highlight(list(range(len(arr_values))), "success"))

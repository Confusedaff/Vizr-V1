"""dynamic_programming_1d: a DPTableVisualizer, filled in cell by cell via
fill_dp_cell steps that also draw dependency arrows back to the cell(s)
each new value was derived from."""
from __future__ import annotations

from manim_engine.components.dp_table.dp_table_visualizer import DPTableVisualizer
from manim_engine.renderer.config import PAUSE_SHORT
from manim_engine.templates.base_scene import BaseVisualizationScene


class DynamicProgramming1DScene(BaseVisualizationScene):
    def build_visualization(self) -> None:
        data = self.scene_data
        size = len(data.input.array or []) or max(
            (s.index + 1 for s in data.steps if s.action == "fill_dp_cell"), default=1
        )

        dp = DPTableVisualizer(size)
        self.safe_play(dp.build_in())

        narration_iter = iter(data.narration)

        for step in data.steps:
            action = step.action

            if action == "fill_dp_cell":
                self.safe_play(*dp.fill_cell(step.index, step.value, step.depends_on))

            elif action == "show_result":
                self.safe_play(*dp.highlight(step.indices or list(dp.filled), "success"))
                if step.message:
                    self.safe_play(self.narrate(step.message))

            else:
                continue

            try:
                cap = next(narration_iter)
                self.safe_play(self.narrate(cap))
            except StopIteration:
                pass

            self.wait(PAUSE_SHORT)

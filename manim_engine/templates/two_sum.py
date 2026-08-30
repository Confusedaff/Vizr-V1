"""two_sum: array + a hashmap side panel tracking seen values, ending with
a highlighted pair when the answer is found."""
from __future__ import annotations

from manim import LEFT, RIGHT

from manim_engine.components.arrays.array_visualizer import ArrayVisualizer
from manim_engine.components.hashmap.hashmap_visualizer import HashMapVisualizer
from manim_engine.components.pointers.pointer_group import PointerGroup
from manim_engine.renderer.config import PAUSE_SHORT
from manim_engine.templates.base_scene import BaseVisualizationScene


class TwoSumScene(BaseVisualizationScene):
    def build_visualization(self) -> None:
        data = self.scene_data
        arr_values = data.input.array or []

        array_viz = ArrayVisualizer(arr_values)
        array_viz.shift(LEFT * 2.0)
        pointers = PointerGroup()
        hashmap = HashMapVisualizer()
        hashmap.shift(RIGHT * 4.0)

        self.play(array_viz.build_in())
        self.add(pointers, hashmap)

        narration_iter = iter(data.narration)

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

            elif action == "highlight_pair":
                self.safe_play(*array_viz.highlight(step.indices, step.color))

            elif action == "clear_highlight":
                self.safe_play(*array_viz.clear_highlight())

            elif action == "hashmap_insert":
                self.safe_play(*hashmap.insert(step.key, step.value))

            elif action == "hashmap_lookup":
                self.safe_play(*hashmap.lookup(step.key, step.found))

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

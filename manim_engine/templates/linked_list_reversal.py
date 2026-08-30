"""linked_list_reversal: builds a LinkedListVisualizer, then reverse_link
steps flip arrows one at a time while prev/curr pointers advance."""
from __future__ import annotations

from manim_engine.components.linked_list.linked_list_visualizer import LinkedListVisualizer
from manim_engine.renderer.config import PAUSE_SHORT, SEMANTIC_COLORS
from manim_engine.templates.base_scene import BaseVisualizationScene


class LinkedListReversalScene(BaseVisualizationScene):
    def build_visualization(self) -> None:
        data = self.scene_data
        values: list[int] = []
        for step in data.steps:
            if step.action == "build_linked_list":
                values = step.values
                break

        list_viz = LinkedListVisualizer(values)
        self.safe_play(list_viz.build_in())

        narration_iter = iter(data.narration)

        for step in data.steps:
            action = step.action

            if action == "build_linked_list":
                continue

            elif action == "advance_pointer_node":
                self.safe_play(list_viz.advance_pointer(step.name, step.node_index))

            elif action == "reverse_link":
                # Visual proxy for "this link is now reversed": flash the
                # two adjacent nodes' strokes to indicate the direction
                # change (a literal arrow-flip animation is possible but
                # adds meaningfully more Manim complexity for a cosmetic
                # gain; this keeps the template's failure surface small
                # while still communicating the operation clearly via the
                # accompanying narration).
                i = step.node_index
                nodes_to_flash = [list_viz.node_circles[i]]
                if i + 1 < len(list_viz.node_circles):
                    nodes_to_flash.append(list_viz.node_circles[i + 1])
                self.safe_play(
                    *[n.animate.set_stroke(SEMANTIC_COLORS["highlight"], width=5) for n in nodes_to_flash]
                )

            elif action == "show_result":
                self.safe_play(
                    *[c.animate.set_stroke(SEMANTIC_COLORS["success"], width=4) for c in list_viz.node_circles]
                )
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

"""binary_tree_traversal: visit_node steps highlight nodes in traversal
order with an order label (1st, 2nd, ...)."""
from __future__ import annotations

from manim_engine.components.trees.tree_visualizer import TreeVisualizer
from manim_engine.renderer.config import PAUSE_SHORT
from manim_engine.templates.base_scene import BaseVisualizationScene


class BinaryTreeTraversalScene(BaseVisualizationScene):
    def build_visualization(self) -> None:
        data = self.scene_data
        tree_values = data.input.tree_values or []

        tree_viz = TreeVisualizer(tree_values)
        self.play(tree_viz.build_in())

        narration_iter = iter(data.narration)

        for step in data.steps:
            action = step.action

            if action == "build_tree":
                continue

            elif action == "visit_node":
                self.safe_play(*tree_viz.visit(step.index, step.order_label))

            elif action == "show_result":
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

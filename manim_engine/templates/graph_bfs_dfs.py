"""graph_bfs_dfs: visit_graph_node + traverse_edge steps animate a
breadth-first or depth-first walk over an arbitrary graph."""
from __future__ import annotations

from manim_engine.components.graphs.graph_visualizer import GraphVisualizer
from manim_engine.renderer.config import PAUSE_SHORT
from manim_engine.templates.base_scene import BaseVisualizationScene


class GraphBfsDfsScene(BaseVisualizationScene):
    def build_visualization(self) -> None:
        data = self.scene_data
        nodes = data.input.graph_nodes or []
        edges = data.input.graph_edges or []

        graph_viz = GraphVisualizer(nodes, edges)
        self.play(graph_viz.build_in())

        narration_iter = iter(data.narration)

        for step in data.steps:
            action = step.action

            if action == "build_graph":
                continue

            elif action == "visit_graph_node":
                self.safe_play(*graph_viz.visit_node(step.node, step.order_label))

            elif action == "traverse_edge":
                self.safe_play(*graph_viz.traverse_edge(step.from_node, step.to_node))

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

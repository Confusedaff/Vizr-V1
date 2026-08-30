"""hashmap_ops: standalone hashmap insert/lookup sequence (no array
scaffolding) — used when the prompt is specifically about hashmap
mechanics rather than an array algorithm that happens to use one."""
from __future__ import annotations

from manim_engine.components.hashmap.hashmap_visualizer import HashMapVisualizer
from manim_engine.renderer.config import PAUSE_SHORT
from manim_engine.templates.base_scene import BaseVisualizationScene


class HashMapOpsScene(BaseVisualizationScene):
    def build_visualization(self) -> None:
        data = self.scene_data
        hashmap = HashMapVisualizer()
        self.add(hashmap)

        narration_iter = iter(data.narration)

        for step in data.steps:
            action = step.action

            if action == "hashmap_insert":
                self.safe_play(*hashmap.insert(step.key, step.value))

            elif action == "hashmap_lookup":
                self.safe_play(*hashmap.lookup(step.key, step.found))

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

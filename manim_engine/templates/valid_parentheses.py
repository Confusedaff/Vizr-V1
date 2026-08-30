"""valid_parentheses: a StackVisualizer, with push_stack/pop_stack steps
and an optional CodePanel showing the string being scanned character by
character via highlight_code_line repurposed as a scan-position marker."""
from __future__ import annotations

from manim_engine.components.stack.stack_visualizer import StackVisualizer
from manim_engine.renderer.config import PAUSE_SHORT
from manim_engine.templates.base_scene import BaseVisualizationScene


class ValidParenthesesScene(BaseVisualizationScene):
    def build_visualization(self) -> None:
        data = self.scene_data
        stack = StackVisualizer()
        self.add(stack)

        narration_iter = iter(data.narration)

        for step in data.steps:
            action = step.action

            if action == "push_stack":
                self.safe_play(*stack.push(step.value))

            elif action == "pop_stack":
                self.safe_play(*stack.pop(step.matched))

            elif action == "show_result":
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

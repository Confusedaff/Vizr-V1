"""merge_sort: split_array visually divides a range, merge_array shows the
merged (sorted) subrange replacing it. Simplified single-row
representation — sub-arrays are shown as highlighted sub-ranges of the
same row rather than spawning new rows, keeping the layout bounded
regardless of recursion depth."""
from __future__ import annotations

from manim_engine.components.arrays.array_visualizer import ArrayVisualizer
from manim_engine.renderer.config import PAUSE_SHORT
from manim_engine.templates.base_scene import BaseVisualizationScene


class MergeSortScene(BaseVisualizationScene):
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

            elif action == "split_array":
                left = list(range(step.start, step.mid + 1))
                right = list(range(step.mid + 1, step.end + 1))
                self.play(
                    *array_viz.highlight(left, "highlight"),
                    *array_viz.highlight(right, "secondary"),
                )

            elif action == "merge_array":
                # Update underlying values for the merged range by morphing
                # each existing label's text in place (Transform-in-place
                # via .animate.become()) rather than creating a *second*
                # Text object and leaving the original resident in the
                # scene — that two-object pattern is exactly the ghost-
                # mobject bug found in CaptionBar during development
                # (see manim_engine/components/common/caption_bar.py) and
                # reproduces here if not handled carefully: only ever
                # mutate/replace array_viz.labels[idx] itself, and never
                # add a second Text for the same cell.
                from manim import Text as _Text
                from manim_engine.renderer.config import COLOR_TEXT_PRIMARY, FONT_SIZE_CELL

                anims = []
                for offset, new_val in enumerate(step.result):
                    idx = step.start + offset
                    if idx > step.end or idx >= len(array_viz.labels):
                        continue
                    old_label = array_viz.labels[idx]
                    target = _Text(
                        str(new_val),
                        font_size=min(FONT_SIZE_CELL, int(array_viz._cell_size * 34)) or 10,
                        color=COLOR_TEXT_PRIMARY,
                    )
                    target.move_to(old_label.get_center())
                    array_viz.values[idx] = new_val
                    # old_label remains the single Text object registered
                    # in both array_viz and the Scene; .become() mutates
                    # its points/color in place, so array_viz.labels[idx]
                    # continues to correctly reference the one object on
                    # screen — nothing new is ever added.
                    anims.append(old_label.animate.become(target))
                if anims:
                    self.safe_play(*anims)
                self.safe_play(*array_viz.highlight(list(range(step.start, step.end + 1)), "success"))
                self.safe_play(*array_viz.clear_highlight(list(range(step.start, step.end + 1))))

            elif action == "clear_highlight":
                self.safe_play(*array_viz.clear_highlight())

            elif action == "show_result":
                self.safe_play(*array_viz.highlight(step.indices or list(range(len(arr_values))), "success"))
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

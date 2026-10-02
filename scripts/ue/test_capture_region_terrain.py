"""Regression for Slate re-entry while replacing a completed capture task."""

import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class CaptureTransitionTests(unittest.TestCase):
    def test_builder_waits_for_editor_ticks_before_capture(self):
        script = Path(__file__).with_name("capture_region_terrain.py").read_text()
        unreal = Mock()
        ns = {}
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict(sys.modules, {"unreal": unreal}),
        ):
            exec(compile(script.split("\ntry:\n    main()")[0], __file__, "exec"), ns)
            ns.update(
                _index=5,
                _root=Path(folder),
                _camera=Mock(),
                _world=Mock(),
                _views=[{}] * 5
                + [{"name": "after", "location": [0, 0, 0], "target": [1, 0, 0]}],
            )
            result = ("holder", "spline", "actor", "material", {"status": "TRIAL"})

            def execute(*args):
                yield None
                ns["tick"](0)  # Native sampling may pump Slate.
                yield None
                return result

            with (
                patch.dict(
                    sys.modules,
                    {"bob_native_build_lesson": SimpleNamespace(execute=execute)},
                ),
                patch.dict(os.environ, {"YACS_TERRAIN_SHA": "a" * 40}),
            ):
                ns["schedule"]()
                unreal.AutomationLibrary.take_high_res_screenshot.assert_not_called()
                ns["_lesson_next_poll"] = 0
                ns["tick"](0)
                unreal.AutomationLibrary.take_high_res_screenshot.assert_not_called()
                ns["_lesson_next_poll"] = 0
                ns["tick"](0)
                self.assertIs(ns["_lesson_objects"], result)
                unreal.AutomationLibrary.take_high_res_screenshot.assert_called_once()

    def test_geometry_creation_cannot_consume_previous_completed_task(self):
        script = Path(__file__).with_name("capture_region_terrain.py").read_text()
        marker = "\ntry:\n    main()"
        self.assertIn(marker, script)
        unreal = Mock()
        next_task = Mock()
        next_task.is_valid_task.return_value = True
        unreal.AutomationLibrary.take_high_res_screenshot.return_value = next_task
        unreal.Paths.convert_relative_path_to_full.return_value = "/project"
        ns = {}
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict(sys.modules, {"unreal": unreal}),
        ):
            exec(compile(script.split(marker)[0], str(Path(__file__)), "exec"), ns)
            old_task = Mock()
            old_task.is_task_done.return_value = True
            finish = Mock()
            ns.update(
                _index=2,
                _task=old_task,
                _root=Path(folder),
                _camera=Mock(),
                _world=Mock(),
                _started=0,
                finish=finish,
                _views=[
                    {},
                    {},
                    {"name": "road", "location": [0, 0, 0], "target": [1, 0, 0]},
                ],
            )

            def spawn(*args):
                ns["tick"](0)  # A native call pumps Slate before the new task exists.
                self.assertEqual(ns["_index"], 2)
                finish.assert_not_called()
                return ("actor", "material", "report")

            helper = SimpleNamespace(spawn_trial=spawn)
            original_path = sys.path[:]
            try:
                with (
                    patch.dict(sys.modules, {"ma2141_road_preview": helper}),
                    patch.dict(os.environ, {"YACS_TERRAIN_SHA": "a" * 40}),
                ):
                    ns["schedule"]()
            finally:
                sys.path[:] = original_path
            self.assertIs(ns["_task"], next_task)
            self.assertFalse(ns["_scheduling"])
            finish.assert_not_called()


if __name__ == "__main__":
    unittest.main()

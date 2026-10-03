"""Regression for Sa Calobra inspection plus direct Road_Earthworks CUT."""

import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class CaptureTransitionTests(unittest.TestCase):
    def test_active_capture_keeps_inspector_and_direct_cut_builder(self):
        script = Path(__file__).with_name("capture_region_terrain.py").read_text()
        self.assertNotIn("bob_native_build_lesson", script)
        self.assertNotIn("bob-lesson-before", script)
        self.assertNotIn("bob-lesson-after", script)
        self.assertIn(
            '"bob_mode": "INSPECTOR_PLUS_TRANSIENT_CUT_AND_VERTICAL_SUPPORT"',
            script,
        )
        self.assertIn('"bob_road_earthworks_cut_proof"', script)
        self.assertIn('"road-geometry-inspection-before"', script)
        self.assertIn('"road-geometry-inspection-after"', script)
        self.assertIn('"network-extreme-cut"', script)
        self.assertIn("spawn_extreme_cut_diagnostic", script)
        self.assertIn('"road-contact-rider"', script)
        self.assertIn("unreal.ViewModeIndex.VMI_CLAY", script)
        self.assertIn("ShowFlag.MeshEdges 1", script)
        self.assertIn("ShowFlag.MeshEdges 0", script)
        self.assertIn("spawn_mediterranean_atmosphere", script)
        self.assertIn('"atmosphere": _atmosphere_proof', script)

    def test_geometry_inspection_uses_clay_wireframe_and_selects_road(self):
        script = Path(__file__).with_name("capture_region_terrain.py").read_text()
        marker = "\ntry:\n    main()"
        unreal = Mock()
        unreal.ViewModeIndex.VMI_CLAY = "clay"
        unreal.ViewModeIndex.VMI_LIT = "lit"
        unreal.AutomationLibrary.get_editor_active_viewport_view_mode.return_value = (
            "clay"
        )
        unreal.AutomationLibrary.get_editor_active_viewport_wireframe_opacity.return_value = (
            1.0
        )
        actors = Mock()
        unreal.get_editor_subsystem.return_value = actors
        ns = {}
        with patch.dict(sys.modules, {"unreal": unreal}):
            exec(compile(script.split(marker)[0], str(Path(__file__)), "exec"), ns)

        road_actor = Mock()
        road_component = Mock()
        road_component.get_enable_wireframe_render_pass.return_value = True
        road_actor.get_component_by_class.return_value = road_component
        ns.update(_road_objects=(road_actor, Mock(), {}), _world=Mock())
        ns["_apply_capture_view_mode"](
            {
                "geometry_inspection": True,
                "inspection_mode": "VMI_CLAY",
            }
        )

        unreal.AutomationLibrary.set_editor_viewport_view_mode.assert_called_with(
            "clay"
        )
        unreal.AutomationLibrary.set_editor_active_viewport_wireframe_opacity.assert_called_with(
            1.0
        )
        road_component.set_enable_wireframe_render_pass.assert_called_with(True)
        road_component.set_editor_property.assert_any_call(
            "explicit_show_wireframe", True
        )
        road_component.set_editor_property.assert_any_call(
            "wireframe_color",
            unreal.LinearColor(0.0, 1.0, 1.0, 1.0),
        )
        actors.set_selected_level_actors.assert_called_with([road_actor])
        commands = [
            call.args[1]
            for call in unreal.SystemLibrary.execute_console_command.call_args_list
        ]
        self.assertIn("ShowFlag.MeshEdges 1", commands)

    def test_successful_finish_keeps_editor_open(self):
        script = Path(__file__).with_name("capture_region_terrain.py").read_text()
        marker = "\ntry:\n    main()"
        unreal = Mock()
        ns = {}
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict(sys.modules, {"unreal": unreal}),
        ):
            exec(compile(script.split(marker)[0], str(Path(__file__)), "exec"), ns)
            root = Path(folder)
            ns.update(
                _root=root,
                _manifest={
                    "map_package": "/Game/Worlds/SaCalobra/L_SaCalobraTerrainBaseline"
                },
                _proofs=[{"name": "road-contact-rider"}],
                _road_objects=(
                    "actor",
                    "material",
                    {
                        "terrain_fit": {
                            "status": "REVIEW_REQUIRED",
                            "inspection_complete": True,
                        },
                    },
                    {},
                ),
                _cut_report={
                    "status": "TECHNICAL_CUT_PASS",
                    "patch_modified_vertex_count": 123,
                    "before": {"class_counts": {"CUT_REQUIRED": 986}},
                    "after": {"class_counts": {"CUT_REQUIRED": 0}},
                },
                _bob_inspection_status="REVIEW_REQUIRED",
                _views=[{"name": "road-contact-rider"}],
                _handle=None,
            )
            with patch.dict(
                os.environ,
                {
                    "YACS_TERRAIN_SHA": "a" * 40,
                    "YACS_KEEP_EDITOR_OPEN": "1",
                },
            ):
                ns["finish"]()

            proof = json.loads((root / "terrain-capture-proof.json").read_text())
            self.assertEqual(
                proof["bob_mode"],
                "INSPECTOR_PLUS_TRANSIENT_CUT_AND_VERTICAL_SUPPORT",
            )
            self.assertEqual(proof["bob_inspection_status"], "REVIEW_REQUIRED")
            self.assertEqual(
                proof["builder_lesson_status"],
                "TECHNICAL_CUT_PASS",
            )
            self.assertEqual(proof["bob_cut_patch_modified_vertex_count"], 123)
            self.assertEqual(proof["bob_cut_before_count"], 986)
            self.assertEqual(proof["bob_cut_after_count"], 0)
            self.assertTrue(proof["editor_handoff_requested"])
            self.assertEqual(proof["editor_handoff_view"], "road-contact-rider")
            unreal.EditorPythonScripting.set_keep_python_script_alive.assert_called_with(
                True
            )

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

            road_actor = Mock()
            road_component = Mock()
            road_actor.get_component_by_class.return_value = road_component

            def spawn(*args):
                ns["tick"](0)  # A native call pumps Slate before the new task exists.
                self.assertEqual(ns["_index"], 2)
                finish.assert_not_called()
                return (road_actor, Mock(), {"terrain_fit": {}}, {"pre_fit": {}})

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

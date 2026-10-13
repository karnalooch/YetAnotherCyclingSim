"""Inspection/navigation regression tests; CPU doubles are not native proof."""

from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from scripts.live_host.recipes import rock_contact_scatter as m


def vector(x=0, y=0, z=0):
    return NS(x=x, y=y, z=z)


def rotation():
    return NS(pitch=-20, yaw=10, roll=0)


class RegionInspectionTests(unittest.TestCase):
    def setUp(self):
        self.world = object()
        self.live = NS(world=self.world, map_package=m.SEARCH_REGION["map_package"])
        self.context = {"live": self.live}
        self.camera = (vector(1, 2, 3), rotation())
        self.initial = self.camera
        self.set_calls = []
        self.dirty = [NS(get_path_name=lambda: "/Game/UnsavedOwnerWork")]
        self.viewport = NS(
            get_editor_world=lambda: self.world,
            get_level_viewport_camera_info=lambda: self.camera,
            set_level_viewport_camera_info=self.set_camera,
        )
        self.api = NS(
            UnrealEditorSubsystem=object(),
            get_editor_subsystem=lambda _: self.viewport,
            EditorLoadingAndSavingUtils=NS(
                get_dirty_map_packages=lambda: self.dirty,
                get_dirty_content_packages=lambda: [],
            ),
            Vector=vector,
            MathLibrary=NS(find_look_at_rotation=lambda *_: rotation()),
        )

    def set_camera(self, *camera):
        self.set_calls.append(camera)
        self.camera = camera

    def hit(self, _api, _world, xy, ignored):
        self.assertEqual(ignored, [])
        owner = NS(
            get_path_name=lambda: "/World/ActualMesh",
            get_actor_label=lambda: "BOB mesh",
            get_class=lambda: NS(get_name=lambda: "DynamicMeshActor"),
        )
        component = NS(get_path_name=lambda: "/World/ActualMesh/Component")
        values = [None] * 18
        values[:2] = [True, False]
        values[5], values[7] = vector(*xy, 70000), vector(0, 0, 1)
        values[9:11] = owner, component
        return NS(to_tuple=lambda: values)

    def run_operation(self, operation, digest=None):
        return m.inspect_search_region(
            self.api, self.context, operation, digest or m.search_region_digest()
        )

    def test_reports_actual_mesh_owner_without_landscape_or_placement_claim(self):
        with patch.object(m, "trace_ground", side_effect=self.hit):
            result = self.run_operation("region_inspect")
        self.assertEqual(len(result["samples"]), 26)
        self.assertEqual(result["samples"][-1]["actor_class"], "DynamicMeshActor")
        self.assertFalse(result["surface_registered"])
        self.assertFalse(result["native_contact_executed"])
        self.assertEqual(
            result["dirty_packages_before"], result["dirty_packages_after"]
        )
        self.assertEqual(self.set_calls, [])

    def test_wrong_hash_world_and_busy_job_never_trace_or_move_camera(self):
        with patch.object(m, "trace_ground") as trace:
            self.assertIn(
                "FAILED",
                self.run_operation("region_focus", "a" * 64)["operation_status"],
            )
            self.live.world = object()
            self.assertIn(
                "FAILED", self.run_operation("region_focus")["operation_status"]
            )
            self.live.world = self.world
            self.live._pcg365_remote_job = {"operation_status": "CONTACT_JOB_RUNNING"}
            self.assertIn(
                "FAILED", self.run_operation("region_focus")["operation_status"]
            )
            trace.assert_not_called()
        self.assertEqual(self.set_calls, [])

    def test_missing_surface_cannot_focus(self):
        with patch.object(m, "trace_ground", return_value=None):
            result = self.run_operation("region_focus")
        self.assertIn("FAILED", result["operation_status"])
        self.assertEqual(self.set_calls, [])

    def test_focus_and_restore_preserve_original_camera_across_repeat(self):
        with patch.object(m, "trace_ground", side_effect=self.hit):
            for _ in range(2):
                result = self.run_operation("region_focus")
                self.assertNotIn("FAILED", result["operation_status"])
        self.assertEqual(self.live._pcg365_region_camera["camera"], self.initial)
        result = self.run_operation("region_restore")
        self.assertEqual(self.camera, self.initial)
        self.assertNotIn("FAILED", result["operation_status"])

    def test_camera_drift_rolls_back(self):
        calls = 0

        def drifting_set(*camera):
            nonlocal calls
            calls += 1
            self.camera = (vector(), rotation()) if calls == 1 else camera

        self.viewport.set_level_viewport_camera_info = drifting_set
        with patch.object(m, "trace_ground", side_effect=self.hit):
            result = self.run_operation("region_focus")
        self.assertIn("FAILED", result["operation_status"])
        self.assertEqual(self.camera, self.initial)
        self.assertFalse(hasattr(self.live, "_pcg365_region_camera"))

    def test_no_restore_without_retained_camera(self):
        result = self.run_operation("region_restore")
        self.assertIn("FAILED", result["operation_status"])
        self.assertEqual(self.set_calls, [])


if __name__ == "__main__":
    unittest.main()

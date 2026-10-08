"""Source-bound near Landscape probes and exact original survey camera reuse."""

from __future__ import annotations

import copy
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from scripts.ue import capture_sa_calobra_whole_map_prep as capture


def vector(x, y, z):
    return SimpleNamespace(x=x, y=y, z=z)


def hit_result(start, end, point):
    return SimpleNamespace(
        to_tuple=lambda: (start, end, vector(0, 0, 1), vector(*point), vector(*point))
    )


class NearLandscapeProbeTests(unittest.TestCase):
    def setUp(self):
        self.owner = SimpleNamespace(
            get_path_name=lambda: "/Game/Worlds/SaCalobra/Map.Landscape"
        )
        self.other = SimpleNamespace(
            get_path_name=lambda: "/Game/Worlds/SaCalobra/Map.Road"
        )
        self.actors = [self.owner, self.other]
        self.grade = 0.0
        self.base_height = 10000.0
        self.control_is_blocked = False
        self.missing = False
        self.aim_fraction = None
        self.queries = []

        def trace(
            world, start, end, channel, complex_trace, ignored, debug, ignore_self
        ):
            self.queries.append((start, end, list(ignored)))
            if self.missing or (self.owner in ignored and not self.control_is_blocked):
                return None
            denominator = end.z - start.z - self.grade * (end.x - start.x)
            if abs(denominator) < 1e-9:
                return None
            parameter = (
                self.base_height + self.grade * (start.x - 4800) - start.z
            ) / denominator
            if self.aim_fraction is not None and start.x != end.x:
                parameter = self.aim_fraction
            if not 0 < parameter < 1:
                return None
            point = [
                getattr(start, axis)
                + parameter * (getattr(end, axis) - getattr(start, axis))
                for axis in ("x", "y", "z")
            ]
            return hit_result(start, end, point)

        self.api = SimpleNamespace(
            Vector=vector,
            TraceTypeQuery=SimpleNamespace(ECC_VISIBILITY=0),
            DrawDebugTrace=SimpleNamespace(NONE=0),
            EditorActorSubsystem=object(),
            get_editor_subsystem=lambda _: SimpleNamespace(
                get_all_level_actors=lambda: self.actors
            ),
            SystemLibrary=SimpleNamespace(line_trace_single=Mock(side_effect=trace)),
        )
        self.obj = capture.WholeMapCapture.__new__(capture.WholeMapCapture)
        self.obj.api, self.obj.world, self.obj.landscape = (
            self.api,
            object(),
            self.owner,
        )
        self.obj.inputs = {"hashes": dict(capture.NEAR_INPUTS)}
        self.obj.report = {}

    def test_three_probes_bind_audited_pixels_and_each_exact_raster(self):
        probes = capture.near_source_probes(self.obj.inputs)
        self.assertEqual(
            [(p["row"], p["column"]) for p in probes],
            [(1961, 96), (2048, 121), (2048, 1408)],
        )
        self.assertEqual(
            [p["xy_cm"] for p in probes],
            [[4800, 98050], [6050, 102400], [70400, 102400]],
        )
        for probe in probes:
            self.assertEqual(probe["physical_demand_band"], "UNASSIGNED")
            self.assertEqual(
                probe["pixel_window"], [probe["column"] - 8, probe["row"] - 8, 17, 17]
            )
            self.assertEqual(probe["support"]["exclusion0_cells"], 289)
        for name in capture.NEAR_INPUTS:
            with self.subTest(name=name):
                changed = copy.deepcopy(self.obj.inputs)
                changed["hashes"][name] = "0" * 64
                with self.assertRaisesRegex(ValueError, "exact audited raster"):
                    capture.near_source_probes(changed)

    def test_native_near_probes_ignore_other_actors_and_prove_owner_by_control(self):
        views = self.obj._build_near_views()
        self.assertEqual(tuple(view["frame_id"] for view in views), capture.NEAR_VIEWS)
        self.assertEqual(len(self.queries), 18)
        for index in range(0, len(self.queries), 2):
            primary, control = self.queries[index : index + 2]
            self.assertEqual(primary[:2], control[:2])
            self.assertEqual(primary[2], [self.other])
            self.assertEqual(control[2], self.actors)
        for view in views:
            probe = view["landscape_probe"]
            self.assertAlmostEqual(probe["target_distance_cm"], math.hypot(100, 250))
            self.assertAlmostEqual(probe["hit_distance_cm"], math.hypot(100, 250))
            self.assertEqual(probe["camera_clearance_cm"], 250)
            self.assertFalse(probe["rendered_pixel_depth_verified"])
            self.assertEqual(probe["owner_path"], self.owner.get_path_name())
            for key in ("target_trace", "eye_ground_trace", "aim_trace"):
                self.assertIsNone(probe[key]["owner_excluded_control_hit_cm"])

    def test_actor_left_in_control_rejects_unproven_landscape_ownership(self):
        self.control_is_blocked = True
        with self.assertRaisesRegex(RuntimeError, "Landscape excluded"):
            self.obj._build_near_views()

    def test_native_trace_miss_fails_without_inventing_a_ground_height(self):
        self.missing = True
        with self.assertRaisesRegex(RuntimeError, "Near Landscape trace missed"):
            self.obj._build_near_views()
        self.assertEqual(len(self.queries), 1)

    def test_steep_eye_ground_cannot_force_a_camera_beyond_five_metres(self):
        self.grade = 4.0
        with self.assertRaisesRegex(RuntimeError, "outside 100..500 cm"):
            self.obj._build_near_views()
        self.assertEqual(len(self.queries), 4)

    def test_actual_aim_hit_must_also_be_between_one_and_five_metres(self):
        self.aim_fraction = 0.1
        with self.assertRaisesRegex(RuntimeError, "actual hit leaves"):
            self.obj._build_near_views()

    def test_below_sea_level_landscape_keeps_actual_native_height(self):
        self.base_height = -4000.0
        views = self.obj._build_near_views()
        self.assertTrue(all(view["target"][2] == -4000 for view in views))
        self.assertTrue(all(view["camera"][2] == -3750 for view in views))

    def test_trace_endpoint_normal_and_nonfinite_vectors_are_not_hits(self):
        start, end = [4800, 98050, 150000], [4800, 98050, -150000]
        invalid = SimpleNamespace(
            to_tuple=lambda: (
                vector(*start),
                vector(*end),
                vector(0, 0, 1),
                vector(4800, 98050, float("nan")),
            )
        )
        self.assertIsNone(capture.trace_point(invalid, start, end))
        self.assertIsNone(capture.trace_point(None, start, end))


class OriginalSurveyViewTests(unittest.TestCase):
    def test_b_and_c_keep_exact_original_pose_fov_and_distinct_review_status(self):
        views = capture.original_survey_views()
        self.assertEqual(tuple(view["frame_id"] for view in views), capture.FAR_VIEWS)
        self.assertEqual(
            [view["survey_source"]["index"] for view in views], [661, 1088]
        )
        self.assertEqual(
            [view["survey_source"]["review_card"] for view in views],
            ["SC-P04", "SC-P06"],
        )
        self.assertEqual(
            [view["survey_source"]["proposal_band"] for view in views], ["B", "C"]
        )
        self.assertEqual(
            views[0]["camera"],
            [128574.85024645955, 42739.59235066789, 67930.15472518535],
        )
        self.assertEqual(
            views[1]["target"],
            [142857.13525972454, 90601.8422138785, 72230.78873929933],
        )
        for view in views:
            self.assertEqual(view["fov"], 76.0)
            self.assertFalse(view["survey_source"]["physical_surface_registered"])
            self.assertEqual(view["survey_source"]["original_resolution"], [1280, 720])

    def test_modified_survey_bytes_are_rejected_even_if_rows_still_parse(self):
        original = (capture.ROOT / capture.SURVEY_FILE).read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "frames.csv"
            path.write_bytes(original + b"\n")
            with self.assertRaisesRegex(ValueError, "CSV byte identity changed"):
                capture.original_survey_views(path)


class MaterialParameterTransitionTests(unittest.TestCase):
    def setUp(self):
        self.values = capture.mode_parameters("prepared")
        self.owner = capture.WholeMapCapture.__new__(capture.WholeMapCapture)
        self.owner.instance = object()

        def set_value(_instance, name, value, _association):
            self.values[name] = value

        self.library = SimpleNamespace(
            get_material_instance_scalar_parameter_value=Mock(
                side_effect=lambda _instance, name, _association: self.values[name]
            ),
            set_material_instance_parameter_override=Mock(),
            set_material_instance_scalar_parameter_value=Mock(side_effect=set_value),
            update_material_instance=Mock(),
        )
        self.owner.api = SimpleNamespace(
            MaterialEditingLibrary=self.library,
            MaterialParameterAssociation=SimpleNamespace(GLOBAL_PARAMETER=0),
        )

    def test_same_prepared_values_are_read_without_material_mutation(self):
        for _ in range(2):
            self.assertFalse(
                self.owner._set_parameters(capture.mode_parameters("prepared"))
            )
        self.assertEqual(
            self.library.get_material_instance_scalar_parameter_value.call_count, 8
        )
        self.library.set_material_instance_parameter_override.assert_not_called()
        self.library.set_material_instance_scalar_parameter_value.assert_not_called()
        self.library.update_material_instance.assert_not_called()

    def test_diagnostic_transition_changes_only_the_different_parameter_once(self):
        desired = capture.mode_parameters("domains")
        self.assertTrue(self.owner._set_parameters(desired))
        self.assertEqual(self.values, desired)
        self.library.set_material_instance_scalar_parameter_value.assert_called_once_with(
            self.owner.instance, "DomainMix", 1.0, 0
        )
        self.assertFalse(self.owner._set_parameters(desired))
        self.library.update_material_instance.assert_called_once_with(
            self.owner.instance
        )

    def test_failed_native_setter_is_rejected_by_actual_readback(self):
        self.library.set_material_instance_scalar_parameter_value.side_effect = None
        with self.assertRaisesRegex(RuntimeError, "readback differs: DomainMix"):
            self.owner._set_parameters(capture.mode_parameters("domains"))

    def test_nonfinite_state_fails_before_any_parameter_mutation(self):
        self.values["CheckerMix"] = math.nan
        with self.assertRaisesRegex(RuntimeError, "Non-finite whole-map scalar"):
            self.owner._set_parameters(capture.mode_parameters("domains"))
        self.library.set_material_instance_parameter_override.assert_not_called()
        self.library.set_material_instance_scalar_parameter_value.assert_not_called()
        self.library.update_material_instance.assert_not_called()


if __name__ == "__main__":
    unittest.main()

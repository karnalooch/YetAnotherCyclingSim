"""Synthetic trace fixtures verify the optional sink, never native MCP proof."""

from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts.worldgen.bob_terrain_fit_inspector import inspect_terrain_fit


SHA = "a" * 40


class BobTerrainFitSampleExportTests(unittest.TestCase):
    def setUp(self):
        self.api = Mock()
        self.api.Vector.side_effect = lambda x, y, z: SimpleNamespace(x=x, y=y, z=z)
        path = Path(__file__).with_name("bob_road_earthworks_cut.py")
        specification = importlib.util.spec_from_file_location("_bob_sample_export_fixture", path)
        self.producer = importlib.util.module_from_spec(specification)
        with patch.dict(sys.modules, {"unreal": self.api}):
            specification.loader.exec_module(self.producer)
        self.profile = {
            "stations": [{"station_m": float(station), "lateral_m": [-1.0, 1.0]}
                         for station in range(121)],
        }
        self.vertices = [[float(station), lateral, 100.0]
                         for station in range(121) for lateral in (-1.0, 1.0)]
        self.meta = {"top_vertex_count": len(self.vertices), "cross_section_point_count": 2}
        self.world = object()
        self.misses = set()
        self.trace_index = 0

        def trace(world, start, end, channel, complex_trace, ignore, debug, ignore_self):
            self.assertIs(world, self.world)
            self.assertTrue(complex_trace)
            self.assertEqual(ignore, [])
            self.assertTrue(ignore_self)
            self.assertEqual(start.z - end.z, 20000.0)
            index = self.trace_index
            self.trace_index += 1
            if index in self.misses:
                return None
            # Synthetic 2 m penetration makes >100 actionable sample rows.
            return SimpleNamespace(to_tuple=lambda: [
                SimpleNamespace(x=start.x, y=start.y, z=10200.0),
            ])

        self.api.SystemLibrary.line_trace_single.side_effect = trace

    def measure(self, **extra):
        return self.producer.measure_smooth_terrain_fit(
            self.world, self.profile, self.vertices, self.meta, exact_sha=SHA,
            contact_band_max_m=0.08,
            geometry_inspection_view="road-geometry-inspection-before", **extra,
        )

    def landscape_fixture(self):
        self.landscape_component = SimpleNamespace(
            get_path_name=lambda: "/World/Landscape.Collision_0",
            get_class=lambda: SimpleNamespace(get_path_name=lambda:
                "/Script/Landscape.LandscapeHeightfieldCollisionComponent"),
            get_editor_property=lambda name: None,
        )
        self.landscape = SimpleNamespace(
            get_path_name=lambda: "/World/Landscape",
            get_components_by_class=Mock(return_value=[self.landscape_component]),
        )
        self.road = SimpleNamespace(get_path_name=lambda: "/World/YACS_PERSIST_ROAD")
        self.support = SimpleNamespace(get_path_name=lambda: "/World/YACS_PERSIST_SUPPORT_0")
        self.actors = [self.landscape, self.road, self.support]
        self.api.GameplayStatics.get_all_actors_of_class.return_value = [self.landscape]
        self.api.get_editor_subsystem.return_value.get_all_level_actors.return_value = self.actors
        self.hit_fields = {
            "blocking_hit": True, "hit_actor": self.landscape,
            "hit_component": self.landscape_component,
        }

        def trace(world, start, end, channel, complex_trace, ignore, debug, ignore_self):
            self.assertEqual(ignore, [self.road, self.support])
            self.assertNotIn(self.landscape, ignore)
            self.assertIs(world, self.world)
            self.assertTrue(complex_trace)
            index = self.trace_index
            self.trace_index += 1
            if index in self.misses:
                return None
            impact = SimpleNamespace(x=start.x, y=start.y, z=10200.0)
            fields = {"impact_point": impact, **self.hit_fields}
            return SimpleNamespace(get_editor_property=lambda name: fields.get(name),
                                   to_tuple=lambda: [impact])

        self.api.SystemLibrary.line_trace_single.side_effect = trace

    def test_landscape_mode_ignores_saved_pavement_and_retains_same_complete_rows(self):
        ordinary = self.measure()
        self.trace_index = 0
        self.api.reset_mock()
        self.landscape_fixture()
        sink = Mock()
        before = deepcopy((self.profile, self.vertices, self.meta))
        with patch.object(self.producer, "apply_cut_patch") as authoring:
            report = self.measure(landscape=self.landscape, sample_sink=sink)
            authoring.assert_not_called()
        self.assertEqual(report, ordinary)
        self.assertEqual(len(sink.call_args.kwargs["samples"]), 242)
        self.assertEqual(self.api.SystemLibrary.line_trace_single.call_count, 242)
        self.assertEqual((self.profile, self.vertices, self.meta), before)
        self.landscape.get_components_by_class.assert_called_once_with(self.api.PrimitiveComponent)
        self.assertTrue(all(report[name] is False for name in (
            "earthworks_authoring_permitted", "geometry_repair_executed",
            "road_admitted", "eligible_for_learning",
        )))

    def test_landscape_mode_missing_collision_remains_incomplete(self):
        self.landscape_fixture()
        self.misses = {0, 241}
        sink = Mock()
        report = self.measure(landscape=self.landscape, sample_sink=sink)
        self.assertEqual(report["status"], "INSPECTION_INCOMPLETE")
        self.assertEqual(report["trace_miss_count"], 2)
        self.assertIsNone(sink.call_args.kwargs["samples"][0]["landscape_z_m"])

    def test_landscape_mode_nonblocking_result_does_not_count_as_owned_sample(self):
        self.landscape_fixture()
        self.hit_fields = {"blocking_hit": False}
        report = self.measure(landscape=self.landscape)
        self.assertEqual(report["status"], "INSPECTION_INCOMPLETE")
        self.assertEqual(report["trace_miss_count"], 242)
        self.assertEqual(report["evaluated_sample_count"], 0)

    def test_landscape_mode_rejects_unknown_blocking_actor_or_component_ownership(self):
        for field in ("blocking_hit", "hit_actor", "hit_component"):
            with self.subTest(field=field):
                self.landscape_fixture()
                self.hit_fields.pop(field)
                sink = Mock()
                with self.assertRaises(RuntimeError):
                    self.measure(landscape=self.landscape, sample_sink=sink)
                sink.assert_not_called()

    def test_landscape_mode_rejects_foreign_actor_or_unowned_component(self):
        for field in ("hit_actor", "hit_component"):
            with self.subTest(field=field):
                self.landscape_fixture()
                self.hit_fields[field] = (
                    self.road if field == "hit_actor" else
                    SimpleNamespace(get_path_name=lambda: "/World/Landscape.Collision_0")
                )
                with self.assertRaisesRegex(RuntimeError, "unknown or foreign"):
                    self.measure(landscape=self.landscape)

    def test_landscape_mode_requires_exactly_one_matching_world_landscape(self):
        for mode in ("absent", "duplicate", "foreign"):
            with self.subTest(mode=mode):
                self.landscape_fixture()
                matches = {"absent": [], "duplicate": [self.landscape, self.landscape],
                           "foreign": [self.road]}[mode]
                self.api.GameplayStatics.get_all_actors_of_class.return_value = matches
                self.api.SystemLibrary.line_trace_single.reset_mock()
                with self.assertRaisesRegex(RuntimeError, "single supplied Landscape"):
                    self.measure(landscape=self.landscape)
                self.api.SystemLibrary.line_trace_single.assert_not_called()

    def test_landscape_mode_rejects_missing_or_ambiguous_actor_component_inventories(self):
        for mode in ("missing actor", "duplicate actor", "empty components", "duplicate component"):
            with self.subTest(mode=mode):
                self.landscape_fixture()
                if mode == "missing actor":
                    self.api.get_editor_subsystem.return_value.get_all_level_actors.return_value = [self.road]
                elif mode == "duplicate actor":
                    self.api.get_editor_subsystem.return_value.get_all_level_actors.return_value += [self.road]
                else:
                    self.landscape.get_components_by_class.return_value = (
                        [] if mode == "empty components" else [self.landscape_component] * 2
                    )
                self.api.SystemLibrary.line_trace_single.reset_mock()
                with self.assertRaisesRegex(RuntimeError, "inventory"):
                    self.measure(landscape=self.landscape)
                self.api.SystemLibrary.line_trace_single.assert_not_called()

    def test_landscape_mode_tuple_position_fallback_never_supplies_owner_evidence(self):
        self.landscape_fixture()
        self.hit_fields["impact_point"] = None
        sink = Mock()
        report = self.measure(landscape=self.landscape, sample_sink=sink)
        self.assertEqual(report["sample_count"], 242)
        self.assertEqual(sink.call_args.kwargs["samples"][0]["landscape_z_m"], 102.0)
        self.hit_fields.pop("hit_actor")
        with self.assertRaisesRegex(RuntimeError, "ownership"):
            self.measure(landscape=self.landscape)

    def test_landscape_mode_rejects_off_ray_owned_impact(self):
        self.landscape_fixture()
        self.hit_fields["impact_point"] = SimpleNamespace(x=5000.0, y=5000.0, z=10200.0)
        with self.assertRaisesRegex(RuntimeError, "not on the inspected ray"):
            self.measure(landscape=self.landscape)

    def test_landscape_mode_rejects_owned_nonterrain_mesh_component(self):
        self.landscape_fixture()
        owned_mesh = SimpleNamespace(
            get_path_name=lambda: "/World/Landscape.OwnedMesh_0",
            get_class=lambda: SimpleNamespace(get_path_name=lambda: "/Script/Engine.StaticMeshComponent"),
        )
        self.landscape.get_components_by_class.return_value += [owned_mesh]
        self.hit_fields["hit_component"] = owned_mesh
        with self.assertRaisesRegex(RuntimeError, "unknown or foreign"):
            self.measure(landscape=self.landscape)

    def test_landscape_mode_rejects_missing_or_unavailable_collision_component_type(self):
        for reflected in ("/Script/Engine.StaticMeshComponent", None):
            with self.subTest(reflected=reflected):
                self.landscape_fixture()
                self.landscape_component.get_class = lambda: (
                    SimpleNamespace(get_path_name=lambda: reflected) if reflected else None
                )
                self.api.SystemLibrary.line_trace_single.reset_mock()
                with self.assertRaisesRegex(RuntimeError, "collision"):
                    self.measure(landscape=self.landscape)
                self.api.SystemLibrary.line_trace_single.assert_not_called()

    def test_sink_receives_all_measured_rows_with_original_order_and_units(self):
        sink = Mock()
        original = deepcopy((self.profile, self.vertices, self.meta))
        report = self.measure(sample_sink=sink)
        sink.assert_called_once()
        samples = sink.call_args.kwargs["samples"]
        self.assertEqual(len(samples), 242)
        self.assertEqual(report["sample_count"], 242)
        self.assertEqual(len(report["worst_action_samples"]), 100)
        self.assertEqual(samples[-1], {
            "station_m": 120.0, "lateral_m": 1.0, "local_xy_m": [120.0, 1.0],
            "road_surface_z_m": 100.0, "landscape_z_m": 102.0,
        })
        self.assertEqual(report, inspect_terrain_fit(
            samples, exact_sha=SHA, contact_band_max_m=0.08,
            structure_review_threshold_m=4.0,
            geometry_inspection_view="road-geometry-inspection-before",
        ))
        self.assertEqual(sink.call_args.kwargs["inspection"], report)
        self.assertEqual((self.profile, self.vertices, self.meta), original)
        self.assertEqual(self.api.SystemLibrary.line_trace_single.call_count, 242)

    def test_sink_preserves_trace_misses_and_incomplete_result(self):
        self.misses = {4, 241}
        sink = Mock()
        report = self.measure(sample_sink=sink)
        samples = sink.call_args.kwargs["samples"]
        self.assertEqual(len(samples), 242)
        self.assertIsNone(samples[4]["landscape_z_m"])
        self.assertIsNone(samples[241]["landscape_z_m"])
        self.assertEqual(report["trace_miss_count"], 2)
        self.assertEqual(report["status"], "INSPECTION_INCOMPLETE")
        self.assertFalse(report["road_admitted"])

    def test_default_call_keeps_existing_report_and_trace_behavior(self):
        without_sink = self.measure()
        self.trace_index = 0
        sink = Mock()
        with_sink = self.measure(sample_sink=sink)
        self.assertEqual(with_sink, without_sink)
        self.assertEqual(self.api.SystemLibrary.line_trace_single.call_count, 484)

    def test_sink_cannot_change_returned_inspection_or_measurement_inputs(self):
        original = deepcopy((self.profile, self.vertices, self.meta))

        def modify_copies(*, samples, inspection):
            samples[0]["local_xy_m"][0] = 99999.0
            samples.clear()
            inspection["worst_action_samples"][0]["local_xy_m"][0] = 99999.0
            inspection["status"] = "PASS"
            inspection["earthworks_authoring_permitted"] = True

        report = self.measure(sample_sink=modify_copies)
        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertFalse(report["earthworks_authoring_permitted"])
        self.assertEqual(report["worst_action_samples"][0]["local_xy_m"], [0.0, -1.0])
        self.assertEqual((self.profile, self.vertices, self.meta), original)

    def test_invalid_sink_fails_before_native_traces(self):
        with self.assertRaisesRegex(TypeError, "trusted callable"):
            self.measure(sample_sink="arbitrary Python")
        self.api.SystemLibrary.line_trace_single.assert_not_called()

    def test_sink_failure_propagates_without_authoring(self):
        with patch.object(self.producer, "apply_cut_patch") as authoring:
            with self.assertRaisesRegex(OSError, "export failed"):
                self.measure(sample_sink=Mock(side_effect=OSError("export failed")))
            authoring.assert_not_called()


if __name__ == "__main__":
    unittest.main()

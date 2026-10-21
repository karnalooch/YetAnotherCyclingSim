"""Synthetic L07 admission/path/native-query boundary tests, never UE evidence."""

from copy import deepcopy
from fnmatch import fnmatchcase
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from textwrap import dedent
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts.ue import readback_lesson07_geometry as reader


ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "scripts/ue/Invoke-YacsLesson07Readback.ps1"
WORKFLOW = ROOT / ".github/workflows/yacs-lesson07-unreal-readonly.yml"


def landscape_rows():
    rows = []
    positions = [[x * 254, y * 254] for x in range(32) for y in range(32)]
    for label in sorted(reader.EXPECTED_ACTORS):
        values = {"component_size_quads": [254], "subsection_size_quads": [127],
                  "num_subsections": [2], "section_base_x": [x * 254 for x in range(32)],
                  "section_base_y": [x * 254 for x in range(32)]}
        rows.append({
            "label": label, "component_count": 1024,
            "actual_component_properties": {
                key: {"complete": True, "read_count": 1024, "total": 1024, "values": value}
                for key, value in values.items()
            },
            "component_section_bases": deepcopy(positions),
            "location_cm": [0.0, 0.0, 0.0], "rotation_deg_pitch_yaw_roll": [0.0, 0.0, 0.0],
            "scale": [50.0, 50.0, 185.7248], "bounds_origin_cm": [0.0, 0.0, 0.0],
            "bounds_extent_cm": [203200.0, 203200.0, 23678.0],
            "assigned_material": reader.EXPECTED_MATERIAL + ".MI_Landscape_Instance_YACS",
            "hole_material": {"observed": True, "value": None},
            "edit_layers": {"observed": True, "value": []},
            "target_layers": {"observed": True, "value": []},
        })
    return rows


def native_layout_reply(component_path, fields=None):
    return {"schema_version": 1, "observed": True, "component_path": component_path,
            "world_package": reader.LEVEL_PATH,
            "fields": fields if fields is not None else {
                "component_size_quads": 254, "subsection_size_quads": 127,
                "num_subsections": 2, "section_base_x": 0, "section_base_y": 0,
            }}


class NativeComponentLayoutTests(unittest.TestCase):
    def setUp(self):
        self.path = reader.LEVEL_PATH + ".World:PersistentLevel.Landscape.Component0"
        self.component = SimpleNamespace(
            get_path_name=lambda: self.path,
            get_editor_property=Mock(side_effect=AssertionError("no editor-property fallback")),
        )
        self.getter = Mock()
        self.api = SimpleNamespace(YacsLandscapeMeshDiagnosticLibrary=SimpleNamespace(
            read_lesson07_component_layout=self.getter))

    def read(self, value):
        self.getter.return_value = json.dumps(value)
        result = reader.read_component_layout(self.api, self.component)
        self.component.get_editor_property.assert_not_called()
        return result

    def test_native_integer_and_exact_double_tokens_preserve_actual_fields(self):
        for floating in (False, True):
            value = native_layout_reply(self.path, {
                "component_size_quads": 126, "subsection_size_quads": 63,
                "num_subsections": 2, "section_base_x": -126, "section_base_y": 252,
            })
            if floating:
                value["schema_version"] = 1.0
                value["fields"] = {name: float(number) for name, number in value["fields"].items()}
            with self.subTest(floating=floating):
                result = self.read(value)
                self.assertTrue(result["observed"])
                self.assertIsNone(result["error"])
                self.assertEqual(result["component_path"], self.path)
                self.assertEqual(result["world_package"], reader.LEVEL_PATH)
                self.assertEqual(result["fields"], value["fields"])
                self.assertTrue(all(type(number) is int for number in result["fields"].values()))
                self.assertEqual(result["fields"]["component_size_quads"], 126)

    def test_wrong_schema_identity_missing_fields_and_native_refusal_are_unknown(self):
        good = native_layout_reply(self.path)
        cases = [None, [], {**good, "schema_version": True}, {**good, "schema_version": 2},
                 {**good, "observed": "true"}, {**good, "component_path": "/Game/Other.Component"},
                 {**good, "world_package": "/Game/Other"}, {**good, "fields": {}},
                 {**good, "fields": {**good["fields"], "unrequested": 1}},
                 {"schema_version": 1, "observed": False, "error": "native world refusal"}]
        for value in cases:
            with self.subTest(value=value):
                result = self.read(value)
                self.assertFalse(result["observed"])
                self.assertIsNone(result["fields"])
                self.assertTrue(result["error"])
        self.assertIn("native world refusal", self.read(cases[-1])["error"])

    def test_non_int32_values_never_truncate_or_become_design_defaults(self):
        for name in reader.COMPONENT_FIELDS:
            for number in (None, True, 254.9, "254", float("nan"), float("inf"),
                           float("-inf"), 2**31, -(2**31) - 1):
                value = native_layout_reply(self.path)
                value["fields"][name] = number
                with self.subTest(name=name, number=number):
                    result = self.read(value)
                    self.assertFalse(result["observed"])
                    self.assertIsNone(result["fields"])
                    measured = reader.actual_component_settings([result])
                    self.assertTrue(all(not row["complete"] and row["read_count"] == 0
                                        and row["values"] == [] for row in measured.values()))

    def test_unavailable_native_getter_bad_json_and_exceptions_retain_errors(self):
        result = reader.read_component_layout(SimpleNamespace(), self.component)
        self.assertFalse(result["observed"])
        self.assertIn("YacsLandscapeMeshDiagnosticLibrary", result["error"])
        for raw in (None, "not JSON", "x" * 4097):
            with self.subTest(raw=raw[:20] if raw else raw):
                self.getter.return_value = raw
                result = reader.read_component_layout(self.api, self.component)
                self.assertFalse(result["observed"])
                self.assertIsNone(result["fields"])
                self.assertTrue(result["error"])
        self.getter.side_effect = RuntimeError("native read unavailable")
        result = reader.read_component_layout(self.api, self.component)
        self.assertIn("native read unavailable", result["error"])
        self.component.get_editor_property.assert_not_called()


class NativeComponentSampleTests(unittest.TestCase):
    def setUp(self):
        self.path = reader.LEVEL_PATH + ".World:PersistentLevel.SaCalobra_Unified_0_0.Component0"
        self.component = SimpleNamespace(get_path_name=lambda: self.path)
        self.value = {
            "schema_version": 1, "observed": True, "component_path": self.path,
            "world_package": reader.LEVEL_PATH, "actor_name": "SaCalobra_Unified_0_0",
            "vertex_indices": [0, 254, 65024], "visibility_observed": True,
            "visibility_status": "ALLOCATED_READ",
            "samples": [[32768, -25.012, 100.0, 0.0, 0],
                        [32769, -25.012, 150.0, 1.45, 255],
                        [65535, -25.012, 200.0, 100.0, 171]],
        }
        self.getter = Mock(side_effect=lambda *_args: json.dumps(self.value))
        self.api = SimpleNamespace(YacsLandscapeMeshDiagnosticLibrary=SimpleNamespace(
            read_lesson07_component_samples=self.getter))

    def read(self, indices=None):
        return reader.read_component_samples(self.api, self.component, [0, 254, 65024] if indices is None else indices)

    def test_native_samples_retain_exact_world_coordinates_and_raw_codes(self):
        result = self.read()
        self.assertEqual(result["samples"], self.value["samples"])
        self.assertEqual(result["samples"][0][1], -25.012)
        self.getter.assert_called_once_with(self.component, [0, 254, 65024])

    def test_missing_visibility_is_explicit_unknown_and_not_fabricated_zero(self):
        for status in ("NOT_ALLOCATED", "READ_FAILED"):
            self.value.update(visibility_observed=False, visibility_status=status)
            for row in self.value["samples"]:
                row[4] = None
            self.assertTrue(all(row[4] is None for row in self.read()["samples"]))
        self.value["samples"][0][4] = 0
        with self.assertRaisesRegex(ValueError, "visibility sample"):
            self.read()

    def test_malformed_native_identity_counts_and_values_fail_closed(self):
        original = deepcopy(self.value)
        for key, bad in (("schema_version", True), ("observed", False),
                         ("component_path", "/Game/Other.Component"), ("world_package", "/Game/Other"),
                         ("actor_name", "Other"), ("vertex_indices", [0, 254, 65023]),
                         ("vertex_indices", [False, 254, 65024]), ("samples", []),
                         ("visibility_observed", "true"), ("visibility_status", "UNKNOWN")):
            self.value = {**deepcopy(original), key: bad}
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                self.read()
        for column, bad in ((0, 1.5), (0, 65536), (1, float("nan")), (3, float("inf")),
                            (4, -1), (4, 256), (4, True), (4, None)):
            self.value = deepcopy(original)
            self.value["samples"][0][column] = bad
            with self.subTest(column=column, bad=bad), self.assertRaises(ValueError):
                self.read()

    def test_bad_requests_stop_before_native_call_and_oversized_reply_is_rejected(self):
        for indices in ([], [0, 0], [-1], [65025], [True], list(range(1025))):
            with self.subTest(indices=indices[:3]), self.assertRaises(ValueError):
                self.read(indices)
        self.getter.assert_not_called()
        self.getter.side_effect = None
        self.getter.return_value = "x" * (512 * 1024 + 1)
        with self.assertRaisesRegex(ValueError, "bounded JSON"):
            self.read()


class NativeSeamMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.api = SimpleNamespace(
            Vector=lambda x, y, z: SimpleNamespace(x=x, y=y, z=z),
            TraceTypeQuery=SimpleNamespace(TRACE_TYPE_QUERY1=1), DrawDebugTrace=SimpleNamespace(NONE=0),
            SystemLibrary=SimpleNamespace(line_trace_single=Mock(return_value=None)),
        )
        self.world = object()
        self.tiles = {}
        self.calls = 0
        for ix in range(2):
            for iy in range(2):
                name = f"SaCalobra_Unified_{ix}_{iy}"
                # Synthetic native-transform fixture includes the actual -90deg
                # orientation; tests must not assume local X is geographic X.
                def transform(point, ix=ix, iy=iy):
                    return self.api.Vector(-406425 + ix * 406400 + point.y * 50,
                                           -25 + iy * 406400 - point.x * 50, point.z)
                actor = SimpleNamespace(
                    get_name=lambda name=name: name,
                    get_actor_transform=lambda transform=transform: SimpleNamespace(transform_location=transform),
                    get_actor_bounds=lambda _collision, transform=transform: (
                        transform(self.api.Vector(4064, 4064, 0)), self.api.Vector(203200, 203200, 1000)),
                )
                components, layouts = [], []
                for x in range(32):
                    for y in range(32):
                        fields = {**native_layout_reply("fixture")["fields"],
                                  "section_base_x": x * 254, "section_base_y": y * 254}
                        path = reader.LEVEL_PATH + f".World:PersistentLevel.{name}.Component_{x}_{y}"
                        components.append(SimpleNamespace(
                            get_path_name=lambda path=path: path, get_owner=lambda actor=actor: actor,
                            actor=name, transform=transform, fields=fields,
                        ))
                        layouts.append({"observed": True, "fields": fields})
                self.tiles[name] = actor, components, layouts
        self.actors = [tile[0] for tile in self.tiles.values()]

        def getter(component, indices):
            self.calls += 1
            rows = []
            for index in indices:
                x, y = index % 255, index // 255
                pos = component.transform(self.api.Vector(
                    component.fields["section_base_x"] + x, component.fields["section_base_y"] + y, 0))
                rows.append([32768, pos.x, pos.y, 1000.0, 0])
            return json.dumps({
                "schema_version": 1, "observed": True, "component_path": component.get_path_name(),
                "world_package": reader.LEVEL_PATH, "actor_name": component.actor,
                "vertex_indices": indices, "samples": rows, "visibility_observed": True,
                "visibility_status": "ALLOCATED_READ",
            })
        self.api.YacsLandscapeMeshDiagnosticLibrary = SimpleNamespace(read_lesson07_component_samples=getter)

    def test_all_four_complete_two_sided_edges_and_bounded_collision_are_measured(self):
        result = reader.native_seam_readback(self.api, self.world, self.actors, self.tiles)
        self.assertEqual(self.calls, 256)
        self.assertEqual({s["id"] for s in result["seams"]}, {"x_0", "x_1", "y_0", "y_1"})
        self.assertTrue(result["height_samples_complete"])
        self.assertTrue(result["visibility_samples_complete"])
        self.assertTrue(result["collision_queries_complete"])
        self.assertFalse(result["geometry_accepted"])
        self.assertFalse(result["source_height_interpolation_proved"])
        self.assertFalse(result["visibility_layer_proved_in_ue"])
        for seam in result["seams"]:
            for side in ("a", "b"):
                self.assertEqual(len(seam[side]["samples"]), 8129)
                self.assertEqual(len(seam[side]["component_joins"]), 31)
            self.assertEqual(seam["peer_summary"]["max_xy_gap_cm"], 0)
            self.assertEqual(seam["peer_summary"]["max_abs_height_delta_cm"], 0)
            self.assertEqual(len(seam["collision_probes"]), 130)
            self.assertTrue(all(p["at_vertex"]["observed"] and p["at_vertex"]["hit"] is False
                                for p in seam["collision_probes"]))
        self.assertEqual(self.api.SystemLibrary.line_trace_single.call_count, 1040)
        for call in self.api.SystemLibrary.line_trace_single.call_args_list:
            self.assertEqual(len(call.args[5]), 3)  # Other tiles cannot answer for this side.
        # Full evidence, with realistic high-precision doubles, retains headroom
        # for the existing per-component structural inventory under the 8MiB cap.
        for seam in result["seams"]:
            for side in ("a", "b"):
                for row in seam[side]["samples"]:
                    row[1:4] = [x + 0.123456789012345 for x in row[1:4]]
        self.assertLess(len(json.dumps(result, separators=(",", ":"), allow_nan=False)), 6 * 1024**2)

    def test_component_join_defect_is_preserved_when_deduplicating_shared_vertex(self):
        actor, components, layouts = self.tiles["SaCalobra_Unified_0_0"]
        plan = reader.landscape_edge_plans(self.api, actor, components, layouts)[0]
        original = self.api.YacsLandscapeMeshDiagnosticLibrary.read_lesson07_component_samples
        count = 0
        def discontinuous(component, indices):
            nonlocal count
            count += 1
            value = json.loads(original(component, indices))
            if count == 2:
                value["samples"][0][3] += 3.0
            return json.dumps(value)
        self.api.YacsLandscapeMeshDiagnosticLibrary.read_lesson07_component_samples = discontinuous
        result = reader.read_native_edge(self.api, actor, plan)
        self.assertEqual(len(result["samples"]), 8129)
        self.assertEqual(result["component_joins"][0]["delta_xyz_cm"][2], 3.0)
        self.assertEqual(result["component_joins"][0]["next_component_sample"][3], 1003.0)

    def test_failed_seam_retains_completed_side_and_other_seams_without_completeness(self):
        original = self.api.YacsLandscapeMeshDiagnosticLibrary.read_lesson07_component_samples
        failed = False
        def unavailable_once(component, indices):
            nonlocal failed
            if component.actor == "SaCalobra_Unified_1_0" and not failed:
                failed = True
                raise RuntimeError("native sample source unavailable")
            return original(component, indices)
        self.api.YacsLandscapeMeshDiagnosticLibrary.read_lesson07_component_samples = unavailable_once
        result = reader.native_seam_readback(self.api, self.world, self.actors, self.tiles)
        self.assertFalse(result["height_samples_complete"])
        self.assertFalse(result["collision_queries_complete"])
        self.assertFalse(result["geometry_accepted"])
        first = result["seams"][0]
        self.assertFalse(first["observed"])
        self.assertIn("native sample source unavailable", first["error"])
        self.assertEqual(len(first["a"]["samples"]), 8129)
        self.assertTrue(all(seam["observed"] for seam in result["seams"][1:]))

    def test_collision_rejects_wrong_actor_component_nonfinite_and_unknown(self):
        target = self.actors[0]
        component = self.tiles[target.get_name()][1][0]
        hit = {"blocking_hit": True, "hit_actor": target, "hit_component": component,
               "impact_point": self.api.Vector(0, 0, 1000)}
        trace = self.api.SystemLibrary.line_trace_single
        for changes in ({}, {"hit_actor": self.actors[1]}, {"hit_component": None},
                        {"impact_point": self.api.Vector(0, 0, float("nan"))}, {"blocking_hit": "true"}):
            trace.return_value = SimpleNamespace(to_dict=lambda changes=changes: {**hit, **changes})
            result = reader.seam_collision_trace(self.api, self.world, self.actors, target, [0, 0])
            self.assertEqual(result["observed"], not bool(changes))
        trace.side_effect = RuntimeError("collision unavailable")
        result = reader.seam_collision_trace(self.api, self.world, self.actors, target, [0, 0])
        self.assertFalse(result["observed"])
        self.assertIn("collision unavailable", result["error"])


class LandscapeLayerOwnerTests(unittest.TestCase):
    def setUp(self):
        self.owner_type = type("Landscape", (), {})
        self.owner = self.owner_type()
        self.owner.get_path_name = Mock(return_value=reader.LEVEL_PATH + ".World:PersistentLevel.Owner")
        self.owner.get_edit_layers_bp = Mock(return_value=[SimpleNamespace(get_name_bp=lambda: "Procedural Edits")])
        self.owner.get_target_layer_names = Mock(return_value=["visibility"])
        self.proxy = SimpleNamespace(get_landscape_actor=Mock(return_value=self.owner))
        self.api = SimpleNamespace(Landscape=self.owner_type)

    def test_proxy_uses_actual_owning_landscape_layer_apis(self):
        result = reader.actual_landscape_layers(self.api, self.proxy)
        self.assertTrue(result["landscape_owner"]["observed"])
        self.assertEqual(result["edit_layers"]["value"], ["Procedural Edits"])
        self.assertEqual(result["target_layers"]["value"], ["visibility"])
        self.owner.get_target_layer_names.assert_called_once_with(True)
        self.proxy.get_landscape_actor.assert_called_once_with()

    def test_missing_wrong_or_unavailable_owner_is_unknown(self):
        for owner in (None, object()):
            self.proxy.get_landscape_actor.return_value = owner
            result = reader.actual_landscape_layers(self.api, self.proxy)
            self.assertTrue(all(not row["observed"] and row["error"] for row in result.values()))
        self.proxy.get_landscape_actor.side_effect = RuntimeError("owner query unavailable")
        result = reader.actual_landscape_layers(self.api, self.proxy)
        self.assertIn("owner query unavailable", result["edit_layers"]["error"])
        self.proxy.get_landscape_actor.side_effect = None
        self.proxy.get_landscape_actor.return_value = self.owner
        self.owner.get_path_name.return_value = "/Game/Other.World:PersistentLevel.Owner"
        result = reader.actual_landscape_layers(self.api, self.proxy)
        self.assertFalse(result["target_layers"]["observed"])
        self.owner.get_edit_layers_bp.assert_not_called()

    def test_none_names_and_failed_layer_queries_remain_unknown_but_empty_is_observed(self):
        for value in (None, [None], [SimpleNamespace(get_name_bp=lambda: None)]):
            self.owner.get_edit_layers_bp.return_value = value
            result = reader.actual_landscape_layers(self.api, self.proxy)
            self.assertFalse(result["edit_layers"]["observed"])
            self.assertTrue(result["target_layers"]["observed"])
        for value in (None, [None]):
            self.owner.get_target_layer_names.return_value = value
            result = reader.actual_landscape_layers(self.api, self.proxy)
            self.assertFalse(result["target_layers"]["observed"])
        self.owner.get_edit_layers_bp.side_effect = RuntimeError("layer query unavailable")
        self.assertIn("layer query unavailable", reader.actual_landscape_layers(
            self.api, self.proxy)["edit_layers"]["error"])
        self.owner.get_edit_layers_bp.side_effect = None
        self.owner.get_edit_layers_bp.return_value = []
        self.owner.get_target_layer_names.return_value = []
        result = reader.actual_landscape_layers(self.api, self.proxy)
        self.assertTrue(result["edit_layers"]["observed"])
        self.assertEqual(result["edit_layers"]["value"], [])
        self.assertTrue(result["target_layers"]["observed"])


class NativeInspectionReportingTests(unittest.TestCase):
    def setUp(self):
        landscape_type = type("Landscape", (), {})
        proxy_type = type("LandscapeProxy", (), {})
        component_type = type("LandscapeComponent", (), {})
        def vector(x, y, z):
            return SimpleNamespace(x=x, y=y, z=z)
        self.world = SimpleNamespace(get_path_name=lambda: reader.LEVEL_PATH + ".World")
        self.actors = []
        for label in sorted(reader.EXPECTED_ACTORS):
            owner = landscape_type()
            owner.get_path_name = lambda name=label: reader.LEVEL_PATH + ".World:PersistentLevel." + name
            owner.get_edit_layers_bp = lambda: []
            owner.get_target_layer_names = lambda _include_visibility: ["visibility"]
            components = []
            for x in range(32):
                for y in range(32):
                    component = component_type()
                    component.fields = native_layout_reply("fixture")["fields"]
                    component.fields.update(section_base_x=x * 254, section_base_y=y * 254)
                    component.get_path_name = lambda name=f"{label}.Component_{x}_{y}": (
                        reader.LEVEL_PATH + ".World:PersistentLevel." + name)
                    components.append(component)
            actor = proxy_type()
            actor.get_name = lambda name=label: name
            actor.get_actor_label = lambda name=label: name
            actor.get_class = lambda: SimpleNamespace(get_name=lambda: "LandscapeStreamingProxy")
            actor.get_actor_location = lambda: vector(0.0, 0.0, 0.0)
            actor.get_actor_scale3d = lambda: vector(50.0, 50.0, 185.7248)
            actor.get_actor_rotation = lambda: SimpleNamespace(pitch=0.0, yaw=0.0, roll=0.0)
            actor.get_actor_bounds = lambda _collision: (vector(0.0, 0.0, 0.0), vector(203200.0, 203200.0, 23678.0))
            actor.get_components_by_class = lambda _type, values=components: values
            actor.get_editor_property = lambda name: (
                SimpleNamespace(get_path_name=lambda: reader.EXPECTED_MATERIAL + ".MI_Landscape_Instance_YACS")
                if name == "landscape_material" else None)
            actor.get_landscape_actor = lambda value=owner: value
            self.actors.append(actor)
        self.trace = Mock()
        self.seams = Mock(return_value={"height_samples_complete": True, "collision_queries_complete": True,
                                       "fixture": "not native evidence"})
        self.getter = Mock(side_effect=lambda component: json.dumps(
            native_layout_reply(component.get_path_name(), component.fields)))
        self.api = SimpleNamespace(
            Landscape=landscape_type, LandscapeProxy=proxy_type, LandscapeComponent=component_type,
            EditorLoadingAndSavingUtils=SimpleNamespace(load_map=lambda _path: self.world),
            EditorActorSubsystem=object(), get_editor_subsystem=lambda _type: SimpleNamespace(
                get_all_level_actors=lambda: self.actors),
            Vector=vector, TraceTypeQuery=SimpleNamespace(TRACE_TYPE_QUERY1=1),
            DrawDebugTrace=SimpleNamespace(NONE=0), SystemLibrary=SimpleNamespace(line_trace_single=self.trace),
            YacsLandscapeMeshDiagnosticLibrary=SimpleNamespace(read_lesson07_component_layout=self.getter),
        )

    def hit(self, impact=(0.0, 0.0, 1000.0)):
        return SimpleNamespace(to_dict=lambda: {
            "blocking_hit": True, "impact_point": self.api.Vector(*impact),
            "hit_actor": self.actors[0],
            "hit_component": self.actors[0].get_components_by_class(self.api.LandscapeComponent)[0],
        })

    def inspect(self):
        preparation = {"fixture": "no native engine or geometry"}
        dependencies = {"problems": [], "queries_complete": True, "dependency_closure_complete": False}
        with patch.object(reader, "native_dependencies", return_value=dependencies) as query, \
                patch.object(reader, "native_seam_readback", self.seams), patch("builtins.print"):
            report = reader.inspect_map(self.api, preparation)
        query.assert_called_once_with(self.api, preparation)
        self.assertEqual(len(report["landscapes"]), 4)
        self.assertEqual(report["total_components"], 4096)
        self.assertEqual(len(report["sampled_heights"]), 4)
        self.assertTrue(report["native_dependencies"]["observed"])
        self.assertFalse(report["geometry_accepted"])
        self.assertFalse(report["material_render_verified"])
        return report

    def test_structural_observations_complete_without_any_geometry_acceptance(self):
        self.trace.return_value = self.hit()
        report = self.inspect()
        self.assertTrue(report["structural_readback_complete"])
        self.assertTrue(report["native_component_properties_complete"])
        self.assertTrue(all(sample["observed"] and sample["hit"] for sample in report["sampled_heights"]))
        self.assertEqual(self.getter.call_count, 4096)
        self.assertEqual(self.trace.call_count, 4)

    def test_no_hit_and_api_exception_preserve_all_points_structure_and_dependencies(self):
        self.trace.side_effect = [None, self.hit(), RuntimeError("native trace unavailable"), self.hit()]
        report = self.inspect()
        samples = report["sampled_heights"]
        self.assertTrue(samples[0]["observed"])
        self.assertIs(samples[0]["hit"], False)
        self.assertTrue(samples[1]["hit"])
        self.assertFalse(samples[2]["observed"])
        self.assertIsNone(samples[2]["hit"])
        self.assertIn("native trace unavailable", samples[2]["error"])
        self.assertTrue(samples[3]["observed"])
        self.assertFalse(report["structural_readback_complete"])
        self.assertTrue(report["components_pass"])
        self.assertEqual(self.trace.call_count, 4)

    def test_nonfinite_hit_is_unknown_and_cannot_silently_complete_as_json_null(self):
        self.trace.side_effect = [self.hit((float("nan"), 0.0, 1000.0)), self.hit(),
                                  self.hit((0.0, 0.0, float("inf"))), self.hit()]
        report = self.inspect()
        self.assertFalse(report["structural_readback_complete"])
        self.assertTrue(report["components_pass"])
        for index in (0, 2):
            self.assertFalse(report["sampled_heights"][index]["observed"])
            self.assertIn("non-finite", report["sampled_heights"][index]["error"])
        self.assertTrue(any("non-finite" in reason for reason in report["reasons"]))
        json.dumps(reader.finite_json(report), allow_nan=False)

    def test_missing_native_seam_getter_retains_structural_observations_without_pass(self):
        self.trace.return_value = self.hit()
        self.seams.side_effect = RuntimeError("native seam getter unavailable")
        report = self.inspect()
        self.assertFalse(report["structural_readback_complete"])
        self.assertTrue(report["components_pass"])
        self.assertFalse(report["native_seams"]["observed"])
        self.assertIn("native seam getter unavailable", report["native_seams"]["error"])


class NativeQueryBoundaryTests(unittest.TestCase):
    def test_actual_material_parent_is_required_only_when_referenced(self):
        original = "/Game/PegasusDemo/Materials/Landscape/M_Pegasus_Landscape_Master"
        self.assertNotIn(original, reader.REQUIRED_PACKAGES)
        self.assertIn(reader.EXPECTED_MATERIAL, reader.REQUIRED_PACKAGES)
        result = reader.dependency_inventory(
            [reader.EXPECTED_MATERIAL], lambda _name: [original], lambda _name: True,
            {reader.EXPECTED_MATERIAL},
        )
        self.assertFalse(result["queries_complete"])
        self.assertIn(original, result["problems"][0])

    def test_xy_representation_bound_preserves_measurement_and_rejects_actual_scale_drift(self):
        actual = 49.99999701976776
        result = reader.xy_scale_representation([actual, actual, 185.7248])
        self.assertTrue(result["within_one_binary32_input_step"])
        self.assertEqual(result["actual_tile_span_delta_cm"], [(actual - 50) * 8128] * 2)
        self.assertFalse(result["geometry_accepted"])
        for scale in (*reader.XY_SCALE_INTERVAL_CM, 50.0):
            rows = landscape_rows()
            rows[0]["scale"][0] = scale
            self.assertEqual(reader.structure_problems(rows), [])
        lower, upper = reader.XY_SCALE_INTERVAL_CM
        for scale in (math.nextafter(lower, -math.inf), math.nextafter(upper, math.inf),
                      49.9999, 50.0001, -50, float("nan"), float("inf")):
            rows = landscape_rows()
            rows[0]["scale"][1] = scale
            with self.subTest(scale=scale):
                self.assertTrue(reader.structure_problems(rows))

    def test_complete_cyclic_disk_queries_do_not_claim_full_asset_or_geometry_proof(self):
        dependencies = {"/Game/Map": ["/Game/Material", "/Script/Engine"],
                        "/Game/Material": ["/Game/Map", "/Engine/Default"], "/Engine/Default": []}
        result = reader.dependency_inventory(
            ["/Game/Map"], dependencies.__getitem__, lambda _name: True,
            {"/Game/Map", "/Game/Material"},
        )
        self.assertTrue(result["queries_complete"])
        self.assertEqual(len(result["packages"]), 4)
        self.assertFalse(result["dependency_closure_complete"])

    def test_missing_unstaged_dependency_blocks_before_query_or_silent_fallback(self):
        query = Mock(side_effect=lambda name: ["/Game/Missing"] if name == "/Game/Map" else [])
        result = reader.dependency_inventory(["/Game/Map"], query, lambda _name: True, {"/Game/Map"})
        self.assertFalse(result["queries_complete"])
        self.assertIn("not staged", result["problems"][0])
        query.assert_called_once_with("/Game/Map")

    def test_none_exception_and_missing_script_remain_incomplete(self):
        for mode in ("none", "exception", "missing_script", "unknown_exists"):
            def query(_name):
                if mode == "exception":
                    raise RuntimeError("query unavailable")
                return None if mode == "none" else ["/Script/HoudiniEngineRuntime"]

            def exists(name):
                if mode == "unknown_exists":
                    return None
                return not (mode == "missing_script" and name.startswith("/Script/"))

            with self.subTest(mode=mode):
                result = reader.dependency_inventory(["/Game/Map"], query, exists, {"/Game/Map"})
                self.assertFalse(result["queries_complete"])
                self.assertTrue(result["problems"])

    def test_empty_seed_set_and_excessive_native_graph_never_complete(self):
        self.assertFalse(reader.dependency_inventory([], Mock(), Mock(), set())["queries_complete"])
        with patch.object(reader, "MAX_DEPENDENCIES", 2):
            result = reader.dependency_inventory(
                ["/Game/A"], lambda name: {"/Game/A": ["/Game/B"], "/Game/B": ["/Game/C"]}[name],
                lambda _name: True, {"/Game/A", "/Game/B", "/Game/C"},
            )
        self.assertFalse(result["queries_complete"])
        self.assertIn("bound", result["problems"][0])

    def test_truthy_wrong_world_stops_before_actor_queries(self):
        actor_query = Mock(side_effect=AssertionError("must not inspect an unrelated world"))
        api = SimpleNamespace(
            EditorLoadingAndSavingUtils=SimpleNamespace(load_map=lambda _path: SimpleNamespace(
                get_path_name=lambda: "/Game/Other.World")), get_editor_subsystem=actor_query,
        )
        with self.assertRaisesRegex(RuntimeError, "Actual loaded world"):
            reader.inspect_map(api, {})
        actor_query.assert_not_called()

    def test_component_settings_do_not_complete_empty_or_partial_native_observations(self):
        measured = reader.actual_component_settings([])
        self.assertTrue(all(not value["complete"] for value in measured.values()))
        measured = reader.actual_component_settings([
            {"observed": True, "fields": native_layout_reply("fixture")["fields"]},
            {"observed": False, "fields": None, "error": "native read unavailable"},
        ])
        self.assertTrue(all(not value["complete"] and value["read_count"] == 1
                            and value["total"] == 2 for value in measured.values()))

    def test_structural_inventory_checks_individual_actors_grids_and_unknowns(self):
        self.assertEqual(reader.structure_problems(landscape_rows()), [])
        cases = ("empty", "duplicate_actor", "unequal_counts", "duplicate_component", "unknown_property",
                 "wrong_subsection", "unknown_layers", "missing_material", "nan_rotation", "bad_scale")
        for mode in cases:
            rows = landscape_rows()
            if mode == "empty":
                rows = []
            elif mode == "duplicate_actor":
                rows[1]["label"] = rows[0]["label"]
            elif mode == "unequal_counts":
                rows[0]["component_count"] -= 1
                rows[1]["component_count"] += 1  # Total still 4096.
            elif mode == "duplicate_component":
                rows[0]["component_section_bases"][1] = rows[0]["component_section_bases"][0]
            elif mode == "unknown_property":
                rows[0]["actual_component_properties"]["section_base_x"]["complete"] = False
            elif mode == "wrong_subsection":
                rows[0]["actual_component_properties"]["subsection_size_quads"]["values"] = [63]
            elif mode == "unknown_layers":
                rows[0]["edit_layers"]["observed"] = False
            elif mode == "missing_material":
                rows[0]["assigned_material"] = None
            elif mode == "nan_rotation":
                rows[0]["rotation_deg_pitch_yaw_roll"][0] = float("nan")
            else:
                rows[0]["scale"][2] = -1.0
            with self.subTest(mode=mode):
                self.assertTrue(reader.structure_problems(rows))

    def test_nonfinite_native_values_are_serializable_unknowns_with_recorded_failures(self):
        rows = landscape_rows()
        rows[0]["scale"][2] = float("nan")
        value = {"rows": rows, "reasons": reader.structure_problems(rows), "geometry_accepted": False}
        result = json.loads(json.dumps(reader.finite_json(value), allow_nan=False))
        self.assertIsNone(result["rows"][0]["scale"][2])
        self.assertTrue(result["reasons"])
        self.assertFalse(result["geometry_accepted"])


class PreparationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.project = root / "candidate"
        self.proof = root / "proof"
        self.proof.mkdir()
        self.map = self.project / reader.MAP_FILE
        self.map.parent.mkdir(parents=True)
        self.map.write_bytes(b"synthetic tiny saved map fixture")
        identity = reader.file_identity(self.map, 1024)
        original_bytes = b"synthetic original map fixture"
        self.original_pin = {"sha256": hashlib.sha256(original_bytes).hexdigest(),
                             "size_bytes": len(original_bytes)}
        material_pins, assets = {}, []
        for index, relative in enumerate(reader.CURRENT_MATERIAL_PINS):
            path = self.project / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"synthetic current material {index}".encode())
            material = reader.file_identity(path, 1024)
            material_pins[relative] = (material["sha256"], material["size_bytes"])
            assets.append({"relative": relative, "source_identity": material, "copied_identity": material})
        self.pins = patch.multiple(
            reader, MAP_SHA256=identity["sha256"], MAP_SIZE=identity["size_bytes"],
            ORIGINAL_MAP_SHA256=self.original_pin["sha256"], ORIGINAL_MAP_SIZE=self.original_pin["size_bytes"],
            CURRENT_MATERIAL_PINS=material_pins,
        )
        self.pins.start()
        self.addCleanup(self.pins.stop)
        self.manifest = self.proof / "staging.json"
        self.report = self.proof / "l07-native-geometry.json"
        self.value = {
            "schema_version": 1, "status": "L07_COPIED_BYTES_NATIVE_READ_PENDING",
            "source_head": "a" * 40, "candidate_root": str(self.project), "level": reader.LEVEL_PATH,
            "geometry_accepted": False, "dependency_closure_complete": False,
            "map": {"relative": reader.MAP_FILE, "source_identity": identity,
                    "original_identity": self.original_pin},
            "assets": assets,
            "reader_identity": reader.file_identity(reader.__file__, 256 * 1024), "report_path": str(self.report),
        }
        self.env = {"YACS_L07_EXPECTED_HEAD": "a" * 40,
                    "YACS_L07_PREPARATION_FILE": str(self.manifest),
                    "YACS_LESSON07_READBACK_PATH": str(self.report)}
        self.write_manifest()

    def write_manifest(self):
        self.manifest.write_text(json.dumps(self.value), encoding="utf-8")
        self.env["YACS_L07_PREPARATION_SHA256"] = hashlib.sha256(self.manifest.read_bytes()).hexdigest()

    def test_valid_owned_preparation_and_real_small_map_identity(self):
        _value, _identity, measured, output = reader.authenticated_preparation(self.project, self.env)
        self.assertEqual(measured["sha256"], reader.MAP_SHA256)
        self.assertEqual(output, self.report)
        self.assertFalse(output.exists())

    def test_main_normalizes_relative_native_project_then_enforces_candidate_identity(self):
        relative = "../../../YacsLesson07Candidate/"
        convert = Mock(return_value=str(self.project))
        api = SimpleNamespace(
            Paths=SimpleNamespace(project_dir=Mock(return_value=relative),
                                  convert_relative_path_to_full=convert),
            SystemLibrary=SimpleNamespace(get_engine_version=lambda: "5.8.2-56702186-fixture",
                                          execute_console_command=Mock()),
        )
        with patch.dict("sys.modules", {"unreal": api}), patch.dict(reader.os.environ, self.env), \
                patch.object(reader, "inspect_map", return_value={}) as inspect, patch("builtins.print"):
            reader.main()
            convert.assert_called_once_with(relative)
            inspect.assert_called_once_with(api, self.value)
            report = json.loads(self.report.read_text(encoding="utf-8"))
            self.assertEqual(report["project_root"], str(self.project))
            self.assertTrue(report["candidate_map_unchanged"])
            self.assertFalse(report["geometry_accepted"])
            report_bytes = self.report.read_bytes()

            convert.return_value = str(self.project.parent / "unrelated-candidate")
            inspect.reset_mock()
            with self.assertRaisesRegex(ValueError, "does not identify this isolated L07 read"):
                reader.main()
            inspect.assert_not_called()
            self.assertEqual(self.report.read_bytes(), report_bytes)

    def test_wrong_raw_receipt_hash_prevents_json_parse(self):
        self.env["YACS_L07_PREPARATION_SHA256"] = "f" * 64
        with patch.object(reader.json, "loads", side_effect=AssertionError("must not parse")) as parse:
            with self.assertRaisesRegex(ValueError, "Untrusted"):
                reader.authenticated_preparation(self.project, self.env)
        parse.assert_not_called()

    def test_changed_map_and_reader_bytes_are_rejected(self):
        self.map.write_bytes(b"a different saved map fixture")
        with self.assertRaisesRegex(ValueError, "Candidate map"):
            reader.authenticated_preparation(self.project, self.env)
        self.map.write_bytes(b"synthetic tiny saved map fixture")
        self.value["reader_identity"]["sha256"] = "f" * 64
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "reader bytes"):
            reader.authenticated_preparation(self.project, self.env)

    def test_original_map_is_not_admitted_as_current_and_original_lineage_cannot_move(self):
        current = deepcopy(self.value)
        self.map.write_bytes(b"synthetic original map fixture")
        self.value["map"]["source_identity"] = reader.file_identity(self.map, 1024)
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "pinned saved"):
            reader.authenticated_preparation(self.project, self.env)
        self.map.write_bytes(b"synthetic tiny saved map fixture")
        self.value = deepcopy(current)
        self.value["map"]["original_identity"] = self.value["map"]["source_identity"]
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "original identity"):
            reader.authenticated_preparation(self.project, self.env)

    def test_current_material_pins_reject_missing_substituted_and_falsely_inventoried_assets(self):
        original = deepcopy(self.value)
        for relative in reader.CURRENT_MATERIAL_PINS:
            path = self.project / relative
            content = path.read_bytes()
            path.unlink()
            with self.subTest(relative=relative), self.assertRaises(FileNotFoundError):
                reader.authenticated_preparation(self.project, self.env)
            path.write_bytes(b"changed material")
            with self.assertRaisesRegex(ValueError, "Candidate current material"):
                reader.authenticated_preparation(self.project, self.env)
            path.write_bytes(content)
            self.value["assets"] = [row for row in self.value["assets"] if row["relative"] != relative]
            self.write_manifest()
            with self.assertRaisesRegex(ValueError, "Staged current material"):
                reader.authenticated_preparation(self.project, self.env)
            self.value = deepcopy(original)
            self.write_manifest()

    def test_unrelated_project_changed_pin_and_scope_promotion_are_rejected(self):
        original = deepcopy(self.value)
        for key, bad in (("source_head", "b" * 40), ("candidate_root", str(self.project / "other")),
                         ("geometry_accepted", True), ("dependency_closure_complete", True),
                         ("level", "/Game/Other")):
            self.value = {**deepcopy(original), key: bad}
            self.write_manifest()
            with self.subTest(key=key), self.assertRaises(ValueError):
                reader.authenticated_preparation(self.project, self.env)
        self.value = deepcopy(original)
        self.value["map"]["source_identity"]["sha256"] = "b" * 64
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "pinned saved"):
            reader.authenticated_preparation(self.project, self.env)

    def test_report_cannot_overwrite_or_escape_its_owned_evidence_directory(self):
        self.report.write_bytes(b"retain existing evidence")
        with self.assertRaisesRegex(ValueError, "owned evidence"):
            reader.authenticated_preparation(self.project, self.env)
        self.assertEqual(self.report.read_bytes(), b"retain existing evidence")
        self.env["YACS_LESSON07_READBACK_PATH"] = str(self.proof.parent / "unowned.json")
        self.value["report_path"] = self.env["YACS_LESSON07_READBACK_PATH"]
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "owned evidence"):
            reader.authenticated_preparation(self.project, self.env)

    def test_linked_ancestor_and_traversal_are_rejected(self):
        with self.assertRaises(ValueError):
            reader.plain_path(self.project / ".." / "outside")
        link = self.proof.parent / "linked"
        try:
            link.symlink_to(self.proof, target_is_directory=True)
        except OSError as exc:
            self.skipTest(str(exc))
        with self.assertRaisesRegex(ValueError, "linked/reparse"):
            reader.plain_path(link / "new.json")


class InteriorPlanBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.manifest_path = self.directory / "manifest.json"
        self.manifest_path.write_text(json.dumps({
            "accepted_l06_sha256": reader.SOURCE_CACHE_SHA256}), encoding="utf-8")
        self.manifest_hash = reader.file_identity(self.manifest_path, 1024)["sha256"]
        pin = patch.object(reader, "SOURCE_MANIFEST_SHA256", self.manifest_hash)
        pin.start()
        self.addCleanup(pin.stop)
        self.path = self.directory / "interior.json"
        self.preparation = {"source_head": "a"*40}
        name = "SaCalobra_Unified_0_0"
        self.plan = {
            "schema_version": 1, "status": "SOURCE_SELECTED_INTERIOR_NATIVE_READ_PENDING",
            "source_head": self.preparation["source_head"], "level": reader.LEVEL_PATH,
            "accepted_l06_sha256": reader.SOURCE_CACHE_SHA256,
            "manifest": {"path": str(self.manifest_path), "sha256": self.manifest_hash},
            "original_source_center_bounds_m": [-3999.75, 3999.75], "buffer_vertices": 3,
            "geometry_accepted": False, "source_triangle_interpolation_proved": False,
            "visibility_layer_proved_in_ue": False,
            "actor_registration": {actor: {"location_cm": [0, 0, 0],
                "rotation_deg_pitch_yaw_roll": [0, -90, 0], "scale": [50, 50, 185]}
                for actor in reader.EXPECTED_ACTORS},
            "probes": [{
                "id": "fixture", "actor": name, "source_validity": 1,
                "component_path": reader.LEVEL_PATH + ".World:PersistentLevel." + name + ".Component0",
                "component_section_base": [0, 0],
                "local_vertex_indices": [127*255+127, 127*255+128, 128*255+127, 128*255+128],
                "uniform_source_patch_samples": 64,
                "source_corners": [{"source_validity": 1, "source_voxel_index": [127+x, 127+y, 0],
                    "source_voxel_center_houdini_m": [x*.5, 0, y*.5], "source_vertex_height_m": 1.0}
                    for x, y in ((0, 0), (1, 0), (0, 1), (1, 1))],
            }],
        }
        self.write_plan()

    def write_plan(self):
        self.path.write_text(json.dumps(self.plan), encoding="utf-8")
        self.preparation["interior_plan"] = reader.file_identity(self.path, 1024**2)

    def test_plan_bytes_and_physical_source_manifest_are_authenticated(self):
        self.assertEqual(reader.authenticated_interior_plan(self.preparation), self.plan)
        self.path.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Untrusted repair"):
            reader.authenticated_interior_plan(self.preparation)
        self.write_plan()
        self.manifest_path.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Untrusted repair"):
            reader.authenticated_interior_plan(self.preparation)

    def test_changed_task_source_promotion_or_unbuffered_quad_is_rejected(self):
        original = deepcopy(self.plan)
        for field, value in (("source_head", "b"*40), ("accepted_l06_sha256", "f"*64),
                             ("buffer_vertices", 0), ("geometry_accepted", True)):
            self.plan = {**deepcopy(original), field: value}
            self.write_plan()
            with self.subTest(field=field), self.assertRaises(ValueError):
                reader.authenticated_interior_plan(self.preparation)
        for indices in ([0, 1, 255, 256], [127*255+127]*4):
            self.plan = deepcopy(original)
            self.plan["probes"][0]["local_vertex_indices"] = indices
            self.write_plan()
            with self.assertRaisesRegex(ValueError, "buffered quad"):
                reader.authenticated_interior_plan(self.preparation)

    def test_padding_mixed_class_and_out_of_grid_indices_cannot_claim_interior(self):
        original = deepcopy(self.plan)
        for field, value in (("source_validity", 0),
                             ("source_voxel_center_houdini_m", [4000, 0, 0]),
                             ("source_voxel_index", [8129, 0, 0]),
                             ("source_voxel_index", [0, 0, 1])):
            self.plan = deepcopy(original)
            self.plan["probes"][0]["source_corners"][0][field] = value
            self.write_plan()
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                reader.authenticated_interior_plan(self.preparation)


class InteriorReadbackTests(unittest.TestCase):
    def setUp(self):
        self.name = "SaCalobra_Unified_0_0"
        self.path = reader.LEVEL_PATH + ".World:PersistentLevel." + self.name + ".Component0"
        self.indices = [127*255+127, 127*255+128, 128*255+127, 128*255+128]
        self.actor = SimpleNamespace(
            get_name=lambda: self.name, get_actor_location=lambda: SimpleNamespace(x=0, y=0, z=0),
            get_actor_rotation=lambda: SimpleNamespace(pitch=0, yaw=-90, roll=0),
            get_actor_scale3d=lambda: SimpleNamespace(x=50, y=50, z=561),
        )
        self.component = SimpleNamespace(get_path_name=lambda: self.path)
        self.collision = SimpleNamespace(
            get_owner=lambda: self.actor, get_render_component=lambda: self.component,
            get_path_name=lambda: self.path + "Collision")
        self.hit = {"blocking_hit": True, "hit_actor": self.actor, "hit_component": self.collision,
                    "impact_point": SimpleNamespace(x=25, y=25, z=100)}
        self.reply = {"schema_version": 1, "observed": True, "component_path": self.path,
                      "world_package": reader.LEVEL_PATH, "actor_name": self.name,
                      "vertex_indices": self.indices, "visibility_observed": True,
                      "visibility_status": "ALLOCATED_READ",
                      "samples": [[32868, 0, 0, 100, 0], [32868, 50, 0, 100, 0],
                                  [32868, 0, 50, 100, 0], [32868, 50, 50, 100, 0]]}
        self.api = SimpleNamespace(
            Vector=lambda x, y, z: SimpleNamespace(x=x, y=y, z=z),
            TraceTypeQuery=SimpleNamespace(TRACE_TYPE_QUERY1=1), DrawDebugTrace=SimpleNamespace(NONE=0),
            SystemLibrary=SimpleNamespace(line_trace_single=lambda *_args: SimpleNamespace(to_dict=lambda: self.hit)),
            YacsLandscapeMeshDiagnosticLibrary=SimpleNamespace(
                read_lesson07_component_samples=lambda *_args: json.dumps(self.reply)))
        self.plan = {
            "tiles": [{"actor": self.name, "selected_by_validity": {"0": 0, "1": 1}}],
            "actor_registration": {self.name: {"location_cm": [0, 0, 0],
                "rotation_deg_pitch_yaw_roll": [0, -90, 0], "scale": [50, 50, 185]}},
            "probes": [{"id": "fixture", "actor": self.name, "component_path": self.path,
                        "component_section_base": [0, 0], "local_vertex_indices": self.indices}],
        }
        self.tiles = {self.name: (self.actor, [self.component], [
            {"observed": True, "fields": {"section_base_x": 0, "section_base_y": 0}}])}
        self.preparation = {"interior_plan": {"path": "fixture", "sha256": "a"*64}}

    def read(self):
        with patch.object(reader, "authenticated_interior_plan", return_value=self.plan):
            return reader.native_interior_readback(
                self.api, object(), [self.actor], self.tiles, self.preparation)

    def test_reads_four_actual_corners_and_center_with_matching_collision_render_component(self):
        value = self.read()
        self.assertTrue(value["samples_complete"])
        row = value["probes"][0]
        self.assertEqual(row["native_corners"]["vertex_indices"], self.indices)
        self.assertEqual(row["center_collision"]["query_xy_cm"], [25, 25])
        self.assertEqual(row["center_collision"]["hit_render_component"], self.path)
        self.assertFalse(value["geometry_accepted"])
        self.assertFalse(value["visibility_layer_proved_in_ue"])
        self.hit = {"blocking_hit": False}
        self.assertTrue(self.read()["samples_complete"])
        self.assertFalse(self.read()["probes"][0]["center_collision"]["hit"])

    def test_wrong_collider_or_changed_grid_registration_is_unknown_not_success(self):
        self.collision.get_render_component = lambda: object()
        value = self.read()
        self.assertFalse(value["samples_complete"])
        self.assertIn("another Landscape render component", value["probes"][0]["error"])
        self.collision.get_render_component = lambda: self.component
        self.plan["actor_registration"][self.name]["location_cm"] = [1, 0, 0]
        value = self.read()
        self.assertFalse(value["samples_complete"])
        self.assertIn("registration changed", value["probes"][0]["error"])

    def test_native_center_uses_fsum_for_real_world_coordinates(self):
        # Actual final-readback values differed by one ULP between the embedded
        # Python summation algorithms. Keep exact coordinates, not a tolerance.
        values = [-6375.0223969160015, -6375.022396465635, -6325.022399295749, -6325.022399445867]
        for sample, value in zip(self.reply["samples"], values):
            sample[1] = value
        expected = math.fsum(values)/4
        sequential = ((values[0]+values[1])+values[2]+values[3])/4
        self.assertNotEqual(expected, sequential)
        value = self.read()
        self.assertTrue(value["samples_complete"])
        self.assertEqual(value["probes"][0]["center_collision"]["query_xy_cm"], [expected, 25.0])


class RepairedPreparationBoundaryTests(unittest.TestCase):
    write_manifest = PreparationBoundaryTests.write_manifest

    def setUp(self):
        PreparationBoundaryTests.setUp(self)
        self.map.write_bytes(b"synthetic original map fixture")
        self.original = reader.file_identity(self.map, 1024)
        backup = self.proof / "original-map-backup.umap"
        backup.write_bytes(self.map.read_bytes())
        self.material_relative = "Content/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS.uasset"
        material = self.project / self.material_relative
        material.parent.mkdir(parents=True, exist_ok=True)
        material.write_bytes(b"same authenticated material")
        material_hash = reader.file_identity(material, 1024)["sha256"]
        before = {reader.MAP_FILE: self.original["sha256"], self.material_relative: material_hash}
        self.map.write_bytes(b"saved repaired map; original remains in backup")
        current = reader.file_identity(self.map, 1024)
        after = {**before, reader.MAP_FILE: current["sha256"]}
        heights = {"schema_version": 1, "success": True, "errors": [],
                   "world_package": reader.LEVEL_PATH, "hash_algorithm": "BLAKE3-256",
                   "actor_count": 4, "component_count": 4096,
                   "component_bindings": [{} for _ in range(4096)], "textures": [{"fixture": True}]}
        self.receipt = {
            "status": "MAP_CACHES_REFRESHED_REOPEN_PENDING", "mode": "REFRESH_MAP",
            "project": str(self.project), "geometry_accepted": False, "fresh_reopen_verified": False,
            "files": before, "files_after": after, "changed_files": [reader.MAP_FILE],
            "protected_files_unchanged": True, "map_saved_after_cache_refresh": True,
            "whole_heightmaps_unchanged": True, "heightmaps_before": heights,
            "heightmaps_after": deepcopy(heights), "map_backup": str(backup),
            "grass_refresh": {"success": True, "errors": [], "world_package": reader.LEVEL_PATH,
                              "actor_count": 4, "component_count": 4096,
                              "updated_component_count": 4096, "grass_type_reference_count_after": 0},
        }
        self.receipt_path = self.proof / "refresh.json"
        self.value["status"] = reader.REPAIRED_PREPARATION_STATUS
        self.value["map"].update(original_identity=self.original, source_identity=current)
        self.value["assets"] = [{"relative": p, "copied_identity": {"sha256": digest}}
                                for p, digest in after.items()]
        self.write_receipt()

    def write_receipt(self):
        self.receipt_path.write_text(json.dumps(self.receipt), encoding="utf-8")
        self.value["map"]["repair_receipts"] = [
            reader.file_identity(self.receipt_path, reader.REPAIR_RECEIPT_LIMIT)]
        self.write_manifest()

    def read(self):
        return reader.authenticated_preparation(self.project, self.env)

    def test_saved_refresh_chain_preserves_original_pin_and_current_asset_identity(self):
        preparation, _identity, observed, _output = self.read()
        self.assertEqual(preparation["map"]["original_identity"], self.original)
        self.assertEqual(observed, self.value["map"]["source_identity"])
        self.assertNotEqual(observed["sha256"], reader.MAP_SHA256)
        self.assertFalse(preparation["geometry_accepted"])
        self.assertFalse(preparation["dependency_closure_complete"])

    def test_plain_mode_or_unauthenticated_repair_cannot_override_original_pin(self):
        original = deepcopy(self.value)
        self.value["status"] = "L07_COPIED_BYTES_NATIVE_READ_PENDING"
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "pinned saved"):
            self.read()
        self.value = original
        self.value["map"]["repair_receipts"][0]["sha256"] = "f" * 64
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "Untrusted repair"):
            self.read()

    def test_failed_unsaved_incomplete_or_protected_change_receipts_are_rejected(self):
        original = deepcopy(self.receipt)
        cases = [
            ("status", "FAILED"), ("status", "CANARY_COMPLETED_UNSAVED"),
            ("mode", "APPLY"), ("map_saved_after_cache_refresh", False),
            ("whole_heightmaps_unchanged", False), ("protected_files_unchanged", False),
            ("geometry_accepted", True), ("fresh_reopen_verified", True),
            ("changed_files", []),
        ]
        for name, bad in cases:
            self.receipt = {**deepcopy(original), name: bad}
            self.write_receipt()
            with self.subTest(name=name, bad=bad), self.assertRaises(ValueError):
                self.read()
        self.receipt = deepcopy(original)
        self.receipt["files_after"][self.material_relative] = "b" * 64
        self.receipt["changed_files"].append(self.material_relative)
        self.write_receipt()
        with self.assertRaisesRegex(ValueError, "protected assets"):
            self.read()
        self.receipt = deepcopy(original)
        self.receipt["heightmaps_after"]["textures"] = [{"changed": True}]
        self.write_receipt()
        with self.assertRaisesRegex(ValueError, "heightmaps"):
            self.read()

    def test_wrong_backup_lineage_and_current_bytes_are_rejected(self):
        Path(self.receipt["map_backup"]).write_bytes(b"substituted original")
        with self.assertRaisesRegex(ValueError, "backup"):
            self.read()
        Path(self.receipt["map_backup"]).write_bytes(b"synthetic original map fixture")
        self.map.write_bytes(b"different current candidate")
        with self.assertRaisesRegex(ValueError, "Candidate map"):
            self.read()

    def test_changed_current_material_or_substituted_staging_inventory_is_rejected(self):
        material = self.project / self.material_relative
        material.write_bytes(b"unauthenticated later change")
        with self.assertRaisesRegex(ValueError, "Candidate asset"):
            self.read()
        self.value["assets"][1]["copied_identity"]["sha256"] = hashlib.sha256(material.read_bytes()).hexdigest()
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "Staged assets"):
            self.read()

    def test_duplicate_receipts_and_broken_hash_chain_are_rejected(self):
        self.value["map"]["repair_receipts"] *= 2
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "Duplicate repair"):
            self.read()
        self.receipt["files"][reader.MAP_FILE] = "b" * 64
        self.write_receipt()
        with self.assertRaisesRegex(ValueError, "broke map lineage"):
            self.read()

    def test_traversal_aliases_and_missing_map_inventory_fail_closed(self):
        for inventory in (
            {reader.MAP_FILE: "a" * 64, "../outside.uasset": "b" * 64},
            {reader.MAP_FILE: "a" * 64, reader.MAP_FILE.replace("/", "\\"): "a" * 64},
            {self.material_relative: "b" * 64},
        ):
            with self.subTest(inventory=inventory), self.assertRaises(ValueError):
                reader.repair_inventory(inventory)

    def consumer_receipt(self, mode="visibility-only"):
        selected = sorted(reader.EXPECTED_ACTORS)
        actors = {}
        for index, name in enumerate(selected):
            path = reader.LEVEL_PATH + ".World:PersistentLevel." + name
            actors[name] = {
                "path": path, "landscape_guid": name + "-guid",
                "location_cm": [index * 10.0, 0.0, 0.0],
                "rotation_deg_pitch_yaw_roll": [0.0, -90.0, 0.000001961],
                "scale": [49.999997, 49.999997, 200.0 + index * 100],
                "edit_layer": "Houdini_Unified_Final", "edit_layer_guid": name + "-layer-guid",
                "component_paths": [path + f".Component_{n}" for n in range(1024)],
                "material": reader.EXPECTED_MATERIAL, "hole_material": None,
            }
        common = max(a["scale"][2] for a in actors.values()) if mode == "height-and-visibility" else None
        transport = {
            "schema_version": 1, "status": "DERIVED_TRANSPORT_READY_NATIVE_UPDATE_NOT_RUN",
            "source_head": self.value["source_head"], "mode": mode, "selected_actors": selected,
            "source_map": reader.LEVEL_PATH, "source_map_identity": self.original,
            "geometry_accepted": False, "required_common_scale_z": common,
        }
        transport_file = self.proof / "transport.json"
        transport_file.write_text(json.dumps(transport), encoding="utf-8")
        result = {
            **deepcopy(self.receipt), "schema_version": 1, "mode": mode,
            "status": "UPDATED_EXISTING_MAP_REOPEN_PENDING", "map_saved": True,
            "source_head": self.value["source_head"], "source_comparison_proved": False,
            "visibility_source_proved": False, "source_map_identity": self.original,
            "map_before": self.original, "map_after": self.value["map"]["source_identity"],
            "selected_actors": selected, "completed_actors": selected,
            "transport_manifest": reader.file_identity(transport_file, 65536),
            "actors_before": actors, "actors_after": deepcopy(actors),
            "required_common_scale_z": common,
            "native_outputs": [{
                "actor": name, "target_layer": layer, "extents": [0, 0, 8128, 8128],
                "created_landscape": False, "layer_was_created": False, "clear_layer": False,
                "cooked_edit_layer": "Houdini_Unified_Final", "cooked_layer_requires_baking": False,
            } for name in selected for layer in (
                ["height", "visibility"] if mode == "height-and-visibility" else ["visibility"])],
        }
        for key in ("heightmaps_before", "heightmaps_after"):
            result[key]["height_source_scope"] = "composite_and_existing_edit_layer_all_mips"
        if common is not None:
            for actor in result["actors_after"].values():
                actor["scale"][2] = common
            result["heightmaps_after"]["textures"] = [{"new_quantization": True}]
            result["whole_heightmaps_unchanged"] = False
        return result

    def validate_consumer(self, value):
        reader.validate_consumer_repair(
            value, self.original["sha256"], self.value["map"]["source_identity"]["sha256"],
            self.value["source_head"])

    def test_saved_consumer_modes_only_admit_their_exact_transform_and_height_changes(self):
        for mode in ("visibility-only", "height-and-visibility"):
            value = self.consumer_receipt(mode)
            self.validate_consumer(value)
            name = sorted(reader.EXPECTED_ACTORS)[0]
            for field, altered in (("landscape_guid", "different"), ("edit_layer_guid", "new-layer"),
                                   ("location_cm", [1, 2, 3]), ("component_paths", ["replaced"])):
                bad = deepcopy(value)
                bad["actors_after"][name][field] = altered
                with self.subTest(mode=mode, field=field), self.assertRaisesRegex(ValueError, "unapproved"):
                    self.validate_consumer(bad)
            bad = deepcopy(value)
            bad["native_outputs"][0]["clear_layer"] = True
            with self.assertRaisesRegex(ValueError, "target contract"):
                self.validate_consumer(bad)
        value = self.consumer_receipt()
        value["heightmaps_after"]["textures"] = [{"changed": True}]
        with self.assertRaisesRegex(ValueError, "changed native heightmaps"):
            self.validate_consumer(value)

    def test_consumer_requires_authenticated_transport_complete_actors_and_existing_layer_reads(self):
        original = self.consumer_receipt("height-and-visibility")
        for key, bad in (("completed_actors", []), ("selected_actors", ["SaCalobra_Unified_0_0"]),
                         ("map_saved", False), ("source_head", "b" * 40),
                         ("required_common_scale_z", 999.0)):
            value = {**deepcopy(original), key: bad}
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate_consumer(value)
        value = deepcopy(original)
        value["transport_manifest"]["sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "Untrusted"):
            self.validate_consumer(value)
        value = deepcopy(original)
        del value["heightmaps_after"]["height_source_scope"]
        with self.assertRaisesRegex(ValueError, "complete native"):
            self.validate_consumer(value)


class WorkflowBoundaryTests(unittest.TestCase):
    def test_launcher_and_reader_pins_agree_without_repointing_original_lineage(self):
        value = WRAPPER.read_text(encoding="utf-8")
        for name, expected in (("MapPin", (reader.MAP_SHA256, reader.MAP_SIZE)),
                               ("OriginalMapPin", (reader.ORIGINAL_MAP_SHA256, reader.ORIGINAL_MAP_SIZE))):
            match = re.search(r"\$" + name + r" = @\{ sha256 = '([a-f0-9]{64})'; size_bytes = \[long\](\d+) \}", value)
            self.assertIsNotNone(match)
            self.assertEqual((match[1], int(match[2])), expected)
        self.assertNotEqual(reader.MAP_SHA256, reader.ORIGINAL_MAP_SHA256)
        block = value.split("$MaterialPins = @{", 1)[1].split("\n$LevelPackage", 1)[0]
        material_pins = {relative: (sha, int(size)) for relative, sha, size in re.findall(
            r"'(Content/[^']+)' = @\{\s+sha256 = '([a-f0-9]{64})'; size_bytes = \[long\](\d+)", block)}
        self.assertEqual(material_pins, reader.CURRENT_MATERIAL_PINS)

        # Agreement between two stale constants must not admit an obsolete MI.
        # The verified nine-package retention supersedes the old Flatten-only MI;
        # the historical recovery receipt still anchors the unchanged map lineage.
        checkpoint = json.loads((ROOT / "docs/assets/lesson07-surface-repair-20261021/retention-39643271947-server-lfs-readback.json").read_text(encoding="utf-8"))
        self.assertEqual(checkpoint["status"], "REMOTE_LFS_BYTES_VERIFIED_BRANCH_NOT_UPDATED")
        self.assertIs(checkpoint["storage_started_empty"], True)
        saved_mi = [row for row in checkpoint["assets"] if row["path"].endswith("/MI_Landscape_Instance_YACS.uasset")]
        self.assertEqual(len(saved_mi), 1)
        self.assertEqual(
            reader.CURRENT_MATERIAL_PINS[saved_mi[0]["path"]],
            (saved_mi[0]["sha256"], saved_mi[0]["size_bytes"]),
        )
        historical = json.loads((ROOT / "docs/assets/lesson07-recovery-20261020/receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(reader.MAP_SHA256, historical["map_sha256"])
        self.assertNotEqual(saved_mi[0]["sha256"], historical["saved_sha256"])

    @unittest.skipUnless(shutil.which("git"), "Git required to inspect committed asset pointers")
    def test_current_pins_match_committed_asset_pointers_without_lfs_payloads(self):
        if not (ROOT / ".git").exists():
            self.skipTest("Repository HEAD is unavailable in a source archive")
        # Read Git objects, not the sparse or LFS-materialized working tree.
        # Do not allow a partial clone to fetch implicitly during a CPU test.
        env = {**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0",
               "GIT_OPTIONAL_LOCKS": "0"}
        pins = {reader.MAP_FILE: (reader.MAP_SHA256, reader.MAP_SIZE),
                **reader.CURRENT_MATERIAL_PINS}
        for relative, expected in pins.items():
            with self.subTest(relative=relative):
                result = subprocess.run(
                    ["git", "-c", "protocol.allow=never", "cat-file", "blob", "HEAD:" + relative],
                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                match = re.fullmatch(
                    r"version https://git-lfs.github.com/spec/v1\noid sha256:([a-f0-9]{64})\nsize (\d+)\n?",
                    result.stdout,
                )
                self.assertIsNotNone(match, "Expected a committed LFS pointer: " + relative)
                self.assertEqual((match[1], int(match[2])), expected)

    def test_l07_paths_include_cache_gate_and_copied_assets_without_other_worlds(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        push = workflow.split("  push:\n", 1)[1].split("\npermissions:", 1)[0]
        path_lines = push.split("    paths:\n", 1)[1].strip("\n").splitlines()
        paths = []
        for line in path_lines:
            match = re.fullmatch(r"      - ([A-Za-z0-9_./-]+(?:/\*\*)?)", line)
            self.assertIsNotNone(match, "Only literal paths and trailing /** are admitted")
            paths.append(match.group(1))

        # For this restricted syntax, fnmatchcase has the same path behavior as
        # Actions. Exercise real changed-file routes, including nested assets.
        routes = {
            ".github/workflows/yacs-lesson07-unreal-readonly.yml": True,
            "scripts/ue/Invoke-YacsLesson07Readback.ps1": True,
            "scripts/ue/readback_lesson07_geometry.py": True,
            "scripts/ue/test_lesson07_readback.py": True,
            "scripts/ci/classify_changes.py": True,
            "scripts/ci/materialize_unreal_cache_inputs.py": True,
            "scripts/ci/test_materialize_unreal_cache_inputs.py": True,
            "Content/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap": True,
            "Content/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape.uasset": True,
            "Content/PegasusDemo/Materials/M_Landscape.uasset": True,
            "Content/PegasusDemo/Materials/Functions/MF_Landscape.uasset": True,
            "Content/Generated/YACS/Lesson06/L_SaCalobra.umap": False,
            "Content/Generated/YACS/OtherWorld/L_World.umap": False,
            "Content/Generated/YACS/Lesson07_Unified_Other/L_World.umap": False,
            "Content/PegasusDemo/OtherAssets/T_Texture.uasset": False,
            "Content/PegasusDemo/Materials_Other/M_Landscape.uasset": False,
            "Content/OtherWorld/Materials/M_Landscape.uasset": False,
            "scripts/houdini/setup_lesson07_unified_houdini.py": False,
            "scripts/ue/bake_lesson07_landscape.py": False,
            "scripts/ci/unrelated.py": False,
            "Source/YetAnotherCyclingSim/Unrelated.cpp": False,
            "docs/tooling/sidefx/LESSON07_MATERIAL_SETUP.md": False,
        }
        for path, expected in routes.items():
            with self.subTest(path=path):
                self.assertEqual(any(fnmatchcase(path, pattern) for pattern in paths), expected)

    @unittest.skipUnless(shutil.which("git") and shutil.which("pwsh"), "Git and PowerShell 7 required for actual checkout fixture")
    def test_owned_workflow_git_config_preserves_blob_bytes_after_crlf_baseline(self):
        value = WORKFLOW.read_text(encoding="utf-8")
        step = value.split("      - name: Isolate Git configuration for the new code checkout\n", 1)[1]
        body = dedent(step.split("        run: |\n", 1)[1].split("\n      - name:", 1)[0])
        body = body.replace("${{ github.run_id }}", "fixture").replace("${{ github.run_attempt }}", "1")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            template = root / "empty-template"
            template.mkdir()
            private_global = root / "private-global.gitconfig"
            original_config = b"[core]\n\tautocrlf = false\n\teol = crlf\n"
            private_global.write_bytes(original_config)
            env = {key: item for key, item in os.environ.items() if not key.upper().startswith("GIT_")}
            env.update(GIT_CONFIG_GLOBAL=str(private_global), GIT_CONFIG_NOSYSTEM="1",
                       GIT_ATTR_NOSYSTEM="1", GIT_TEMPLATE_DIR=str(template),
                       RUNNER_TEMP=str(root), GITHUB_ENV=str(root / "github-env"))

            def git(*args):
                return subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True,
                                      check=True, timeout=15).stdout

            relative = "scripts/ue/Invoke-YacsLesson07Readback.ps1"
            target = repo / relative
            target.parent.mkdir(parents=True)
            expected = WRAPPER.read_bytes().replace(b"\r\n", b"\n")
            target.write_bytes(expected)
            (repo / ".gitattributes").write_bytes(b"* text=auto\n")
            git("init", "--quiet")
            git("add", "--", ".gitattributes", relative)
            blob = git("show", ":" + relative)
            self.assertEqual(blob, expected)
            target.unlink()
            git("checkout-index", "--force", "--", relative)
            self.assertEqual(target.read_bytes(), blob.replace(b"\n", b"\r\n"))
            self.assertNotEqual(hashlib.sha256(target.read_bytes()).digest(), hashlib.sha256(blob).digest())

            script = root / "workflow-config.ps1"
            script.write_text(body, encoding="utf-8")
            subprocess.run(["pwsh", "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script)],
                           cwd=repo, env=env, capture_output=True, check=True, timeout=30)
            exported = dict(line.split("=", 1) for line in (root / "github-env").read_text(encoding="utf-8-sig").splitlines())
            self.assertEqual(exported, {"GIT_CONFIG_GLOBAL": str(root / "l07-fixture-1.gitconfig"),
                                        "GIT_CONFIG_NOSYSTEM": "1"})
            env.update(exported)
            self.assertEqual(git("config", "--global", "--get", "core.autocrlf").strip(), b"false")
            self.assertEqual(git("config", "--global", "--get", "core.eol").strip(), b"lf")
            target.unlink()
            git("checkout-index", "--force", "--", relative)
            self.assertEqual(target.read_bytes(), blob)
            self.assertEqual(hashlib.sha256(target.read_bytes()).digest(), hashlib.sha256(blob).digest())
            self.assertEqual(private_global.read_bytes(), original_config)

    @unittest.skipUnless(shutil.which("jq"), "jq unavailable for actual workflow selector execution")
    def test_actual_ci_selector_ignores_other_contexts_and_never_uses_older_green_run(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        selector = re.search(r"row=\$\(jq .*?'\n(.*?)\n\s*' <<<", workflow, re.S).group(1)
        base = {"id": 1, "name": "CyclingSim CI", "path": ".github/workflows/ci.yml", "head_sha": "a" * 40,
                "head_branch": "codex/365-world-graph", "head_repository": {"full_name": "owner/repo"},
                "created_at": "2026-10-20T12:00:00Z", "run_attempt": 1, "status": "completed", "conclusion": "success"}

        def select(runs):
            result = subprocess.run(
                ["jq", "-r", "--arg", "sha", "a" * 40, "--arg", "repo", "owner/repo", selector],
                input=json.dumps({"workflow_runs": runs}), text=True, capture_output=True, check=True, timeout=10,
            )
            return result.stdout.strip()

        for key, wrong in (("head_sha", "b" * 40), ("head_branch", "main"),
                           ("head_repository", {"full_name": "fork/repo"}), ("path", ".github/workflows/other.yml")):
            with self.subTest(key=key):
                self.assertEqual(select([{**base, key: wrong}]), "")
        pending = {**base, "id": 2, "created_at": "2026-10-20T12:01:00Z", "status": "in_progress", "conclusion": None}
        self.assertEqual(select([base, pending]), "2|in_progress|pending")
        self.assertEqual(select([base, {**pending, "status": "completed", "conclusion": "failure"}]), "2|completed|failure")
        older_rerun = {**base, "run_attempt": 2, "status": "in_progress", "conclusion": None}
        newer_green = {**pending, "status": "completed", "conclusion": "success"}
        self.assertEqual(select([older_rerun, newer_green]), "1|in_progress|pending")

    def test_host_job_is_serialized_after_ci_and_checks_powershell_before_native_launch(self):
        value = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("runs-on: ubuntu-latest", value[:value.index("  ue-readback:")])
        host_job = value[value.index("  ue-readback:"):]
        self.assertIn("needs: await_ci", host_job)
        self.assertIn("group: yacs-unreal-ci-${{ github.repository }}", host_job)
        self.assertLess(host_job.index("Language.Parser]::ParseFile"), host_job.index("-ProtectedCiRunId"))
        self.assertIn("-m unittest scripts.ue.test_lesson07_readback", host_job)


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 unavailable; Windows workflow executes these actual gates")
class PowerShellBoundaryTests(unittest.TestCase):
    def test_actual_hash_copy_cache_module_bounds_and_matching_error_log(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "contracts.ps1"
            script.write_text(r'''
param([string] $Wrapper, [string] $Fixture)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$MapRelative = 'Content/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap'
$LevelPackage = '/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Wrapper, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors.Message -join '; ') }
& {
    $project = 'fixture.uproject'; $reader = 'fixture.py'; $log = 'fixture.log'
    $launch = @($ast.FindAll({ param($node)
        $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and
        $node.Left -is [System.Management.Automation.Language.VariableExpressionAst] -and
        $node.Left.VariablePath.UserPath -ceq 'editorArguments'
    }, $true))
    if ($launch.Count -ne 1) { throw 'Missing unique production editor arguments.' }
    . ([scriptblock]::Create($launch[0].Extent.Text))
    if ($editorArguments -contains '-NoShaderCompile' -or $editorArguments -notcontains '-NullRHI') {
        throw 'Read-only startup must retain NullRHI without removing shader statistics.'
    }
}
foreach ($name in @('Assert-L07PlainPath', 'Get-L07Identity', 'Assert-L07Identity', 'Assert-L07Pin', 'Protect-L07Identity', 'Read-L07Json',
    'Copy-L07Exclusive', 'Copy-L07InventoriedAsset', 'Assert-L07Materialized', 'Get-L07AssetInventory', 'Assert-L07CacheProvenance',
    'Get-L07ModuleClosure', 'Get-L07LogFindings', 'Assert-L07NativeReport')) {
    $nodes = @($ast.FindAll({ param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name
    }, $true))
    if ($nodes.Count -ne 1) { throw ('Missing unique production function: ' + $name) }
    . ([scriptblock]::Create($nodes[0].Extent.Text))
}
function Must-Reject([scriptblock] $Action, [string] $Label) {
    $rejected = $false
    try { & $Action | Out-Null } catch { $rejected = $true }
    if (-not $rejected) { throw ('Production gate admitted ' + $Label) }
}
$source = Join-Path $Fixture 'source.bin'
[IO.File]::WriteAllText($source, 'original bytes')
$identity = Get-L07Identity $source
$pin = @{ sha256 = $identity.sha256; size_bytes = $identity.size_bytes }
Assert-L07Pin $identity $pin
$badPin = $pin.Clone(); $badPin.sha256 = ('f' * 64)
Must-Reject { Assert-L07Pin $identity $badPin } 'changed current asset hash'
$badPin = $pin.Clone(); $badPin.size_bytes++
Must-Reject { Assert-L07Pin $identity $badPin } 'changed current asset size'
$target = Join-Path $Fixture 'copy.bin'
$copied = Copy-L07Exclusive $identity $target
if ($copied.sha256 -cne $identity.sha256) { throw 'Independent copy differs.' }
$protectedInputs = [Collections.Generic.List[object]]::new()
$configDir = Join-Path $Fixture 'Config'
[void][IO.Directory]::CreateDirectory($configDir)
$emptyIni = Join-Path $configDir 'Empty.ini'
[IO.File]::WriteAllBytes($emptyIni, [byte[]]::new(0))
Must-Reject { Get-L07Identity $emptyIni } 'empty file without config allowance'
$emptyIdentity = Get-L07Identity $emptyIni 8MB -AllowEmpty
$emptyTarget = Join-Path $Fixture 'candidate/Config/Empty.ini'
$emptyCopy = Copy-L07Exclusive $emptyIdentity $emptyTarget 8MB -AllowEmpty
if ($emptyCopy.size_bytes -ne 0 -or $emptyCopy.sha256 -cne $emptyIdentity.sha256) { throw 'Empty configuration copy differs.' }
Assert-L07Identity $emptyIdentity 8MB -AllowEmpty
Assert-L07Identity $emptyCopy 8MB -AllowEmpty
Protect-L07Identity $emptyIdentity 'original-config' 8MB -AllowEmpty
Protect-L07Identity $emptyCopy 'copied-config' 8MB -AllowEmpty
foreach ($entry in $protectedInputs) {
    if ($entry.allow_empty -isnot [bool] -or -not $entry.allow_empty) { throw 'Empty-config allowance was lost.' }
    $after = Get-L07Identity $entry.identity.path $entry.limit -AllowEmpty:$entry.allow_empty
    if ($after.size_bytes -ne $entry.identity.size_bytes -or $after.sha256 -cne $entry.identity.sha256) { throw 'Empty protected config changed.' }
}
Must-Reject { Copy-L07Exclusive $emptyIdentity (Join-Path $Fixture 'unallowed/Empty.ini') } 'empty copy without allowance'
foreach ($name in @('empty.dll', 'empty.umap', 'empty.json')) {
    $emptyRequired = Join-Path $Fixture $name
    [IO.File]::WriteAllBytes($emptyRequired, [byte[]]::new(0))
    Must-Reject { Get-L07Identity $emptyRequired } ('empty required input ' + $name)
}
[IO.File]::WriteAllText($emptyIni, 'changed configuration')
Must-Reject { Assert-L07Identity $emptyIdentity 8MB -AllowEmpty } 'changed empty config'
Must-Reject { Copy-L07Exclusive $identity $target } 'overwrite'
[IO.File]::WriteAllText($source, 'modified bytes')
Must-Reject { Copy-L07Exclusive $identity (Join-Path $Fixture 'never-created.bin') } 'changed source'
if (Test-Path -LiteralPath (Join-Path $Fixture 'never-created.bin')) { throw 'Changed source created a target.' }
Must-Reject { Assert-L07PlainPath (Join-Path $Fixture '../escape') } 'traversal'
$assets = Join-Path $Fixture 'Content/Known'
[void][IO.Directory]::CreateDirectory($assets)
[IO.File]::WriteAllText((Join-Path $assets 'T_A.uasset'), 'fixture asset bytes')
$inventory = @(Get-L07AssetInventory $Fixture @('Content/Known') 1024 2)
if ($inventory.Count -ne 1) { throw 'Valid bounded fixture inventory failed.' }
& {
    # Execute the production budget assignments with the actual ordered inventory
    # shape, a >2 GiB input and an empty valid config, without allocating big files.
    $assets = @($inventory[0], [ordered]@{ size_bytes = [long]3GB })
    $moduleRows = @(@{ source_identity = [ordered]@{ size_bytes = [long]42 } })
    $metadataRows = @(@{ source_identity = [ordered]@{ size_bytes = [long]0 } },
                      @{ source_identity = [ordered]@{ size_bytes = [long]17 } })
    $assignments = @($ast.FindAll({ param($node)
        $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and
        $node.Left -is [System.Management.Automation.Language.VariableExpressionAst] -and
        $node.Left.VariablePath.UserPath -ceq 'plannedBytes'
    }, $true))
    if ($assignments.Count -eq 0) { throw 'Production copy budget was not exercised.' }
    foreach ($assignment in $assignments) { . ([scriptblock]::Create($assignment.Extent.Text)) }
    if ($plannedBytes -ne ([long]3GB + $inventory[0].size_bytes + 59)) {
        throw 'Copy budget omitted or truncated asset/module/config bytes.'
    }
}
$changedTarget = Join-Path $Fixture 'changed-inventory-copy'
[IO.File]::WriteAllText((Join-Path $assets 'T_A.uasset'), 'fixture asset bytes that grew after inventory')
Must-Reject { Copy-L07InventoriedAsset $inventory[0] $changedTarget } 'size changed after inventory'
if (Test-Path -LiteralPath $changedTarget) { throw 'Grown asset created a target before disk-budget refusal.' }
Must-Reject { Get-L07AssetInventory $Fixture @('Content/Known') 1 2 } 'byte bound'
Must-Reject { Get-L07AssetInventory $Fixture @('Content/Known') 1024 0 } 'file count bound'
[IO.File]::WriteAllText((Join-Path $assets 'T_B.uasset'), 'version https://git-lfs.github.com/spec/v1')
Must-Reject { Get-L07AssetInventory $Fixture @('Content/Known') 1024 2 } 'LFS pointer'
$moduleRoot = Join-Path $Fixture 'Binaries/Win64'
[void][IO.Directory]::CreateDirectory($moduleRoot)
[IO.File]::WriteAllText((Join-Path $moduleRoot 'UnrealEditor-Test.dll'), 'synthetic module bytes')
$moduleFile = Join-Path $moduleRoot 'UnrealEditor.modules'
@{ BuildId = 'engine-build'; Modules = @{ Test = 'UnrealEditor-Test.dll' } } | ConvertTo-Json | Set-Content -LiteralPath $moduleFile
$modules = @(Get-L07ModuleClosure $Fixture 'Binaries/Win64/UnrealEditor.modules' @{ Test = 'UnrealEditor-Test.dll' } 'engine-build')
if ($modules.Count -ne 2) { throw 'Valid module closure failed.' }
Must-Reject { Get-L07ModuleClosure $Fixture 'Binaries/Win64/UnrealEditor.modules' @{ Test = 'UnrealEditor-Test.dll' } 'other-build' } 'BuildId mismatch'
Must-Reject { Get-L07ModuleClosure $Fixture 'Binaries/Win64/UnrealEditor.modules' @{ Other = 'UnrealEditor-Test.dll' } 'engine-build' } 'module mapping'
$environment = @{ Identity = 'env'; Engine = @{ Identity = 'engine'; Root = 'engine-root' }; Toolchain = @{ Identity = 'tools' } }
$fingerprints = @{ compile = 'compile'; proof = 'proof' }
$state = @{ SchemaVersion = 3; CompilePassed = $true; ProofPassed = $true; CompileHead = ('a' * 40); ProofHead = ('b' * 40)
    CompileFingerprint = 'compile'; ProofFingerprint = 'proof'; EnvironmentIdentity = 'env'; EngineIdentity = 'engine'
    ToolchainIdentity = 'tools'; EngineRoot = 'engine-root'; BuildCachePolicy = 'ubt-native-incremental-v1' }
Assert-L07CacheProvenance $state $fingerprints $environment
if ($state.CompileHead -ceq $state.ProofHead) { throw 'Fixture must preserve different actual compile/proof heads.' }
foreach ($field in @('CompileFingerprint', 'ProofFingerprint', 'EnvironmentIdentity', 'EngineIdentity', 'ToolchainIdentity', 'EngineRoot')) {
    $bad = $state.Clone(); $bad[$field] = 'different'
    Must-Reject { Assert-L07CacheProvenance $bad $fingerprints $environment } $field
}
$bad = $state.Clone(); $bad.ProofPassed = 'true'
Must-Reject { Assert-L07CacheProvenance $bad $fingerprints $environment } 'string proof boolean'
$log = Join-Path $Fixture 'editor.log'
[IO.File]::WriteAllText($log, "LogTemp: Display: safe`nLogLinker: Warning: Can't find file '/Game/Missing'`n")
$findings = Get-L07LogFindings $log
if ($findings.total -ne 1 -or $findings.lines.Count -ne 1 -or $findings.truncated) { throw 'Real matching error log was not inventoried.' }
& {
    # Exercise the real post-exit block with a crash and an absent report.
    # Missing output must not replace the original process failure.
    $ownedEditor = [pscustomobject]@{ ExitCode = -1073741571 }
    $receipt = @{}
    $reportPath = Join-Path $Fixture 'not-produced.json'
    $wrapperText = [IO.File]::ReadAllText($Wrapper)
    $start = $wrapperText.IndexOf('    $receipt.owned_editor_exit_code = $ownedEditor.ExitCode')
    $end = $wrapperText.IndexOf('    Assert-L07NativeReport $native.value', $start)
    if ($start -lt 0 -or $end -lt 0) { throw 'Missing production post-exit block.' }
    $message = ''
    try { . ([scriptblock]::Create($wrapperText.Substring($start, $end - $start))) }
    catch { $message = $_.Exception.Message }
    if ($message -notlike '*exit code -1073741571*' -or $message -notlike "*$log*") {
        throw ('Crash cause was hidden by report handling: ' + $message)
    }
}
$report = @{ schema_version = 2; source_head = ('c' * 40); project_root = $Fixture; preparation_identity = @{ sha256 = ('d' * 64) }
    level = $LevelPackage; engine_version = '5.8.2-56702186'; status = 'STRUCTURE_READBACK_COMPLETE_GEOMETRY_PENDING'
    structural_readback_complete = $true; candidate_map_unchanged = $true; native_component_properties_complete = $true; components_pass = $true
    geometry_accepted = $false; source_height_interpolation_proved = $false; visibility_layer_proved_in_ue = $false
    material_render_verified = $false; dependency_closure_complete = $false; total_landscape_actors = 4; total_components = 4096; reasons = @()
    native_dependencies = @{ observed = $true; value = @{ queries_complete = $true } } }
Assert-L07NativeReport $report ('c' * 40) $Fixture ('d' * 64)
foreach ($field in @('geometry_accepted', 'source_height_interpolation_proved', 'visibility_layer_proved_in_ue', 'dependency_closure_complete')) {
    $bad = $report.Clone(); $bad[$field] = $true
    Must-Reject { Assert-L07NativeReport $bad ('c' * 40) $Fixture ('d' * 64) } ('false scope promotion ' + $field)
}
$bad = $report.Clone(); $bad.native_dependencies = @{ observed = $true; value = @{ queries_complete = $null } }
Must-Reject { Assert-L07NativeReport $bad ('c' * 40) $Fixture ('d' * 64) } 'unknown package queries'
'L07_ACTUAL_POWERSHELL_GATES_PASS'
''', encoding="utf-8")
            result = subprocess.run(
                ["pwsh", "-NoProfile", "-File", str(script), str(WRAPPER), directory],
                capture_output=True, text=True, check=False, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("L07_ACTUAL_POWERSHELL_GATES_PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()

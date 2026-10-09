"""Behavioral whole-map contract, shader dependency, coverage and rollback tests."""

from __future__ import annotations

import ast
import builtins
import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts.ue import capture_sa_calobra_whole_map_prep as capture
from scripts.ue import sa_calobra_whole_map_prep as prep


class Component:
    def __init__(self, landscape, index):
        self.landscape, self.index = landscape, index
        self.props = {
            "override_material": object() if index == 230 else None,
            "forced_lod": index % 3 - 1,
        }

    def get_path_name(self):
        return f"/Test/Landscape.Component_{self.index:04}"

    def get_name(self):
        return f"Component_{self.index}"

    def get_editor_property(self, name):
        return self.props[name]

    def set_editor_property(self, name, value):
        self.props[name] = value

    def get_material(self, index):
        return self.props["override_material"] or self.landscape.material


class Landscape:
    def __init__(self, count=1024):
        self.material = object()
        self.components = [Component(self, index) for index in range(count)]

    def get_components_by_class(self, _kind):
        return self.components

    def get_editor_property(self, _name):
        return self.material

    def set_editor_property(self, _name, value):
        self.material = value


def fake_api(landscape, mismatch=None):
    master = SimpleNamespace(get_path_name=lambda: "master")
    instance = SimpleNamespace(get_path_name=lambda: "instance")
    calls = []

    def audit(component, expected):
        calls.append((component.index, expected))
        return json.dumps(
            {
                "component": component.get_path_name(),
                "all_instances_match": component.index != mismatch,
                "render_instance_count": 1,
                "expected_material": expected.get_path_name(),
            }
        )

    console = {name: "0" for name in prep.CONSOLE_NAMES}
    console["r.ScreenPercentage"] = "83.0"
    camera = [SimpleNamespace(x=1, y=2, z=3), SimpleNamespace(pitch=4, yaw=5, roll=0)]
    viewport = SimpleNamespace(
        get_level_viewport_camera_info=lambda: tuple(camera),
        set_level_viewport_camera_info=lambda *values: camera.__setitem__(
            slice(None), list(values)
        ),
    )
    api = SimpleNamespace(
        LandscapeComponent=Component,
        UnrealEditorSubsystem=object,
        SystemLibrary=SimpleNamespace(
            get_console_variable_string_value=lambda name: console[name],
            execute_console_command=lambda _world, command: console.__setitem__(
                *command.split(" ", 1)
            ),
        ),
        get_editor_subsystem=lambda _kind: viewport,
        YacsTextureAuditLibrary=SimpleNamespace(
            describe_landscape_material_instances=audit,
            drain_asset_compilation_and_collect_garbage=lambda: json.dumps(
                {"ok": True, "remaining_after": 0, "shader_jobs_after": 0}
            ),
        ),
    )
    return api, master, instance, calls, console


class NativeCompilationTests(unittest.TestCase):
    def test_zero_queues_preserve_actual_native_worker_and_memory_evidence(self):
        result = {
            "ok": True,
            "remaining_before": 11,
            "remaining_after": 0,
            "shader_jobs_before": 8,
            "shader_jobs_after": 0,
            "shader_active_workers_before": 2,
            "shader_active_workers_after": 0,
            "available_physical_before": 9 * 1024**3,
            "available_physical_after": 8 * 1024**3,
        }
        native = Mock(return_value=json.dumps(result))
        api = SimpleNamespace(
            YacsTextureAuditLibrary=SimpleNamespace(
                drain_asset_compilation_and_collect_garbage=native
            )
        )
        self.assertEqual(prep.drain_compilation(api), result)
        native.assert_called_once()

    def test_pending_queues_fail_with_exact_native_evidence_without_retry(self):
        for ok, assets, shaders in (
            (False, 2, 0),
            (False, 0, 3),
            (True, 1, 0),
            (True, 0, 1),
            (False, 0, 0),
        ):
            with self.subTest(ok=ok, assets=assets, shaders=shaders):
                result = {
                    "ok": ok,
                    "remaining_before": 11,
                    "remaining_after": assets,
                    "shader_jobs_before": 8,
                    "shader_jobs_after": shaders,
                    "shader_active_workers_after": 1,
                    "shader_external_physical_after": 123456,
                    "available_physical_after": 7 * 1024**3,
                }
                native = Mock(return_value=json.dumps(result))
                api = SimpleNamespace(
                    YacsTextureAuditLibrary=SimpleNamespace(
                        drain_asset_compilation_and_collect_garbage=native
                    )
                )
                with self.assertRaisesRegex(
                    RuntimeError, "native asset compilation did not drain:"
                ) as error:
                    prep.drain_compilation(api)
                self.assertEqual(
                    json.loads(str(error.exception).split(": ", 1)[1]), result
                )
                native.assert_called_once()


class BindingTests(unittest.TestCase):
    def test_every_native_root_checked_against_master_and_overrides_restored(self):
        landscape = Landscape()
        original, override = (
            landscape.material,
            landscape.components[230].props["override_material"],
        )
        api, master, instance, calls, _console = fake_api(landscape)
        with patch.object(
            prep, "mesh_material_snapshot", return_value=[{"road": "unchanged"}]
        ):
            binding = prep.LandscapeBinding(api, landscape, master, instance)
            rows = binding.apply()
            self.assertEqual(len(rows), 1024)
            self.assertEqual({index for index, _ in calls}, set(range(1024)))
            self.assertTrue(all(expected is master for _, expected in calls))
            self.assertTrue(all(row["assigned_instance"] == "instance" for row in rows))
            self.assertEqual(binding.restore(), [])
        self.assertIs(landscape.material, original)
        self.assertIs(landscape.components[230].props["override_material"], override)

    def test_last_render_root_mismatch_does_not_leave_partial_assignment(self):
        landscape = Landscape()
        original = landscape.material
        api, master, instance, calls, _console = fake_api(landscape, mismatch=1023)
        with patch.object(prep, "mesh_material_snapshot", return_value=[]):
            binding = prep.LandscapeBinding(api, landscape, master, instance)
            with self.assertRaisesRegex(RuntimeError, "render root"):
                binding.apply()
            self.assertTrue(binding.applied)
            self.assertEqual(binding.restore(), [])
        self.assertEqual(len(calls), 1024)
        self.assertIs(landscape.material, original)

    def test_partial_aoi_and_changed_separate_material_fail_closed(self):
        landscape = Landscape(9)
        api, master, instance, *_ = fake_api(landscape)
        with self.assertRaisesRegex(RuntimeError, "1024"):
            prep.LandscapeBinding(api, landscape, master, instance)
        landscape = Landscape()
        with patch.object(prep, "mesh_material_snapshot", side_effect=[[1], [2]]):
            binding = prep.LandscapeBinding(api, landscape, master, instance)
            with self.assertRaisesRegex(RuntimeError, "separate road"):
                binding.assert_other_materials()

    def test_adaptive_lod_and_all_original_console_component_values_restore(self):
        landscape = Landscape()
        api, _master, _instance, _calls, console = fake_api(landscape)
        original_console = dict(console)
        original_lods = [
            component.props["forced_lod"] for component in landscape.components
        ]
        environment = prep.CaptureEnvironment(api, object(), landscape)
        environment.enable_adaptive()
        environment.assert_adaptive()
        self.assertTrue(
            all(
                component.props["forced_lod"] == -1
                for component in landscape.components
            )
        )
        console["r.ScreenPercentage"] = "100"
        self.assertEqual(environment.restore(), [])
        self.assertEqual(console, original_console)
        self.assertEqual(
            [component.props["forced_lod"] for component in landscape.components],
            original_lods,
        )
        self.assertTrue(environment.report["restored"])

    def test_absent_legacy_aa_variable_does_not_block_snapshot_or_restore(self):
        landscape = Landscape()
        api, _master, _instance, _calls, console = fake_api(landscape)
        console.pop("r.PostProcessAAQuality", None)
        original = dict(console)
        getter = Mock(side_effect=lambda name: console.get(name, ""))
        api.SystemLibrary.get_console_variable_string_value = getter
        environment = prep.CaptureEnvironment(api, object(), landscape)
        environment.enable_adaptive()
        console["r.ScreenPercentage"] = "100"
        self.assertEqual(environment.restore(), [])
        self.assertEqual(console, original)
        self.assertTrue(environment.report["restored"])
        self.assertEqual(
            {call.args[0] for call in getter.call_args_list},
            {
                "r.ForceLOD",
                "r.ScreenPercentage",
                "showflag.DynamicShadows",
                "r.Streaming.FullyLoadUsedTextures",
                "r.HighResScreenshotDelay",
                "r.Test.FreezeTemporalSequences",
            },
        )

    def test_missing_required_capture_variable_still_fails_before_mutation(self):
        for name in prep.CONSOLE_NAMES:
            with self.subTest(name=name):
                landscape = Landscape()
                api, _master, _instance, _calls, console = fake_api(landscape)
                del console[name]
                api.SystemLibrary.get_console_variable_string_value = (
                    lambda key, values=console: values.get(key, "")
                )
                api.SystemLibrary.execute_console_command = Mock()
                original_lods = [
                    component.props["forced_lod"] for component in landscape.components
                ]
                with self.assertRaisesRegex(
                    RuntimeError, "Unverified capture console variable: " + name
                ):
                    prep.CaptureEnvironment(api, object(), landscape)
                api.SystemLibrary.execute_console_command.assert_not_called()
                self.assertEqual(
                    [
                        component.props["forced_lod"]
                        for component in landscape.components
                    ],
                    original_lods,
                )

    def test_memory_gate_checks_physical_and_commit_before_mutation(self):
        for physical, commit in ((7, 20), (20, 11)):
            with (
                self.subTest(physical=physical, commit=commit),
                self.assertRaisesRegex(RuntimeError, "memory gate"),
            ):
                prep.memory_checkpoint(
                    "fixture",
                    8,
                    12,
                    memory=lambda p=physical, c=commit: {
                        "free_physical": p * 1024**3,
                        "free_commit": c * 1024**3,
                    },
                )
        row = prep.memory_checkpoint(
            "fixture",
            8,
            12,
            memory=lambda: {"free_physical": 8 * 1024**3, "free_commit": 12 * 1024**3},
        )
        self.assertEqual(row["status"], "PASS")


class CameraTests(unittest.TestCase):
    def test_ground_trace_accepts_sea_level_and_rejects_misses_and_endpoints(self):
        def vector(x, y, z):
            return SimpleNamespace(x=x, y=y, z=z)

        obj = capture.WholeMapCapture.__new__(capture.WholeMapCapture)
        trace = Mock()
        obj.world = object()
        obj.api = SimpleNamespace(
            Vector=vector,
            SystemLibrary=SimpleNamespace(line_trace_single=trace),
            TraceTypeQuery=SimpleNamespace(ECC_VISIBILITY=0),
            DrawDebugTrace=SimpleNamespace(NONE=0),
        )
        endpoints = (vector(25000, 25000, -150000), vector(25000, 25000, 150000))
        for height in (0.0, -130.0):
            trace.return_value = SimpleNamespace(
                to_tuple=lambda height=height: (
                    endpoints + (vector(25000, 25000, height),)
                )
            )
            self.assertEqual(obj._ground_height(25000, 25000), height)
            self.assertEqual(trace.call_args.args[2].z, -150000)
        for invalid in (
            None,
            SimpleNamespace(to_tuple=lambda: endpoints),
            SimpleNamespace(to_tuple=lambda: (vector(25000, 25000, float("nan")),)),
        ):
            trace.return_value = invalid
            with self.assertRaisesRegex(RuntimeError, "trace missed"):
                obj._ground_height(25000, 25000)

    def plan(self):
        ground = [
            ([x, y, 1000], [x - 3000, y - 4000, 3000])
            for x in (25000, 100000, 175000)
            for y in (25000, 100000, 175000)
        ]
        pilots = [
            {
                "frame_id": name,
                "camera": [45000, 50000, 44000],
                "target": [42000, 50000, 43000],
                "fov": 76.0,
            }
            for name in ("window-0021-forward-00005", "window-0023-forward-00000")
        ]
        return capture.build_view_plan(
            ground,
            pilots,
            (0, 201600, 0, 201600, 0, 60000),
            {"origin_cm": [40950, 47250, 42648], "extent_cm": [3150, 3150, 1613]},
            [44100, 47250, 43500],
            near_views=[
                {
                    "frame_id": name,
                    "kind": "source_grid_landscape_near",
                    "camera": [100, 0, 250],
                    "target": [0, 0, 0],
                    "fov": 60.0,
                }
                for name in capture.NEAR_VIEWS
            ],
            far_views=capture.original_survey_views(),
        )

    def test_whole_area_and_matched_seam_coverage_are_explicit(self):
        views = self.plan()
        steps = capture.build_steps(views)
        self.assertEqual(len(views), 21)
        self.assertEqual(len(steps), 43)
        self.assertEqual(
            [i for i, (_, mode) in enumerate(steps) if mode == "baseline"],
            list(range(9)),
        )
        self.assertEqual(
            Counter(mode for _, mode in steps),
            {
                "baseline": 9,
                "prepared": 21,
                "domains": 4,
                "checker": 7,
                "normal-near": 1,
                "normal-far": 1,
            },
        )
        seam = [view for view in views if view["kind"] == "same_source_boundary_probe"]
        self.assertEqual(seam[0]["target"], seam[1]["target"])
        self.assertNotEqual(seam[0]["camera"], seam[1]["camera"])
        self.assertEqual(
            {
                tuple(view["target"][:2])
                for view in views
                if view["kind"] == "distributed_ground"
            },
            {(x, y) for x in (25000, 100000, 175000) for y in (25000, 100000, 175000)},
        )

    def test_missing_distributed_pose_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            capture.build_steps(self.plan()[1:])

    def test_distance_changes_only_explicit_micro_detail_settings(self):
        self.assertEqual(prep.near_detail_factor(1000), 1)
        self.assertEqual(prep.near_detail_factor(50000), 0)
        self.assertAlmostEqual(prep.near_detail_factor(13750), 0.5)
        with self.assertRaises(ValueError):
            prep.near_detail_factor(0, 10, 1)
        near, far = (
            capture.mode_parameters("normal-near"),
            capture.mode_parameters("normal-far"),
        )
        self.assertEqual(
            {key for key in near if near[key] != far[key]}, {"ForcedDetailFactor"}
        )
        self.assertEqual(capture.mode_parameters("prepared")["ForceDetailMix"], 0)

    def test_normal_response_reports_measured_pixels_without_cost_claim(self):
        a = (128, 1, 3, bytes([10, 20, 30]) * 128)
        b = (128, 1, 3, bytes([12, 22, 32]) * 128)
        result = capture.paired_normal_response(a, b)
        self.assertEqual(result["sampled_pixels"], 8)
        self.assertEqual(result["changed_pixels_at_least_2_levels"], 8)
        self.assertEqual(result["mean_absolute_rgb_delta_0_255"], 2)
        self.assertEqual(
            capture.paired_normal_response(a, a)["status"], "NO_CLEAR_SHADING_RESPONSE"
        )

    def test_whole_map_enters_before_legacy_detail_or_camera_input(self):
        path = prep.ROOT / "scripts/ue/capture_sa_calobra_component230_cliff.py"
        tree = ast.parse(path.read_text())
        main = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        start = next(
            i
            for i, node in enumerate(main.body)
            if isinstance(node, ast.Assign)
            and ast.unparse(node.targets[0]) == "_mesh_receipt['lighting']"
        )
        tail = ast.FunctionDef(
            name="route", args=main.args, body=main.body[start:], decorator_list=[]
        )
        calls = []
        namespace = {
            "os": SimpleNamespace(environ={"YACS_WHOLE_MAP_PREP": "bundle"}),
            "_mesh_receipt": {},
            "lighting": {},
            "_begin_whole_map_prep": lambda: calls.append("whole"),
            "_begin_detail_native": lambda: self.fail(
                "Detail treatment lane must not run"
            ),
        }
        exec(  # noqa: S102 - execute only the checked-in routing tail
            compile(
                ast.fix_missing_locations(ast.Module(body=[tail], type_ignores=[])),
                str(path),
                "exec",
            ),
            namespace,
        )
        namespace["route"]()
        self.assertEqual(calls, ["whole"])


class GraphNode:
    def __init__(self, kind):
        self.kind, self.properties, self.inputs = kind, {}, {}

    def set_editor_property(self, name, value):
        self.properties[name] = value


class GraphTests(unittest.TestCase):
    def test_five_roles_reach_output_but_camera_distance_cannot_change_macro_color(
        self,
    ):
        nodes, outputs = [], {}

        def create(_material, cls):
            node = GraphNode(cls.__name__)
            nodes.append(node)
            return node

        def connect(source, output, target, pin):
            target.inputs[pin] = (source, output)
            return True

        unreal = SimpleNamespace(
            MaterialEditingLibrary=SimpleNamespace(
                create_material_expression=create,
                connect_material_expressions=connect,
                connect_material_property=lambda source, _pin, prop: (
                    outputs.__setitem__(prop, source) is None
                ),
            ),
            LinearColor=lambda *values: values,
            MaterialSamplerType=SimpleNamespace(
                SAMPLERTYPE_LINEAR_COLOR=0, SAMPLERTYPE_NORMAL=1, SAMPLERTYPE_COLOR=2
            ),
            MaterialProperty=SimpleNamespace(
                MP_BASE_COLOR="color",
                MP_NORMAL="normal",
                MP_ROUGHNESS="roughness",
                MP_EMISSIVE_COLOR="emissive",
            ),
        )
        classes = (
            "WorldPosition",
            "ComponentMask",
            "Constant2Vector",
            "TextureSampleParameter2D",
            "TextureObjectParameter",
            "Add",
            "Multiply",
            "Subtract",
            "Divide",
            "ScalarParameter",
            "Constant",
            "Constant3Vector",
            "LinearInterpolate",
            "Saturate",
            "OneMinus",
            "Distance",
            "CameraPositionWS",
            "Max",
            "Normalize",
            "Floor",
            "Frac",
        )
        for name in classes:
            setattr(
                unreal,
                "MaterialExpression" + name,
                type("MaterialExpression" + name, (), {}),
            )
        module_name = "scripts.ue.build_sa_calobra_whole_map_master"
        with patch.dict(sys.modules, {"unreal": unreal}):
            builder = importlib.import_module(module_name)
            with (
                patch.object(builder, "unreal", unreal),
                patch.object(builder, "LIB", unreal.MaterialEditingLibrary),
                patch.object(
                    builder.Graph,
                    "project",
                    lambda _self, texture, _tile, _normal: texture,
                ),
            ):
                recipe = {
                    "roles": {
                        role: {"tile_cm": 200, "roughness": 0.8} for role in prep.ROLES
                    }
                }
                builder.build_graph(
                    object(),
                    object(),
                    {
                        role: {"BaseColor": object(), "Normal": object()}
                        for role in prep.ROLES
                    },
                    recipe,
                )
        sys.modules.pop(module_name, None)

        def ancestors(node):
            found = {node}
            for parent, _output in node.inputs.values():
                found |= ancestors(parent)
            return found

        color, normal = ancestors(outputs["color"]), ancestors(outputs["normal"])
        self.assertFalse(
            any(
                node.kind
                in ("MaterialExpressionDistance", "MaterialExpressionCameraPositionWS")
                for node in color
            )
        )
        self.assertTrue(
            any(node.kind == "MaterialExpressionCameraPositionWS" for node in normal)
        )
        color_textures = {
            node.properties.get("parameter_name")
            for node in color
            if node.kind == "MaterialExpressionTextureObjectParameter"
        }
        self.assertEqual(color_textures, {role + "BaseColorTex" for role in prep.ROLES})
        all_textures = [
            node
            for node in nodes
            if node.kind
            in (
                "MaterialExpressionTextureObjectParameter",
                "MaterialExpressionTextureSampleParameter2D",
            )
        ]
        self.assertEqual(len(all_textures), 11)
        self.assertEqual(set(outputs), {"color", "normal", "roughness", "emissive"})


class CleanupTests(unittest.TestCase):
    @staticmethod
    def capture_fixture():
        obj = capture.WholeMapCapture.__new__(capture.WholeMapCapture)
        obj.stopped, obj.handle, obj.native_started = False, 7, True
        obj.report = {"captures": [], "bindings": {}}
        obj.steps = capture.build_steps(CameraTests().plan())
        obj.master_data, obj.instance, obj.parameter_originals = {}, None, {}
        obj.inputs = {"root": Path("/unused"), "manifest_sha256": "same"}
        obj.clock, obj.started = lambda: 1, 0
        obj.component = SimpleNamespace(notify_mesh_modified=Mock())
        obj.api = SimpleNamespace(
            unregister_slate_post_tick_callback=Mock(
                side_effect=RuntimeError("callback failure")
            ),
            YacsLandscapeMeshDiagnosticLibrary=SimpleNamespace(
                end_component230_detail=Mock(
                    return_value=json.dumps({"status": "DETAIL_NATIVE_RESTORED"})
                )
            ),
        )
        obj.binding = SimpleNamespace(
            applied=False,
            restore=Mock(return_value=[]),
            assert_other_materials=Mock(),
        )
        obj._write, obj.done = Mock(), Mock()
        return obj

    def test_stop_requires_all_forty_three_captures_and_the_complete_plan(self):
        for capture_count, plan_count, complete in (
            (43, 43, True),
            (30, 43, False),
            (30, 30, False),
            (43, 42, False),
        ):
            with self.subTest(captures=capture_count, plan=plan_count):
                obj = self.capture_fixture()
                obj.root = Path("/unused")
                obj.api.unregister_slate_post_tick_callback.side_effect = None
                records = [
                    {
                        "frame_id": frame["frame_id"],
                        "mode": mode,
                        "file": "frames/" + frame["frame_id"] + "-" + mode + ".png",
                        "sha256": "a" * 64,
                    }
                    for frame, mode in obj.steps
                ]
                obj.report["captures"] = records[:capture_count]
                obj.steps = obj.steps[:plan_count]
                obj.binding.applied = True
                obj.binding.audit = Mock(return_value=[{} for _ in range(1024)])
                with (
                    patch.object(
                        capture, "load_inputs", return_value={"manifest_sha256": "same"}
                    ),
                    patch.object(
                        capture,
                        "decode_png",
                        return_value=(16, 1, 3, bytes([100, 100, 100]) * 16),
                    ) as decode,
                ):
                    obj.stop()
                self.assertEqual(obj.report["capture_complete"], complete)
                self.assertTrue(obj.report["bindings"]["verified_again_after_captures"])
                obj.binding.restore.assert_called_once()
                obj._write.assert_called_once()
                if complete:
                    self.assertEqual(
                        obj.report["status"], "CAPTURED_PENDING_SCENE_CLEANUP"
                    )
                    self.assertIsNone(obj.report["error"])
                    obj.done.assert_called_once_with(None)
                    self.assertEqual(decode.call_count, 2)
                    self.assertEqual(
                        obj.report["near_far_material_response"]["status"],
                        "NO_CLEAR_SHADING_RESPONSE",
                    )
                else:
                    self.assertEqual(obj.report["status"], "FAILED")
                    self.assertIn("coverage is incomplete", obj.report["error"])
                    obj.done.assert_called_once_with(obj.report["error"])
                    decode.assert_not_called()

    def test_callback_failure_still_restores_native_and_landscape_and_calls_owner(self):
        obj = self.capture_fixture()
        with patch.object(
            capture, "load_inputs", return_value={"manifest_sha256": "same"}
        ):
            obj.stop()
        obj.api.YacsLandscapeMeshDiagnosticLibrary.end_component230_detail.assert_called_once()
        obj.binding.restore.assert_called_once()
        obj.done.assert_called_once()
        self.assertIn("callback failure", obj.report["error"])
        self.assertEqual(obj.report["status"], "FAILED")

    def test_restoration_and_evidence_write_errors_cannot_skip_owner_cleanup(self):
        obj = self.capture_fixture()
        obj.api.unregister_slate_post_tick_callback.side_effect = None
        obj.binding.restore.side_effect = RuntimeError("native setter failure")
        obj._write.side_effect = OSError("disk full")
        with patch.object(
            capture, "load_inputs", return_value={"manifest_sha256": "same"}
        ):
            obj.stop()
        obj.api.YacsLandscapeMeshDiagnosticLibrary.end_component230_detail.assert_called_once()
        obj.done.assert_called_once_with(obj.report["error"])
        self.assertIn("native setter failure", obj.report["error"])
        self.assertIn("disk full", obj.report["error"])
        self.assertEqual(obj.report["status"], "FAILED")
        self.assertFalse(obj.report["separate_mesh_materials_preserved"])

    def test_owner_diagnostic_and_transient_errors_still_restore_environment(self):
        source = (
            prep.ROOT / "scripts/ue/capture_sa_calobra_component230_cliff.py"
        ).read_text(encoding="utf-8")
        functions = [
            node
            for node in ast.parse(source).body
            if isinstance(node, ast.FunctionDef)
            and node.name in ("finish", "_finish_body")
        ]
        environment = SimpleNamespace(restore=Mock(return_value=[]))
        capture_owner = SimpleNamespace(mark_cleanup=Mock())
        api = SimpleNamespace(
            EditorPythonScripting=SimpleNamespace(set_keep_python_script_alive=Mock()),
            SystemLibrary=SimpleNamespace(execute_console_command=Mock()),
            YacsLandscapeMeshDiagnosticLibrary=SimpleNamespace(
                read_component230_heightfield=Mock(
                    side_effect=OSError("diagnostic unavailable")
                )
            ),
            log=Mock(),
            log_error=Mock(),
        )
        namespace = {
            "unreal": api,
            "json": json,
            "_finished": False,
            "_handle": None,
            "_world": object(),
            "_target_component": object(),
            "_terrain_source": {},
            "_before_hash": None,
            "_before_scene": None,
            "_whole_map_environment": environment,
            "_survey_capture": None,
            "_detail_capture": None,
            "_whole_map_capture": capture_owner,
            "_paired_custom_record": None,
            "_destroy_transient": Mock(
                side_effect=RuntimeError("actor subsystem failed")
            ),
            "_write_receipt": Mock(side_effect=OSError("receipt write failed")),
        }
        exec(  # noqa: S102 - execute only the repository's parsed cleanup functions with injected wrappers
            compile(
                ast.Module(body=functions, type_ignores=[]), "owner-cleanup", "exec"
            ),
            namespace,
        )
        namespace["finish"]()
        namespace["_destroy_transient"].assert_called_once()
        environment.restore.assert_called_once()
        api.EditorPythonScripting.set_keep_python_script_alive.assert_called_once_with(
            False
        )
        capture_owner.mark_cleanup.assert_called_once()
        error = capture_owner.mark_cleanup.call_args.args[0]
        for expected in (
            "diagnostic unavailable",
            "actor subsystem failed",
            "receipt write failed",
        ):
            self.assertIn(expected, error)
        self.assertTrue(namespace["_finished"])
        self.assertIn("COMPONENT230_CLIFF_VISUAL_FAIL", api.log_error.call_args.args[0])


class BootstrapIsolationTests(unittest.TestCase):
    def test_capture_bootstrap_imports_helpers_from_an_isolated_outside_directory(self):
        script = prep.ROOT / "scripts/ue/capture_sa_calobra_component230_cliff.py"
        # Execute the actual bootstrap in a fresh interpreter without the test
        # runner's repository sys.path. Stop before native/environment setup.
        code = """
import ast, pathlib, sys, types
script = pathlib.Path(sys.argv[1])
tree = ast.parse(script.read_text(encoding='utf-8'))
boundary = next(i for i, node in enumerate(tree.body)
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == 'MAP'
            for target in node.targets))
sys.modules['unreal'] = types.ModuleType('unreal')
namespace = {'__file__': str(script)}
exec(compile(ast.Module(body=tree.body[:boundary], type_ignores=[]),
             str(script), 'exec'), namespace)
from scripts.ue.sa_calobra_whole_map_prep import CaptureEnvironment
assert CaptureEnvironment.__module__ == 'scripts.ue.sa_calobra_whole_map_prep'
assert pathlib.Path(sys.path[0]) == script.parents[2]
"""
        with tempfile.TemporaryDirectory() as outside:
            result = subprocess.run(
                [sys.executable, "-I", "-c", code, str(script)],
                cwd=outside,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_only_empty_engine_entry_world_admits_graph_bootstrap(self):
        path, components, landscapes = ["/Engine/Maps/Entry.Entry"], [], []
        world = SimpleNamespace(get_path_name=lambda: path[0])
        actor = SimpleNamespace(get_components_by_class=lambda _kind: components)
        editor, actors = object(), object()
        api = SimpleNamespace(
            UnrealEditorSubsystem=editor,
            EditorActorSubsystem=actors,
            Landscape=Landscape,
            LandscapeComponent=Component,
            GameplayStatics=SimpleNamespace(
                get_all_actors_of_class=lambda *_args: landscapes
            ),
            get_editor_subsystem=lambda kind: (
                SimpleNamespace(get_editor_world=lambda: world)
                if kind is editor
                else SimpleNamespace(get_all_level_actors=lambda: [actor])
            ),
        )
        self.assertTrue(prep.assert_isolated_bootstrap(api)["isolated"])
        path[0] = prep.MAP + ".Map"
        with self.assertRaisesRegex(RuntimeError, "isolated"):
            prep.assert_isolated_bootstrap(api)
        path[0] = "/Engine/Maps/Entry.Entry"
        components.append(object())
        with self.assertRaisesRegex(RuntimeError, "no Landscape"):
            prep.assert_isolated_bootstrap(api)
        components.clear()
        landscapes.append(object())
        with self.assertRaisesRegex(RuntimeError, "no Landscape"):
            prep.assert_isolated_bootstrap(api)


class StartupMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.receipt = Path(self.temporary.name) / "startup-memory.json"
        self.events = []
        self.drain = {
            "ok": True,
            "remaining_before": 2,
            "remaining_after": 0,
            "shader_jobs_before": 3,
            "shader_jobs_after": 0,
            "shader_external_physical_before": 320000000,
            "shader_external_physical_after": 12000000,
            "shader_active_workers_before": 3,
            "shader_active_workers_after": 0,
        }

        def native_drain():
            self.events.append("native-drain")
            return json.dumps(self.drain)

        self.native_call = Mock(side_effect=native_drain)
        api = SimpleNamespace(
            MaterialEditingLibrary=SimpleNamespace(),
            SystemLibrary=SimpleNamespace(get_engine_version=lambda: "5.8.2-56702186"),
            YacsTextureAuditLibrary=SimpleNamespace(
                drain_asset_compilation_and_collect_garbage=self.native_call
            ),
        )
        for name in ("CameraPositionWS", "Distance", "Floor", "Frac", "Max"):
            setattr(api, "MaterialExpression" + name, object())
        name = "scripts.ue.build_sa_calobra_whole_map_master"
        with patch.dict(sys.modules, {"unreal": api}):
            self.builder = importlib.import_module(name)
        self.addCleanup(lambda: sys.modules.pop(name, None))
        self.world = {
            "package": "/Engine/Maps/Entry",
            "landscape_actor_count": 0,
            "landscape_component_count": 0,
            "isolated": True,
        }
        settings = patch.dict(
            os.environ,
            {
                "YACS_WHOLE_MAP_MASTER_RECEIPT": str(
                    self.receipt.with_name("master.json")
                ),
                "YACS_CLIFF_VISUAL_EXPECTED_SHA": "a" * 40,
            },
        )
        settings.start()
        self.addCleanup(settings.stop)

    def mocks(self, after_physical):
        measurements = iter(
            [
                {"free_physical": 7278485504, "free_commit": 56487071744},
                {"free_physical": after_physical, "free_commit": 57000000000},
            ]
        )

        def measure():
            self.events.append("memory")
            return next(measurements)

        def collect():
            self.events.append("python-gc")
            return 7

        def gate(*args, **kwargs):
            self.events.append("gate")
            return prep.memory_checkpoint(*args, **kwargs)

        for target, name, side_effect in (
            (self.builder, "available_memory", measure),
            (self.builder.gc, "collect", collect),
            (self.builder, "memory_checkpoint", gate),
        ):
            mock = patch.object(target, name, side_effect=side_effect)
            mock.start()
            self.addCleanup(mock.stop)

    def test_cleanup_runs_once_before_unchanged_gate_and_retains_worker_evidence(self):
        self.mocks(9 * 1024**3)
        report = self.builder.reclaim_startup_memory(self.world)
        self.assertEqual(
            self.events, ["memory", "python-gc", "native-drain", "memory", "gate"]
        )
        self.assertEqual(report, json.loads(self.receipt.read_bytes()))
        self.assertEqual(report["status"], "STARTUP_MEMORY_READY")
        self.assertEqual(report["memory_checkpoint"]["minimum_free_physical_gib"], 8)
        self.assertEqual(report["memory_checkpoint"]["minimum_free_commit_gib"], 12)
        self.assertEqual(report["compile_drain"], self.drain)
        self.assertEqual(report["python_collected"], 7)
        self.assertEqual(report["python_gc_invocations"], 1)
        self.assertEqual(report["native_drain_invocations"], 1)
        self.assertEqual(
            report["available_physical_delta_bytes"], 9 * 1024**3 - 7278485504
        )
        self.native_call.assert_called_once()

    def test_insufficient_after_memory_writes_failure_before_source_or_assets_load(
        self,
    ):
        self.mocks(7400000000)
        with (
            patch.object(
                self.builder, "assert_isolated_bootstrap", return_value=self.world
            ),
            patch.object(self.builder, "load_inputs") as load_inputs,
        ):
            with self.assertRaisesRegex(RuntimeError, "Whole-map memory gate failed"):
                self.builder.main()
            load_inputs.assert_not_called()
        report = json.loads(self.receipt.read_bytes())
        self.assertEqual(report["status"], "STARTUP_MEMORY_FAILED")
        self.assertEqual(report["memory_after"]["free_physical"], 7400000000)
        self.assertEqual(report["compile_drain"], self.drain)
        self.assertFalse(report["generated_assets_created"])
        self.assertIn('"minimum_free_physical_gib": 8', report["error"])
        self.assertIn('"minimum_free_commit_gib": 12', report["error"])
        self.native_call.assert_called_once()

    def test_incomplete_native_drain_keeps_failure_and_after_observation(self):
        self.mocks(9 * 1024**3)
        self.drain.update(ok=False, remaining_after=1)
        with self.assertRaisesRegex(RuntimeError, "did not drain"):
            self.builder.reclaim_startup_memory(self.world)
        report = json.loads(self.receipt.read_bytes())
        self.assertEqual(report["status"], "STARTUP_MEMORY_FAILED")
        self.assertEqual(report["compile_drain"], self.drain)
        self.assertEqual(report["memory_after"]["free_physical"], 9 * 1024**3)
        self.assertEqual(self.events, ["memory", "python-gc", "native-drain", "memory"])
        self.native_call.assert_called_once()


class CleanupResultTests(unittest.TestCase):
    @staticmethod
    def owner(status, restored, errors=None):
        value = capture.WholeMapCapture.__new__(capture.WholeMapCapture)
        value.report = {
            "status": status,
            "error": None,
            "cleanup": {"status": "PENDING"},
        }
        value.environment = SimpleNamespace(
            report={"restored": restored, "restore_errors": errors or []}
        )
        value._write = Mock()
        return value

    def test_capture_failure_and_verified_environment_restore_stay_distinct(self):
        value = self.owner("FAILED", True)
        value.mark_cleanup("Whole-map native asset compilation did not drain")
        self.assertEqual(value.report["status"], "FAILED")
        self.assertEqual(value.report["cleanup"]["status"], "FAILED")
        self.assertEqual(
            value.report["cleanup"]["capture_environment"],
            {"status": "RESTORED", "restore_errors": []},
        )
        self.assertIn("did not drain", value.report["error"])
        value._write.assert_called_once()

    def test_complete_capture_requires_actual_environment_restore(self):
        value = self.owner("CAPTURED_PENDING_SCENE_CLEANUP", False, ["LOD mismatch"])
        value.mark_cleanup(None)
        self.assertEqual(value.report["status"], "FAILED")
        self.assertIn("did not restore", value.report["error"])
        self.assertEqual(
            value.report["cleanup"]["capture_environment"],
            {"status": "FAILED", "restore_errors": ["LOD mismatch"]},
        )

    def test_full_native_success_retains_original_admission_fields(self):
        value = self.owner("CAPTURED_PENDING_SCENE_CLEANUP", True)
        value.mark_cleanup(None)
        self.assertEqual(value.report["status"], "WHOLE_MAP_PREPARATION_PASS")
        self.assertIsNone(value.report["error"])
        self.assertEqual(value.report["cleanup"]["status"], "RESTORED")
        self.assertTrue(value.report["cleanup"]["source_scene_snapshot_unchanged"])
        self.assertEqual(
            value.report["cleanup"]["capture_environment"]["status"],
            "RESTORED",
        )

    def test_successful_teardown_cannot_admit_incomplete_capture(self):
        value = self.owner("FAILED", True)
        value.mark_cleanup(None)
        self.assertEqual(value.report["status"], "FAILED")
        self.assertIn("did not complete", value.report["error"])
        self.assertEqual(
            value.report["cleanup"]["capture_environment"]["status"],
            "RESTORED",
        )


class ReusablePreviewTests(unittest.TestCase):
    def test_package_inventory_includes_actual_bulk_and_rejects_unknown_siblings(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(prep, "ROOT", Path(directory)),
        ):
            path = prep.asset_file(prep.MASTER_PATH)
            path.parent.mkdir(parents=True)
            path.write_bytes(b"package")
            path.with_suffix(".ubulk").write_bytes(b"bulk")
            rows = prep.package_files(prep.MASTER_PATH)
            self.assertEqual(
                {Path(row["file"]).suffix for row in rows}, {".uasset", ".ubulk"}
            )
            path.with_suffix(".unknown").write_bytes(b"unrecognized")
            with self.assertRaisesRegex(ValueError, "Unsupported"):
                prep.package_files(prep.MASTER_PATH)

    def instance_fixture(self):
        recipe = prep.rendering_recipe()
        scalars = dict(prep.SCALARS)
        for role, settings in recipe["roles"].items():
            scalars[role + "TileSizeCm"] = settings["tile_cm"]
            scalars[role + "Roughness"] = settings["roughness"]
        texture_paths = {"WeightTex": prep.MASTER_PACKAGE + "/T_WholeMapWeights"}
        sources = {
            role: {
                channel: {"asset": f"{prep.LIBRARY}/{role}/{channel}"}
                for channel in ("BaseColor", "Normal")
            }
            for role in prep.ROLES
        }
        texture_paths.update(
            {
                role + channel + "Tex": row["asset"]
                for role, items in sources.items()
                for channel, row in items.items()
            }
        )
        textures = {
            key: SimpleNamespace(get_path_name=lambda value=value: value + ".Texture")
            for key, value in texture_paths.items()
        }
        lib = SimpleNamespace(
            get_scalar_parameter_names=lambda _instance: list(scalars),
            get_texture_parameter_names=lambda _instance: list(textures),
            get_material_instance_scalar_parameter_value=lambda _instance, name, _association: (
                scalars[name]
            ),
            get_material_instance_texture_parameter_value=lambda _instance, name, _association: (
                textures[name]
            ),
        )
        api = SimpleNamespace(
            MaterialEditingLibrary=lib,
            MaterialParameterAssociation=SimpleNamespace(GLOBAL_PARAMETER=0),
            YacsTextureAuditLibrary=SimpleNamespace(
                drain_asset_compilation_and_collect_garbage=Mock(
                    return_value=json.dumps(
                        {"ok": True, "remaining_after": 0, "shader_jobs_after": 0}
                    )
                ),
                describe_texture=lambda _texture: json.dumps(
                    {
                        "is_default_texture": False,
                        "is_compiling": False,
                        "size_x": 4033,
                        "size_y": 4033,
                        "srgb": False,
                    }
                ),
            ),
        )
        master = SimpleNamespace(get_editor_property=lambda _name: True)
        receipt = {"source_assets": sources, "rendering_recipe": recipe}
        return api, master, receipt, scalars, textures

    def test_unsaved_scalar_and_texture_binding_changes_are_rejected(self):
        api, master, receipt, scalars, textures = self.instance_fixture()
        self.assertEqual(
            len(
                prep.verify_instance(api, master, object(), receipt)[
                    "texture_readbacks"
                ]
            ),
            11,
        )
        scalars["NearDetailStartCm"] += 10
        with self.assertRaisesRegex(RuntimeError, "in-memory scalar"):
            prep.verify_instance(api, master, object(), receipt)
        scalars["NearDetailStartCm"] -= 10
        textures["WeightTex"] = SimpleNamespace(
            get_path_name=lambda: "/Game/Wrong.Texture"
        )
        with self.assertRaisesRegex(RuntimeError, "in-memory texture"):
            prep.verify_instance(api, master, object(), receipt)

    def test_all_actual_texture_bindings_load_before_native_barrier_and_audit(self):
        api, master, receipt, _scalars, textures = self.instance_fixture()
        events, resolved = [], set()
        ready = False
        audit = api.YacsTextureAuditLibrary.describe_texture
        native = {
            "ok": True,
            "remaining_before": 11,
            "remaining_after": 0,
            "shader_jobs_after": 0,
        }

        def get_binding(_instance, name, _association):
            events.append(("get", name))
            resolved.add(name)
            return textures[name]

        def drain():
            nonlocal ready
            self.assertEqual(resolved, set(textures))
            events.append(("drain", None))
            ready = True
            return json.dumps(native)

        def describe(texture):
            self.assertTrue(ready, "Native fallback audited before its loading barrier")
            events.append(("audit", texture.get_path_name()))
            return audit(texture)

        api.MaterialEditingLibrary.get_material_instance_texture_parameter_value = (
            get_binding
        )
        api.YacsTextureAuditLibrary.drain_asset_compilation_and_collect_garbage = Mock(
            side_effect=drain
        )
        api.YacsTextureAuditLibrary.describe_texture = describe
        result = prep.verify_instance(api, master, object(), receipt)
        self.assertEqual([event[0] for event in events[:12]], ["get"] * 11 + ["drain"])
        self.assertEqual([event[0] for event in events[12:]], ["get", "audit"] * 11)
        self.assertEqual(result["texture_compile_drain"], native)
        self.assertEqual(len(result["texture_readbacks"]), 11)
        api.YacsTextureAuditLibrary.drain_asset_compilation_and_collect_garbage.assert_called_once()

    def test_texture_still_default_or_compiling_after_barrier_is_rejected(self):
        for flag in ("is_default_texture", "is_compiling"):
            with self.subTest(flag=flag):
                api, master, receipt, _scalars, _textures = self.instance_fixture()
                api.YacsTextureAuditLibrary.describe_texture = (
                    lambda _texture, key=flag: json.dumps(
                        {
                            "is_default_texture": False,
                            "is_compiling": False,
                            key: True,
                        }
                    )
                )
                with self.assertRaisesRegex(
                    RuntimeError, "Prepared native texture fallback: WeightTex"
                ):
                    prep.verify_instance(api, master, object(), receipt)
                api.YacsTextureAuditLibrary.drain_asset_compilation_and_collect_garbage.assert_called_once()

    def test_texture_binding_changed_during_barrier_is_rejected(self):
        api, master, receipt, _scalars, textures = self.instance_fixture()

        def drain():
            textures["WeightTex"] = SimpleNamespace(
                get_path_name=lambda: "/Game/Wrong.Texture"
            )
            return json.dumps(
                {"ok": True, "remaining_after": 0, "shader_jobs_after": 0}
            )

        api.YacsTextureAuditLibrary.drain_asset_compilation_and_collect_garbage = drain
        with self.assertRaisesRegex(
            RuntimeError, "binding changed after readiness barrier"
        ):
            prep.verify_instance(api, master, object(), receipt)

    def test_preview_failed_apply_reports_incomplete_restore_and_retains_handles(self):
        state_name = "_yacs_whole_map_preparation_preview"
        self.addCleanup(
            lambda: (
                delattr(builtins, state_name) if hasattr(builtins, state_name) else None
            )
        )
        landscape = Landscape()
        api, master, instance, _calls, _console = fake_api(landscape)
        api.SystemLibrary.get_engine_version = lambda: "5.8.2-56702186"
        api.Landscape = Landscape
        api.GameplayStatics = SimpleNamespace(
            get_all_actors_of_class=lambda *_: [landscape]
        )
        world = SimpleNamespace(get_path_name=lambda: prep.MAP + ".Map")
        api.get_editor_subsystem = lambda _kind: SimpleNamespace(
            get_editor_world=lambda: world
        )
        api.load_asset = lambda path: master if path == prep.MASTER_PATH else instance
        assets = [
            {"asset": path, "sha256": "hash", "package_files": []}
            for path in (
                prep.MASTER_PATH,
                prep.INSTANCE_PATH,
                prep.MASTER_PACKAGE + "/T_WholeMapWeights",
            )
        ]
        receipt = {
            "status": "WHOLE_MAP_FIXED_MASTER_SAVED",
            "prep_manifest_sha256": "manifest",
            "source_assets": {},
            "rendering_recipe": {},
            "generated_assets": assets,
        }
        binding = SimpleNamespace(
            apply=Mock(side_effect=RuntimeError("partial setter failure")),
            restore=Mock(return_value=["one material failed to restore"]),
        )
        environment = SimpleNamespace(
            enable_adaptive=Mock(), restore=Mock(return_value=[])
        )
        with (
            patch.dict(sys.modules, {"unreal": api}),
            patch.object(
                prep, "load_inputs", return_value={"manifest_sha256": "manifest"}
            ),
            patch.object(
                prep, "checked_bytes", return_value=json.dumps(receipt).encode()
            ),
            patch.object(prep, "source_assets", return_value={}),
            patch.object(prep, "rendering_recipe", return_value={}),
            patch.object(prep, "digest", return_value="hash"),
            patch.object(prep, "package_files", return_value=[]),
            patch.object(prep, "memory_checkpoint", return_value={}),
            patch.object(prep, "verify_instance") as verified,
            patch.object(prep, "LandscapeBinding", return_value=binding),
            patch.object(prep, "CaptureEnvironment", return_value=environment),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "rollback incomplete: one material"
            ):
                prep.preview(bundle="bundle", master_receipt="receipt")
            self.assertTrue(hasattr(builtins, state_name))
            verified.assert_called_once()
            binding.restore.return_value = []
            self.assertEqual(prep.preview("restore")["status"], "RESTORED")
            self.assertFalse(hasattr(builtins, state_name))


if __name__ == "__main__":
    unittest.main()

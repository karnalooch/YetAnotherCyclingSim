"""Behavioral input, PNG, visibility-gate and cleanup tests; no Unreal render claim."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zlib

from scripts.ue import sa_calobra_detail_capture as detail


def png(path, width, height, raw):
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data))
        )

    Path(path).write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


class InputAndPixelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def input_bundle(self):
        objects = {
            "source/combined-mesh.json": {"vertices_cm": [], "triangles": []},
            "pilot/triangle-bands.json": {"bands": "A"},
            "pilot/manifest.json": {
                "frames": [
                    {"frame_id": name, "width": 1280, "height": 720, "fov": 76.0}
                    for name in detail.FRAME_IDS
                ]
            },
            "treatment/treatment-mesh.json": {"vertices_cm": [], "triangles": []},
        }
        hashes = {}
        for name, obj in objects.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((json.dumps(obj) + "\r\n").encode())
            hashes[name] = detail.digest(path)
        manifest = {
            "source_mesh_sha256": hashes["source/combined-mesh.json"],
            "mask_sha256": hashes["pilot/triangle-bands.json"],
            "trial_mesh_sha256": hashes["treatment/treatment-mesh.json"],
        }
        (self.root / "treatment/treatment-manifest.json").write_bytes(
            json.dumps(manifest).encode()
        )
        return patch.multiple(
            detail,
            SOURCE_SHA=manifest["source_mesh_sha256"],
            MASK_SHA=manifest["mask_sha256"],
            PILOT_SHA=hashes["pilot/manifest.json"],
        )

    def test_input_hash_covers_same_consumed_bytes_without_reopen(self):
        with (
            self.input_bundle(),
            patch.object(
                detail, "digest", side_effect=AssertionError("Must hash consumed bytes")
            ),
        ):
            loaded = detail.load_inputs(self.root)
        self.assertTrue(loaded["texts"]["source"].endswith("\r\n"))
        self.assertEqual(
            loaded["hashes"]["source"],
            hashlib.sha256(loaded["texts"]["source"].encode()).hexdigest(),
        )

    def test_rejects_stale_source_and_trial_hash(self):
        with self.input_bundle():
            path = self.root / "treatment/treatment-mesh.json"
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "payload hash"):
                detail.load_inputs(self.root)
            path = self.root / "source/combined-mesh.json"
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "fixed v8"):
                detail.load_inputs(self.root)

    def test_bounded_input_rejects_before_open(self):
        path = self.root / "large.json"
        path.write_bytes(b"12345")
        with patch.object(
            Path,
            "open",
            side_effect=AssertionError("Oversized input must not be opened"),
        ):
            with self.assertRaisesRegex(ValueError, "Oversized"):
                detail._bounded_bytes(path, 4)

    def test_png_decodes_all_five_filters_against_known_pixels(self):
        first, second = (
            bytes((10, 20, 30, 40, 60, 80)),
            bytes((7, 27, 47, 100, 120, 140)),
        )
        encoded = {
            0: second,
            1: bytes((7, 27, 47, 93, 93, 93)),
            2: bytes((253, 7, 17, 60, 60, 60)),
            3: bytes((2, 17, 32, 77, 77, 77)),
            4: bytes((253, 7, 17, 60, 60, 60)),
        }
        for mode, row in encoded.items():
            with self.subTest(filter=mode):
                path = self.root / "fixture.png"
                png(path, 2, 2, b"\0" + first + bytes((mode,)) + row)
                decoded = detail.decode_png(path, (2, 2))
                self.assertEqual(decoded[:3], (2, 2, 3))
                self.assertEqual(decoded[3], first + second)

    def test_png_rejects_crc_wrong_dimensions_and_extra_decoded_data(self):
        path = self.root / "fixture.png"
        png(path, 2, 1, b"\0" + bytes(6))
        with self.assertRaisesRegex(ValueError, "dimensions"):
            detail.decode_png(path, (3, 1))
        data = bytearray(path.read_bytes())
        data[-1] ^= 1
        path.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "CRC"):
            detail.decode_png(path, (2, 1))
        png(path, 2, 1, b"\0" + bytes(7))
        with self.assertRaisesRegex(ValueError, "payload length"):
            detail.decode_png(path, (2, 1))

    def test_visibility_requires_paired_change_inside_selected_projection(self):
        magenta = (3, 1, 3, bytes((240, 0, 240, 240, 0, 240, 240, 0, 240)))
        cyan = (3, 1, 3, bytes((0, 240, 240, 240, 0, 240, 0, 240, 240)))
        self.assertEqual(detail.visible_patch_pixels(magenta, cyan, {0, 1}), [0])
        self.assertEqual(detail.visible_patch_pixels(magenta, magenta, {0, 1, 2}), [])
        with self.assertRaisesRegex(ValueError, "projected"):
            detail.visible_patch_pixels(magenta, cyan, {-1})

    def test_detail_enters_before_legacy_review_camera_read(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "ue/capture_sa_calobra_component230_cliff.py"
        )
        tree = ast.parse(source.read_text(encoding="utf-8"))
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
            "os": SimpleNamespace(environ={"YACS_DETAIL_NATIVE": "bundle"}),
            "_mesh_receipt": {},
            "lighting": {},
            "_begin_detail_native": lambda: calls.append("detail"),
        }
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[tail], type_ignores=[])),
                str(source),
                "exec",
            ),
            namespace,
        )
        with patch.object(
            Path,
            "read_text",
            side_effect=AssertionError("Legacy review cameras are unavailable"),
        ):
            namespace["route"]()
        self.assertEqual(calls, ["detail"])


class Actor:
    def __init__(self):
        self.location = SimpleNamespace(x=0, y=0, z=0)
        self.rotation = SimpleNamespace(pitch=0, yaw=0, roll=0)
        self.properties, self.materials = {}, [object()]

    def get_component_by_class(self, _kind):
        return self

    def set_editor_property(self, name, value):
        self.properties[name] = value

    def get_editor_property(self, name):
        return self.properties[name]

    def set_actor_location(self, value, *_):
        self.location = value

    def get_actor_location(self):
        return self.location

    def set_actor_rotation(self, value, *_):
        self.rotation = value

    def get_actor_rotation(self):
        return self.rotation

    def get_num_materials(self):
        return len(self.materials)

    def get_material(self, index):
        return self.materials[index] if index < len(self.materials) else None

    def set_material(self, index, value):
        self.materials.extend([None] * max(0, index + 1 - len(self.materials)))
        self.materials[index] = value

    def notify_mesh_modified(self):
        pass

    def get_collision_enabled(self):
        return 0


class CaptureLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.size, self.visible, self.reenter = (32, 18), True, False
        self.calls, self.modes, self.shots, self.unregistered = [], [], [], []
        self.component, self.camera = Actor(), Actor()
        self.original = self.component.get_material(0)
        frames = [
            {
                "frame_id": name,
                "width": 32,
                "height": 18,
                "fov": 76.0,
                "camera": [0, 0, 0],
                "target": [1, 0, 0],
            }
            for name in detail.FRAME_IDS
        ]
        source = {
            "vertices_cm": [
                [0, 10, -5, -5, 10, -5, -5, 1],
                [1, 10, 5, -5, 10, 5, -5, 1],
                [2, 10, 0, 5, 10, 0, 5, 1],
            ],
            "triangles": [[0, 1, 2]],
        }
        inputs = {
            "texts": {key: "{}" for key in ("source", "mask", "trial", "manifest")},
            "hashes": {"source": detail.SOURCE_SHA, "mask": detail.MASK_SHA},
            "data": {
                "pilot": {"frames": frames},
                "source": source,
                "manifest": {"selected_face_indices": [0]},
            },
        }
        api = SimpleNamespace(
            Vector=lambda x, y, z: SimpleNamespace(x=x, y=y, z=z),
            CameraComponent=object,
            MathLibrary=SimpleNamespace(
                find_look_at_rotation=lambda *_: SimpleNamespace(pitch=0, yaw=0, roll=0)
            ),
            CollisionEnabled=SimpleNamespace(NO_COLLISION=0),
            ComparisonTolerance=SimpleNamespace(LOW=0),
            ViewModeIndex=SimpleNamespace(VMI_LIT=0),
            MaterialExpressionConstant3Vector=object,
            MaterialProperty=SimpleNamespace(MP_EMISSIVE_COLOR=0),
            LinearColor=lambda *args: args,
            SystemLibrary=SimpleNamespace(
                get_engine_version=lambda: "5.8.2-56702186+++UE5+Release-5.8",
                execute_console_command=lambda *_: None,
            ),
            MaterialEditingLibrary=SimpleNamespace(
                create_material_expression=lambda *_: Actor(),
                connect_material_property=lambda *_: True,
                recompile_material=lambda *_: None,
            ),
            register_slate_post_tick_callback=lambda _: "callback",
            unregister_slate_post_tick_callback=self.unregistered.append,
            YacsLandscapeMeshDiagnosticLibrary=SimpleNamespace(
                begin_component230_detail=lambda *_: json.dumps(
                    {
                        "status": "DETAIL_NATIVE_SOURCE_VERIFIED",
                        "vertex_count": 29415,
                        "triangle_count": 58216,
                        "source_row_to_native_triangle_id": list(range(58216)),
                    }
                ),
                set_component230_detail_mode=self.mode,
                end_component230_detail=self.restore,
                create_component230_detail_material=lambda: object(),
            ),
            AutomationLibrary=SimpleNamespace(
                finish_loading_before_screenshot=self.loading,
                take_high_res_screenshot=self.screenshot,
                set_editor_viewport_view_mode=lambda _: None,
            ),
        )
        self.api = api
        with patch.object(detail, "load_inputs", return_value=inputs):
            self.capture = detail.DetailCapture(
                api,
                object(),
                object(),
                self.camera,
                self.component,
                self.root / "capture",
                self.root / "input",
                "a" * 40,
                {},
                self.calls.append,
            )
        decoder = detail.decode_png
        for mocked in (
            patch.object(detail, "prepare_capture", side_effect=self.readiness),
            patch.object(
                detail, "decode_png", side_effect=lambda p: decoder(p, self.size)
            ),
        ):
            mocked.start()
            self.addCleanup(mocked.stop)

    def mode(self, _component, mode):
        if mode == "trial":
            self.assertEqual(
                self.capture.report["visibility"]["status"], "VISIBLE_IN_CAPTURED_SCENE"
            )
            self.assertGreaterEqual(len(self.capture.report["captures"]), 8)
            trial = self.capture.report["trial"]
            witness = self.capture.root / trial["witness_receipt_file"]
            self.assertEqual(detail.digest(witness), trial["witness_receipt_sha256"])
            self.assertIs(json.loads(witness.read_bytes())["trial_applied"], False)
        self.modes.append(mode)
        return json.dumps(
            {
                "status": "DETAIL_NATIVE_MODE_APPLIED",
                "mode": mode,
                "material_slot_face_counts": [58216, 0, 0, 0, 0, 0],
                "triangle_count": 58216,
                "outside_or_shared_normal_max_delta": 0,
                "topology_unchanged": True,
                "native_uvs_unchanged": True,
                "every_source_face_rendered_once": True,
            }
        )

    def restore(self, _component):
        self.modes.append("restore")
        return json.dumps(
            {
                "status": "DETAIL_NATIVE_RESTORED",
                "complete_native_snapshot_restored": True,
            }
        )

    def loading(self):
        if self.reenter:
            self.capture.tick(0)

    def readiness(self, _api, _landscape, _eye, _rotation, root, **kwargs):
        self.assertTrue(kwargs["request_height_mips"])
        self.loading()
        root.mkdir(parents=True)
        result = {"status": "NATIVE_LOADING_AND_MIPS_READY"}
        (root / "capture-readiness.json").write_bytes(json.dumps(result).encode())
        return result

    def screenshot(self, **kwargs):
        path = Path(kwargs["filename"])
        color = (
            (240, 0, 240)
            if self.visible and "patch-magenta" in path.name
            else (
                (0, 240, 240)
                if self.visible and "patch-cyan" in path.name
                else (96, 96, 96)
            )
        )
        png(path, *self.size, (b"\0" + bytes(color) * self.size[0]) * self.size[1])
        self.shots.append(path)
        task = SimpleNamespace(completed=False)
        task.is_valid_task = lambda: True
        task.is_task_done = lambda: task.completed
        return task

    def run_capture(self):
        self.capture.start()
        for _ in range(45):
            if self.capture.stopped:
                break
            self.capture.task.completed = True
            self.capture.tick(0)
        self.assertTrue(self.capture.stopped)

    def test_visible_patch_has_immutable_witness_before_trial_and_full_cleanup(self):
        self.reenter = True
        self.run_capture()
        self.assertEqual(self.calls, [None])
        self.assertEqual(
            self.modes, [mode for mode in detail.MODES for _ in range(2)] + ["restore"]
        )
        self.assertEqual(len(self.shots), 40)
        self.assertEqual(len(self.capture.report["captures"]), 10)
        self.assertIs(self.component.get_material(0), self.original)
        self.assertTrue(all(value is None for value in self.component.materials[1:]))
        witness = json.loads(
            (self.capture.root / "visibility-witness.json").read_bytes()
        )
        self.assertEqual(witness["visibility"], self.capture.report["visibility"])
        self.assertEqual(len(witness["paired_captures"]), 4)
        self.capture.mark_cleanup()
        self.assertEqual(self.capture.report["status"], "DETAIL_NATIVE_CAPTURE_PASS")

    def test_occluded_patch_blocks_trial_and_restores_native_scene(self):
        self.visible = False
        self.run_capture()
        self.assertNotIn("trial", self.modes)
        self.assertEqual(self.modes[-1], "restore")
        self.assertFalse(self.capture.report["trial"]["applied"])
        self.assertEqual(
            self.capture.report["visibility"]["status"], "NO_CORROBORATED_VISIBILITY"
        )
        self.assertIn("trial is blocked", self.calls[0])
        self.capture.mark_cleanup()
        self.assertEqual(self.capture.report["status"], "FAILED")

    def test_callback_unregister_failure_still_restores_and_hands_off_cleanup(self):
        self.capture.start()
        self.api.unregister_slate_post_tick_callback = lambda _: (_ for _ in ()).throw(
            RuntimeError("unregister failed")
        )
        self.capture.stop("capture failed")
        self.assertEqual(self.modes[-1], "restore")
        self.assertEqual(len(self.calls), 1)
        self.assertIn("unregister failed", self.calls[0])
        self.assertIs(self.component.get_material(0), self.original)

    def test_native_restore_failure_still_restores_materials_and_reports_failure(self):
        self.capture.start()
        self.api.YacsLandscapeMeshDiagnosticLibrary.end_component230_detail = lambda _: (
            json.dumps({"status": "DETAIL_NATIVE_FAIL"})
        )
        self.capture.stop()
        self.assertEqual(len(self.calls), 1)
        self.assertIn("DETAIL_NATIVE_FAIL", self.calls[0])
        self.assertIs(self.component.get_material(0), self.original)
        self.capture.mark_cleanup()
        self.assertEqual(self.capture.report["status"], "FAILED")

    def test_native_begin_rejection_never_installs_diagnostic_materials(self):
        self.api.YacsLandscapeMeshDiagnosticLibrary.begin_component230_detail = (
            lambda *_: json.dumps({"status": "DETAIL_NATIVE_FAIL"})
        )
        self.capture.start()
        self.assertTrue(self.capture.stopped)
        self.assertEqual(self.modes, [])
        self.assertEqual(self.component.materials, [self.original])
        self.assertEqual(len(self.calls), 1)


if __name__ == "__main__":
    unittest.main()

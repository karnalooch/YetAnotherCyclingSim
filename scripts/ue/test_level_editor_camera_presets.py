"""Offline source and native-fault simulation; not Unreal/visual acceptance."""

import csv
import hashlib
import io
import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.ue import level_editor_camera_presets as camera
from scripts.ue import level_editor_material_bridge as bridge
from scripts.ue.test_level_editor_material_bridge import Fixture


class CameraTests(unittest.TestCase):
    def test_presets_match_pinned_survey_camera_not_road_position(self):
        raw = (Path(__file__).resolve().parents[2] / camera.SURVEY_PATH).read_bytes()
        self.assertEqual(camera.SURVEY_SHA256, hashlib.sha256(raw).hexdigest())
        rows = {
            row["frame_id"]: row for row in csv.DictReader(io.StringIO(raw.decode()))
        }
        self.assertEqual(5, len(camera.PRESETS))
        self.assertEqual(set(camera.PRESETS), set(camera.COMMANDS.values()))
        for name in camera.PRESETS:
            view = camera.preset(name)
            row = rows[view["frame_id"]]
            self.assertEqual(json.loads(row["camera_location_cm"]), view["location_cm"])
            self.assertEqual(json.loads(row["target_cm"]), view["target_cm"])
            self.assertEqual(float(row["fov_deg"]), view["reference_fov_deg"])
            self.assertNotEqual(
                json.loads(row["road_position_cm"]), view["location_cm"]
            )
            self.assertFalse(view["viewport_fov_verified"])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.fixture = Fixture(Path(temporary.name))
        self.manager = self.fixture.manager
        self.fixture.api.Vector = lambda x, y, z: SimpleNamespace(x=x, y=y, z=z)

        def look(location, target):
            dx, dy, dz = (
                getattr(target, k) - getattr(location, k) for k in ("x", "y", "z")
            )
            return SimpleNamespace(
                pitch=math.degrees(math.atan2(dz, math.hypot(dx, dy))),
                yaw=math.degrees(math.atan2(dy, dx)),
                roll=0.0,
            )

        self.fixture.api.MathLibrary = SimpleNamespace(find_look_at_rotation=look)
        self.manager.editor.set_level_viewport_camera_info = self.set_camera

    def set_camera(self, location, rotation):
        self.fixture.camera = (location, rotation)

    def request(self, name="view", preset="road", **extra):
        return bridge.canonical(
            {
                "schema_version": 1,
                "session_id": "synthetic",
                "request_id": name,
                "action": "camera",
                "preset": preset,
                "expected_sequence": self.manager.sequence,
                **extra,
            }
        )

    def test_every_preset_reads_back_without_material_mutation_or_capture(self):
        before = self.manager.observe()
        for index, name in enumerate(camera.PRESETS, 1):
            result = json.loads(self.manager.handle_json(self.request(name, name)))
            self.assertEqual(index, result["sequence"])
            self.assertEqual("COMPLETED", result["status"])
            self.assertEqual(before, result["after"])
            self.assertEqual([], result["captures"])
            camera.validate_receipt(result)
        self.assertEqual([], self.fixture.mids)

    def test_invalid_presets_and_extra_coordinates_fail_before_native_mutation(self):
        original = self.fixture.camera
        for name in ("../road", "POKAŻ DROGĘ", None, [], "arbitrary"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.manager.handle_json(self.request(preset=name))
        with self.assertRaises(ValueError):
            self.manager.handle_json(self.request(location_cm=[1, 2, 3]))
        self.assertEqual(original, self.fixture.camera)
        self.assertEqual(set(), self.manager.used)

    def test_wrong_rotation_rolls_back_and_preserves_material_preview(self):
        self.manager.set_values(
            {"paint_roughness": 0.4, "paint_color": [0.2, 0.3, 0.4, 1]}
        )
        original_camera, original_material = self.fixture.camera, self.manager.observe()

        def wrong(location, rotation):
            if location is original_camera[0]:
                self.set_camera(location, rotation)
            else:
                self.set_camera(location, SimpleNamespace(pitch=0.0, yaw=0.0, roll=0.0))

        self.manager.editor.set_level_viewport_camera_info = wrong
        with self.assertRaisesRegex(ValueError, "did not read back"):
            self.manager.handle_json(self.request())
        self.assertEqual(original_camera, self.fixture.camera)
        self.assertEqual(original_material, self.manager.observe())
        self.assertEqual(0, self.manager.sequence)
        receipt = json.loads(
            (self.fixture.root / bridge.REQUEST_ROOT / "view/receipt.json").read_text()
        )
        self.assertTrue(receipt["camera_restored_after_failure"])
        self.assertEqual("BLOCKED", receipt["status"])

    def test_camera_is_refused_while_material_capture_pending(self):
        self.manager.pending = {"owned": True}
        with self.assertRaisesRegex(ValueError, "still pending"):
            self.manager.handle_json(self.request())

    def test_missing_viewport_does_not_restore_materials(self):
        self.manager.set_values(
            {"paint_roughness": 0.4, "paint_color": [0.2, 0.3, 0.4, 1]}
        )
        original_material = self.manager.observe()
        self.manager.editor.get_level_viewport_camera_info = lambda: None
        with self.assertRaisesRegex(ValueError, "No primary"):
            self.manager.handle_json(self.request())
        self.assertEqual(original_material, self.manager.observe())

    def test_setter_raises_after_mutation_and_rolls_back_once(self):
        original = self.fixture.camera
        calls = []

        def setter(location, rotation):
            calls.append((location, rotation))
            self.set_camera(location, rotation)
            if location is not original[0]:
                raise RuntimeError("synthetic camera setter failed after mutation")

        self.manager.editor.set_level_viewport_camera_info = setter
        with self.assertRaisesRegex(RuntimeError, "setter failed"):
            self.manager.handle_json(self.request())
        self.assertEqual(original, self.fixture.camera)
        self.assertEqual(2, len(calls))

    def test_initial_camera_getter_failure_is_retained_without_material_restore(self):
        self.manager.set_values(
            {"paint_roughness": 0.4, "paint_color": [0.2, 0.3, 0.4, 1]}
        )
        original_material = self.manager.observe()

        def getter():
            raise RuntimeError("synthetic camera getter failed")

        self.manager.editor.get_level_viewport_camera_info = getter
        with self.assertRaisesRegex(RuntimeError, "getter failed"):
            self.manager.handle_json(self.request())
        self.assertEqual(original_material, self.manager.observe())
        receipt = json.loads(
            (self.fixture.root / bridge.REQUEST_ROOT / "view/receipt.json").read_text()
        )
        self.assertFalse(receipt["camera_restore_attempted"])
        self.assertEqual("BLOCKED", receipt["status"])

    def test_readback_getter_failure_rolls_back_once(self):
        original = self.fixture.camera
        reads = []

        def getter():
            reads.append(True)
            if len(reads) == 2:
                raise RuntimeError("synthetic camera readback failed")
            return self.fixture.camera

        self.manager.editor.get_level_viewport_camera_info = getter
        with self.assertRaisesRegex(RuntimeError, "readback failed"):
            self.manager.handle_json(self.request())
        self.assertEqual(original, self.fixture.camera)
        self.assertEqual(3, len(reads))

    def test_nonfinite_state_and_angle_wrap(self):
        view = camera.preset("road")
        actual = {key: list(view[key]) for key in ("location_cm", "rotation_deg")}
        actual["rotation_deg"][1] += 360
        self.assertTrue(camera.matches(actual, view))
        actual["location_cm"][0] = float("nan")
        with self.assertRaises(ValueError):
            camera.matches(actual, view)


if __name__ == "__main__":
    unittest.main()

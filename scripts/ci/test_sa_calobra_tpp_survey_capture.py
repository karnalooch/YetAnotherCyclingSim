"""Screenshot lifecycle tests without Unreal, frozen files, or a render claim."""

from __future__ import annotations

import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.proof.sa_calobra_tpp_survey import SurveyConfig, build_survey_plan
from scripts.ue.sa_calobra_tpp_survey_capture import RESOLUTION, SurveyCapture


def vector(x=0, y=0, z=0):
    return SimpleNamespace(x=x, y=y, z=z)


def rotation(pitch=0, yaw=0, roll=0):
    return SimpleNamespace(pitch=pitch, yaw=yaw, roll=roll)


def write_png(path, size=RESOLUTION):
    def chunk(kind, payload):
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload))
        )

    width, height = size
    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress((b"\0" + b"\x60" * width * 3) * height))
    data += chunk(b"IEND", b"")
    Path(path).write_bytes(data)


class Actor:
    def __init__(self, *, mesh_assigns=True):
        self.location = vector()
        self.rotation = rotation()
        self.scale = vector(1, 1, 1)
        self.properties = {}
        self.mesh_assigns = mesh_assigns

    def get_component_by_class(self, _type):
        return self

    def set_editor_property(self, name, value):
        self.properties[name] = value

    def get_editor_property(self, name):
        return self.properties[name]

    def set_actor_location(self, position, *_args):
        self.location = position
        return True

    def get_actor_location(self):
        return self.location

    def set_actor_rotation(self, value, *_args):
        self.rotation = value
        return True

    def get_actor_rotation(self):
        return self.rotation

    def set_static_mesh(self, _mesh):
        return self.mesh_assigns

    def set_collision_enabled(self, value):
        self.properties["collision"] = value

    def set_cast_shadow(self, value):
        self.properties["shadow"] = value

    def set_actor_label(self, _label):
        pass

    def get_actor_bounds(self, _colliding):
        return vector(), vector(
            *(50 * getattr(self.scale, axis) for axis in ("x", "y", "z"))
        )

    def set_actor_scale3d(self, value):
        self.scale = value


class Task:
    def __init__(self):
        self.completed = False

    def is_valid_task(self):
        return True

    def is_task_done(self):
        return self.completed


class CaptureLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "frames").mkdir()
        self.clock = SimpleNamespace(now=0)
        self.calls, self.retained, self.unregistered, self.screenshots = [], [], [], []
        self.spawned = Actor()
        self.write_images = True
        self.size = RESOLUTION
        api = SimpleNamespace(
            Vector=vector,
            Rotator=rotation,
            CameraComponent=object,
            StaticMeshComponent=object,
            StaticMeshActor=object,
            EditorActorSubsystem=object,
            MathLibrary=SimpleNamespace(find_look_at_rotation=lambda *_: rotation()),
            ComparisonTolerance=SimpleNamespace(LOW=0),
            CollisionEnabled=SimpleNamespace(NO_COLLISION=0),
            ComponentMobility=SimpleNamespace(MOVABLE=1),
            SystemLibrary=SimpleNamespace(get_engine_version=lambda: "5.8.2-test"),
            load_asset=lambda _: object(),
            get_editor_subsystem=lambda _: SimpleNamespace(
                spawn_actor_from_class=lambda *_args, **_kwargs: self.spawned
            ),
            register_slate_post_tick_callback=lambda _: "callback-id",
            unregister_slate_post_tick_callback=self.unregistered.append,
            AutomationLibrary=SimpleNamespace(take_high_res_screenshot=self.screenshot),
        )
        capture = SurveyCapture.__new__(SurveyCapture)
        capture.api, capture.world, capture.landscape = api, object(), object()
        capture.camera, capture.ball = Actor(), Actor()
        capture.root = self.root
        capture.done, capture.retain_actor = self.calls.append, self.retained.append
        capture.clock = lambda: self.clock.now
        capture.handle, capture.task, capture.pending = "callback-id", None, None
        capture.index, capture.stopped, capture.started = 0, False, 0
        plan = build_survey_plan(
            [
                {
                    "id": "frozen",
                    "sections": [[[0, -2, 0], [0, 2, 0]], [[10, -2, 0], [10, 2, 0]]],
                }
            ],
            SurveyConfig("a" * 40),
        )
        capture.report = dict(
            plan,
            planned_frames=plan["frames"],
            frames=[],
            status="RUNNING",
            error=None,
            cleanup={"status": "PENDING"},
        )
        self.capture = capture
        self.prepare = patch(
            "scripts.ue.sa_calobra_tpp_survey_capture.prepare_capture",
            side_effect=self.readiness,
        )
        self.prepare.start()
        self.addCleanup(self.prepare.stop)
        self.reenter = False

    def readiness(self, *_args, **kwargs):
        self.assertTrue(kwargs["request_height_mips"])
        if self.reenter:
            self.capture.tick(0)  # Simulate a loading barrier pumping Slate.
        report = {
            "status": "NATIVE_LOADING_AND_MIPS_READY",
            "height_mip_lease_requested": True,
            "textures_after": [{"resident_mips": 4, "mips": 4}],
        }
        output = Path(_args[4])
        output.mkdir(parents=True, exist_ok=True)
        (output / "capture-readiness.json").write_text(json.dumps(report))
        return report

    def screenshot(self, **kwargs):
        self.screenshots.append(kwargs)
        if self.write_images:
            write_png(kwargs["filename"], self.size)
        return Task()

    def test_waits_for_native_task_and_keeps_readiness_receipt(self):
        self.capture._submit()
        self.capture.tick(0)
        self.assertEqual(self.capture.index, 0)
        self.assertEqual(self.capture.report["frames"], [])
        self.capture.task.completed = True
        self.capture.tick(0)
        self.assertEqual(self.capture.index, 1)
        frame = self.capture.report["frames"][0]
        self.assertEqual(
            frame["native_readiness"]["status"], "NATIVE_LOADING_AND_MIPS_READY"
        )
        self.assertTrue(frame["native_readiness"]["full_height_mips_requested"])
        self.assertEqual((frame["width_px"], frame["height_px"]), RESOLUTION)
        self.assertEqual(
            frame["camera_location_cm"],
            self.capture.report["planned_frames"][0]["camera_location_cm"],
        )

    def test_reentrant_loading_does_not_duplicate_completed_frame(self):
        self.capture._submit()
        self.capture.task.completed = True
        self.reenter = True
        self.capture.tick(0)
        self.assertEqual(self.capture.index, 1)
        self.assertEqual(len(self.capture.report["frames"]), 1)
        self.assertEqual(len(self.screenshots), 2)
        self.assertFalse(self.capture.stopped)

    def test_success_requires_owner_cleanup_and_is_idempotent(self):
        self.capture._submit()
        for _ in range(self.capture.report["frame_count"]):
            self.capture.task.completed = True
            self.capture.tick(0)
        self.assertEqual(self.capture.report["status"], "CAPTURE_PENDING_CLEANUP")
        self.assertEqual(self.calls, [None])
        self.assertEqual(self.unregistered, ["callback-id"])
        self.capture.tick(0)
        self.capture.stop()
        self.assertEqual(len(self.calls), 1)
        self.capture.mark_cleanup()
        self.assertEqual(self.capture.report["status"], "CAPTURED")
        self.assertEqual(
            json.loads((self.root / "survey.json").read_text())["cleanup"]["status"],
            "RESTORED",
        )
        self.assertFalse((self.root / "survey.json.tmp").exists())

    def test_cleanup_failure_invalidates_complete_capture(self):
        self.capture.report["frames"] = list(self.capture.report["planned_frames"])
        self.capture.mark_cleanup("source Landscape changed")
        self.assertEqual(self.capture.report["status"], "FAILED")
        self.assertEqual(self.capture.report["cleanup"]["status"], "FAILED")
        self.assertEqual(self.capture.report["error"], "source Landscape changed")

    def test_missing_or_wrong_size_image_invokes_owner_cleanup(self):
        for write_images, size, message in (
            (False, RESOLUTION, "FileNotFoundError"),
            (True, (32, 32), "dimensions differ"),
        ):
            with self.subTest(write_images=write_images, size=size):
                self.write_images, self.size = write_images, size
                self.capture.stopped = False
                self.capture._submit()
                self.capture.task.completed = True
                self.capture.tick(0)
                self.assertEqual(self.capture.report["status"], "FAILED")
                self.assertIn(message, self.calls[-1])
                self.assertEqual(self.capture.report["frames"], [])

    def test_screenshot_timeout_stops_with_the_pending_filename(self):
        self.capture._submit()
        self.clock.now = 121
        self.capture.tick(0)
        self.assertEqual(self.capture.report["status"], "FAILED")
        self.assertIn("screenshot deadline", self.calls[0])
        self.assertIn(self.capture.pending["file"], self.calls[0])

    def test_sphere_is_retained_before_setup_failure(self):
        self.spawned.mesh_assigns = False
        with self.assertRaisesRegex(RuntimeError, "assign native sphere"):
            self.capture.start()
        self.assertEqual(self.retained, [self.spawned])
        self.assertEqual(self.capture.ball, self.spawned)

    def test_sphere_bounds_are_read_back_and_capture_is_visual_only(self):
        self.capture.start()
        self.assertEqual(self.capture.report["sphere"]["radius_cm"], 40)
        self.assertFalse(self.capture.report["sphere"]["collision"])
        self.assertEqual(self.spawned.properties["collision"], 0)
        self.assertEqual(self.spawned.scale.x, 0.8)
        self.assertFalse(self.capture.report["physics_playback"])
        self.assertFalse(self.capture.report["route_or_terrain_modified"])

    def test_stale_existing_frame_is_never_overwritten(self):
        path = self.root / self.capture.report["planned_frames"][0]["file"]
        path.write_bytes(b"existing evidence")
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            self.capture._submit()
        self.assertEqual(path.read_bytes(), b"existing evidence")
        self.assertEqual(self.screenshots, [])

    def test_receipt_write_failure_still_invokes_owner_cleanup(self):
        with patch.object(
            self.capture, "_write", side_effect=OSError("proof disk full")
        ):
            self.capture.stop()
        self.assertEqual(self.capture.report["status"], "FAILED")
        self.assertIn("proof disk full", self.calls[0])
        self.assertEqual(self.unregistered, ["callback-id"])

    def test_camera_setter_failure_cannot_certify_requested_metric_pose(self):
        with (
            patch.object(self.capture.camera, "set_actor_location", return_value=False),
            self.assertRaisesRegex(RuntimeError, "camera position readback failed"),
        ):
            self.capture._submit()
        self.assertEqual(self.screenshots, [])

    def test_invalid_native_screenshot_task_is_rejected(self):
        with (
            patch.object(
                self.capture.api.AutomationLibrary,
                "take_high_res_screenshot",
                return_value=None,
            ),
            self.assertRaisesRegex(RuntimeError, "Invalid TPP screenshot task"),
        ):
            self.capture._submit()


if __name__ == "__main__":
    unittest.main()

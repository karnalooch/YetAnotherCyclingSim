"""Offline contracts for a real-window GPU road render; native pixels still pending."""

from __future__ import annotations

from copy import deepcopy

import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts.ue import road_asphalt_gpu_review as gpu


def fixture_csv(*, missing=(), duplicate=False, wrong_fov=False):
    """Synthetic values only: never passed off as accepted source proof."""
    headers = [
        "frame_id", "window_id", "direction", "station_m",
        "road_position_cm", "camera_location_cm", "target_cm",
        "fov_deg", "width_px", "height_px",
        "native_readiness_status", "visual_review_status",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=headers, lineterminator="\r\n")
    writer.writeheader()
    rows = []
    for frame_id in gpu.FRAME_IDS:
        if frame_id in missing:
            continue
        row = {
            "frame_id": frame_id,
            "window_id": "reviewed-VIAL_TR70190001272-1-interval-24-0",
            "direction": "reverse" if "-reverse-" in frame_id else "forward",
            "station_m": "5.0",
            "road_position_cm": json.dumps([500.0, 600.0, 700.0]),
            "camera_location_cm": json.dumps([500.0, 600.0, 950.0]),
            "target_cm": json.dumps([1300.0, 600.0, 700.0]),
            "fov_deg": "60" if wrong_fov else "76",
            "width_px": str(gpu.RESOLUTION[0]),
            "height_px": str(gpu.RESOLUTION[1]),
            "native_readiness_status": "NATIVE_LOADING_AND_MIPS_READY",
            "visual_review_status": "UNREVIEWED",
        }
        writer.writerow(row)
        rows.append(row)
    if duplicate:
        writer.writerow(rows[-1])
    return stream.getvalue().encode("utf-8")


class RoadGpuReviewContractTests(unittest.TestCase):
    def test_four_pinned_road_poses_are_forward_and_reverse(self):
        raw = fixture_csv()
        poses = gpu.validated_road_views(raw, hashlib.sha256(raw).hexdigest())
        self.assertEqual([p["frame_id"] for p in poses], list(gpu.FRAME_IDS))
        self.assertEqual([p["direction"] for p in poses].count("forward"), 2)
        self.assertEqual([p["direction"] for p in poses].count("reverse"), 2)
        self.assertEqual([p["fov_deg"] for p in poses], [76.0] * 4)

    def test_changed_source_or_missing_direction_is_not_admitted(self):
        raw = fixture_csv()
        with self.assertRaisesRegex(ValueError, "changed"):
            gpu.validated_road_views(raw, "a" * 64)
        for options in (
            {"missing": (gpu.FRAME_IDS[0],)},
            {"duplicate": True},
            {"wrong_fov": True},
        ):
            with self.subTest(options=options):
                modified = fixture_csv(**options)
                with self.assertRaises(ValueError):
                    gpu.validated_road_views(
                        modified, hashlib.sha256(modified).hexdigest()
                    )

    def test_invalid_coordinates_fail_closed_even_on_matching_hash(self):
        raw = fixture_csv()
        changed = raw.replace(b"[500.0, 600.0, 950.0]", b"[NaN, 600.0, 950.0]")
        self.assertNotEqual(raw, changed)
        with self.assertRaisesRegex(ValueError, "vector"):
            gpu.validated_road_views(
                changed, hashlib.sha256(changed).hexdigest()
            )

    def test_png_must_be_nonuniform_and_lit_visual_still_unadmitted(self):
        with patch.object(gpu, "RESOLUTION", (6, 4)):
            pixels = bytearray()
            for i in range(24):
                pixels.extend((i, i + 1, i + 2))
            with patch.object(
                gpu, "decode_png", return_value=(6, 4, 3, pixels)
            ):
                report = gpu.frame_statistics("synthetic.png")
                self.assertEqual(report["unique_sampled_rgb"], 24)
                self.assertFalse(report["visual_quality_reviewed"])
                self.assertFalse(report["road_pixels_isolated"])
            with patch.object(
                gpu, "decode_png",
                return_value=(6, 4, 3, bytearray([0] * 72)),
            ):
                with self.assertRaisesRegex(ValueError, "uniform"):
                    gpu.frame_statistics("synthetic-blank.png")

    def test_transient_camera_dirties_only_the_unsaved_derived_map(self):
        def fake_api(map_paths, content_paths):
            return SimpleNamespace(
                EditorLoadingAndSavingUtils=SimpleNamespace(
                    get_dirty_map_packages=lambda: map_paths,
                    get_dirty_content_packages=lambda: content_paths,
                )
            )

        report = gpu.audit_transient_capture_dirty_packages(
            fake_api([gpu.saved.MAP], [])
        )
        self.assertTrue(report["derived_map_dirty_in_memory"])
        self.assertTrue(report["no_original_or_content_package_dirty"])
        self.assertFalse(report["dirty_derived_package_saved"])
        self.assertEqual(report["dirty_content_count"], 0)
        self.assertFalse(
            gpu.audit_transient_capture_dirty_packages(
                fake_api([], [])
            )["derived_map_dirty_in_memory"]
        )
        for maps, content in (
            ([gpu.session.operation.MAP_PACKAGE], []),
            (["/Game/Other/L_World"], []),
            ([gpu.saved.MAP], ["/Game/Generated/YACS/T_Changed"]),
            ([], ["/Game/Materials/M_Changed"]),
            ([gpu.saved.MAP] * 9, []),
        ):
            with self.subTest(maps=maps, content=content):
                with self.assertRaises(ValueError):
                    gpu.audit_transient_capture_dirty_packages(
                        fake_api(maps, content)
                    )

    def test_gpu_screenshot_completion_quiesces_before_editor_exit(self):
        class Dummy:
            def __init__(self):
                self.stopped = False
                self.busy = False
                self.task = None
                self.finish_requested_at = 40.0
                self.events = []
            def stop(self):
                self.events.append("stop")

        job = Dummy()
        with patch.object(gpu.time, "monotonic", return_value=49.9):
            gpu.RoadLitCapture.tick(job, 0.05)
        self.assertEqual(job.events, [])
        with patch.object(gpu.time, "monotonic", return_value=50.0):
            gpu.RoadLitCapture.tick(job, 0.05)
        self.assertEqual(job.events, ["stop"])

    def test_host_plan_authenticates_all_source_poses_not_just_count(self):
        plan = gpu.material_views.current_view_plan()
        with tempfile.TemporaryDirectory() as temp:
            proof = Path(temp)
            path = proof / gpu.EXPECTED_VIEW_PLAN

            def write(value):
                raw = json.dumps(value, sort_keys=True).encode()
                path.write_bytes(raw)
                return hashlib.sha256(raw).hexdigest()

            digest = write(plan)
            with patch.dict("os.environ", {"YACS_ROAD_MATERIAL_VIEW_PLAN_SHA256": digest}):
                observed, identity = gpu.authenticated_view_plan(proof)
                self.assertEqual(observed, plan)
                self.assertEqual(identity["sha256"], digest)
                self.assertEqual(observed["frame_count"], 68)
            with patch.dict("os.environ", {"YACS_ROAD_MATERIAL_VIEW_PLAN_SHA256": "a" * 64}):
                with self.assertRaisesRegex(ValueError, "bytes changed"):
                    gpu.authenticated_view_plan(proof)
            for mutate in (
                lambda value: value["frames"].reverse(),
                lambda value: value["frames"][15]["camera_location_cm"].__setitem__(0, -99),
                lambda value: value.update(whole_area_owner_accepted=True),
            ):
                changed = deepcopy(plan)
                mutate(changed)
                digest = write(changed)
                with patch.dict("os.environ", {"YACS_ROAD_MATERIAL_VIEW_PLAN_SHA256": digest}):
                    with self.assertRaisesRegex(ValueError, "source poses"):
                        gpu.authenticated_view_plan(proof)

    def test_pure_library_import_cannot_launch_unreal_or_capture(self):
        self.assertNotIn("unreal", gpu.__dict__)
        self.assertFalse(hasattr(gpu, "RUN_IMMEDIATELY"))
        self.assertEqual(gpu.RECEIPT, "road-asphalt-lit-review.json")
        self.assertEqual(gpu.FRAME_DEADLINE_SECONDS, 180)
        self.assertEqual(gpu.TOTAL_DEADLINE_SECONDS, 1080)


class RoadGpuNativePoseTests(unittest.TestCase):
    """Exercise native pose boundaries through the actual submission/tick path."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.proof = Path(temporary.name)
        self.row = {
            "frame_id": "window-0112-forward-00001",
            "window_id": "synthetic-native-pose-test",
            "direction": "forward", "station_m": 5.0,
            "camera_location_cm": [1.0, 2.0, 3.0],
            "target_cm": [4.0, 6.0, 3.0],
            "road_position_cm": [1.0, 2.0, 0.0],
            "fov_deg": 76.0,
        }
        self.vector = lambda x, y, z: SimpleNamespace(x=x, y=y, z=z)
        self.component = SimpleNamespace(
            set_editor_property=Mock(), get_editor_property=Mock(return_value=76.0),
        )
        self.camera = SimpleNamespace(
            set_actor_location=Mock(), set_actor_rotation=Mock(return_value=True),
            get_component_by_class=Mock(return_value=self.component),
            get_actor_location=Mock(return_value=self.vector(1, 2, 3)),
            get_actor_forward_vector=Mock(return_value=self.vector(0.6, 0.8, 0)),
        )
        self.api = SimpleNamespace(
            Vector=self.vector, CameraComponent=object(),
            MathLibrary=SimpleNamespace(find_look_at_rotation=Mock(return_value=object())),
            ViewModeIndex=SimpleNamespace(VMI_LIT=object()),
            ComparisonTolerance=SimpleNamespace(LOW=object()),
            AutomationLibrary=SimpleNamespace(
                set_editor_viewport_view_mode=Mock(),
                finish_loading_before_screenshot=Mock(),
                take_high_res_screenshot=Mock(side_effect=self.screenshot),
            ),
        )
        self.job = gpu.RoadLitCapture(
            self.api, {"proof": self.proof, "frames": [self.row]}, object(), object()
        )
        self.job.camera = self.camera
        self.job.prepare_pose = Mock()
        self.job.stop = Mock()
        self.enterContext(patch.object(gpu, "decode_png", return_value=(1, 1, 3, b"rgb")))
        self.enterContext(patch.object(gpu, "frame_statistics", return_value={
            "width": 1280, "height": 720, "unique_sampled_rgb": 24,
        }))

    def screenshot(self, **arguments):
        self.assertIs(arguments["camera"], self.camera)
        Path(arguments["filename"]).write_bytes(b"SYNTHETIC PNG")
        return SimpleNamespace(is_valid_task=lambda: True, is_task_done=lambda: True)

    def test_rotation_setter_failure_cannot_submit_a_png(self):
        for result in (False, None, 1):
            with self.subTest(result=result):
                self.camera.set_actor_rotation.return_value = result
                with self.assertRaisesRegex(ValueError, "rotation setter rejected"):
                    self.job.submit_pose()
                self.assertIsNone(self.job.pending_camera_observation)
        self.job.prepare_pose.assert_not_called()
        self.api.AutomationLibrary.take_high_res_screenshot.assert_not_called()

    def test_successful_but_noop_rotation_cannot_reuse_previous_view(self):
        self.camera.get_actor_forward_vector.return_value = self.vector(1, 0, 0)
        with self.assertRaisesRegex(ValueError, "forward direction differs"):
            self.job.submit_pose()
        self.api.AutomationLibrary.take_high_res_screenshot.assert_not_called()
        self.assertIsNone(self.job.pending_camera_observation)

    def test_readback_observes_drift_during_loading_barrier(self):
        def rotate_during_loading():
            self.camera.get_actor_forward_vector.return_value = self.vector(-0.6, -0.8, 0)

        self.api.AutomationLibrary.finish_loading_before_screenshot.side_effect = rotate_during_loading
        with self.assertRaisesRegex(ValueError, "forward direction differs"):
            self.job.submit_pose()
        self.api.AutomationLibrary.take_high_res_screenshot.assert_not_called()

    def test_nonfinite_or_zero_native_forward_is_rejected(self):
        for values in ((0, 0, 0), (float("nan"), 0, 0), (0, float("inf"), 0)):
            with self.subTest(values=values):
                self.camera.get_actor_forward_vector.return_value = self.vector(*values)
                with self.assertRaisesRegex(ValueError, "forward vector is invalid"):
                    self.job.submit_pose()
        self.api.AutomationLibrary.take_high_res_screenshot.assert_not_called()

    def test_each_prime_and_final_retains_actual_pose_without_replacing_source_pose(self):
        requested = deepcopy(self.row)
        self.job.submit_pose()
        for _ in range(gpu.PRIMING_FRAMES + 1):
            self.job.tick(0.05)
        self.job.stop.assert_not_called()
        self.assertEqual(self.row, requested)
        self.assertEqual(len(self.job.frames), 1)
        frame = self.job.frames[0]
        self.assertEqual({key: frame[key] for key in requested}, requested)
        observations = [frame["native_camera_observation"], *(
            prime["native_camera_observation"] for prime in frame["priming_frames"]
        )]
        self.assertEqual(observations, [{
            "rotation_setter_accepted": True,
            "location_cm": [1.0, 2.0, 3.0],
            "forward_unit": [0.6, 0.8, 0.0],
            "fov_deg": 76.0, "forward_error": 0.0,
        }] * (gpu.PRIMING_FRAMES + 1))
        self.assertEqual(self.camera.get_actor_forward_vector.call_count,
                         gpu.PRIMING_FRAMES + 1)

    def test_direction_is_rechecked_between_priming_captures(self):
        self.job.submit_pose()
        self.camera.get_actor_forward_vector.return_value = self.vector(-0.6, -0.8, 0)
        self.job.tick(0.05)
        self.job.stop.assert_called_once()
        self.assertIn("forward direction differs", self.job.stop.call_args.args[0])
        self.assertEqual(self.api.AutomationLibrary.take_high_res_screenshot.call_count, 1)
        self.assertEqual(self.job.frames, [])

    def test_pending_screenshot_gets_bounded_recovery_room(self):
        self.job.started = 0.0
        with patch.object(gpu.time, "monotonic", return_value=0.0):
            self.job.submit_pose()
        self.job.task.is_task_done = Mock(return_value=False)
        with patch.object(gpu.time, "monotonic", return_value=98.964):
            self.job.tick(0.05)
        self.job.stop.assert_not_called()
        self.job.task.is_task_done.assert_called_once()
        self.assertEqual(self.job.frames, [])
        self.assertEqual(self.job.completed_priming_frames, 0)
        self.assertEqual(self.job.max_completed_screenshot_seconds, 0.0)

    def test_completed_task_and_existing_png_cannot_bypass_shot_deadline(self):
        self.job.started = 0.0
        with patch.object(gpu.time, "monotonic", return_value=0.0):
            self.job.submit_pose()
        self.assertTrue(self.job.pending_path.is_file())
        self.job.task.is_task_done = Mock(return_value=True)
        with patch.object(gpu.time, "monotonic", return_value=180.001):
            self.job.tick(0.05)
        self.job.task.is_task_done.assert_not_called()
        self.job.stop.assert_called_once()
        self.assertIn("screenshot deadline exceeded (180.001s > 180s)",
                      self.job.stop.call_args.args[0])
        self.assertEqual(self.job.frames, [])
        self.assertEqual(self.job.completed_priming_frames, 0)
        self.assertEqual(self.job.max_completed_screenshot_seconds, 0.0)

    def test_total_deadline_still_rejects_a_recent_completed_task(self):
        self.job.started = 0.0
        with patch.object(gpu.time, "monotonic", return_value=1000.0):
            self.job.submit_pose()
        self.job.task.is_task_done = Mock(return_value=True)
        with patch.object(gpu.time, "monotonic", return_value=1080.001):
            self.job.tick(0.05)
        self.job.task.is_task_done.assert_not_called()
        self.job.stop.assert_called_once()
        self.assertIn("bounded total deadline", self.job.stop.call_args.args[0])
        self.assertEqual(self.job.frames, [])
        self.assertEqual(self.job.completed_priming_frames, 0)

    def test_each_prime_and_final_records_elapsed_and_worst_completion(self):
        self.job.started = 0.0
        with patch.object(gpu.time, "monotonic", return_value=0.0):
            self.job.submit_pose()
        elapsed_values = [0.1, 1.2, 98.964, 0.4]
        clock = 0.0
        for elapsed in elapsed_values:
            clock += elapsed
            with patch.object(gpu.time, "monotonic", return_value=clock):
                self.job.tick(0.05)
        self.job.stop.assert_not_called()
        self.assertEqual(len(self.job.frames), 1)
        frame = self.job.frames[0]
        measured = [row["screenshot_elapsed_seconds"] for row in frame["priming_frames"]]
        measured.append(frame["screenshot_elapsed_seconds"])
        for actual, expected in zip(measured, elapsed_values, strict=True):
            self.assertAlmostEqual(actual, expected)
        self.assertAlmostEqual(self.job.max_completed_screenshot_seconds, 98.964)
        self.assertEqual(self.job.completed_priming_frames, 3)


class RoadGpuStopLifecycleTests(unittest.TestCase):
    def assert_stop_lifecycle(self, error=None):
        """Exercise real stop/receipt code with synthetic native boundaries."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        proof = Path(temporary.name)
        stage = proof / "stage.json"
        prior = proof / "saved-road-host-receipt.json"
        stage.write_text("synthetic stage", encoding="utf-8")
        prior.write_text("synthetic prior proof", encoding="utf-8")
        view_plan = gpu.material_views.current_view_plan()
        plan_path = proof / gpu.EXPECTED_VIEW_PLAN
        plan_path.write_text(json.dumps(view_plan), encoding="utf-8")
        frames = deepcopy(view_plan["frames"])
        context = {
            "proof": proof, "retained": proof / "retained",
            "exact_sha": "a" * 40, "run_token": "synthetic-stop-test",
            "original": {"native_inventory": {}},
            "manifest": {
                "material_instance": "/Game/Synthetic/MI_Road",
                "shoulder_network": {"material": {}, "support_count": 186,
                    "material_target_count": 185, "selected_triangle_count": 70000},
                "material_master": "/Game/Synthetic/M_Road", "texture_objects": {},
                "dry_asphalt_response": {}, "road_mesh": {}, "assets": [],
                "expected_normalized_inventory_sha256": "b" * 64,
            },
            "manifest_id": {"sha256": "c" * 64, "size_bytes": 1},
            "profile_identity": {"file": gpu.saved.PROFILE_DIAGNOSTIC,
                                 "sha256": "e" * 64, "size_bytes": 1},
            "rows": [], "source_dependencies": [], "frames": frames,
            "source_plan": {}, "view_plan": view_plan,
            "view_plan_identity": gpu.session._identity(plan_path),
            "stage_path": stage, "stage_identity": gpu.session._identity(stage),
            "host_receipt_identity": gpu.session._identity(prior),
        }
        events = []

        def record(name, result=None):
            def invoke(*_args, **_kwargs):
                events.append(name)
                return result
            return invoke

        position = SimpleNamespace(x=1.0, y=2.0, z=3.0)
        viewport_before = (position, object())
        actors = SimpleNamespace(destroy_actor=Mock(side_effect=record("camera", True)))
        viewport = SimpleNamespace(
            set_level_viewport_camera_info=Mock(side_effect=record("viewport restore")),
            get_level_viewport_camera_info=Mock(
                side_effect=record("viewport readback", viewport_before)
            ),
        )

        def release_lifecycle(keep_alive):
            self.assertIs(keep_alive, False)
            self.assertTrue((proof / gpu.RECEIPT).is_file())
            events.append("release lifecycle")

        api = SimpleNamespace(
            EditorActorSubsystem="actors", UnrealEditorSubsystem="viewport",
            get_editor_subsystem={"actors": actors, "viewport": viewport}.__getitem__,
            unregister_slate_post_tick_callback=Mock(side_effect=record("callback")),
            EditorLoadingAndSavingUtils=SimpleNamespace(
                get_dirty_map_packages=Mock(side_effect=record("dirty maps", [gpu.saved.MAP])),
                get_dirty_content_packages=Mock(side_effect=record("dirty content", [])),
            ),
            EditorPythonScripting=SimpleNamespace(
                set_keep_python_script_alive=Mock(side_effect=release_lifecycle)
            ),
            SystemLibrary=SimpleNamespace(quit_editor=Mock()),
        )
        job = gpu.RoadLitCapture(api, context, object(), object())
        job.camera, job.handle, job.viewport_before = object(), object(), viewport_before
        job.frames = frames
        job.completed_priming_frames = len(frames) * gpu.PRIMING_FRAMES
        job.max_completed_screenshot_seconds = 98.964
        job.residency_leases = {
            "synthetic texture": SimpleNamespace(
                set_force_mip_levels_to_be_resident=Mock(side_effect=record("mip release"))
            )
        }
        for target, name, label, result in (
            (gpu.baseline, "native_inventory", "native inventory", {}),
            (gpu.saved, "expected_saved_inventory", "scene comparison", "b" * 64),
            (gpu.saved.shoulder, "verify_loaded", "shoulder mesh", None),
            (gpu.saved.shoulder_material, "verify_material", "shoulder material", None),
            (gpu.saved, "verify_road_mesh", "road full buffers", None),
            (gpu.saved, "verify_material_instance", "dry response", None),
            (gpu.saved, "verify_retained_files", "saved packages", None),
            (gpu.session, "_verify_rows", "source assets", None),
            (gpu.saved, "verified_manifest_identity", "manifest", context["manifest_id"]),
            (gpu.saved, "verified_profile_identity", "profile diagnostic", context["profile_identity"]),
        ):
            self.enterContext(patch.object(target, name, side_effect=record(label, result)))
        original_identity = gpu.session._identity
        original_writer = gpu.saved.write_once

        def identity(path, *args):
            if path == stage:
                events.append("stage identity")
            elif path == prior:
                events.append("prior proof")
            elif path == plan_path:
                events.append("camera plan")
            return original_identity(path, *args)

        def write_receipt(path, value):
            result = original_writer(path, value)
            events.append("receipt written")
            return result

        self.enterContext(patch.object(gpu.session, "_identity", side_effect=identity))
        self.enterContext(patch.object(gpu.saved, "write_once", side_effect=write_receipt))
        job.stop(error)
        cleanup = {"callback", "camera", "viewport restore", "viewport readback", "mip release"}
        guards = {
            "dirty maps", "dirty content", "native inventory", "scene comparison",
            "shoulder mesh", "shoulder material", "saved packages", "source assets",
            "stage identity", "manifest", "prior proof",
            "road full buffers", "dry response", "camera plan",
            "profile diagnostic",
        }
        self.assertCountEqual(events, [*cleanup, *guards, "receipt written", "release lifecycle"])
        self.assertLess(max(events.index(name) for name in cleanup),
                        min(events.index(name) for name in guards))
        self.assertLess(max(events.index(name) for name in guards), events.index("receipt written"))
        self.assertLess(events.index("receipt written"), events.index("release lifecycle"))
        api.SystemLibrary.quit_editor.assert_not_called()
        self.assertTrue(job.stopped)
        receipt = json.loads((proof / gpu.RECEIPT).read_text(encoding="utf-8"))
        self.assertEqual(receipt["frame_deadline_seconds"], 180)
        self.assertEqual(receipt["max_completed_screenshot_seconds"], 98.964)
        self.assertTrue(receipt["transient_camera_destroyed"])
        self.assertTrue(receipt["residency_requests_released"])
        self.assertEqual(receipt["gpu_shutdown_quiescence_seconds"], 10.0)
        self.assertFalse(receipt["whole_area_visual_admitted"])
        self.assertFalse(receipt["performance_pass"])
        self.assertEqual(receipt["road_profile_diagnostic_sha256"], "e" * 64)
        return receipt

    def test_successful_stop_finishes_cleanup_and_proof_before_releasing_script_lifecycle(self):
        receipt = self.assert_stop_lifecycle()
        self.assertEqual(receipt["status"], "ROAD_ASPHALT_LIT_REVIEW_FRAMES_RETAINED")
        self.assertEqual(receipt["errors"], [])
        self.assertTrue(receipt["native_lit_frames_retained"])

    def test_capture_error_still_cleans_up_and_returns_failed_proof_before_lifecycle_release(self):
        receipt = self.assert_stop_lifecycle("synthetic capture callback failure")
        self.assertEqual(receipt["status"], "ROAD_ASPHALT_LIT_REVIEW_FAILED")
        self.assertEqual(receipt["errors"], ["synthetic capture callback failure"])
        for field in (
            "native_lit_frames_retained", "capture_readiness_verified",
            "sources_and_saved_assets_unchanged", "shoulder_network_material_ids_verified",
            "shoulder_wall_materials_unchanged",
        ):
            self.assertFalse(receipt[field])


if __name__ == "__main__":
    unittest.main()

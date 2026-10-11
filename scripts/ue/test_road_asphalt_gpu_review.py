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
    def surface_fixture(self, *, edge_markings=True, crack_canary=True):
        manifest, prepared, fresh, host = {}, {}, {}, {"crack_normal_space_verified": False}
        for name, enabled in (("edge_markings", edge_markings), ("crack_canary", crack_canary)):
            for row in (manifest, prepared, fresh):
                row[name + "_enabled"] = enabled
            host[name + "_requested"] = enabled
            host[name + "_fresh_reload_verified"] = enabled
            fresh[name + "_fresh_reload_verified"] = enabled
            singular = "edge_marking" if name == "edge_markings" else "crack"
            fresh[singular + "_material_reapplied"] = False
            fresh[singular + "_geometry_reapplied"] = False
            fresh[singular + "_readback"] = None
            if enabled:
                manifest[name] = {"plan_sha256": "a" * 64,
                                  "source_correspondence": {"native_source_witness_sha256": "b" * 64}}
                fresh[singular + "_readback"] = {"read_only": True, "owner_visual_pass": False,
                    "performance_pass": False, "plan_sha256": "a" * 64, "native_source_witness_sha256": "b" * 64}
        if edge_markings:
            fresh["edge_marking_readback"].update(status="EDGE_MARKINGS_FRESH_READBACK_VERIFIED",
                all_marking_buffers_verified=True, full_source_buffers_preserved=True)
        if crack_canary:
            fresh["edge_marking_readback"]["aggregate_owner"] = "local_crack_canary"
            fresh["crack_readback"].update(status="LOCAL_CRACKS_FRESH_READBACK_VERIFIED_NORMAL_REVIEW_PENDING",
                actor_count=2, all_crack_buffers_verified=True, full_source_and_existing_paint_buffers_preserved=True,
                caller_fresh_process_and_saved_bytes_required=True, world_normal_canary_required=True,
                normal_space_verified=False)
        return host, prepared, fresh, manifest

    def test_gpu_binds_explicit_surface_modes_to_the_same_fresh_native_readback(self):
        # The saved-consumer tests own validation of the full native creation
        # receipt. This test exercises the GPU's independent cross-process link.
        for edges, cracks in ((False, False), (True, False), (True, True)):
            with self.subTest(edges=edges, cracks=cracks):
                host, prepared, fresh, manifest = self.surface_fixture(edge_markings=edges, crack_canary=cracks)
                with patch.object(gpu.saved, "crack_canary_inventory") as inventory:
                    modes, observations = gpu.authenticate_surface_detail_proofs(
                        host, prepared, fresh, manifest, edge_markings=edges, crack_canary=cracks)
                self.assertEqual(modes, {"edge_markings": edges, "crack_canary": cracks})
                self.assertEqual(observations, {"edge_markings": fresh["edge_marking_readback"],
                                               "crack_canary": fresh["crack_readback"]})
                self.assertEqual(inventory.call_count, int(cracks))

    def test_gpu_refuses_lane_switches_reapplied_details_and_different_source_witness(self):
        mutations = (
            lambda h, p, f, m: h.update(crack_canary_requested=False),
            lambda h, p, f, m: h.update(crack_canary_fresh_reload_verified="true"),
            lambda h, p, f, m: p.update(crack_canary_enabled=False),
            lambda h, p, f, m: f.update(edge_marking_geometry_reapplied=True),
            lambda h, p, f, m: f.update(crack_material_reapplied=True),
            lambda h, p, f, m: f["crack_readback"].update(native_source_witness_sha256="c" * 64),
            lambda h, p, f, m: f["crack_readback"].update(plan_sha256="c" * 64),
            lambda h, p, f, m: f["crack_readback"].update(actor_count=1),
            lambda h, p, f, m: f["crack_readback"].update(all_crack_buffers_verified=False),
            lambda h, p, f, m: f["crack_readback"].update(normal_space_verified=True),
            lambda h, p, f, m: f["edge_marking_readback"].update(aggregate_owner="white_only"),
            lambda h, p, f, m: m.update(crack_canary_enabled="true"),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                args = self.surface_fixture()
                mutate(*args)
                with patch.object(gpu.saved, "crack_canary_inventory"), self.assertRaises(ValueError):
                    gpu.authenticate_surface_detail_proofs(*args, edge_markings=True, crack_canary=True)
        args = self.surface_fixture(edge_markings=True, crack_canary=False)
        args[3]["crack_canary"] = {"unexpected": True}
        with self.assertRaisesRegex(ValueError, "Disabled surface"):
            gpu.authenticate_surface_detail_proofs(*args, edge_markings=True, crack_canary=False)

    def test_crack_diagnostic_marker_cannot_take_over_a_foreign_or_dual_lane(self):
        token = "38100000000-1"
        for env, enabled in (({"YACS_ROAD_CRACK_CONTROLS_OWNED": "different"}, True),
                             ({"YACS_ROAD_CRACK_CONTROLS_OWNED": token,
                               gpu.visual_controls.OWNED_ENV: token}, True),
                             ({"YACS_ROAD_CRACK_CONTROLS_OWNED": token}, False)):
            with self.subTest(env=env, enabled=enabled), tempfile.TemporaryDirectory() as temp:
                context = {"proof": Path(temp), "run_token": token, "manifest": {"crack_canary_enabled": enabled}}
                with patch.dict("os.environ", env, clear=True), self.assertRaises(ValueError):
                    gpu.RoadLitCapture(SimpleNamespace(), context, object(), object())
                self.assertEqual(list(Path(temp).iterdir()), [])
        with tempfile.TemporaryDirectory() as temp, patch.dict("os.environ", {
                "YACS_ROAD_CRACK_CONTROLS_OWNED": token}, clear=True):
            job = gpu.RoadLitCapture(SimpleNamespace(), {"proof": Path(temp), "run_token": token,
                "manifest": {"crack_canary_enabled": True}}, object(), object())
            self.assertEqual(job.phase, "lit")
            self.assertEqual(job.control_family, "road-crack")
            self.assertEqual(job.control_plan["frame_count"], 16)
            self.assertEqual(job.control_module.digest(job.control_plan),
                             "f6f8a4fef0c10438fee2ee88827f797b9451ebf5d9e1f0b2334f754f593738d8")
            self.assertEqual(job.control_receipt_name, "road-crack-visual-controls.json")

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
                get_editor_active_viewport_view_mode=Mock(),
                finish_loading_before_screenshot=Mock(),
                take_high_res_screenshot=Mock(side_effect=self.screenshot),
            ),
        )
        self.api.AutomationLibrary.get_editor_active_viewport_view_mode.return_value = self.api.ViewModeIndex.VMI_LIT
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
        for capture in [*frame["priming_frames"], frame]:
            self.assertEqual(capture["native_viewmode_before"], "VMI_LIT")
            self.assertEqual(capture["native_viewmode_after"], "VMI_LIT")
        self.assertEqual(self.api.AutomationLibrary.get_editor_active_viewport_view_mode.call_count,
                         2 * (gpu.PRIMING_FRAMES + 1))

    def test_successful_lit_setter_with_wrong_native_mode_cannot_submit(self):
        self.api.AutomationLibrary.get_editor_active_viewport_view_mode.return_value = object()
        with self.assertRaisesRegex(ValueError, "Native viewport viewmode differs"):
            self.job.submit_pose()
        self.api.AutomationLibrary.take_high_res_screenshot.assert_not_called()
        self.assertIsNone(self.job.pending_viewmode_before)

    def test_native_viewmode_drift_during_lit_task_cannot_be_retained(self):
        self.job.submit_pose()
        self.api.AutomationLibrary.get_editor_active_viewport_view_mode.return_value = object()
        self.job.tick(0.05)
        self.job.stop.assert_called_once()
        self.assertIn("Native viewport viewmode differs", self.job.stop.call_args.args[0])
        self.assertEqual(self.job.prime_evidence, [])
        self.assertEqual(self.job.frames, [])
        self.assertEqual(self.api.AutomationLibrary.take_high_res_screenshot.call_count, 1)

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


class RoadGpuControlPhaseTests(unittest.TestCase):
    """Run the existing 68+8 submission loop against synthetic native boundaries."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        proof = Path(temporary.name)
        plan = gpu.material_views.current_view_plan()
        self.context = {
            "proof": proof, "run_token": "12345678-1", "exact_sha": "a" * 40,
            "frames": deepcopy(plan["frames"]), "view_plan": deepcopy(plan),
            "manifest_id": {"sha256": "c" * 64},
            "view_plan_identity": {"sha256": "d" * 64},
        }
        self.mode, self.position, self.forward = "lit", None, None
        self.shots, self.preparations, self.applied = [], [], []
        self.vector = lambda x, y, z: SimpleNamespace(x=x, y=y, z=z)
        self.component = SimpleNamespace(
            set_editor_property=Mock(), get_editor_property=lambda _name: 76.0)

        def location(value, *_):
            self.position = value

        def rotation(pair, *_):
            eye, target = pair
            delta = [getattr(target, name) - getattr(eye, name) for name in "xyz"]
            length = sum(value * value for value in delta) ** 0.5
            self.forward = self.vector(*(value / length for value in delta))
            return True

        self.camera = SimpleNamespace(
            set_actor_location=location, set_actor_rotation=rotation,
            get_component_by_class=lambda _kind: self.component,
            get_actor_location=lambda: self.position,
            get_actor_forward_vector=lambda: self.forward,
        )
        self.api = SimpleNamespace(
            Vector=self.vector, CameraComponent=object(),
            MathLibrary=SimpleNamespace(find_look_at_rotation=lambda eye, target: (eye, target)),
            ViewModeIndex=SimpleNamespace(VMI_LIT="lit", VMI_VISUALIZE_BUFFER="visualize"),
            ComparisonTolerance=SimpleNamespace(LOW=object()),
            AutomationLibrary=SimpleNamespace(
                set_editor_viewport_view_mode=lambda mode: setattr(self, "mode", mode),
                get_editor_active_viewport_view_mode=lambda: self.mode,
                finish_loading_before_screenshot=lambda: None,
                take_high_res_screenshot=self.screenshot,
            ),
        )
        owner = self

        class SyntheticControls:
            """The real controller is independently covered by its dedicated tests."""

            def __init__(self, api, context):
                self.plan = gpu.visual_controls.control_plan()
                self.current = None

            def begin(self):
                owner.assertEqual(len(owner.shots), 68 * (gpu.PRIMING_FRAMES + 1))
                return {"status": "READY", **owner.job.control_preflight}

            def apply(self, job_id):
                job = next(row for row in self.plan["jobs"] if row["job_id"] == job_id)
                self.current = job["control"]
                owner.applied.append(job_id)
                owner.mode = "visualize" if self.current in gpu.visual_controls.BUFFERS else "lit"

            def observe(self):
                expected = "visualize" if self.current in gpu.visual_controls.BUFFERS else "lit"
                if owner.mode != expected:
                    raise ValueError("synthetic native diagnostic viewmode drift")
                return {
                    "control": self.current, "active_viewmode_readback": expected,
                    "road_material_readback": "uniform" if self.current == "uniform-lit" else "original",
                    "requested_buffer": gpu.visual_controls.BUFFERS.get(self.current),
                    "buffer_name_readback_verified": False,
                }

        self.enterContext(patch.dict("os.environ", {gpu.visual_controls.OWNED_ENV: self.context["run_token"]}))
        self.enterContext(patch.object(gpu.visual_controls, "VisualControls", SyntheticControls))
        self.enterContext(patch.object(gpu, "decode_png", return_value=(1, 1, 3, b"rgb")))
        self.enterContext(patch.object(gpu, "frame_statistics", return_value={"width": 1280, "height": 720}))
        self.job = gpu.RoadLitCapture(self.api, self.context, object(), object())
        self.job.camera = self.camera
        self.job.stop = Mock()
        self.job.control_preflight = {"ownership": {"fixture": True}, "native_api": {"fixture": True}}

        def prepare(row, eye, rotation):
            self.preparations.append((self.job.capture_root(), row["frame_id"]))
            self.job.pose_readiness = {"status": "NATIVE_LOADING_AND_MIPS_READY"}

        self.job.prepare_pose = prepare

    def screenshot(self, **arguments):
        path = Path(arguments["filename"])
        path.write_bytes(b"SYNTHETIC CONTROL PNG")
        self.shots.append((path, self.mode))
        return SimpleNamespace(is_valid_task=lambda: True, is_task_done=lambda: True)

    def complete_lit(self):
        self.job.submit_pose()
        for _ in range(68 * (gpu.PRIMING_FRAMES + 1)):
            self.job.tick(0.05)
        self.assertEqual(len(self.job.frames), 68)
        self.assertEqual(self.job.phase, "controls")
        self.assertEqual(len(self.job.control_frames), 0)
        self.assertIsNone(self.job.finish_requested_at)

    def test_original_68_remain_ordered_before_eight_separate_controls_in_same_loop(self):
        original = deepcopy(self.context)
        self.complete_lit()
        for _ in range(8 * (gpu.PRIMING_FRAMES + 1)):
            self.job.tick(0.05)
        self.job.stop.assert_not_called()
        self.assertEqual(self.context, original)
        self.assertIsNotNone(self.job.finish_requested_at)
        self.assertEqual([row["frame_id"] for row in self.job.frames],
                         [row["frame_id"] for row in original["frames"]])
        self.assertTrue(all(row["file"].startswith("road-asphalt-lit-review/frames/")
                            and row["render_mode"] == "lit" for row in self.job.frames))
        self.assertEqual(len(self.job.control_frames), 8)
        self.assertEqual(self.job.completed_priming_frames, 204)
        self.assertEqual(self.job.control_completed_priming_frames, 24)
        self.assertEqual(self.applied, [job["job_id"] for job in self.job.control_plan["jobs"]])
        self.assertEqual(len(self.shots), 304)
        self.assertEqual(len(self.preparations), 76)
        for frame, job in zip(self.job.control_frames, self.job.control_plan["jobs"], strict=True):
            self.assertEqual(frame["source_frame_id"], job["camera"]["frame_id"])
            self.assertEqual(frame["control_mode"], job["control"])
            self.assertEqual(frame["camera_location_cm"], job["camera"]["camera_location_cm"])
            self.assertEqual(frame["target_cm"], job["camera"]["target_cm"])
            self.assertTrue(frame["file"].startswith("road-asphalt-visual-controls/frames/"))
            for capture in [*frame["priming_frames"], frame]:
                expected_mode = "VMI_VISUALIZE_BUFFER" if job["control"] in gpu.visual_controls.BUFFERS else "VMI_LIT"
                self.assertEqual(capture["native_viewmode_before"], expected_mode)
                self.assertEqual(capture["native_viewmode_after"], expected_mode)
                self.assertEqual(capture["native_control_observation_before"],
                                 capture["native_control_observation_after"])
                self.assertFalse(capture["native_control_observation_before"]["buffer_name_readback_verified"])

    def test_missing_native_api_is_rejected_before_first_camera_or_capture(self):
        self.api.EditorPythonScripting = SimpleNamespace(set_keep_python_script_alive=Mock())
        self.api.get_editor_subsystem = Mock()
        with patch.object(gpu.visual_controls, "preflight",
                          side_effect=ValueError("synthetic missing installed buffer")):
            self.job.start()
        self.job.stop.assert_called_once()
        self.assertIn("missing installed buffer", self.job.stop.call_args.args[0])
        self.api.get_editor_subsystem.assert_not_called()
        self.assertEqual(self.shots, [])

    def test_buffer_viewmode_drift_during_task_cannot_become_debug_evidence(self):
        self.complete_lit()
        for _ in range(gpu.PRIMING_FRAMES + 1):
            self.job.tick(0.05)
        self.assertEqual(self.job.capture_row()["control_mode"], "current-basecolor")
        self.assertEqual(self.mode, "visualize")
        self.mode = "lit"
        shots = len(self.shots)
        self.job.tick(0.05)
        self.job.stop.assert_called_once()
        self.assertIn("diagnostic viewmode drift", self.job.stop.call_args.args[0])
        self.assertEqual(len(self.shots), shots)
        self.assertEqual(len(self.job.frames), 68)
        self.assertEqual(len(self.job.control_frames), 1)

    def test_control_phase_keeps_original_per_shot_and_total_deadlines(self):
        self.complete_lit()
        self.job.started = 0.0
        self.job.submitted = 1000.0
        self.job.task.is_task_done = Mock(return_value=True)
        with patch.object(gpu.time, "monotonic", return_value=1080.001):
            self.job.tick(0.05)
        self.job.task.is_task_done.assert_not_called()
        self.job.stop.assert_called_once()
        self.assertIn("bounded total deadline", self.job.stop.call_args.args[0])
        self.assertEqual(gpu.FRAME_DEADLINE_SECONDS, 180)
        self.assertEqual(len(self.job.control_frames), 0)


class RoadGpuStopLifecycleTests(unittest.TestCase):
    def test_partial_crack_restore_cannot_report_verified_restoration(self):
        # Exercise receipt generation directly: the native failure may preserve
        # material bytes while failing visibility, MID cleanup or dirty state.
        job = gpu.RoadLitCapture.__new__(gpu.RoadLitCapture)
        job.control_family = "road-crack"
        job.control_module = SimpleNamespace(digest=lambda _plan: "f" * 64)
        job.control_plan = {"frame_count": 1, "jobs": [{"job_id": "synthetic"}]}
        job.control_frames = [{"frame_id": "synthetic"}]
        job.control_completed_priming_frames = gpu.PRIMING_FRAMES
        job.control_begin = {"status": "READY"}
        job.control_preflight = {}
        job.control_max_completed_screenshot_seconds = 0.1
        job.context = {
            "exact_sha": "a" * 40, "run_token": "12345678-1",
            "manifest_id": {"sha256": "b" * 64},
            "view_plan_identity": {"sha256": "c" * 64},
        }
        restoration = {
            "status": "RESTORED", "cleanup_errors": [],
            "original_material_restored": True, "owned_viewports_returned_to_lit": True,
            "saved_and_staged_package_bytes_unchanged": True,
            "original_visibility_restored": True, "original_mic_probe_values_zero": True,
            "transient_mids_detached": True, "transient_mid_refs_released": True,
            "dirty_content_count": 0,
        }
        job.control_restore = deepcopy(restoration)
        self.assertTrue(job.visual_control_receipt([], {})["control_restoration_verified"])
        failures = [(key, False) for key, value in restoration.items() if value is True]
        failures.extend([
            ("status", "FAILED"), ("cleanup_errors", ["visibility failed"]),
            ("cleanup_errors", None), ("dirty_content_count", 1),
            ("dirty_content_count", False),
        ])
        for key, value in failures:
            with self.subTest(field=key, value=value):
                job.control_restore = {**deepcopy(restoration), key: value}
                receipt = job.visual_control_receipt([], {})
                self.assertEqual(receipt["status"], "ROAD_CRACK_VISUAL_CONTROLS_FAILED")
                self.assertFalse(receipt["control_restoration_verified"])
                self.assertFalse(receipt["normal_space_verified"])

    def assert_stop_lifecycle(self, error=None, *, with_controls=False, restore_error=False):
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
            "exact_sha": "a" * 40, "run_token": "12345678-1",
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
        if with_controls:
            self.enterContext(patch.dict("os.environ", {gpu.visual_controls.OWNED_ENV: context["run_token"]}))
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
        if with_controls:
            restored = {
                "status": "RESTORED", "cleanup_errors": [],
                "original_material_restored": True, "owned_viewports_returned_to_lit": True,
                "saved_and_staged_package_bytes_unchanged": True,
            }

            def restore_controls():
                events.append("controls restored")
                if restore_error:
                    raise RuntimeError("synthetic control restoration failure")
                return restored

            job.phase = "controls"
            job.controls = SimpleNamespace(restore=restore_controls, report={"status": "FAILED"})
            job.control_begin = {"status": "READY"}
            job.control_frames = [{"frame_id": row["job_id"]} for row in job.control_plan["jobs"]]
            job.control_completed_priming_frames = 8 * gpu.PRIMING_FRAMES
        for target, name, label, result in (
            (gpu.baseline, "native_inventory", "native inventory", {}),
            (gpu.saved, "expected_saved_inventory", "scene comparison", "b" * 64),
            (gpu.saved.shoulder, "verify_loaded", "shoulder mesh", None),
            (gpu.saved.shoulder_material, "verify_material", "shoulder material", None),
            (gpu.saved, "verify_road_mesh", "road full buffers", None),
            (gpu.saved, "verify_surface_details", "surface details", {"edge_markings": None, "crack_canary": None}),
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
            events.append("control receipt written" if path.name == gpu.CONTROL_RECEIPT else "receipt written")
            return result

        self.enterContext(patch.object(gpu.session, "_identity", side_effect=identity))
        self.enterContext(patch.object(gpu.saved, "write_once", side_effect=write_receipt))
        job.stop(error)
        cleanup = {"callback", "camera", "viewport restore", "viewport readback", "mip release"}
        if with_controls:
            cleanup.add("controls restored")
        guards = {
            "dirty maps", "dirty content", "native inventory", "scene comparison",
            "shoulder mesh", "shoulder material", "saved packages", "source assets",
            "stage identity", "manifest", "prior proof",
            "road full buffers", "dry response", "camera plan",
            "profile diagnostic", "surface details",
        }
        expected_writes = ["receipt written"] + (["control receipt written"] if with_controls else [])
        self.assertCountEqual(events, [*cleanup, *guards, *expected_writes, "release lifecycle"])
        self.assertLess(max(events.index(name) for name in cleanup),
                        min(events.index(name) for name in guards))
        self.assertLess(max(events.index(name) for name in guards), events.index("receipt written"))
        self.assertLess(events.index("receipt written"), events.index("release lifecycle"))
        if with_controls:
            self.assertLess(events.index("receipt written"), events.index("control receipt written"))
            self.assertLess(events.index("control receipt written"), events.index("release lifecycle"))
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
        if with_controls:
            self.control_receipt = json.loads((proof / gpu.CONTROL_RECEIPT).read_text())
            self.assertEqual(self.control_receipt["lit_review_receipt"],
                             {"file": gpu.RECEIPT, **original_identity(proof / gpu.RECEIPT)})
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

    def test_controls_restore_before_conservation_and_write_separate_linked_receipt(self):
        receipt = self.assert_stop_lifecycle(with_controls=True)
        self.assertEqual(receipt["status"], "ROAD_ASPHALT_LIT_REVIEW_FRAMES_RETAINED")
        self.assertEqual(receipt["frame_count"], 68)
        self.assertEqual(receipt["completed_priming_frames"], 204)
        self.assertEqual(self.control_receipt["status"], "ROAD_ASPHALT_VISUAL_CONTROLS_FRAMES_RETAINED")
        self.assertEqual(self.control_receipt["frame_count"], 8)
        self.assertEqual(self.control_receipt["completed_priming_frames"], 24)
        self.assertTrue(self.control_receipt["control_restoration_verified"])

    def test_control_capture_failure_keeps_valid_lit_sequence_and_marks_debug_failed(self):
        receipt = self.assert_stop_lifecycle("synthetic debug capture failure", with_controls=True)
        self.assertEqual(receipt["status"], "ROAD_ASPHALT_LIT_REVIEW_FRAMES_RETAINED")
        self.assertEqual(receipt["errors"], [])
        self.assertEqual(self.control_receipt["status"], "ROAD_ASPHALT_VISUAL_CONTROLS_FAILED")
        self.assertEqual(self.control_receipt["errors"], ["synthetic debug capture failure"])
        self.assertTrue(self.control_receipt["control_restoration_verified"])

    def test_control_restore_failure_fails_both_receipts_but_runs_all_other_cleanup(self):
        receipt = self.assert_stop_lifecycle(with_controls=True, restore_error=True)
        self.assertEqual(receipt["status"], "ROAD_ASPHALT_LIT_REVIEW_FAILED")
        self.assertTrue(any("control restoration" in value for value in receipt["errors"]))
        self.assertEqual(self.control_receipt["status"], "ROAD_ASPHALT_VISUAL_CONTROLS_FAILED")
        self.assertFalse(self.control_receipt["control_restoration_verified"])


if __name__ == "__main__":
    unittest.main()

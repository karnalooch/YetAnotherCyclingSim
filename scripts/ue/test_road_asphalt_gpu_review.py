"""Offline contracts for a real-window GPU road render; native pixels still pending."""

from __future__ import annotations

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

    def test_pure_library_import_cannot_launch_unreal_or_capture(self):
        self.assertNotIn("unreal", gpu.__dict__)
        self.assertFalse(hasattr(gpu, "RUN_IMMEDIATELY"))
        self.assertEqual(gpu.RECEIPT, "road-asphalt-lit-review.json")
        self.assertEqual(gpu.FRAME_DEADLINE_SECONDS, 90)
        self.assertEqual(gpu.TOTAL_DEADLINE_SECONDS, 380)


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
        frames = [{"frame_id": frame} for frame in gpu.FRAME_IDS]
        context = {
            "proof": proof, "retained": proof / "retained",
            "exact_sha": "a" * 40, "run_token": "synthetic-stop-test",
            "original": {"native_inventory": {}},
            "manifest": {
                "material_instance": "/Game/Synthetic/MI_Road",
                "shoulder_window": {"material": {}}, "assets": [],
                "expected_normalized_inventory_sha256": "b" * 64,
            },
            "manifest_id": {"sha256": "c" * 64, "size_bytes": 1},
            "rows": [], "source_dependencies": [], "frames": frames,
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
            (gpu.saved, "verify_retained_files", "saved packages", None),
            (gpu.session, "_verify_rows", "source assets", None),
            (gpu.saved, "verified_manifest_identity", "manifest", context["manifest_id"]),
        ):
            self.enterContext(patch.object(target, name, side_effect=record(label, result)))
        original_identity = gpu.session._identity
        original_writer = gpu.saved.write_once

        def identity(path, *args):
            if path == stage:
                events.append("stage identity")
            elif path == prior:
                events.append("prior proof")
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
        }
        self.assertCountEqual(events, [*cleanup, *guards, "receipt written", "release lifecycle"])
        self.assertLess(max(events.index(name) for name in cleanup),
                        min(events.index(name) for name in guards))
        self.assertLess(max(events.index(name) for name in guards), events.index("receipt written"))
        self.assertLess(events.index("receipt written"), events.index("release lifecycle"))
        api.SystemLibrary.quit_editor.assert_not_called()
        self.assertTrue(job.stopped)
        receipt = json.loads((proof / gpu.RECEIPT).read_text(encoding="utf-8"))
        self.assertTrue(receipt["transient_camera_destroyed"])
        self.assertTrue(receipt["residency_requests_released"])
        self.assertEqual(receipt["gpu_shutdown_quiescence_seconds"], 10.0)
        self.assertFalse(receipt["whole_area_visual_admitted"])
        self.assertFalse(receipt["performance_pass"])
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
            "sources_and_saved_assets_unchanged", "window0112_shoulder_material_ids_verified",
            "window0112_wall_material_unchanged",
        ):
            self.assertFalse(receipt[field])


if __name__ == "__main__":
    unittest.main()

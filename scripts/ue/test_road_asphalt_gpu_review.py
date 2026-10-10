"""Offline contracts for a real-window GPU road render; native pixels still pending."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import unittest
from unittest.mock import patch

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

    def test_pure_library_import_cannot_launch_unreal_or_capture(self):
        self.assertNotIn("unreal", gpu.__dict__)
        self.assertFalse(hasattr(gpu, "RUN_IMMEDIATELY"))
        self.assertEqual(gpu.RECEIPT, "road-asphalt-lit-review.json")
        self.assertEqual(gpu.FRAME_DEADLINE_SECONDS, 90)
        self.assertEqual(gpu.TOTAL_DEADLINE_SECONDS, 380)


if __name__ == "__main__":
    unittest.main()

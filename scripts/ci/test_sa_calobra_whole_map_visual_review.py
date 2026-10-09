"""CPU-only regression checks for fail-closed whole-map appearance triage."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.ci.sa_calobra_whole_map_visual_review import audit_near_views


class WholeMapVisualReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.proof = Path(self.temp.name)
        (self.proof / "frames").mkdir()
        self.rows = []
        for frame_id in ("near-landscape-1", "near-landscape-2"):
            for mode in ("baseline", "prepared", "checker"):
                self.set_image(frame_id, mode, (220, 220, 220))

    def set_image(self, frame_id, mode, color):
        relative = f"frames/{frame_id}-{mode}.png"
        Image.new("RGB", (8, 8), color).save(self.proof / relative)
        key = (frame_id, mode)
        self.rows = [r for r in self.rows if (r["frame_id"], r["mode"]) != key]
        self.rows.append(
            {
                "frame_id": frame_id,
                "mode": mode,
                "file": relative,
                "sha256": "a" * 64,
                "camera_location_cm": [100, 0, 250],
                "target_cm": [0, 0, 0],
                "camera_rotation_deg": [-68, 180, 0],
                "fov_deg": 60,
            }
        )

    def scan(self):
        return audit_near_views(
            self.proof, self.rows, ("near-landscape-1", "near-landscape-2"), (8, 8)
        )

    def test_prepared_only_blackout_is_review_required_but_not_geometry_proof(self):
        self.set_image("near-landscape-2", "prepared", (0, 0, 0))
        report = self.scan()
        self.assertEqual(report["status"], "VISUAL_REVIEW_REQUIRED")
        self.assertEqual(report["flagged_views"], ["near-landscape-2"])
        self.assertEqual(report["observations"][1]["prepared_only_dark_fraction"], 1)
        self.assertEqual(report["visual_acceptance"], "PENDING_OWNER")
        self.assertFalse(report["production_material_update_authorized"])
        self.assertIn("Does not prove rendered pixel depth", report["scope"])

    def test_dark_baseline_or_checker_do_not_support_prepared_only_claim(self):
        for control in ("baseline", "checker"):
            with self.subTest(control=control):
                self.set_image("near-landscape-2", "prepared", (0, 0, 0))
                self.set_image("near-landscape-2", control, (0, 0, 0))
                report = self.scan()
                self.assertEqual(report["flagged_views"], [])
                self.set_image("near-landscape-2", control, (220, 220, 220))

    def test_identical_clean_frames_do_not_flag(self):
        self.assertEqual(self.scan()["status"], "NO_LARGE_PREPARED_ONLY_BLACKOUT")

    def test_missing_corrupt_mismatched_or_tampered_frame_fails(self):
        relative = self.proof / "frames/near-landscape-2-prepared.png"
        relative.unlink()
        with self.assertRaisesRegex(ValueError, "Missing or symlinked"):
            self.scan()
        relative.write_bytes(b"not a PNG")
        with self.assertRaises(Exception):
            self.scan()
        self.set_image("near-landscape-2", "prepared", (0, 0, 0))
        self.rows[-1]["camera_location_cm"] = [900, 900, 900]
        with self.assertRaisesRegex(ValueError, "unequal camera"):
            self.scan()

    def test_duplicate_frame_key_and_bad_dimensions_rejected(self):
        self.rows.append(dict(self.rows[0]))
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            self.scan()
        self.rows.pop()
        relative = self.proof / "frames/near-landscape-2-prepared.png"
        Image.new("RGB", (10, 10), (10, 10, 10)).save(relative)
        with self.assertRaisesRegex(ValueError, "dimensions"):
            self.scan()


if __name__ == "__main__":
    unittest.main()

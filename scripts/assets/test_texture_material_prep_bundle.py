import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from texture_material_prep_bundle import ROLES, inspect_bundle, inspect_reopen


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        job = "a" * 32
        folder = f"/Game/Generated/YACS/TextureMaterialPrep/Runs/{job}"
        self.receipt = {
            "job_id": job,
            "status": "exported_review_required",
            "engine_version": "5.8.2-test-fixture",
            "graph_asset": folder + "/TG.TG",
            "output_folder": folder,
            "recipe": {"resolution": 128, "worldSizeMeters": {"x": 2, "y": 4}},
            "outputs": {
                role: {
                    "file": role + ".png",
                    "asset": f"{folder}/{role}.{role}",
                    "srgb": role == "BaseColor",
                }
                for role in ROLES
            },
        }
        for role in (*ROLES, "Source"):
            color = (128, 128, 255) if role == "Normal" else (128, 128, 128)
            Image.new("RGB", (128, 128), color).save(self.path / (role + ".png"))

    def inspect(self):
        (self.path / "ue-receipt.json").write_text(
            json.dumps(self.receipt), encoding="utf-8"
        )
        return inspect_bundle(self.path)

    def test_metrics_keep_data_linear_and_never_admit(self):
        report, _ = self.inspect()
        self.assertEqual(report["admission"], "review_required")
        self.assertEqual(report["scale"]["pixels_per_meter"], [64, 32])
        self.assertLess(
            report["outputs"]["Normal"]["normal"]["unit_length_error_max"], 0.001
        )
        self.assertEqual(report["outputs"]["Height"]["encoding"], "linear")
        self.assertEqual(
            report["outputs"]["Height"]["identity"]["transfer"],
            "linear declared by caller",
        )

    def test_missing_or_wrong_role_rejected(self):
        del self.receipt["outputs"]["Height"]
        with self.assertRaisesRegex(ValueError, "role"):
            self.inspect()

    def test_constant_black_failure_detected_even_when_ue_reported_success(self):
        varied = np.full((128, 128, 3), 20, dtype=np.uint8)
        varied[:, 64:] = 200
        Image.fromarray(varied).save(self.path / "Source.png")
        Image.new("RGB", (128, 128), (0, 0, 0)).save(self.path / "BaseColor.png")
        report, _ = self.inspect()
        self.assertEqual(report["technical_validation"], "failed")
        self.assertTrue(report["failures"])

    def test_path_escape_rejected(self):
        self.receipt["outputs"]["Height"]["file"] = "../Source.png"
        with self.assertRaisesRegex(ValueError, "path"):
            self.inspect()

    def test_wrong_color_space_rejected(self):
        self.receipt["outputs"]["Height"]["srgb"] = True
        with self.assertRaisesRegex(ValueError, "color space"):
            self.inspect()

    def test_wrong_dimensions_rejected(self):
        Image.new("RGB", (64, 128)).save(self.path / "Height.png")
        with self.assertRaisesRegex(ValueError, "resolution"):
            self.inspect()

    def test_bad_world_scale_rejected(self):
        self.receipt["recipe"]["worldSizeMeters"]["x"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite"):
            self.inspect()

    def test_normal_wrap_angle_detects_flipped_tangent(self):
        pixels = np.full((128, 128, 3), (128, 128, 255), dtype=np.uint8)
        pixels[:, 0] = (255, 128, 128)
        pixels[:, -1] = (0, 128, 128)
        Image.fromarray(pixels).save(self.path / "Normal.png")
        report, _ = self.inspect()
        self.assertGreater(
            report["outputs"]["Normal"]["normal"]["wrap_angles"]["x"]["max_deg"], 179
        )

    def test_reopen_requires_exact_decoded_pixels_and_job(self):
        report, pixels = self.inspect()
        (self.path / "reopen.json").write_text(
            json.dumps(
                {"job_id": report["job_id"], "status": "reopened_settings_verified"}
            )
        )
        result = inspect_reopen(self.path, report["job_id"], pixels)
        self.assertEqual(result["status"], "verified_pixels_and_settings")
        changed = pixels["Height"].copy()
        changed[0, 0, 0] += 1
        Image.fromarray(changed).save(self.path / "Height.png")
        with self.assertRaisesRegex(ValueError, "pixels differ"):
            inspect_reopen(self.path, report["job_id"], pixels)


if __name__ == "__main__":
    unittest.main()

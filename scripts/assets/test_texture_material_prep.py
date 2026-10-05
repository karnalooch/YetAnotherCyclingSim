"""Synthetic evidence and safety checks; no UE, downloads or production assets."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

import numpy as np
from PIL import Image

import texture_material_prep as prep


class TexturePrepTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "limestone-fixture.png"
        Image.new("RGB", (32, 32), (128, 128, 128)).save(self.source)

    def test_srgb_midpoint_is_linear_not_half_brightness(self):
        pixels, _ = prep.read_source(self.source)
        report = prep.analyze(pixels)
        self.assertAlmostEqual(report["luminance"]["mean"], 0.21586, places=5)

    def test_flat_tile_has_finite_json_and_no_fabricated_admission(self):
        report = prep.measure(np.full((16, 16, 3), 0.4))
        for axis in report["axes"].values():
            self.assertEqual(axis["boundary"]["mean"], 0)
            self.assertIsNone(axis["boundary_to_interior_ratio"])
        self.assertEqual(report["screening"]["status"], "within_provisional_limits")
        self.assertEqual(report["admission"], "review_required")
        json.dumps(report, allow_nan=False)

    def test_horizontal_and_vertical_ramps_detect_the_correct_seam(self):
        image = np.broadcast_to(np.linspace(0, 1, 32)[None, :, None], (32, 32, 3))
        x = prep.measure(image)
        y = prep.measure(image.swapaxes(0, 1))
        self.assertEqual(x["axes"]["x"]["boundary"]["mean"], 1)
        self.assertEqual(x["axes"]["y"]["boundary"]["mean"], 0)
        self.assertEqual(y["axes"]["y"], x["axes"]["x"])
        self.assertEqual(x["screening"]["status"], "review_required")

    def test_equal_edges_can_still_have_a_gradient_kink(self):
        image = np.full((32, 32, 3), 0.5)
        image[:, 1] = 0.9
        image[:, -2] = 0.1
        report = prep.measure(image)
        self.assertEqual(report["axes"]["x"]["boundary"]["mean"], 0)
        self.assertGreater(report["axes"]["x"]["wrap_gradient_mismatch"]["p95"], 0.39)
        self.assertIn("x: gradient mismatch", report["screening"]["reasons"])

    def test_periodic_samples_do_not_require_equal_endpoint_texels(self):
        row = 0.5 + 0.1 * np.sin(np.arange(256) * 2 * np.pi / 256)
        report = prep.measure(np.broadcast_to(row[None, :, None], (16, 256, 3)))
        self.assertGreater(report["axes"]["x"]["boundary"]["mean"], 0)
        self.assertLess(report["axes"]["x"]["wrap_gradient_mismatch"]["p95"], 0.00001)

    def test_delight_diagnostics_do_not_claim_recovered_albedo(self):
        before = prep.measure(np.full((16, 16, 3), 0.2))
        after = prep.measure(np.full((16, 16, 3), 0.4))
        result = prep.compare_luminance(before, after)
        self.assertIn("mean_drift", result["flags"])
        self.assertFalse(result["physical_delighting_proven"])
        zero = prep.compare_luminance(prep.measure(np.zeros((8, 8, 3))), after)
        self.assertIsNone(zero["mean_relative_drift"])
        json.dumps(zero, allow_nan=False)

    def test_luminance_plane_detects_directional_gradient(self):
        a = np.broadcast_to(np.linspace(0.2, 0.8, 32)[None, :, None], (32, 32, 3))
        luma = prep.measure(a)["luminance"]
        self.assertGreater(luma["plane_explained_variance"], 0.99)
        self.assertGreater(luma["column_mean_range"], 0.59)
        self.assertLess(luma["row_mean_range"], 0.000001)

    def test_invalid_numeric_inputs_fail_closed(self):
        for value in (float("nan"), float("inf"), -0.1, 1.1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                prep.measure(np.full((8, 8, 3), value))
        with self.assertRaises(ValueError):
            prep.measure(np.zeros((8, 8)))

    def test_profile_alpha_and_unsupported_dimensions_are_rejected(self):
        variants = [
            ("RGBA", (8, 8), (128, 128, 128, 127), {}),
            ("RGB", (8, 8), (128, 128, 128), {"icc_profile": b"unverified-profile"}),
            ("RGB", (7, 8), (128, 128, 128), {}),
        ]
        for mode, size, color, options in variants:
            Image.new(mode, size, color).save(self.source, **options)
            with self.assertRaises(ValueError):
                prep.read_source(self.source)

    def test_rgb16_png_is_rejected_before_pillow_downconverts(self):
        def chunk(kind, data):
            return (
                struct.pack(">I", len(data))
                + kind
                + data
                + struct.pack(">I", zlib.crc32(kind + data))
            )

        raw = (b"\x00" + struct.pack(">HHH", 0, 32768, 65535) * 8) * 8
        png = (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 16, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b"")
        )
        self.source.write_bytes(png)
        with self.assertRaisesRegex(ValueError, "bit depth"):
            prep.read_source(self.source)

    def test_recipe_is_deterministic_but_never_executable(self):
        _, source = prep.read_source(self.source)
        a = prep.prepare_recipe(source, {"DeLightStrength": 0.25, "Seed": 4})
        b = prep.prepare_recipe(source, {"Seed": 4, "DeLightStrength": 0.25})
        self.assertEqual(a["draft_recipe_id"], b["draft_recipe_id"])
        self.assertEqual(a["status"], "blocked")
        self.assertIsNone(a["execution_identity"])
        self.assertEqual(a["scale"]["status"], "unresolved")
        c = prep.prepare_recipe(source, {"Seed": 5}, world_size=[2, 2])
        self.assertNotEqual(a["draft_recipe_id"], c["draft_recipe_id"])
        self.assertEqual(c["scale"]["pixels_per_meter"], [256, 256])
        self.assertEqual(c["scale"]["status"], "proposed")

    def test_parameter_and_scale_errors_are_rejected(self):
        _, source = prep.read_source(self.source)
        for params in (
            {"Path": "../../Content"},
            {"NormalStrength": float("nan")},
            {"Seed": True},
            {"Seed": 1.5},
            {"GenerateAO": 0},
            {"RoughnessMin": 0.9, "RoughnessMax": 0.5},
            {"ColorGain": [1, 1]},
            {"ColorGain": [1, 1, 3]},
        ):
            with self.subTest(params=params), self.assertRaises(ValueError):
                prep.prepare_recipe(source, params)
        for scale in ([0, 1], [float("inf"), 1], [True, 1], [1]):
            with self.assertRaises(ValueError):
                prep.scale_metadata(scale, 512, 512)

    def test_new_runs_and_exclusive_writes_preserve_existing_bytes(self):
        run = prep.new_evidence_directory(self.root)
        other = prep.new_evidence_directory(self.root)
        self.assertNotEqual(run, other)
        target = run / "existing.json"
        prep.write_json(target, {"original": True})
        before = target.read_bytes()
        with self.assertRaises(FileExistsError):
            prep.write_json(target, {"overwrite": True})
        self.assertEqual(target.read_bytes(), before)

    def test_capabilities_never_infer_running_plugins_from_descriptors(self):
        engine = self.root / "engine"
        (engine / "Engine/Build").mkdir(parents=True)
        (engine / "Engine/Build/Build.version").write_text(
            '{"MajorVersion":5,"MinorVersion":8,"PatchVersion":2}'
        )
        project = self.root / "Project.uproject"
        project.write_text('{"Plugins":[{"Name":"TextureGraph","Enabled":true}]}')
        result = prep.inspect_capabilities(project, engine)
        self.assertTrue(result["plugins"]["TextureGraph"]["project_explicitly_enabled"])
        self.assertFalse(result["plugins"]["TextureGraph"]["installed"])
        self.assertFalse(result["runtime_reflection_verified"])
        self.assertEqual(result["status"], "blocked")

    def test_cli_creates_labeled_previews_and_hashes_without_touching_source(self):
        original = self.source.read_bytes()
        allocate = prep.new_evidence_directory
        with patch.object(
            prep, "new_evidence_directory", side_effect=lambda: allocate(self.root)
        ):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = prep.main(
                    [
                        "analyze",
                        "--source",
                        str(self.source),
                        "--input-color-space",
                        "srgb",
                        "--world-size-m",
                        "2",
                        "2",
                    ]
                )
        self.assertEqual(code, 0)
        run = Path(output.getvalue().strip())
        receipt = json.loads((run / "receipt.json").read_text())
        for name, sha in receipt["files"].items():
            self.assertEqual(prep.digest((run / name).read_bytes()), sha)
        for name in (
            "tiling-2x2.png",
            "tiling-4x4.png",
            "seam-x-1to1.png",
            "corner-1to1.png",
        ):
            with Image.open(run / name) as image:
                self.assertLessEqual(max(image.size), 1066)
        self.assertEqual(self.source.read_bytes(), original)
        report = json.loads((run / "analyze.json").read_text())
        self.assertEqual(report["ue_validation"], "not_run")

    def test_cli_rejects_mismatched_baseline_without_evidence_writes(self):
        baseline = self.root / "different.png"
        Image.new("RGB", (16, 16)).save(baseline)
        with patch.object(prep, "new_evidence_directory") as allocate:
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                code = prep.main(
                    [
                        "analyze",
                        "--source",
                        str(self.source),
                        "--baseline",
                        str(baseline),
                        "--input-color-space",
                        "srgb",
                    ]
                )
        self.assertEqual(code, 2)
        self.assertIn("dimensions must match", errors.getvalue())
        allocate.assert_not_called()


if __name__ == "__main__":
    unittest.main()

"""Verify that missing evidence, footprints and subpixel clearance reject points."""

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from scripts.assets.prepare_sa_calobra_pcg_masks import selectors, verified_manifest
from scripts.assets.read_sa_calobra_pcg_masks import evaluate


class PcgMaskTests(unittest.TestCase):
    def test_invalid_height_blocks_high_but_keeps_observed_low_class(self):
        counts = np.zeros((6, 2, 2), dtype=np.uint32)
        counts[1, 0, 0] = 1
        counts[3, 0, 0] = 2
        counts[2, 1, 0] = 1
        result = selectors(
            counts,
            np.array([[1, 0], [0, 0]], dtype=np.uint8),
            np.array([[False, False], [True, False]]),
        )
        np.testing.assert_array_equal(result[:, 0, 0], [1, 0, 0])
        np.testing.assert_array_equal(result[:, 1, 0], [0, 0, 0])
        np.testing.assert_array_equal(result[:, 0, 1], [255, 255, 255])

    def test_asset_footprint_and_subpixel_offset_reduce_clearance(self):
        bands = np.ones((3, 10, 10), dtype=np.uint8)
        distance = np.full((10, 10), 0.25, dtype=np.float32)
        self.assertTrue(evaluate(bands, distance, 200, 200, 0, 0.1, 0.1)["selected"])
        self.assertFalse(evaluate(bands, distance, 224, 200, 0, 0.1, 0.1)["selected"])
        self.assertFalse(evaluate(bands, distance, 0, 0, 0, 0.3, 0)["selected"])
        self.assertFalse(evaluate(bands, distance, -26, 200, 0, 0.1, 0)["selected"])
        bands[0, 4, 4] = 255
        self.assertEqual(
            evaluate(bands, distance, 200, 200, 0, 0.1, 0)["reason"], "unknown"
        )

    def test_no_implicit_asset_radius_or_nan_clearance(self):
        for radius, clearance in [(0, 0), (0.5, float("nan")), (-1, 0), (0.5, -1)]:
            with self.assertRaises(ValueError):
                evaluate(
                    np.ones((3, 2, 2)), np.ones((2, 2)), 0, 0, 0, radius, clearance
                )

    def test_stale_manifest_rejected_before_loading_products(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "manifest.json"
            path.write_text(
                json.dumps({"fingerprint": "0" * 64, "geometry_mutation": False}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Stale"):
                verified_manifest(path)


if __name__ == "__main__":
    unittest.main()

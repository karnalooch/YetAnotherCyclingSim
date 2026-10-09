"""Do not admit candidates against a cold, near-black reference frame."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from scripts.assets.analyze_sa_calobra_component230_cliff_visual import (
    baseline_readiness,
    image_metrics,
)


class BaselineReadinessTests(unittest.TestCase):
    def measure(self, image):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "reference.png"
            Image.fromarray(image).save(path)
            return baseline_readiness(image_metrics(path))

    def test_cold_connected_cavity_rejected(self):
        image = np.full((128, 128, 3), 180, dtype=np.uint8)
        image[20:90, 20:90] = 0
        result = self.measure(image)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["large_near_black_regions"], 1)

    def test_small_isolated_dark_details_remain_allowed(self):
        image = np.full((128, 128, 3), 180, dtype=np.uint8)
        image[::3, ::3] = 0
        self.assertEqual(self.measure(image)["status"], "PASS")

    def test_normal_shadow_is_not_a_near_black_cavity(self):
        image = np.full((128, 128, 3), 30, dtype=np.uint8)
        self.assertEqual(self.measure(image)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()

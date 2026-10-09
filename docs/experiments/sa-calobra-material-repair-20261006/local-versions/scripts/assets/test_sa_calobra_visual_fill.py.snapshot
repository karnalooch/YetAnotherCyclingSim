"""Bounded visual inference must not become placement or cross hard barriers."""

import unittest

import numpy as np

from scripts.assets.prepare_sa_calobra_visual_fill import repair


class VisualFillTests(unittest.TestCase):
    def test_gap_filled_without_mutating_evidence(self):
        weights = np.zeros((9, 9, 4), dtype=np.uint8)
        weights[..., 0] = 255
        available = np.full((9, 9), 255, dtype=np.uint8)
        available[4, 4] = 0
        weights[4, 4, 0] = 0
        original = weights.copy()
        result, kind = repair(weights, available, np.zeros((9, 9), dtype=np.uint16))
        self.assertEqual(result[4, 4, 0], 255)
        self.assertEqual(kind[4, 4], 1)
        self.assertEqual(available[4, 4], 0)
        np.testing.assert_array_equal(weights, original)

    def test_no_donor_crosses_road(self):
        weights = np.zeros((9, 9, 4), dtype=np.uint8)
        weights[:, :4, 1] = 255
        available = np.zeros((9, 9), dtype=np.uint8)
        available[:, :4] = 255
        reasons = np.zeros((9, 9), dtype=np.uint16)
        reasons[:, 4] = 1
        result, kind = repair(weights, available, reasons)
        self.assertFalse(result[:, 4:].any())
        self.assertTrue((kind[:, 5:] == 2).all())

    def test_bob_water_do_not_cut_shading(self):
        weights = np.zeros((5, 5, 4), dtype=np.uint8)
        weights[..., 2] = 255
        result, kind = repair(
            weights,
            np.full((5, 5), 255, dtype=np.uint8),
            np.full((5, 5), 4 | 16, dtype=np.uint16),
        )
        np.testing.assert_array_equal(result, weights)
        self.assertTrue((kind == 0).all())

    def test_all_unknown_stays_neutral(self):
        result, kind = repair(
            np.zeros((5, 5, 4), dtype=np.uint8),
            np.zeros((5, 5), dtype=np.uint8),
            np.full((5, 5), 128, dtype=np.uint16),
        )
        self.assertFalse(result.any())
        self.assertTrue((kind == 2).all())

    def test_weights_normalized_alpha_preserved_and_distance_bounded(self):
        weights = np.zeros((9, 20, 4), dtype=np.uint8)
        weights[:, 0, :3] = [85, 85, 85]
        weights[..., 3] = 72
        available = np.zeros((9, 20), dtype=np.uint8)
        available[:, 0] = 255
        result, kind = repair(weights, available, np.zeros((9, 20), dtype=np.uint16))
        self.assertTrue((result[..., :3].sum(axis=2) <= 255).all())
        np.testing.assert_array_equal(result[..., 3], weights[..., 3])
        self.assertTrue((kind[:, 9:] == 2).all())


if __name__ == "__main__":
    unittest.main()

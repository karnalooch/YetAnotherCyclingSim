"""Protect evidence boundaries in the 2B presentation-only material adapter."""

import unittest
import numpy as np
from scripts.assets.prepare_sa_calobra_material_inputs import blend_weights


class MaterialInputTests(unittest.TestCase):
    def test_visual_filter_preserves_exact_holdbacks_and_unknowns(self):
        selectors = np.zeros((3, 7, 7), dtype=np.uint8)
        selectors[0, :, :3] = 1
        selectors[:, 3, 2] = 255
        reasons = np.zeros((7, 7), dtype=np.uint16)
        reasons[3, 1] = 1
        values = blend_weights(selectors, reasons, np.zeros((7, 7)), blend_radius=2)
        self.assertEqual(int(values[3, 1, :3].sum()), 0)
        self.assertEqual(int(values[3, 2].sum()), 0)
        self.assertGreater(values[2, 3, 0], 0)
        self.assertLess(values[2, 3, 0], 255)
        self.assertTrue(np.all(values[..., :3].astype(np.uint16).sum(axis=2) <= 255))
        with self.assertRaises(ValueError):
            blend_weights(selectors, reasons, np.zeros((7, 7)), blend_radius=3)

    def test_unknown_and_every_hard_exclusion_cannot_gain_material_evidence(self):
        reasons = np.array([[0, 1, 2, 4, 8, 16, 32, 64, 128, 65535]], dtype=np.uint16)
        selectors = np.ones((3, 1, 10), dtype=np.uint8)
        values = blend_weights(selectors, reasons, np.full((1, 10), 0.6))
        self.assertTrue(np.all(values[0, 1:, :3] == 0))
        self.assertTrue(np.all(values[0, 8:, 3] == 0))
        selectors[:, 0, 0] = 255
        values = blend_weights(selectors, reasons, np.full((1, 10), 0.6))
        self.assertTrue(np.all(values[0, 0] == 0))

    def test_overlapping_vegetation_does_not_add_or_invent_rock(self):
        selectors = np.array([[[1, 1, 0]], [[0, 1, 0]], [[0, 1, 0]]], dtype=np.uint8)
        reasons = np.zeros((1, 3), dtype=np.uint16)
        rock = np.array([[0.8, 0.8, 0.2]], dtype=np.float32)
        before = selectors.copy()
        actual = blend_weights(selectors, reasons, rock)
        np.testing.assert_array_equal(
            actual, [[[255, 0, 0, 255], [0, 255, 0, 255], [0, 0, 51, 255]]]
        )
        np.testing.assert_array_equal(selectors, before)

    def test_missing_historical_rock_stays_neutral(self):
        actual = blend_weights(
            np.zeros((3, 1, 1), dtype=np.uint8),
            np.zeros((1, 1), dtype=np.uint16),
            np.array([[-32767]], dtype=np.float32),
        )
        np.testing.assert_array_equal(actual, [[[0, 0, 0, 255]]])

    def test_invalid_evidence_fails_before_packing(self):
        selectors = np.zeros((3, 1, 1), dtype=np.uint8)
        reasons = np.zeros((1, 1), dtype=np.uint16)
        for rock in (np.nan, np.inf, -0.1, 1.1):
            with self.subTest(rock=rock), self.assertRaises(ValueError):
                blend_weights(selectors, reasons, np.array([[rock]]))
        with self.assertRaises(ValueError):
            blend_weights(selectors + 2, reasons, np.zeros((1, 1)))


if __name__ == "__main__":
    unittest.main()

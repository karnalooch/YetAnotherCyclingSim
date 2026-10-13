"""Protect unknown/exclusion semantics and raster-to-world registration."""

import unittest

import numpy as np

from scripts.assets.build_sa_calobra_spatial_treatment_plan import cell_edges, layers


class SpatialPlanTests(unittest.TestCase):
    def test_pixel_edges_preserve_native_sample_origin(self):
        self.assertEqual(cell_edges(0, 0), [-0.25, -0.25, 0.25, 0.25])
        self.assertEqual(cell_edges(4032, 4032), [2015.75, 2015.75, 2016.25, 2016.25])

    def test_unknown_is_not_maintained_or_candidate(self):
        result = layers(
            np.array([[255, 0, 1]]),
            np.array([[255, 0, 0]]),
            np.array([[False, False, False]]),
        )
        self.assertEqual(result["unknown"].tolist(), [[True, False, False]])
        self.assertEqual(result["maintained"].tolist(), [[False, True, False]])

    def test_protected_candidate_fails_closed(self):
        with self.assertRaises(ValueError):
            layers(np.array([[1]]), np.array([[0]]), np.array([[True]]))

    def test_road_only_display_retains_separate_exclusions(self):
        result = layers(
            np.array([[0, 0]]),
            np.array([[0, 0]]),
            np.array([[True, True]]),
            np.array([[True, False]]),
        )
        self.assertEqual(result["protected"].tolist(), [[True, False]])
        self.assertEqual(result["other_exclusions"].tolist(), [[False, True]])
        with self.assertRaises(ValueError):
            layers(
                np.array([[0, 1]]),
                np.array([[0, 0]]),
                np.array([[True, True]]),
                np.array([[True, False]]),
            )

    def test_invalid_selector_fails_closed(self):
        with self.assertRaises(ValueError):
            layers(np.array([[2]]), np.array([[0]]), np.array([[False]]))

    def test_overlapping_candidates_fail_closed(self):
        with self.assertRaises(ValueError):
            layers(np.array([[1]]), np.array([[1]]), np.array([[False]]))


if __name__ == "__main__":
    unittest.main()

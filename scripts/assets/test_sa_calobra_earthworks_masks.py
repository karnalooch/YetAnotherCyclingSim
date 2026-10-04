import unittest

import numpy as np

from scripts.assets.prepare_sa_calobra_earthworks_masks import NODATA, accumulate_patch


class EarthworksMasksTests(unittest.TestCase):
    def setUp(self):
        self.base = np.full((3, 4), 100, dtype=np.float32)
        self.depth = np.full((3, 4), NODATA, dtype=np.float32)
        self.rect = dict(min_x=1, min_y=1, max_x=2, max_y=1, width=2, height=1)

    def test_centimetres_overlap_and_encoding_bound(self):
        accumulate_patch(self.depth, self.base, np.array([[9900, 10000.5]]), self.rect)
        np.testing.assert_allclose(self.depth[1, 1:3], [0.993, 0])
        accumulate_patch(self.depth, self.base, np.array([[9950, 9800]]), self.rect)
        np.testing.assert_allclose(self.depth[1, 1:3], [0.993, 1.993])
        self.assertEqual(self.depth[0, 0], NODATA)
        np.testing.assert_array_equal(self.base, np.full((3, 4), 100))

    def test_unknown_ground_preserved(self):
        self.base[1, 1] = NODATA
        accumulate_patch(self.depth, self.base, np.array([[9900, 9900]]), self.rect)
        self.assertEqual(self.depth[1, 1], NODATA)

    def test_unsupported_raise_and_nonfinite_rejected(self):
        for target in [np.array([[10001, 9900]]), np.array([[np.nan, 9900]])]:
            with self.assertRaises(ValueError):
                accumulate_patch(self.depth, self.base, target, self.rect)

    def test_bounds_and_dimensions_rejected(self):
        with self.assertRaises(ValueError):
            accumulate_patch(self.depth, self.base, np.zeros((2, 2)), self.rect)
        self.rect["max_x"] = 4
        with self.assertRaises(ValueError):
            accumulate_patch(self.depth, self.base, np.zeros((1, 2)), self.rect)

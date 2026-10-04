import unittest
import numpy as np
from scripts.assets.prepare_sa_calobra_mask_review import uv_at_xy, diagnostic_classes


class MaskReviewTests(unittest.TestCase):
    def test_pixel_centers_do_not_have_half_pixel_shift(self):
        for cell in (0, 2016, 4032):
            uv = uv_at_xy(cell * 50, cell * 50)
            self.assertAlmostEqual(uv[0] * 4033 - 0.5, cell)
            self.assertAlmostEqual(uv[1] * 4033 - 0.5, cell)

    def test_amber_is_relief_review_not_error(self):
        np.testing.assert_array_equal(
            diagnostic_classes(np.array([[10.0, 81.0]]), np.array([[0, 0]])), [[0, 1]]
        )

    def test_building_and_unknown_priority(self):
        np.testing.assert_array_equal(
            diagnostic_classes(
                np.array([[81.0, 81.0, np.nan, -32767.0]]), np.array([[1, 255, 1, 0]])
            ),
            [[2, 3, 3, 3]],
        )

    def test_unknown_building_value_fails_closed(self):
        with self.assertRaises(ValueError):
            diagnostic_classes(np.zeros((1, 1)), np.array([[4]]))

    def test_dimensions_fail_closed(self):
        with self.assertRaises(ValueError):
            diagnostic_classes(np.zeros((1, 1)), np.zeros((2, 2)))


if __name__ == "__main__":
    unittest.main()

import unittest

from scripts.assets.prepare_ma2141_cut_patch import (
    GRID_STEP_M,
    NEUTRAL_HEIGHT,
    _encode_delta_m,
    _inside_triangle,
)


class Ma2141CutPatchTests(unittest.TestCase):
    def test_triangle_interpolation_accepts_inside_and_rejects_outside(self):
        tri = ((0.0, 0.0, 10.0), (1.0, 0.0, 11.0), (0.0, 1.0, 12.0))
        self.assertAlmostEqual(_inside_triangle(0.25, 0.25, tri), 10.75)
        self.assertIsNone(_inside_triangle(0.75, 0.75, tri))

    def test_cut_delta_encoding_is_neutral_at_zero_and_below_neutral_for_cut(self):
        manifest = {"scale_z": 100.0}
        self.assertEqual(_encode_delta_m(0.0, manifest), NEUTRAL_HEIGHT)
        self.assertLess(_encode_delta_m(-0.5, manifest), NEUTRAL_HEIGHT)

    def test_native_grid_contract_remains_half_meter(self):
        self.assertEqual(GRID_STEP_M, 0.5)


if __name__ == "__main__":
    unittest.main()

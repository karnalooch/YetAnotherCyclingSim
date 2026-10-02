import unittest

from scripts.assets.prepare_ma2141_cut_patch import (
    GRID_STEP_M,
    _inside_triangle,
    _patch_bounds,
    _world_height_cm,
)


class Ma2141CutPatchTests(unittest.TestCase):
    def test_triangle_interpolation_accepts_inside_and_rejects_outside(self):
        tri = ((0.0, 0.0, 10.0), (1.0, 0.0, 11.0), (0.0, 1.0, 12.0))
        self.assertAlmostEqual(_inside_triangle(0.25, 0.25, tri), 10.75)
        self.assertIsNone(_inside_triangle(0.75, 0.75, tri))

    def test_world_height_patch_uses_centimeters(self):
        manifest = {"scale_z": 128.0, "location_z_cm": 10000.0}
        self.assertAlmostEqual(_world_height_cm(32768, manifest), 10000.0)
        # UE height decoding is (encoded - 32768) * scale_z / 128 cm.
        self.assertAlmostEqual(_world_height_cm(32769, manifest), 10001.0)
        self.assertAlmostEqual(_world_height_cm(32896, manifest), 10128.0)
        self.assertAlmostEqual(_world_height_cm(32767, manifest), 9999.0)

    def test_requested_edge_vertices_are_inside_texture_coverage(self):
        # Native run 37048303292 left its westernmost requested vertex uncut.
        requested = {(2088, 1147): 598.75, (2089, 1148): 598.70}
        left, right, top, bottom = _patch_bounds(requested)
        for x, y in requested:
            self.assertLess(left, x)
            self.assertLess(x, right)
            self.assertLess(top, y)
            self.assertLess(y, bottom)

    def test_boundary_request_without_room_for_neutral_texel_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "neutral native texel"):
            _patch_bounds({(0, 1): 10.0})

    def test_native_grid_contract_remains_half_meter(self):
        self.assertEqual(GRID_STEP_M, 0.5)


if __name__ == "__main__":
    unittest.main()

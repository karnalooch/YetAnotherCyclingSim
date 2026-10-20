"""Host-side numeric regression checks for L07 tiled Landscape geometry."""
import unittest

import numpy as np

from scripts.houdini.l07_tile_invariants import (
    compare_all_four,
    compare_edge,
    interpolate_bilinear,
    mask_padding,
)


def synthetic_tiles():
    result = {}
    for iy in (0, 1):
        for ix in (0, 1):
            x0, z0 = 2 * ix - 2, 2 * iy - 2
            xx, zz = np.meshgrid(np.linspace(x0, x0 + 2, 3),
                                 np.linspace(z0, z0 + 2, 3))
            data = (10 * xx + 3 * zz).astype(np.float32)
            result[(ix, iy)] = (data, (x0, 0, z0), (x0 + 2, 0, z0 + 2))
    return result


class L07NativeInvariants(unittest.TestCase):
    def test_exact_world_aligned_seams(self):
        stats = compare_all_four(synthetic_tiles())
        self.assertEqual(len(stats), 4)
        self.assertTrue(all(s["sample_error"] == 0 for s in stats.values()))

    def test_reversed_volume_storage_does_not_create_false_seam(self):
        tiles = synthetic_tiles()
        a, first, last = tiles[(0, 0)]
        tiles[(0, 0)] = (a[::-1, :], (first[0], 0, last[2]),
                          (last[0], 0, first[2]))
        stats = compare_all_four(tiles)
        self.assertEqual(stats["z_west"]["sample_error"], 0)

    def test_sample_values_equal_but_world_positions_wrong(self):
        tiles = synthetic_tiles()
        a, start, end = tiles[(1, 0)]
        tiles[(1, 0)] = (a, (0.5, 0, -2), (2.5, 0, 0))
        with self.assertRaisesRegex(ValueError, "world-coordinate mismatch"):
            compare_all_four(tiles)

    def test_float32_world_position_roundoff_is_not_a_height_seam(self):
        first = synthetic_tiles()[(0, 0)]
        data, start, end = synthetic_tiles()[(1, 0)]
        second = (data, (0.000244140625, 0, -2), (2.000244140625, 0, 0))
        result = compare_edge(first, second, "east", "west")
        self.assertLess(result["position_error_m"], 0.0005)
        self.assertEqual(result["sample_error"], 0)

    def test_subcentimeter_vertical_discontinuity_fails(self):
        tiles = synthetic_tiles()
        a, start, end = tiles[(1, 0)]
        altered = a.copy()
        altered[:, 0] += np.float32(0.01)
        tiles[(1, 0)] = (altered, start, end)
        with self.assertRaisesRegex(ValueError, "voxel mismatch"):
            compare_all_four(tiles)

    def test_outer_padding_cannot_survive_alpha_transfer(self):
        mask = np.ones((5, 5), dtype=np.float32)
        output, padded = mask_padding(mask, (-2, 0, -2), (2, 0, 2),
                                      (-1, 1), (-1, 1))
        self.assertEqual(padded, 16)
        self.assertEqual(int(np.count_nonzero(output)), 9)
        self.assertEqual(float(output[0, 0]), 0)

    def test_native_255_alpha_is_normalized_to_binary_unit_visibility(self):
        mask = np.full((5, 5), 255.0, dtype=np.float32)
        mask[2, 2] = 0
        output, padded = mask_padding(
            mask, (-2, 0, -2), (2, 0, 2), (-1, 1), (-1, 1)
        )
        self.assertEqual(padded, 16)
        self.assertEqual(float(output.max()), 1.0)
        self.assertEqual(float(output[2, 2]), 0.0)
        self.assertEqual(int(np.count_nonzero(output)), 8)

    def test_off_grid_point_requires_interpolation(self):
        tile, start, end = synthetic_tiles()[(1, 1)]
        self.assertAlmostEqual(
            interpolate_bilinear(tile, start, end, 0.25, 0.25), 3.25
        )

    def test_invalid_missing_tile_fails_closed(self):
        tiles = synthetic_tiles()
        del tiles[(1, 1)]
        with self.assertRaisesRegex(ValueError, "four"):
            compare_all_four(tiles)


if __name__ == "__main__":
    unittest.main()

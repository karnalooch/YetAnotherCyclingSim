import unittest
from unittest.mock import patch
import numpy as np
from scripts.worldgen import pcg365_wall_batches as wall


class WallBatchTests(unittest.TestCase):
    def test_shared_vertices_do_not_duplicate_cells(self):
        coverage=np.zeros((18,22),dtype=int)
        for r0,c0,r1,c1 in wall.batches((19,23),8):
            coverage[r0:r1,c0:c1]+=1
        np.testing.assert_array_equal(coverage,1)

    def test_texture_centres_keep_original_source_coordinates(self):
        for bounds in wall.batches((4033,4033)):
            transform=wall.texture_transform(bounds)
            for axis,lo,hi in [('x',bounds[1],bounds[3]),('y',bounds[0],bounds[2])]:
                self.assertEqual(transform['location'][axis]-transform['scale'][axis]+25,lo*50)
                self.assertEqual(transform['location'][axis]+transform['scale'][axis]-25,hi*50)

    def test_dense_readback_is_refused_before_a_tool_call(self):
        for count in [257, 100000, -1, 1.5, True]:
            with self.assertRaises(ValueError):
                wall.require_small_native_probe(count)
        wall.require_small_native_probe(256)

    def test_protected_and_unknown_samples_are_rejected(self):
        rgba = np.zeros((3, 3, 4), dtype=np.uint8)
        rgba[1, 1] = [13, 255, 0, 255]
        selected = rgba[:, :, 3] > 0
        clearance = np.full((3, 3), 135.0)
        reasons = np.zeros((3, 3), dtype=np.uint8)
        with patch.object(wall, 'GRID_SIZE', 3):
            wall.validate_pixels(rgba, selected, clearance, reasons)
            reasons[1, 1] = 1
            with self.assertRaisesRegex(ValueError, 'Protected'):
                wall.validate_pixels(rgba, selected, clearance, reasons)
            reasons[1, 1] = 0
            clearance[1, 1] = np.nan
            with self.assertRaisesRegex(ValueError, 'Unknown'):
                wall.validate_pixels(rgba, selected, clearance, reasons)

    def test_vegetation_bits_do_not_widen_protected_mask(self):
        rgba = np.zeros((3, 3, 4), dtype=np.uint8)
        rgba[1, 1] = [13, 255, 0, 255]
        selected = rgba[:, :, 3] > 0
        clearance = np.full((3, 3), 135.0)
        reasons = np.full((3, 3), 192, dtype=np.uint8)
        with patch.object(wall, 'GRID_SIZE', 3):
            wall.validate_pixels(rgba, selected, clearance, reasons)


if __name__ == '__main__':
    unittest.main()


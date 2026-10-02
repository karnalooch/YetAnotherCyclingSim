import unittest
import numpy as np
from scripts.assets.prepare_ma2141_diagnostic import sample_encoded, select_alignment


class Ma2141DiagnosticTests(unittest.TestCase):
    def test_real_source_hairpin_is_bounded_and_preserves_original_vertex(self):
        line, clip, station = select_alignment()
        self.assertAlmostEqual(clip.length, 300.0, places=7)
        self.assertTrue(clip.is_simple)
        self.assertLess(line.interpolate(station).distance(clip), 1e-8)
        self.assertAlmostEqual(station, 809.8444497192457, places=6)

    def test_bilinear_native_height_has_correct_northing_axis(self):
        heights = np.zeros((4033, 4033), dtype=np.uint16)
        heights[0, 0] = 32768
        heights[0, 1] = 32896
        heights[1, 0] = 33024
        heights[1, 1] = 33152
        manifest = {
            "origin_epsg_m": [1000, 2000],
            "scale_z": 100,
            "location_z_cm": 10000,
        }
        self.assertEqual(sample_encoded(heights, manifest, 1000.25, 1999.75), 101.5)
        with self.assertRaisesRegex(ValueError, "outside"):
            sample_encoded(heights, manifest, 1000, 2000.5)


if __name__ == "__main__":
    unittest.main()

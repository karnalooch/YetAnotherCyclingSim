import unittest
import tempfile
from pathlib import Path
import numpy as np
from scripts.assets.prepare_ma2141_diagnostic import (
    IGR_SOURCE,
    compare_igr_profile,
    sample_encoded,
    select_alignment,
)


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

    def test_igr_source_match_does_not_admit_raw_z_as_earthworks(self):
        _, clip, _ = select_alignment()
        points = [
            {"easting_m": p.x, "northing_m": p.y, "native_dtm_z_m": 600.0}
            for p in [clip.interpolate(s) for s in (0, 100, 200, 300)]
        ]
        review = compare_igr_profile(points)
        self.assertLess(review["max_xy_difference_m"], 1e-6)
        self.assertEqual(review["source_properties"]["surfacecategory"], "paved")
        self.assertEqual(review["vertical_datum"], "UNVERIFIED")
        self.assertFalse(review["earthwork_input_admitted"])
        self.assertFalse(review["physics_input_admitted"])
        # Older receipts contain coincident 150.0/150.00000000000023 samples.
        repeated = [points[0], points[1], points[1].copy(), *points[2:]]
        self.assertEqual(
            compare_igr_profile(repeated)["source_linear_profile_max_abs_slope"],
            review["source_linear_profile_max_abs_slope"],
        )
        with self.assertRaisesRegex(ValueError, "station order"):
            compare_igr_profile(list(reversed(points)))
        points[0]["easting_m"] += 20
        with self.assertRaisesRegex(ValueError, "XY does not match"):
            compare_igr_profile(points)

    def test_igr_source_mutation_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.json"
            source.write_bytes(IGR_SOURCE.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                compare_igr_profile([], source)


if __name__ == "__main__":
    unittest.main()

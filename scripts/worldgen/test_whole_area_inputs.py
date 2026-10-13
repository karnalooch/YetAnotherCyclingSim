"""Source-mask and exclusion-envelope boundaries for the whole-area adapter."""
import math
import unittest
import numpy as np
from scripts.worldgen.build_pcg365_world import pcgex_records
from scripts.worldgen.pcg365_whole_area import input_radius
from scripts.worldgen.pcg365_pcgex_graph import available_extent_cm

class WholeAreaInputs(unittest.TestCase):
    def test_cliff_resolution_never_expands_or_fills_the_source_mask(self):
        cliff = np.zeros((17, 17), dtype=np.uint8)
        scree = cliff.copy()
        reasons = cliff.copy()
        slope = np.full(cliff.shape, 65.)
        treatment = np.full((3, 3), 2, dtype=np.uint8)
        cliff[0, 0] = cliff[8, 8] = cliff[16, 16] = cliff[7, 8] = 1
        reasons[8, 8] = 128
        records = pcgex_records(cliff, scree, reasons, slope, treatment,
                                np.full(cliff.shape, 100.), kind="cliff", stride=8)
        self.assertEqual(records, [[0, 0, 65., 25.], [16, 16, 65., 25.]])
        scree[16, 16] = 255
        self.assertEqual(len(pcgex_records(cliff, scree, reasons, slope, treatment,
                         np.full(cliff.shape, 100.), kind="cliff", stride=8)), 1)

    def test_cliff_mask_requires_matching_treatment_and_valid_source(self):
        cliff = np.ones((8, 8), dtype=np.uint8)
        other = np.zeros_like(cliff)
        slope = np.full(cliff.shape, 65.)
        for treatment, value in [(3, 65.), (2, np.nan), (2, -1.), (2, 91.)]:
            slope[:] = value
            self.assertEqual(pcgex_records(cliff, other, other, slope,
                np.array([[treatment]], dtype=np.uint8), np.full(cliff.shape, 100.),
                kind="cliff", stride=8), [])

    def test_clearance_bounds_keep_every_corner_inside_source_exclusion_distance(self):
        policy = {"source_clearance_cm": 50., "embed_along_normal_cm": 5.}
        for distance in [55.001, 100., 465., 1515.]:
            extent = available_extent_cm(distance, policy)
            self.assertAlmostEqual(math.sqrt(3 * extent ** 2) + 5 + 50, distance)
        self.assertEqual(available_extent_cm(54., policy), 0.)

    def test_final_exclusion_envelope_includes_seating_offset(self):
        assets = [{"expected_native_bounds_cm": {"min": [-3, -4, -2], "max": [1, 1, 12]}}]
        policy = {"embed_along_normal_cm": 5., "seat_offset": [0, 120, -200]}
        self.assertAlmostEqual(input_radius(assets, policy), 13 + math.hypot(120, 200))

if __name__ == "__main__":
    unittest.main()

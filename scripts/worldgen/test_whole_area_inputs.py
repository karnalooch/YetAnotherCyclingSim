"""Source-mask and exclusion-envelope boundaries for the whole-area adapter."""
import math
import unittest
from unittest.mock import patch
import numpy as np
from scripts.worldgen.build_pcg365_world import pcgex_records, cliff_clearance
from scripts.worldgen.pcg365_whole_area import input_radius, update_world
from scripts.worldgen.pcg365_pcgex_graph import available_extent_cm, input_clearance_cm

class WholeAreaInputs(unittest.TestCase):
    def test_source_world_is_blocked_before_mcp_or_disk_mutation(self):
        with patch("scripts.worldgen.pcg365_whole_area.g.Author") as author:
            with patch("scripts.worldgen.pcg365_whole_area.save") as save:
                with self.assertRaisesRegex(ValueError, "WHOLE_AREA_NATIVE_BLOCKED_SOURCE_MAP"):
                    update_world("not-read", "not-read", "not-created", "not-read")
                author.assert_not_called()
                save.assert_not_called()


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

    def test_cliff_consumer_keeps_all_six_holdbacks_and_unknown_terrain(self):
        cliff = np.ones((8, 8), dtype=np.uint8)
        scree = np.zeros_like(cliff)
        reasons = np.zeros_like(cliff)
        slope = np.full(cliff.shape, 65.)
        reasons[0, :] = [1, 2, 4, 8, 16, 32, 64, 128]
        cliff[1, 0] = 255
        scree[1, 1] = 255
        slope[1, 2] = np.nan
        distance = cliff_clearance(cliff, scree, reasons, slope, 63)
        records = pcgex_records(cliff, scree, reasons, slope, np.array([[2]], dtype=np.uint8),
                                distance, kind="cliff", protected_bits=63)
        cells = {(r, c) for r, c, _, _ in records}
        self.assertEqual(len(cells), 64 - 6 - 3)
        self.assertIn((0, 6), cells)
        self.assertIn((0, 7), cells)
        self.assertTrue(np.all(distance[0, :6] == 0))
        self.assertTrue(np.all(distance[1, :3] == 0))
        self.assertGreater(distance[0, 7], 0)
        self.assertEqual(reasons[0, 7], 128)
        with self.assertRaisesRegex(ValueError, "Unsupported consumer"):
            pcgex_records(cliff, scree, reasons, slope, np.array([[2]], dtype=np.uint8),
                          distance, kind="scree", protected_bits=63)

    def test_mesh_footprint_caps_fit_without_expanding_exclusion_clearance(self):
        policy = {"source_clearance_cm": 50., "embed_along_normal_cm": 5., "fit_extent_cap_cm": 350.}
        for distance in [54., 100., 660., 9000.]:
            extent = available_extent_cm(distance, policy)
            trace = input_clearance_cm(distance, policy)
            self.assertLessEqual(extent, 350.)
            self.assertLessEqual(trace, distance)
            if distance >= 55.:
                self.assertAlmostEqual(math.sqrt(3) * extent + 55., trace)

    def test_final_exclusion_envelope_includes_seating_offset(self):
        assets = [{"expected_native_bounds_cm": {"min": [-3, -4, -2], "max": [1, 1, 12]}}]
        policy = {"embed_along_normal_cm": 5., "seat_offset": [0, 120, -200]}
        self.assertAlmostEqual(input_radius(assets, policy), 13 + math.hypot(120, 200))

if __name__ == "__main__":
    unittest.main()

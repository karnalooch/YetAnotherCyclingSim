"""Tests for the Component_230 Phase 2B connected cliff-skin plan."""

import unittest

import numpy as np

from scripts.assets.prepare_sa_calobra_component230_cliff_visual import (
    COMPONENT,
    _coarse_skin_cells,
    _representative,
    _supported_bridge,
    _unit_interval,
    build_plan,
)


class Component230CliffVisualPlanTests(unittest.TestCase):
    def test_stable_unit_interval(self):
        self.assertEqual(_unit_interval("a"), _unit_interval("a"))
        self.assertNotEqual(_unit_interval("a"), _unit_interval("b"))
        self.assertGreaterEqual(_unit_interval("a"), 0.0)
        self.assertLessEqual(_unit_interval("a"), 1.0)

    def test_representative_prefers_highest_score_then_spatial_order(self):
        mask = np.zeros((8, 8), dtype=bool)
        score = np.zeros((8, 8), dtype=np.float64)
        mask[2, 2] = True
        mask[2, 3] = True
        mask[3, 2] = True
        score[2, 3] = 5.0
        score[3, 2] = 5.0

        row, col, occupancy = _representative(mask, score, 0, 8, 0, 8)

        self.assertEqual((row, col), (2, 3))
        self.assertEqual(occupancy, 3)

    def test_supported_bridge_joins_only_source_backed_gap(self):
        seed = np.zeros((3, 5), dtype=bool)
        seed[1, 1] = True
        seed[1, 3] = True
        support = seed.copy()
        support[1, 2] = True

        joined = _supported_bridge(seed, support)

        self.assertTrue(joined[1, 2])
        self.assertEqual(int(joined.sum()), 3)

        unsupported = seed.copy()
        joined_without_source = _supported_bridge(seed, unsupported)
        self.assertFalse(joined_without_source[1, 2])

    def test_coarse_skin_cells_are_connected_and_fail_closed(self):
        rows = COMPONENT["row_max"] + 4
        cols = COMPONENT["col_max"] + 4
        cliff = np.zeros((rows, cols), dtype=bool)
        protected = np.zeros((rows, cols), dtype=bool)

        r0 = COMPONENT["row_min"] + 16
        c0 = COMPONENT["col_min"] + 16
        cliff[r0 : r0 + 25, c0 : c0 + 25] = True
        # One 2 m cell inside the cliff is hard-protected and must not appear.
        protected[r0 + 8 : r0 + 13, c0 + 8 : c0 + 13] = True

        cells, occupancy = _coarse_skin_cells(cliff, protected)

        self.assertGreater(len(cells), 1)
        self.assertGreater(int((occupancy > 0).sum()), 1)
        for cell in cells:
            block = protected[
                int(cell["row0"]) : int(cell["row1"]) + 1,
                int(cell["col0"]) : int(cell["col1"]) + 1,
            ]
            self.assertFalse(bool(block.any()))

    def test_synthetic_plan_is_deterministic_narrow_and_clustered(self):
        rows = COMPONENT["row_max"] + 4
        cols = COMPONENT["col_max"] + 4
        row_index, _col_index = np.indices((rows, cols))

        elevation = row_index.astype(np.float32) * 0.35
        slope = np.full((rows, cols), 10.0, dtype=np.float32)
        roughness = np.full((rows, cols), 0.1, dtype=np.float32)
        reasons = np.zeros((rows, cols), dtype=np.uint16)
        water = np.zeros((rows, cols), dtype=bool)

        # Seed distant hard authority so the conservative distance field is valid.
        reasons[10, 10] = 1
        water[20, 20] = True

        r0 = COMPONENT["row_min"] + 20
        c0 = COMPONENT["col_min"] + 20
        slope[r0 : r0 + 13, c0 : c0 + 13] = 64.0
        roughness[r0 : r0 + 13, c0 : c0 + 13] = 2.2

        # Adjacent moderate rough cells satisfy Phase 1 scree contract.
        slope[r0 : r0 + 13, c0 + 14 : c0 + 23] = 30.0
        roughness[r0 : r0 + 13, c0 + 14 : c0 + 23] = 0.9

        first = build_plan(elevation, slope, roughness, reasons, water)
        second = build_plan(
            elevation.copy(),
            slope.copy(),
            roughness.copy(),
            reasons.copy(),
            water.copy(),
        )

        self.assertEqual(first, second)
        self.assertGreater(first["counts"]["skin_cluster_count"], 0)
        self.assertGreater(first["counts"]["skin_cell_count"], 1)
        self.assertLess(
            first["counts"]["skin_cluster_count"],
            first["counts"]["skin_cell_count"],
        )
        self.assertGreaterEqual(first["counts"]["scree_rock_count"], 0)
        self.assertFalse(first["hard_policy"]["bob"])
        self.assertFalse(first["hard_policy"]["buildings"])
        self.assertFalse(first["hard_policy"]["infrastructure"])
        self.assertEqual(first["hard_policy"]["mapped_water_buffer_m"], 0.5)
        self.assertEqual(first["skin_contract"]["source_grid_step_m"], 1.0)


if __name__ == "__main__":
    unittest.main()

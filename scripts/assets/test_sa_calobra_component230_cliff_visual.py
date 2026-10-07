"""Tests for the Component_230 Phase 2B visual placement plan."""

import unittest

import numpy as np

from scripts.assets.prepare_sa_calobra_component230_cliff_visual import (
    COMPONENT,
    _patch_ids,
    _representative,
    _unit_interval,
    build_plan,
)
from scripts.assets.prepare_sa_calobra_cliff_erosion_handoff import label_components_8


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

    def test_patch_ids_are_stable_from_top_left_anchor(self):
        mask = np.zeros((6, 6), dtype=bool)
        mask[1, 1:3] = True
        mask[4, 4] = True
        labels = label_components_8(mask)

        first = _patch_ids(labels)
        second = _patch_ids(labels.copy())

        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        self.assertNotEqual(first[1], first[2])

    def test_synthetic_plan_is_deterministic_and_narrow(self):
        rows = COMPONENT["row_max"] + 4
        cols = COMPONENT["col_max"] + 4
        row_index, _col_index = np.indices((rows, cols))

        elevation = (row_index.astype(np.float32) * 0.6)
        slope = np.full((rows, cols), 10.0, dtype=np.float32)
        roughness = np.full((rows, cols), 0.1, dtype=np.float32)
        reasons = np.zeros((rows, cols), dtype=np.uint16)
        water = np.zeros((rows, cols), dtype=bool)

        # Seed a distant hard domain so the conservative distance field is valid.
        reasons[10, 10] = 1
        water[20, 20] = True

        r0 = COMPONENT["row_min"] + 20
        c0 = COMPONENT["col_min"] + 20
        slope[r0 : r0 + 4, c0 : c0 + 4] = 60.0
        roughness[r0 : r0 + 4, c0 : c0 + 4] = 2.0

        # Adjacent moderate rough cells satisfy the Phase 1 scree contract.
        slope[r0 : r0 + 4, c0 + 4 : c0 + 8] = 30.0
        roughness[r0 : r0 + 4, c0 + 4 : c0 + 8] = 0.8

        first = build_plan(elevation, slope, roughness, reasons, water)
        second = build_plan(
            elevation.copy(),
            slope.copy(),
            roughness.copy(),
            reasons.copy(),
            water.copy(),
        )

        self.assertEqual(first, second)
        self.assertGreater(first["counts"]["plate_count"], 0)
        self.assertGreater(first["counts"]["scree_rock_count"], 0)
        self.assertFalse(first["hard_policy"]["bob"])
        self.assertFalse(first["hard_policy"]["buildings"])
        self.assertFalse(first["hard_policy"]["infrastructure"])
        self.assertEqual(first["hard_policy"]["mapped_water_buffer_m"], 0.5)
        for plate in first["plates"]:
            self.assertGreater(
                plate["clearance_lower_bound_m"],
                0.5 * plate["width_m"],
            )


if __name__ == "__main__":
    unittest.main()

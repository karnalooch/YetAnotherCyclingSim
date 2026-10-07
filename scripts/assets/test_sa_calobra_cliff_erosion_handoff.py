"""Contract tests for deterministic Sa Calobra cliff/scree Phase 2A handoff."""

import unittest

import numpy as np

from scripts.assets.prepare_sa_calobra_cliff_erosion_handoff import (
    COMPONENT_230,
    NODATA,
    _patch_id,
    aggregate_min_by_label,
    label_components_8,
    sample_scree_blocks,
    surface_gradients,
)


class CliffErosionHandoffTests(unittest.TestCase):
    def test_diagonal_cells_are_one_8_connected_patch(self):
        mask = np.zeros((5, 5), dtype=bool)
        mask[0, 0] = True
        mask[1, 1] = True
        mask[2, 2] = True

        labels = label_components_8(mask)

        self.assertEqual(int(labels.max()), 1)
        self.assertTrue((labels[mask] == 1).all())

    def test_component_ids_follow_stable_top_left_anchor_order(self):
        mask = np.zeros((6, 8), dtype=bool)
        mask[4, 6:8] = True
        mask[1, 2:4] = True

        labels = label_components_8(mask)

        self.assertEqual(int(labels[1, 2]), 1)
        self.assertEqual(int(labels[4, 6]), 2)
        np.testing.assert_array_equal(labels > 0, mask)

    def test_bridge_merges_multiple_previous_runs(self):
        mask = np.zeros((3, 5), dtype=bool)
        mask[0, 0] = True
        mask[0, 4] = True
        mask[1, 1:4] = True

        labels = label_components_8(mask)

        self.assertEqual(int(labels.max()), 1)

    def test_scree_sampling_is_deterministic_and_one_per_block(self):
        mask = np.ones((9, 9), dtype=bool)

        first = sample_scree_blocks(mask, block_cells=4)
        second = sample_scree_blocks(mask, block_cells=4)

        for actual, expected in zip(first, second, strict=True):
            np.testing.assert_array_equal(actual, expected)

        rows, cols, _ = first
        blocks = {
            (int(row) // 4, int(col) // 4)
            for row, col in zip(rows, cols, strict=True)
        }
        self.assertEqual(len(rows), 9)
        self.assertEqual(len(blocks), len(rows))
        self.assertTrue(mask[rows, cols].all())

    def test_scree_change_in_other_block_does_not_churn_existing_choice(self):
        mask = np.zeros((8, 8), dtype=bool)
        mask[:4, :4] = True
        rows_a, cols_a, _ = sample_scree_blocks(mask, 4)

        mask[7, 7] = True
        rows_b, cols_b, _ = sample_scree_blocks(mask, 4)

        self.assertEqual(
            (int(rows_a[0]), int(cols_a[0])),
            (int(rows_b[0]), int(cols_b[0])),
        )

    def test_surface_gradient_uses_east_and_south_axes(self):
        rows, cols = np.indices((7, 7))
        elevation = (
            3.0 * cols * 0.5 + 2.0 * rows * 0.5
        ).astype(np.float32)

        gradient_x, gradient_y = surface_gradients(elevation, 0.5)

        self.assertAlmostEqual(float(gradient_x[3, 3]), 3.0)
        self.assertAlmostEqual(float(gradient_y[3, 3]), 2.0)
        self.assertTrue(np.isnan(gradient_x[0, 0]))

    def test_surface_gradient_rejects_nodata_neighborhood(self):
        elevation = np.zeros((5, 5), dtype=np.float32)
        elevation[2, 2] = NODATA

        gradient_x, gradient_y = surface_gradients(elevation)

        self.assertTrue(np.isnan(gradient_x[2, 2]))
        self.assertTrue(np.isnan(gradient_y[2, 2]))

    def test_label_minimum_aggregation(self):
        labels = np.array(
            [[0, 1, 1], [2, 0, 2]],
            dtype=np.int32,
        )
        values = np.array(
            [[8.0, 5.0, 3.0], [7.0, 9.0, 2.0]],
            dtype=np.float32,
        )

        result = aggregate_min_by_label(labels, values)

        self.assertAlmostEqual(float(result[1]), 3.0)
        self.assertAlmostEqual(float(result[2]), 2.0)

    def test_patch_id_is_anchor_stable(self):
        self.assertEqual(_patch_id(10, 20), _patch_id(10, 20))
        self.assertNotEqual(_patch_id(10, 20), _patch_id(10, 21))

    def test_component_230_window_is_exact_127_square(self):
        self.assertEqual(
            COMPONENT_230["row_max"] - COMPONENT_230["row_min"] + 1,
            127,
        )
        self.assertEqual(
            COMPONENT_230["col_max"] - COMPONENT_230["col_min"] + 1,
            127,
        )
        self.assertEqual(
            COMPONENT_230["sample_bounds_local_m"]["x"],
            [378.0, 441.0],
        )
        self.assertEqual(
            COMPONENT_230["sample_bounds_local_m"]["y"],
            [441.0, 504.0],
        )


if __name__ == "__main__":
    unittest.main()

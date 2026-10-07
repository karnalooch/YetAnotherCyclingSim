"""Contract tests for the non-destructive Sa Calobra cliff/erosion selectors."""

import unittest

import numpy as np

from scripts.assets.prepare_sa_calobra_cliff_erosion import (
    NODATA,
    classify,
    terrain_diagnostics,
)


class CliffErosionSelectorTests(unittest.TestCase):
    def base_inputs(self, size=9):
        slope = np.full((size, size), 10.0, dtype=np.float32)
        roughness = np.full((size, size), 0.1, dtype=np.float32)
        elevation = np.zeros((size, size), dtype=np.float32)
        protected = np.zeros((size, size), dtype=bool)
        return slope, roughness, elevation, protected

    def test_steep_rough_cell_becomes_cliff_without_mutating_inputs(self):
        slope, roughness, elevation, protected = self.base_inputs()
        slope[4, 4] = 60.0
        roughness[4, 4] = 2.0
        originals = [array.copy() for array in (slope, roughness, elevation, protected)]

        result = classify(slope, roughness, elevation, protected)

        self.assertEqual(result["cliff_selector"][4, 4], 1)
        self.assertEqual(result["scree_selector"][4, 4], 0)
        for actual, expected in zip(
            (slope, roughness, elevation, protected), originals, strict=True
        ):
            np.testing.assert_array_equal(actual, expected)

    def test_protected_domain_suppresses_cliff_and_scree(self):
        slope, roughness, elevation, protected = self.base_inputs()
        slope[4, 4] = 60.0
        roughness[4, 4] = 2.0
        protected[4, 4] = True
        result = classify(slope, roughness, elevation, protected)
        self.assertEqual(result["cliff_selector"][4, 4], 0)
        self.assertEqual(result["scree_selector"][4, 4], 0)

    def test_moderate_rough_slope_near_cliff_becomes_scree(self):
        slope, roughness, elevation, protected = self.base_inputs()
        slope[4, 4] = 60.0
        roughness[4, 4] = 2.0
        slope[4, 5] = 30.0
        roughness[4, 5] = 0.8
        elevation[4, 5] = 0.6
        result = classify(slope, roughness, elevation, protected)
        self.assertEqual(result["cliff_selector"][4, 4], 1)
        self.assertEqual(result["scree_selector"][4, 5], 1)

    def test_scree_requires_local_height_step(self):
        slope, roughness, elevation, protected = self.base_inputs()
        slope[4, 4] = 60.0
        roughness[4, 4] = 2.0
        slope[4, 5] = 30.0
        roughness[4, 5] = 0.8
        result = classify(slope, roughness, elevation, protected)
        self.assertEqual(result["scree_selector"][4, 5], 0)

    def test_moderate_slope_without_cliff_proximity_is_not_scree(self):
        slope, roughness, elevation, protected = self.base_inputs()
        slope[4, 4] = 30.0
        roughness[4, 4] = 0.8
        result = classify(slope, roughness, elevation, protected)
        self.assertEqual(result["scree_selector"][4, 4], 0)
        self.assertTrue(np.isinf(result["distance_to_cliff_m"]).all())

    def test_invalid_terrain_neighborhood_stays_unknown(self):
        slope, roughness, elevation, protected = self.base_inputs()
        elevation[4, 4] = NODATA
        result = classify(slope, roughness, elevation, protected)
        self.assertEqual(result["cliff_selector"][4, 4], 255)
        self.assertEqual(result["scree_selector"][4, 4], 255)

    def test_diagnostics_measure_cardinal_curvature_and_step(self):
        elevation = np.zeros((5, 5), dtype=np.float32)
        elevation[2, 2] = 4.0
        valid, curvature, step = terrain_diagnostics(elevation)
        self.assertTrue(valid[2, 2])
        self.assertAlmostEqual(float(curvature[2, 2]), 4.0)
        self.assertAlmostEqual(float(step[2, 2]), 4.0)
        self.assertEqual(curvature[0, 0], NODATA)

    def test_parameter_contract_is_fail_closed(self):
        slope, roughness, elevation, protected = self.base_inputs()
        with self.assertRaisesRegex(ValueError, "parameter set"):
            classify(
                slope,
                roughness,
                elevation,
                protected,
                parameters={"cliff_slope_min_deg": 50.0},
            )
        with self.assertRaisesRegex(ValueError, "Scree slope band"):
            classify(
                slope,
                roughness,
                elevation,
                protected,
                parameters={
                    "cliff_slope_min_deg": 50.0,
                    "cliff_roughness_min_m": 0.75,
                    "scree_slope_min_deg": 45.0,
                    "scree_slope_max_deg": 55.0,
                    "scree_roughness_min_m": 0.35,
                    "scree_step_min_m": 0.5,
                    "scree_cliff_proximity_m": 8.0,
                },
            )

    def test_grid_mismatch_is_rejected(self):
        slope, roughness, elevation, protected = self.base_inputs()
        with self.assertRaisesRegex(ValueError, "share one 2D grid"):
            classify(slope, roughness[:-1], elevation, protected)


if __name__ == "__main__":
    unittest.main()

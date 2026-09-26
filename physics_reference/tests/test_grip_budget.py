import dataclasses
import math
import unittest

from cycling_physics import SharedGripBudget, shared_grip_budget


class TestSharedGripBudget(unittest.TestCase):
    def test_zero_demand_leaves_full_axis_capacity(self):
        result = shared_grip_budget(0.0, 0.0)
        self.assertEqual(result.combined_usage, 0.0)
        self.assertEqual(result.remaining_longitudinal_capacity, 1.0)
        self.assertEqual(result.remaining_lateral_capacity, 1.0)
        self.assertFalse(result.exceeded)

    def test_pure_axis_usage_has_exact_parity(self):
        longitudinal = shared_grip_budget(0.7, 0.0)
        lateral = shared_grip_budget(0.0, 0.7)

        self.assertAlmostEqual(longitudinal.combined_usage, 0.7, places=12)
        self.assertAlmostEqual(lateral.combined_usage, 0.7, places=12)
        self.assertAlmostEqual(
            longitudinal.remaining_lateral_capacity,
            math.sqrt(1.0 - 0.7**2),
            places=12,
        )
        self.assertAlmostEqual(
            lateral.remaining_longitudinal_capacity,
            math.sqrt(1.0 - 0.7**2),
            places=12,
        )

    def test_three_four_five_triangle_hits_exact_limit(self):
        result = shared_grip_budget(0.6, 0.8)
        self.assertAlmostEqual(result.combined_usage, 1.0, places=12)
        self.assertAlmostEqual(result.remaining_lateral_capacity, 0.8, places=12)
        self.assertAlmostEqual(result.remaining_longitudinal_capacity, 0.6, places=12)
        self.assertFalse(result.exceeded)

    def test_combined_sub_limit_demands_share_budget(self):
        result = shared_grip_budget(0.5, 0.5)
        self.assertAlmostEqual(result.combined_usage, math.sqrt(0.5), places=12)
        self.assertFalse(result.exceeded)

    def test_two_individually_valid_axes_can_exceed_shared_budget(self):
        result = shared_grip_budget(0.8, 0.8)
        self.assertLessEqual(result.longitudinal_usage, 1.0)
        self.assertLessEqual(result.lateral_usage, 1.0)
        self.assertGreater(result.combined_usage, 1.0)
        self.assertTrue(result.exceeded)

    def test_usage_above_one_is_not_clamped(self):
        result = shared_grip_budget(1.2, 0.0)
        self.assertEqual(result.longitudinal_usage, 1.2)
        self.assertEqual(result.combined_usage, 1.2)
        self.assertEqual(result.remaining_lateral_capacity, 0.0)
        self.assertTrue(result.exceeded)

    def test_invalid_inputs_fail(self):
        for longitudinal, lateral in (
            (-0.01, 0.0),
            (0.0, -0.01),
            (math.nan, 0.0),
            (0.0, math.inf),
            (True, 0.0),
            (0.0, None),
        ):
            with self.subTest(longitudinal=longitudinal, lateral=lateral):
                with self.assertRaises(ValueError):
                    shared_grip_budget(longitudinal, lateral)

    def test_result_is_immutable(self):
        result = shared_grip_budget(0.3, 0.4)
        self.assertIsInstance(result, SharedGripBudget)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.combined_usage = 1.0


if __name__ == "__main__":
    unittest.main()

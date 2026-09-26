import math
import unittest

from cycling_physics import (
    RiderParameters,
    braking_force_demand,
)


def rider():
    return RiderParameters(
        rider_mass_kg=75.0,
        bike_mass_kg=8.5,
        cda_m2=0.32,
        rolling_resistance_coefficient=0.004,
        drivetrain_efficiency=0.97,
    )


class TestBrakingForceDemand(unittest.TestCase):
    def test_zero_brake_applies_zero_force(self):
        result = braking_force_demand(
            rider(),
            grade_decimal=0.0,
            cross_slope_angle_rad=0.0,
            effective_friction_coefficient=0.8,
            brake_ratio=0.0,
            lateral_usage=0.0,
        )
        self.assertEqual(result.applied_longitudinal_usage, 0.0)
        self.assertEqual(result.applied_brake_force_n, 0.0)
        self.assertEqual(result.applied_brake_acceleration_mps2, 0.0)
        self.assertFalse(result.saturated_by_shared_budget)

    def test_full_straight_flat_brake_uses_full_tyre_capacity(self):
        r = rider()
        mu = 0.8
        result = braking_force_demand(
            r,
            grade_decimal=0.0,
            cross_slope_angle_rad=0.0,
            effective_friction_coefficient=mu,
            brake_ratio=1.0,
            lateral_usage=0.0,
        )
        expected_normal = r.total_mass_kg * 9.80665
        expected_force = mu * expected_normal
        self.assertAlmostEqual(result.static_normal_load_n, expected_normal, places=9)
        self.assertAlmostEqual(
            result.standalone_longitudinal_force_capacity_n,
            expected_force,
            places=9,
        )
        self.assertAlmostEqual(result.applied_brake_force_n, expected_force, places=9)
        self.assertAlmostEqual(
            result.applied_brake_acceleration_mps2,
            mu * 9.80665,
            places=9,
        )
        self.assertEqual(result.applied_longitudinal_usage, 1.0)
        self.assertFalse(result.saturated_by_shared_budget)

    def test_grade_and_cross_slope_reduce_static_normal_capacity(self):
        flat = braking_force_demand(
            rider(), 0.0, 0.0, 0.8, 1.0, 0.0
        )
        tilted = braking_force_demand(
            rider(),
            grade_decimal=0.10,
            cross_slope_angle_rad=math.radians(8.0),
            effective_friction_coefficient=0.8,
            brake_ratio=1.0,
            lateral_usage=0.0,
        )
        self.assertLess(tilted.static_normal_load_n, flat.static_normal_load_n)
        self.assertLess(
            tilted.standalone_longitudinal_force_capacity_n,
            flat.standalone_longitudinal_force_capacity_n,
        )

    def test_lateral_usage_caps_applied_braking_without_hiding_overdemand(self):
        result = braking_force_demand(
            rider(),
            grade_decimal=0.0,
            cross_slope_angle_rad=0.0,
            effective_friction_coefficient=0.8,
            brake_ratio=0.8,
            lateral_usage=0.8,
        )
        self.assertGreater(result.requested_budget.combined_usage, 1.0)
        self.assertTrue(result.requested_budget.exceeded)
        self.assertAlmostEqual(
            result.requested_budget.remaining_longitudinal_capacity,
            0.6,
            places=12,
        )
        self.assertAlmostEqual(result.applied_longitudinal_usage, 0.6, places=12)
        self.assertTrue(result.saturated_by_shared_budget)

    def test_request_on_circle_boundary_is_not_reduced_materially(self):
        result = braking_force_demand(
            rider(),
            grade_decimal=0.0,
            cross_slope_angle_rad=0.0,
            effective_friction_coefficient=0.8,
            brake_ratio=0.6,
            lateral_usage=0.8,
        )
        self.assertAlmostEqual(result.requested_budget.combined_usage, 1.0, places=12)
        self.assertAlmostEqual(result.applied_longitudinal_usage, 0.6, places=12)
        self.assertAlmostEqual(
            result.applied_brake_force_n,
            0.6 * result.standalone_longitudinal_force_capacity_n,
            places=9,
        )

    def test_lower_effective_friction_reduces_force_at_same_usage(self):
        dry = braking_force_demand(
            rider(), 0.0, 0.0, 0.8, 0.5, 0.0
        )
        wet = braking_force_demand(
            rider(), 0.0, 0.0, 0.6, 0.5, 0.0
        )
        self.assertLess(
            wet.standalone_longitudinal_force_capacity_n,
            dry.standalone_longitudinal_force_capacity_n,
        )
        self.assertLess(wet.applied_brake_force_n, dry.applied_brake_force_n)

    def test_lateral_overdemand_leaves_no_no_slip_braking_capacity(self):
        result = braking_force_demand(
            rider(),
            grade_decimal=0.0,
            cross_slope_angle_rad=0.0,
            effective_friction_coefficient=0.8,
            brake_ratio=1.0,
            lateral_usage=1.2,
        )
        self.assertEqual(result.requested_budget.remaining_longitudinal_capacity, 0.0)
        self.assertEqual(result.applied_longitudinal_usage, 0.0)
        self.assertEqual(result.applied_brake_force_n, 0.0)
        self.assertTrue(result.saturated_by_shared_budget)

    def test_invalid_inputs_rejected(self):
        r = rider()

        for grade in (math.nan, math.inf, -math.inf):
            with self.subTest(grade=grade):
                with self.assertRaises(ValueError):
                    braking_force_demand(r, grade, 0.0, 0.8, 0.5, 0.0)

        for cross_slope in (
            math.nan,
            math.inf,
            math.pi / 2,
            -math.pi / 2,
        ):
            with self.subTest(cross_slope=cross_slope):
                with self.assertRaises(ValueError):
                    braking_force_demand(r, 0.0, cross_slope, 0.8, 0.5, 0.0)

        for friction in (0.0, -0.1, math.nan, math.inf):
            with self.subTest(friction=friction):
                with self.assertRaises(ValueError):
                    braking_force_demand(r, 0.0, 0.0, friction, 0.5, 0.0)

        for brake in (-0.01, 1.01, math.nan, math.inf, True):
            with self.subTest(brake=brake):
                with self.assertRaises(ValueError):
                    braking_force_demand(r, 0.0, 0.0, 0.8, brake, 0.0)

        for lateral in (-0.01, math.nan, math.inf):
            with self.subTest(lateral=lateral):
                with self.assertRaises(ValueError):
                    braking_force_demand(r, 0.0, 0.0, 0.8, 0.5, lateral)


if __name__ == "__main__":
    unittest.main()

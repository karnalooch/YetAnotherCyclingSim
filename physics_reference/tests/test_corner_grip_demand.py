import math
import unittest

from cycling_physics import (
    ALPINE_SURFACE_GRIP_POLICY,
    CORNER_DIRECTION_RIGHT,
    CORNER_PHASE_APEX,
    CornerContext,
    CornerLateralLimit,
    corner_grip_demand,
    corner_lateral_limit,
)


def context(*, radius=50.0, cross_slope=0.0, wetness=0.0, surface="asphalt"):
    return CornerContext(
        distance_m=100.0,
        lateral_position_m=0.0,
        phase=CORNER_PHASE_APEX,
        has_corner=True,
        corner_start_m=50.0,
        corner_end_m=150.0,
        distance_to_corner_start_m=0.0,
        apex_distance_m=100.0,
        direction=CORNER_DIRECTION_RIGHT,
        signed_curvature_per_m=1.0 / radius,
        centerline_radius_m=radius,
        effective_radius_m=radius,
        road_width_m=6.0,
        left_margin_m=3.0,
        right_margin_m=3.0,
        cross_slope_angle_rad=cross_slope,
        surface_id=surface,
        wetness=wetness,
        roughness=0.0,
    )


def limit_for(ctx, base_mu=0.8):
    return corner_lateral_limit(ctx, ALPINE_SURFACE_GRIP_POLICY, base_mu)


class TestCornerGripDemand(unittest.TestCase):
    def test_zero_speed_and_released_brake_use_no_grip(self):
        ctx = context()
        limit = limit_for(ctx)
        result = corner_grip_demand(ctx, limit, 0.0, 0.0)

        self.assertEqual(result.lateral_acceleration_demand_mps2, 0.0)
        self.assertEqual(result.longitudinal_usage, 0.0)
        self.assertEqual(result.lateral_usage, 0.0)
        self.assertEqual(result.budget.combined_usage, 0.0)
        self.assertFalse(result.budget.exceeded)

    def test_lateral_limit_speed_uses_exact_full_lateral_budget(self):
        ctx = context()
        limit = limit_for(ctx)
        result = corner_grip_demand(
            ctx,
            limit,
            limit.maximum_speed_mps,
            0.0,
        )

        self.assertAlmostEqual(result.lateral_usage, 1.0, places=12)
        self.assertAlmostEqual(result.budget.combined_usage, 1.0, places=12)

    def test_braking_at_lateral_limit_exceeds_shared_budget(self):
        ctx = context()
        limit = limit_for(ctx)
        result = corner_grip_demand(
            ctx,
            limit,
            limit.maximum_speed_mps,
            0.2,
        )

        self.assertAlmostEqual(result.lateral_usage, 1.0, places=12)
        self.assertAlmostEqual(result.longitudinal_usage, 0.2, places=12)
        self.assertGreater(result.budget.combined_usage, 1.0)
        self.assertTrue(result.budget.exceeded)

    def test_three_four_five_demand_hits_exact_circle(self):
        ctx = context()
        limit = limit_for(ctx)
        target_lateral_usage = 0.8
        speed = math.sqrt(
            target_lateral_usage
            * limit.lateral_acceleration_limit_mps2
            * ctx.effective_radius_m
        )

        result = corner_grip_demand(ctx, limit, speed, 0.6)

        self.assertAlmostEqual(result.longitudinal_usage, 0.6, places=12)
        self.assertAlmostEqual(result.lateral_usage, 0.8, places=12)
        self.assertAlmostEqual(result.budget.combined_usage, 1.0, places=12)
        self.assertAlmostEqual(
            result.budget.remaining_longitudinal_capacity,
            0.6,
            places=12,
        )
        self.assertAlmostEqual(
            result.budget.remaining_lateral_capacity,
            0.8,
            places=12,
        )

    def test_wet_surface_increases_usage_at_same_speed(self):
        dry_ctx = context(wetness=0.0)
        wet_ctx = context(wetness=1.0)
        dry_limit = limit_for(dry_ctx)
        wet_limit = limit_for(wet_ctx)
        speed = 12.0

        dry = corner_grip_demand(dry_ctx, dry_limit, speed, 0.0)
        wet = corner_grip_demand(wet_ctx, wet_limit, speed, 0.0)

        self.assertLess(
            wet_limit.lateral_acceleration_limit_mps2,
            dry_limit.lateral_acceleration_limit_mps2,
        )
        self.assertGreater(wet.lateral_usage, dry.lateral_usage)

    def test_supportive_bank_reduces_usage_at_same_speed(self):
        angle = math.radians(5.0)
        flat_ctx = context(cross_slope=0.0)
        supportive_ctx = context(cross_slope=-angle)
        flat_limit = limit_for(flat_ctx)
        supportive_limit = limit_for(supportive_ctx)
        speed = 12.0

        flat = corner_grip_demand(flat_ctx, flat_limit, speed, 0.0)
        supportive = corner_grip_demand(
            supportive_ctx,
            supportive_limit,
            speed,
            0.0,
        )

        self.assertGreater(
            supportive_limit.lateral_acceleration_limit_mps2,
            flat_limit.lateral_acceleration_limit_mps2,
        )
        self.assertLess(supportive.lateral_usage, flat.lateral_usage)

    def test_context_and_limit_must_match(self):
        ctx = context()
        limit = limit_for(ctx)

        wrong_surface = CornerLateralLimit(
            surface_id="paint",
            wetness=limit.wetness,
            grip_multiplier=limit.grip_multiplier,
            effective_friction_coefficient=limit.effective_friction_coefficient,
            bank_support_angle_rad=limit.bank_support_angle_rad,
            lateral_acceleration_limit_mps2=limit.lateral_acceleration_limit_mps2,
            maximum_speed_mps=limit.maximum_speed_mps,
        )
        with self.assertRaisesRegex(ValueError, "surface_id"):
            corner_grip_demand(ctx, wrong_surface, 10.0, 0.0)

        wrong_wetness = CornerLateralLimit(
            surface_id=limit.surface_id,
            wetness=0.5,
            grip_multiplier=limit.grip_multiplier,
            effective_friction_coefficient=limit.effective_friction_coefficient,
            bank_support_angle_rad=limit.bank_support_angle_rad,
            lateral_acceleration_limit_mps2=limit.lateral_acceleration_limit_mps2,
            maximum_speed_mps=limit.maximum_speed_mps,
        )
        with self.assertRaisesRegex(ValueError, "wetness"):
            corner_grip_demand(ctx, wrong_wetness, 10.0, 0.0)

        wrong_bank = CornerLateralLimit(
            surface_id=limit.surface_id,
            wetness=limit.wetness,
            grip_multiplier=limit.grip_multiplier,
            effective_friction_coefficient=limit.effective_friction_coefficient,
            bank_support_angle_rad=0.1,
            lateral_acceleration_limit_mps2=limit.lateral_acceleration_limit_mps2,
            maximum_speed_mps=limit.maximum_speed_mps,
        )
        with self.assertRaisesRegex(ValueError, "bank support"):
            corner_grip_demand(ctx, wrong_bank, 10.0, 0.0)

    def test_approach_context_is_not_physical_lateral_usage(self):
        ctx = context()
        ctx = CornerContext(
            **{
                field: getattr(ctx, field)
                for field in ctx.__dataclass_fields__
                if field != "phase"
            },
            phase="approach",
        )
        limit = limit_for(ctx)
        with self.assertRaisesRegex(ValueError, "entry/apex/exit"):
            corner_grip_demand(ctx, limit, 10.0, 0.2)

    def test_invalid_speed_and_brake_rejected(self):
        ctx = context()
        limit = limit_for(ctx)

        for speed in (-0.01, math.nan, math.inf):
            with self.subTest(speed=speed):
                with self.assertRaises(ValueError):
                    corner_grip_demand(ctx, limit, speed, 0.0)

        for brake in (-0.01, 1.01, math.nan, math.inf, True):
            with self.subTest(brake=brake):
                with self.assertRaises(ValueError):
                    corner_grip_demand(ctx, limit, 10.0, brake)


if __name__ == "__main__":
    unittest.main()

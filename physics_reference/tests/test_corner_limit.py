import math
import unittest

from cycling_physics import (
    ALPINE_SURFACE_GRIP_POLICY,
    CORNER_DIRECTION_LEFT,
    CORNER_DIRECTION_RIGHT,
    CORNER_PHASE_APEX,
    CornerContext,
    SurfaceGripPolicy,
    SurfaceGripRule,
    corner_lateral_limit,
    maximum_corner_speed_mps,
)


def context(
    *,
    curvature=0.02,
    radius=50.0,
    cross_slope=0.0,
    wetness=0.0,
    surface="asphalt",
    direction=CORNER_DIRECTION_RIGHT,
):
    return CornerContext(
        distance_m=100.0,
        lateral_position_m=0.0,
        phase=CORNER_PHASE_APEX,
        has_corner=True,
        corner_start_m=50.0,
        corner_end_m=150.0,
        distance_to_corner_start_m=0.0,
        apex_distance_m=100.0,
        direction=direction,
        signed_curvature_per_m=curvature,
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


class TestCornerLateralLimit(unittest.TestCase):
    def test_flat_road_matches_existing_corner_speed_formula(self):
        ctx = context(wetness=0.5)
        result = corner_lateral_limit(ctx, ALPINE_SURFACE_GRIP_POLICY, 0.8)

        expected = maximum_corner_speed_mps(
            50.0,
            0.8,
            0.875,
        )
        self.assertAlmostEqual(result.maximum_speed_mps, expected, places=12)
        self.assertAlmostEqual(result.bank_support_angle_rad, 0.0, places=12)
        self.assertAlmostEqual(result.grip_multiplier, 0.875, places=12)

    def test_supportive_bank_increases_and_off_camber_reduces_limit(self):
        angle = math.radians(5.0)

        flat = corner_lateral_limit(
            context(cross_slope=0.0),
            ALPINE_SURFACE_GRIP_POLICY,
            0.8,
        )
        supportive = corner_lateral_limit(
            context(cross_slope=-angle),
            ALPINE_SURFACE_GRIP_POLICY,
            0.8,
        )
        adverse = corner_lateral_limit(
            context(cross_slope=angle),
            ALPINE_SURFACE_GRIP_POLICY,
            0.8,
        )

        self.assertGreater(supportive.bank_support_angle_rad, 0.0)
        self.assertLess(adverse.bank_support_angle_rad, 0.0)
        self.assertGreater(supportive.maximum_speed_mps, flat.maximum_speed_mps)
        self.assertLess(adverse.maximum_speed_mps, flat.maximum_speed_mps)

    def test_left_turn_mirrors_cross_slope_sign(self):
        angle = math.radians(5.0)
        right_supportive = corner_lateral_limit(
            context(curvature=0.02, cross_slope=-angle, direction=CORNER_DIRECTION_RIGHT),
            ALPINE_SURFACE_GRIP_POLICY,
            0.8,
        )
        left_supportive = corner_lateral_limit(
            context(
                curvature=-0.02,
                cross_slope=angle,
                direction=CORNER_DIRECTION_LEFT,
            ),
            ALPINE_SURFACE_GRIP_POLICY,
            0.8,
        )

        self.assertAlmostEqual(
            right_supportive.bank_support_angle_rad,
            left_supportive.bank_support_angle_rad,
            places=12,
        )
        self.assertAlmostEqual(
            right_supportive.maximum_speed_mps,
            left_supportive.maximum_speed_mps,
            places=12,
        )

    def test_wet_asphalt_reduces_limit_without_new_coefficients(self):
        dry = corner_lateral_limit(
            context(wetness=0.0),
            ALPINE_SURFACE_GRIP_POLICY,
            0.8,
        )
        wet = corner_lateral_limit(
            context(wetness=1.0),
            ALPINE_SURFACE_GRIP_POLICY,
            0.8,
        )
        self.assertEqual(dry.grip_multiplier, 1.0)
        self.assertEqual(wet.grip_multiplier, 0.75)
        self.assertLess(wet.maximum_speed_mps, dry.maximum_speed_mps)

    def test_effective_racing_line_radius_changes_limit(self):
        outer = context(radius=52.0)
        inner = context(radius=48.0)

        outer_limit = corner_lateral_limit(
            outer,
            ALPINE_SURFACE_GRIP_POLICY,
            0.8,
        )
        inner_limit = corner_lateral_limit(
            inner,
            ALPINE_SURFACE_GRIP_POLICY,
            0.8,
        )
        self.assertGreater(outer_limit.maximum_speed_mps, inner_limit.maximum_speed_mps)

    def test_surface_policy_is_consumed_fail_closed(self):
        only_paint = SurfaceGripPolicy(
            "paint only",
            (SurfaceGripRule("paint", 0.9, 0.6),),
        )
        with self.assertRaisesRegex(ValueError, "not configured"):
            corner_lateral_limit(context(surface="asphalt"), only_paint, 0.8)

    def test_invalid_context_and_base_friction_rejected(self):
        no_corner = context()
        no_corner = CornerContext(
            **{
                field: getattr(no_corner, field)
                for field in no_corner.__dataclass_fields__
                if field != "has_corner"
            },
            has_corner=False,
        )
        with self.assertRaisesRegex(ValueError, "requires a context with a corner"):
            corner_lateral_limit(no_corner, ALPINE_SURFACE_GRIP_POLICY, 0.8)

        for value in (0.0, -0.1, math.nan, math.inf):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    corner_lateral_limit(
                        context(),
                        ALPINE_SURFACE_GRIP_POLICY,
                        value,
                    )

    def test_pathological_bank_friction_combination_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "outside the supported"):
            corner_lateral_limit(
                context(cross_slope=math.radians(80.0)),
                ALPINE_SURFACE_GRIP_POLICY,
                0.8,
            )


if __name__ == "__main__":
    unittest.main()

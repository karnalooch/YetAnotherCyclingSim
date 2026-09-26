import math
import unittest

from cycling_physics.corner_context import (
    CORNER_DIRECTION_LEFT,
    CORNER_DIRECTION_RIGHT,
    CORNER_DIRECTION_STRAIGHT,
    CornerContextSettings,
    corner_context_at,
)
from cycling_physics.cornering import (
    CORNER_PHASE_APPROACH,
    CORNER_PHASE_ENTRY,
    CORNER_PHASE_OUTSIDE,
)
from cycling_physics.road_physics import RoadPhysicsProfile, RoadPhysicsSample


def sample(
    distance_m,
    curvature=0.0,
    *,
    width=6.0,
    cross_slope=0.0,
    surface="asphalt",
    wetness=0.0,
    roughness=0.0,
):
    return RoadPhysicsSample(
        distance_m=distance_m,
        elevation_m=0.0,
        grade_decimal=0.0,
        horizontal_curvature_per_m=curvature,
        vertical_curvature_per_m=0.0,
        road_width_m=width,
        left_cross_slope_angle_rad=cross_slope,
        right_cross_slope_angle_rad=cross_slope,
        surface_id=surface,
        wetness=wetness,
        roughness=roughness,
    )


class TestCornerContext(unittest.TestCase):
    def settings(self, **overrides):
        values = dict(
            min_abs_curvature_per_m=0.01,
            scan_step_m=10.0,
            look_ahead_m=100.0,
            approach_length_m=50.0,
        )
        values.update(overrides)
        return CornerContextSettings(**values)

    def test_straight_context_has_no_corner_and_infinite_radius(self):
        profile = RoadPhysicsProfile(
            "straight",
            (sample(0.0), sample(200.0)),
        )
        context = corner_context_at(profile, 50.0, 1.0, self.settings())

        self.assertFalse(context.has_corner)
        self.assertEqual(context.phase, CORNER_PHASE_OUTSIDE)
        self.assertEqual(context.direction, CORNER_DIRECTION_STRAIGHT)
        self.assertTrue(math.isinf(context.centerline_radius_m))
        self.assertTrue(math.isinf(context.effective_radius_m))
        self.assertAlmostEqual(context.left_margin_m, 4.0)
        self.assertAlmostEqual(context.right_margin_m, 2.0)

    def test_positive_curvature_is_right_and_positive_d_tightens_radius(self):
        profile = RoadPhysicsProfile(
            "right",
            (sample(0.0, 0.02), sample(200.0, 0.02)),
        )
        center = corner_context_at(profile, 25.0, 0.0, self.settings())
        inside = corner_context_at(profile, 25.0, 2.0, self.settings())

        self.assertEqual(center.direction, CORNER_DIRECTION_RIGHT)
        self.assertAlmostEqual(center.centerline_radius_m, 50.0)
        self.assertAlmostEqual(center.effective_radius_m, 50.0)
        self.assertAlmostEqual(inside.effective_radius_m, 48.0)
        self.assertEqual(inside.phase, CORNER_PHASE_ENTRY)

    def test_negative_curvature_is_left_and_negative_d_tightens_radius(self):
        profile = RoadPhysicsProfile(
            "left",
            (sample(0.0, -0.025), sample(200.0, -0.025)),
        )
        inside = corner_context_at(profile, 50.0, -2.0, self.settings())

        self.assertEqual(inside.direction, CORNER_DIRECTION_LEFT)
        self.assertAlmostEqual(inside.centerline_radius_m, 40.0)
        self.assertAlmostEqual(inside.effective_radius_m, 38.0)

    def test_lookahead_finds_upcoming_corner_and_reports_approach(self):
        profile = RoadPhysicsProfile(
            "ahead",
            (
                sample(0.0, 0.0),
                sample(100.0, 0.0),
                sample(110.0, 0.02, cross_slope=math.radians(4.0), wetness=0.5),
                sample(170.0, 0.02, cross_slope=math.radians(4.0), wetness=0.5),
                sample(180.0, 0.0),
                sample(250.0, 0.0),
            ),
        )
        context = corner_context_at(profile, 70.0, 1.0, self.settings())

        self.assertTrue(context.has_corner)
        self.assertEqual(context.phase, CORNER_PHASE_APPROACH)
        self.assertAlmostEqual(context.corner_start_m, 110.0)
        self.assertAlmostEqual(context.distance_to_corner_start_m, 40.0)
        self.assertEqual(context.direction, CORNER_DIRECTION_RIGHT)
        self.assertAlmostEqual(context.cross_slope_angle_rad, math.radians(4.0))
        self.assertAlmostEqual(context.wetness, 0.5)

    def test_surface_metadata_passes_through_without_resolving_grip(self):
        profile = RoadPhysicsProfile(
            "surface",
            (
                sample(0.0, 0.02, surface="paint", wetness=0.75, roughness=0.2),
                sample(100.0, 0.02, surface="paint", wetness=0.75, roughness=0.2),
            ),
        )
        context = corner_context_at(profile, 50.0, 0.0, self.settings())
        self.assertEqual(context.surface_id, "paint")
        self.assertAlmostEqual(context.wetness, 0.75)
        self.assertAlmostEqual(context.roughness, 0.2)

    def test_caller_controls_detection_threshold(self):
        profile = RoadPhysicsProfile(
            "threshold",
            (sample(0.0, 0.005), sample(100.0, 0.005)),
        )
        self.assertFalse(
            corner_context_at(profile, 50.0, 0.0, self.settings()).has_corner
        )
        self.assertTrue(
            corner_context_at(
                profile,
                50.0,
                0.0,
                self.settings(min_abs_curvature_per_m=0.001),
            ).has_corner
        )

    def test_invalid_settings_rejected(self):
        for kwargs in (
            dict(min_abs_curvature_per_m=0.0),
            dict(scan_step_m=0.0),
            dict(look_ahead_m=-1.0),
            dict(approach_length_m=0.0),
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    self.settings(**kwargs)


if __name__ == "__main__":
    unittest.main()

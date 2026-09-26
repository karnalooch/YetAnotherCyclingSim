import math
import unittest

from cycling_physics.road_physics import (
    RoadPhysicsProfile,
    RoadPhysicsSample,
    RoadPhysicsTransitionLimits,
)


def sample(
    distance_m,
    *,
    elevation_m=100.0,
    grade_decimal=0.0,
    curvature=0.0,
    vertical_curvature=0.0,
    width=6.0,
    bank=0.0,
    surface="asphalt",
    wetness=0.0,
    roughness=0.0,
):
    return RoadPhysicsSample(
        distance_m=distance_m,
        elevation_m=elevation_m,
        grade_decimal=grade_decimal,
        horizontal_curvature_per_m=curvature,
        vertical_curvature_per_m=vertical_curvature,
        road_width_m=width,
        bank_angle_rad=bank,
        surface_id=surface,
        wetness=wetness,
        roughness=roughness,
    )


class TestRoadPhysicsProfile(unittest.TestCase):
    def test_profile_interpolates_continuous_fields_and_uses_route_local_d(self):
        profile = RoadPhysicsProfile(
            "  Test road  ",
            (
                sample(0.0, elevation_m=100.0, width=6.0, bank=0.0, wetness=0.0),
                sample(
                    100.0,
                    elevation_m=110.0,
                    grade_decimal=0.10,
                    curvature=0.02,
                    vertical_curvature=0.001,
                    width=8.0,
                    bank=math.radians(8.0),
                    wetness=0.4,
                    roughness=0.2,
                ),
            ),
        )

        state = profile.state_at(50.0, lateral_position_m=2.0)

        self.assertEqual(profile.name, "Test road")
        self.assertAlmostEqual(state.distance_m, 50.0)
        self.assertAlmostEqual(state.lateral_position_m, 2.0)
        self.assertAlmostEqual(state.elevation_m, 105.0)
        self.assertAlmostEqual(state.grade_decimal, 0.05)
        self.assertAlmostEqual(state.horizontal_curvature_per_m, 0.01)
        self.assertAlmostEqual(state.vertical_curvature_per_m, 0.0005)
        self.assertAlmostEqual(state.road_width_m, 7.0)
        self.assertAlmostEqual(state.bank_angle_rad, math.radians(4.0))
        self.assertAlmostEqual(state.wetness, 0.2)
        self.assertAlmostEqual(state.roughness, 0.1)
        self.assertEqual(state.surface_id, "asphalt")
        self.assertAlmostEqual(state.left_edge_m, -3.5)
        self.assertAlmostEqual(state.right_edge_m, 3.5)

    def test_exact_sample_switches_surface_id(self):
        profile = RoadPhysicsProfile(
            "surface transition",
            (
                sample(0.0, surface="asphalt"),
                sample(50.0, surface="paint"),
                sample(100.0, surface="gravel"),
            ),
        )

        self.assertEqual(profile.state_at(49.999).surface_id, "asphalt")
        self.assertEqual(profile.state_at(50.0).surface_id, "paint")
        self.assertEqual(profile.state_at(100.0).surface_id, "gravel")

    def test_lateral_position_must_stay_inside_interpolated_road_width(self):
        profile = RoadPhysicsProfile(
            "width",
            (
                sample(0.0, width=4.0),
                sample(100.0, width=8.0),
            ),
        )

        self.assertAlmostEqual(
            profile.state_at(50.0, 3.0).right_edge_m,
            3.0,
        )
        with self.assertRaisesRegex(ValueError, "outside road bounds"):
            profile.state_at(50.0, 3.001)

    def test_look_ahead_is_deterministic_and_clamps_to_route_end(self):
        profile = RoadPhysicsProfile(
            "look ahead",
            (
                sample(0.0, curvature=0.0),
                sample(100.0, curvature=0.02),
            ),
        )

        self.assertAlmostEqual(profile.state_ahead(25.0, 25.0).distance_m, 50.0)
        self.assertAlmostEqual(profile.state_ahead(90.0, 50.0).distance_m, 100.0)

    def test_transition_limits_are_explicit_and_enforced(self):
        profile = RoadPhysicsProfile(
            "transition",
            (
                sample(0.0, grade_decimal=0.0, curvature=0.0, bank=0.0),
                sample(
                    10.0,
                    grade_decimal=0.10,
                    curvature=0.02,
                    bank=math.radians(10.0),
                ),
            ),
        )

        profile.validate_transition_rates(
            RoadPhysicsTransitionLimits(
                max_abs_grade_change_per_m=0.011,
                max_abs_horizontal_curvature_change_per_m2=0.0021,
                max_abs_bank_angle_change_rad_per_m=0.018,
            )
        )

        with self.assertRaisesRegex(ValueError, "grade change rate"):
            profile.validate_transition_rates(
                RoadPhysicsTransitionLimits(
                    max_abs_grade_change_per_m=0.009,
                    max_abs_horizontal_curvature_change_per_m2=1.0,
                    max_abs_bank_angle_change_rad_per_m=1.0,
                )
            )

    def test_profile_rejects_invalid_distance_domain(self):
        with self.assertRaisesRegex(ValueError, "exactly 0.0"):
            RoadPhysicsProfile("bad", (sample(1.0), sample(2.0)))

        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            RoadPhysicsProfile("bad", (sample(0.0), sample(0.0)))

    def test_sample_rejects_invalid_bank_wetness_and_width(self):
        with self.assertRaisesRegex(ValueError, "bank_angle_rad"):
            sample(0.0, bank=math.pi / 2.0)
        with self.assertRaisesRegex(ValueError, "wetness"):
            sample(0.0, wetness=1.1)
        with self.assertRaisesRegex(ValueError, "road_width_m"):
            sample(0.0, width=0.0)


if __name__ == "__main__":
    unittest.main()

import unittest

from cycling_physics import (
    CORNER_PHASE_APPROACH,
    CornerContextSettings,
    Environment,
    RiderInput,
    RiderParameters,
    RoadPhysicsProfile,
    RoadPhysicsSample,
    SimulationState,
    SurfaceGripPolicy,
    SurfaceGripRule,
    resolve_corner_braking_step,
    step_simulation,
    step_simulation_with_corner_braking,
)


def rider():
    return RiderParameters(
        rider_mass_kg=75.0,
        bike_mass_kg=8.5,
        cda_m2=0.32,
        rolling_resistance_coefficient=0.004,
        drivetrain_efficiency=0.97,
    )


def environment():
    return Environment(
        grade_decimal=0.0,
        wind_speed_mps=0.0,
        air_density_kg_m3=1.225,
    )


def settings():
    return CornerContextSettings(
        min_abs_curvature_per_m=0.01,
        scan_step_m=10.0,
        look_ahead_m=100.0,
        approach_length_m=50.0,
    )


def policy():
    return SurfaceGripPolicy(
        "test grip",
        (
            SurfaceGripRule("asphalt", 1.0, 0.75),
            SurfaceGripRule("paint", 0.9, 0.5),
        ),
    )


def sample(
    distance_m,
    *,
    curvature=0.0,
    surface="asphalt",
    wetness=0.0,
    cross_slope=0.0,
    grade=0.0,
):
    return RoadPhysicsSample(
        distance_m=distance_m,
        elevation_m=0.0,
        grade_decimal=grade,
        horizontal_curvature_per_m=curvature,
        vertical_curvature_per_m=0.0,
        road_width_m=6.0,
        left_cross_slope_angle_rad=cross_slope,
        right_cross_slope_angle_rad=cross_slope,
        surface_id=surface,
        wetness=wetness,
        roughness=0.0,
    )


def straight_profile(*, wetness=0.0):
    return RoadPhysicsProfile(
        "straight",
        (
            sample(0.0, wetness=wetness),
            sample(1000.0, wetness=wetness),
        ),
    )


def approach_profile():
    return RoadPhysicsProfile(
        "approach surface split",
        (
            sample(0.0, surface="asphalt", wetness=0.0),
            sample(90.0, surface="asphalt", wetness=0.0),
            sample(100.0, curvature=0.02, surface="paint", wetness=1.0),
            sample(160.0, curvature=0.02, surface="paint", wetness=1.0),
            sample(170.0, surface="asphalt", wetness=0.0),
            sample(250.0, surface="asphalt", wetness=0.0),
        ),
    )


class TestCornerBrakingStep(unittest.TestCase):
    def test_approach_keeps_lateral_budget_free_and_uses_current_surface(self):
        result = resolve_corner_braking_step(
            approach_profile(),
            settings(),
            policy(),
            0.8,
            0.0,
            rider(),
            RiderInput(power_w=0.0, cadence_rpm=90.0, brake_ratio=0.8),
            SimulationState(speed_mps=15.0, distance_m=70.0, elapsed_time_s=0.0),
        )

        self.assertTrue(result.corner_context.has_corner)
        self.assertEqual(result.corner_context.phase, CORNER_PHASE_APPROACH)
        self.assertEqual(result.corner_context.surface_id, "paint")
        self.assertEqual(result.current_road_state.surface_id, "asphalt")
        self.assertIsNone(result.lateral_limit)
        self.assertIsNone(result.grip_demand)
        self.assertEqual(result.braking_force_demand.lateral_usage, 0.0)
        self.assertAlmostEqual(
            result.braking_force_demand.effective_friction_coefficient,
            0.8,
            places=12,
        )

    def test_active_corner_consumes_lateral_budget_and_caps_braking(self):
        result = resolve_corner_braking_step(
            approach_profile(),
            settings(),
            policy(),
            0.8,
            0.0,
            rider(),
            RiderInput(power_w=0.0, cadence_rpm=90.0, brake_ratio=0.8),
            SimulationState(speed_mps=17.0, distance_m=120.0, elapsed_time_s=0.0),
        )

        self.assertTrue(result.has_active_lateral_demand)
        self.assertIsNotNone(result.grip_demand)
        self.assertGreater(result.grip_demand.lateral_usage, 0.0)
        self.assertLess(
            result.braking_force_demand.applied_longitudinal_usage,
            0.8,
        )
        self.assertTrue(
            result.braking_force_demand.saturated_by_shared_budget
        )

    def test_wet_current_surface_reduces_resolved_brake_force(self):
        input_ = RiderInput(power_w=0.0, cadence_rpm=90.0, brake_ratio=0.5)
        state = SimulationState(speed_mps=12.0, distance_m=20.0, elapsed_time_s=0.0)

        dry = resolve_corner_braking_step(
            straight_profile(wetness=0.0),
            settings(),
            policy(),
            0.8,
            0.0,
            rider(),
            input_,
            state,
        )
        wet = resolve_corner_braking_step(
            straight_profile(wetness=1.0),
            settings(),
            policy(),
            0.8,
            0.0,
            rider(),
            input_,
            state,
        )

        self.assertLess(
            wet.braking_force_demand.applied_brake_force_n,
            dry.braking_force_demand.applied_brake_force_n,
        )

    def test_zero_brake_is_exact_simulation_step_parity(self):
        r = rider()
        env = environment()
        input_ = RiderInput(power_w=250.0, cadence_rpm=90.0, brake_ratio=0.0)
        state = SimulationState(speed_mps=10.0, distance_m=20.0, elapsed_time_s=1.0)

        legacy = step_simulation(r, env, input_, state, 0.05)
        orchestrated = step_simulation_with_corner_braking(
            straight_profile(),
            settings(),
            policy(),
            0.8,
            0.0,
            r,
            env,
            input_,
            state,
            0.05,
        )

        self.assertEqual(
            orchestrated.resolution.braking_force_demand.applied_brake_force_n,
            0.0,
        )
        self.assertEqual(orchestrated.state, legacy)

    def test_fixed_step_result_is_identical_across_render_frame_batching(self):
        profile = straight_profile()
        r = rider()
        env = environment()
        input_ = RiderInput(power_w=300.0, cadence_rpm=90.0, brake_ratio=0.25)

        def run(frame_deltas):
            state = SimulationState(
                speed_mps=0.0,
                distance_m=0.0,
                elapsed_time_s=0.0,
            )
            accumulator = 0.0
            steps = 0
            for delta in frame_deltas:
                accumulator += delta
                while accumulator + 1e-12 >= 0.05:
                    result = step_simulation_with_corner_braking(
                        profile,
                        settings(),
                        policy(),
                        0.8,
                        0.0,
                        r,
                        env,
                        input_,
                        state,
                        0.05,
                    )
                    state = result.state
                    accumulator -= 0.05
                    if accumulator < 0.0 and accumulator > -1e-12:
                        accumulator = 0.0
                    steps += 1
            return state, steps

        at_30_fps = run([1.0 / 30.0] * 90)
        at_60_fps = run([1.0 / 60.0] * 180)
        jittered = run([0.011, 0.027, 0.019, 0.043] * 30)

        self.assertEqual(at_30_fps[1], 60)
        self.assertEqual(at_30_fps[1], at_60_fps[1])
        self.assertEqual(at_30_fps[1], jittered[1])
        self.assertEqual(at_30_fps[0], at_60_fps[0])
        self.assertEqual(at_30_fps[0], jittered[0])


if __name__ == "__main__":
    unittest.main()

import math
import unittest

from cycling_physics import (
    Environment,
    RiderInput,
    RiderParameters,
    SimulationState,
    braking_force_demand,
    step_simulation,
    step_simulation_with_brake_force,
)


def rider():
    return RiderParameters(
        rider_mass_kg=75.0,
        bike_mass_kg=8.5,
        cda_m2=0.32,
        rolling_resistance_coefficient=0.004,
        drivetrain_efficiency=0.97,
    )


def flat_environment():
    return Environment(
        grade_decimal=0.0,
        wind_speed_mps=0.0,
        air_density_kg_m3=1.225,
    )


def state(speed=10.0):
    return SimulationState(
        speed_mps=speed,
        distance_m=0.0,
        elapsed_time_s=0.0,
    )


class TestBrakeForceSimulationStep(unittest.TestCase):
    def test_zero_brake_force_is_exact_regression_parity(self):
        args = (
            rider(),
            flat_environment(),
            RiderInput(power_w=250.0, cadence_rpm=90.0),
            state(10.0),
            0.05,
        )
        legacy = step_simulation(*args)
        explicit_zero = step_simulation_with_brake_force(*args, brake_force_n=0.0)
        self.assertEqual(explicit_zero, legacy)

    def test_positive_brake_force_reduces_speed_relative_to_coast(self):
        r = rider()
        env = flat_environment()
        input_ = RiderInput(power_w=0.0, cadence_rpm=90.0)
        start = state(10.0)

        coast = step_simulation_with_brake_force(
            r, env, input_, start, 0.05, 0.0
        )
        braking = step_simulation_with_brake_force(
            r, env, input_, start, 0.05, 300.0
        )
        self.assertLess(braking.speed_mps, coast.speed_mps)
        self.assertLess(braking.distance_m, coast.distance_m)

    def test_more_brake_force_reduces_speed_more(self):
        r = rider()
        env = flat_environment()
        input_ = RiderInput(power_w=0.0, cadence_rpm=90.0)
        start = state(10.0)

        low = step_simulation_with_brake_force(
            r, env, input_, start, 0.05, 100.0
        )
        high = step_simulation_with_brake_force(
            r, env, input_, start, 0.05, 500.0
        )
        self.assertLess(high.speed_mps, low.speed_mps)

    def test_large_finite_brake_force_never_makes_speed_negative(self):
        result = step_simulation_with_brake_force(
            rider(),
            flat_environment(),
            RiderInput(power_w=0.0, cadence_rpm=90.0),
            state(1.0),
            1.0,
            100000.0,
        )
        self.assertGreaterEqual(result.speed_mps, 0.0)
        self.assertEqual(result.speed_mps, 0.0)

    def test_resolved_tyre_force_can_drive_the_integrator(self):
        r = rider()
        env = flat_environment()
        brake = braking_force_demand(
            r,
            grade_decimal=0.0,
            cross_slope_angle_rad=0.0,
            effective_friction_coefficient=0.8,
            brake_ratio=0.5,
            lateral_usage=0.0,
        )
        start = state(12.0)
        input_ = RiderInput(
            power_w=0.0,
            cadence_rpm=90.0,
            brake_ratio=0.5,
        )
        coast = step_simulation_with_brake_force(
            r, env, input_, start, 0.05, 0.0
        )
        braking = step_simulation_with_brake_force(
            r,
            env,
            input_,
            start,
            0.05,
            brake.applied_brake_force_n,
        )

        self.assertGreater(brake.applied_brake_force_n, 0.0)
        self.assertLess(braking.speed_mps, coast.speed_mps)

    def test_descent_braking_is_separate_from_gravity(self):
        r = rider()
        env = Environment(
            grade_decimal=-0.10,
            wind_speed_mps=0.0,
            air_density_kg_m3=1.225,
        )
        input_ = RiderInput(power_w=0.0, cadence_rpm=90.0)
        start = state(10.0)

        no_brake = step_simulation_with_brake_force(
            r, env, input_, start, 0.05, 0.0
        )
        braking = step_simulation_with_brake_force(
            r, env, input_, start, 0.05, 500.0
        )
        self.assertLess(braking.speed_mps, no_brake.speed_mps)

    def test_invalid_brake_force_rejected(self):
        args = (
            rider(),
            flat_environment(),
            RiderInput(power_w=0.0, cadence_rpm=90.0),
            state(10.0),
            0.05,
        )
        for force in (-0.01, math.nan, math.inf, -math.inf, True, None):
            with self.subTest(force=force):
                with self.assertRaises(ValueError):
                    step_simulation_with_brake_force(*args, brake_force_n=force)

    def test_identical_brake_force_inputs_are_deterministic(self):
        args = (
            rider(),
            flat_environment(),
            RiderInput(power_w=0.0, cadence_rpm=90.0),
            state(10.0),
            0.05,
            350.0,
        )
        first = step_simulation_with_brake_force(*args)
        second = step_simulation_with_brake_force(*args)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

"""Long-run dynamics and step-size stability tests for the reference physics."""

import math
import unittest

from cycling_physics import (
    Environment,
    RiderInput,
    RiderParameters,
    SimulationState,
    step_simulation,
)

RIDER = RiderParameters(
    rider_mass_kg=75.0,
    bike_mass_kg=8.5,
    cda_m2=0.32,
    rolling_resistance_coefficient=0.004,
    drivetrain_efficiency=0.97,
)

AIR_DENSITY_KG_M3 = 1.225

RELATIVE_TOLERANCE = 0.005
FLOAT_EPSILON = 1e-12


def environment_with_grade(grade_decimal):
    return Environment(
        grade_decimal=grade_decimal,
        wind_speed_mps=0.0,
        air_density_kg_m3=AIR_DENSITY_KG_M3,
    )


def rider_input_with_power(power_w):
    return RiderInput(power_w=power_w, cadence_rpm=90.0)


def simulate(state, environment, rider_input, dt_s, duration_s):
    """Run many fixed-size steps and return every intermediate state."""
    steps = int(duration_s / dt_s)
    for _ in range(steps):
        state = step_simulation(RIDER, environment, rider_input, state, dt_s)
        yield state


def final_state(state, environment, rider_input, dt_s, duration_s):
    """Run many fixed-size steps and return the final state."""
    result = state
    for result in simulate(state, environment, rider_input, dt_s, duration_s):
        pass
    return result


def relative_difference(a, b):
    return abs(a - b) / b


class TestStepSizeConvergence(unittest.TestCase):
    def test_coarse_and_fine_step_agree_over_600_seconds(self):
        environment = environment_with_grade(0.0)
        rider_input = rider_input_with_power(250.0)
        start = SimulationState(speed_mps=0.0, distance_m=0.0, elapsed_time_s=0.0)

        coarse = final_state(start, environment, rider_input, 0.05, 600.0)
        fine = final_state(start, environment, rider_input, 0.01, 600.0)

        self.assertGreater(fine.speed_mps, 0.0)
        self.assertLessEqual(
            relative_difference(coarse.speed_mps, fine.speed_mps),
            RELATIVE_TOLERANCE,
        )
        self.assertLessEqual(
            relative_difference(coarse.distance_m, fine.distance_m),
            RELATIVE_TOLERANCE,
        )


class TestMonotonicCoasting(unittest.TestCase):
    def test_speed_never_increases_and_values_stay_non_negative(self):
        environment = environment_with_grade(0.0)
        rider_input = rider_input_with_power(0.0)
        start = SimulationState(speed_mps=12.0, distance_m=0.0, elapsed_time_s=0.0)

        previous_speed = start.speed_mps
        for state in simulate(start, environment, rider_input, 0.05, 30.0):
            self.assertLessEqual(state.speed_mps, previous_speed + FLOAT_EPSILON)
            self.assertGreaterEqual(state.speed_mps, 0.0)
            self.assertGreaterEqual(state.distance_m, 0.0)
            previous_speed = state.speed_mps


class TestStopOnUphill(unittest.TestCase):
    def test_bike_stops_and_stays_stopped_on_8_percent_climb(self):
        environment = environment_with_grade(0.08)
        rider_input = rider_input_with_power(0.0)
        start = SimulationState(speed_mps=5.0, distance_m=0.0, elapsed_time_s=0.0)

        stopped = False
        for state in simulate(start, environment, rider_input, 0.05, 60.0):
            self.assertTrue(math.isfinite(state.speed_mps))
            self.assertTrue(math.isfinite(state.distance_m))
            self.assertTrue(math.isfinite(state.elapsed_time_s))
            self.assertGreaterEqual(state.speed_mps, 0.0)
            self.assertGreaterEqual(state.distance_m, 0.0)
            if state.speed_mps == 0.0:
                stopped = True
            elif stopped:
                self.fail("bike moved again after stopping")

        self.assertTrue(stopped)
        result = final_state(start, environment, rider_input, 0.05, 60.0)
        self.assertEqual(result.speed_mps, 0.0)


class TestAccelerationOnDescent(unittest.TestCase):
    def test_bike_accelerates_from_rest_on_6_percent_descent(self):
        environment = environment_with_grade(-0.06)
        rider_input = rider_input_with_power(0.0)
        start = SimulationState(speed_mps=0.0, distance_m=0.0, elapsed_time_s=0.0)

        result = final_state(start, environment, rider_input, 0.05, 30.0)
        self.assertGreater(result.speed_mps, 0.0)
        self.assertGreater(result.distance_m, 0.0)


class TestDeterministicLongRun(unittest.TestCase):
    def test_two_identical_runs_are_exactly_equal(self):
        environment = environment_with_grade(0.0)
        rider_input = rider_input_with_power(250.0)
        start = SimulationState(speed_mps=0.0, distance_m=0.0, elapsed_time_s=0.0)

        first = final_state(start, environment, rider_input, 0.05, 600.0)
        second = final_state(start, environment, rider_input, 0.05, 600.0)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

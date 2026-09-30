"""Deterministic Golden Ride regression coverage for the reference physics.

The checkpoint values in this file are approved reference outputs. Update them
only when a deliberate physics-model change is reviewed and the resulting drift
is understood.
"""

from dataclasses import dataclass
import unittest

from cycling_physics import (
    Environment,
    RiderInput,
    RiderParameters,
    SimulationState,
    step_simulation,
)

FIXED_STEP_S = 0.05

SPEED_TOLERANCE_MPS = 1e-9
DISTANCE_TOLERANCE_M = 1e-6
TIME_TOLERANCE_S = 1e-8

RIDER = RiderParameters(
    rider_mass_kg=75.0,
    bike_mass_kg=8.5,
    cda_m2=0.32,
    rolling_resistance_coefficient=0.004,
    drivetrain_efficiency=0.97,
)


@dataclass(frozen=True, slots=True)
class GoldenPhase:
    """One fixed-duration phase of the Golden Ride."""

    name: str
    duration_s: float
    environment: Environment
    rider_input: RiderInput
    expected_speed_mps: float
    expected_distance_m: float
    expected_elapsed_time_s: float


GOLDEN_PHASES = (
    GoldenPhase(
        name="warmup_flat",
        duration_s=120.0,
        environment=Environment(
            grade_decimal=0.0,
            wind_speed_mps=0.0,
            air_density_kg_m3=1.225,
        ),
        rider_input=RiderInput(power_w=180.0, cadence_rpm=85.0),
        expected_speed_mps=9.04205091278644,
        expected_distance_m=990.3100920589375,
        expected_elapsed_time_s=120.0,
    ),
    GoldenPhase(
        name="climb_headwind_wet",
        duration_s=180.0,
        environment=Environment(
            grade_decimal=0.06,
            wind_speed_mps=2.0,
            air_density_kg_m3=1.20,
            surface_wetness=0.70,
            rolling_resistance_multiplier=1.18,
            grip_multiplier=0.82,
        ),
        rider_input=RiderInput(power_w=300.0, cadence_rpm=92.0),
        expected_speed_mps=4.725107316129324,
        expected_distance_m=1870.6740284419789,
        expected_elapsed_time_s=300.0,
    ),
    GoldenPhase(
        name="descent_tailwind_coast",
        duration_s=120.0,
        environment=Environment(
            grade_decimal=-0.07,
            wind_speed_mps=-3.0,
            air_density_kg_m3=1.18,
            surface_wetness=0.40,
            rolling_resistance_multiplier=1.08,
            grip_multiplier=0.90,
        ),
        rider_input=RiderInput(power_w=0.0, cadence_rpm=0.0),
        expected_speed_mps=19.854393959326686,
        expected_distance_m=3990.1248734450232,
        expected_elapsed_time_s=420.0,
    ),
    GoldenPhase(
        name="finish_flat_headwind",
        duration_s=180.0,
        environment=Environment(
            grade_decimal=0.0,
            wind_speed_mps=4.0,
            air_density_kg_m3=1.225,
        ),
        rider_input=RiderInput(power_w=220.0, cadence_rpm=88.0),
        expected_speed_mps=7.41078352861369,
        expected_distance_m=5454.449915576454,
        expected_elapsed_time_s=600.0,
    ),
)


def run_golden_ride():
    """Run the approved 10-minute scenario and return phase checkpoints."""
    state = SimulationState(
        speed_mps=0.0,
        distance_m=0.0,
        elapsed_time_s=0.0,
    )
    checkpoints = []

    for phase in GOLDEN_PHASES:
        step_count = round(phase.duration_s / FIXED_STEP_S)
        if abs(step_count * FIXED_STEP_S - phase.duration_s) > TIME_TOLERANCE_S:
            raise AssertionError(
                f"{phase.name} duration must be an exact multiple of the fixed step"
            )

        for _ in range(step_count):
            state = step_simulation(
                RIDER,
                phase.environment,
                phase.rider_input,
                state,
                FIXED_STEP_S,
            )

        checkpoints.append(state)

    return tuple(checkpoints)


class TestGoldenRide(unittest.TestCase):
    def test_checkpoints_match_approved_reference_outputs(self):
        checkpoints = run_golden_ride()

        self.assertEqual(len(checkpoints), len(GOLDEN_PHASES))
        for phase, state in zip(GOLDEN_PHASES, checkpoints, strict=True):
            with self.subTest(phase=phase.name):
                self.assertAlmostEqual(
                    state.speed_mps,
                    phase.expected_speed_mps,
                    delta=SPEED_TOLERANCE_MPS,
                )
                self.assertAlmostEqual(
                    state.distance_m,
                    phase.expected_distance_m,
                    delta=DISTANCE_TOLERANCE_M,
                )
                self.assertAlmostEqual(
                    state.elapsed_time_s,
                    phase.expected_elapsed_time_s,
                    delta=TIME_TOLERANCE_S,
                )

    def test_identical_runs_are_exactly_repeatable(self):
        self.assertEqual(run_golden_ride(), run_golden_ride())


if __name__ == "__main__":
    unittest.main()

"""Tests for the sample Alpine Journey route and its ride plan."""

import unittest

from cycling_physics import (
    ALPINE_JOURNEY,
    Environment,
    RiderInput,
    RiderParameters,
    SimulationState,
    step_simulation,
)

EXPECTED_NAMES = [
    "Village Start",
    "River Descent",
    "Meadow Rollers",
    "Forest Approach",
    "Challenge Climb",
    "Mountain Shelf",
    "High Valley Descent",
    "Lakeside Finish",
]

EXPECTED_LENGTHS_M = [1000.0, 1200.0, 1500.0, 1000.0, 1500.0, 1000.0, 1500.0, 1300.0]

POWER_PLAN = {
    "Village Start": (220.0, 90.0),
    "River Descent": (140.0, 80.0),
    "Meadow Rollers": (230.0, 90.0),
    "Forest Approach": (250.0, 88.0),
    "Challenge Climb": (300.0, 82.0),
    "Mountain Shelf": (200.0, 88.0),
    "High Valley Descent": (0.0, 0.0),
    "Lakeside Finish": (240.0, 92.0),
}

RIDER = RiderParameters(
    rider_mass_kg=75.0,
    bike_mass_kg=8.5,
    cda_m2=0.32,
    rolling_resistance_coefficient=0.004,
    drivetrain_efficiency=0.97,
)

DT_S = 0.05
AIR_DENSITY_KG_M3 = 1.225
MAX_TIME_S = 3600.0


def boundary_distances_m():
    cumulative = []
    running = 0.0
    for length in EXPECTED_LENGTHS_M:
        running += length
        cumulative.append(running)
    return cumulative


def midpoint_distances_m():
    cumulative = [0.0] + boundary_distances_m()
    return [
        0.5 * (cumulative[i] + cumulative[i + 1])
        for i in range(len(EXPECTED_LENGTHS_M))
    ]


def ride_alpine_journey():
    """Ride the full route with the sample power plan; returns the final state."""
    state = SimulationState(speed_mps=0.0, distance_m=0.0, elapsed_time_s=0.0)
    while state.distance_m < ALPINE_JOURNEY.total_length_m and state.elapsed_time_s < MAX_TIME_S:
        segment = ALPINE_JOURNEY.segment_at_distance(state.distance_m)
        power_w, cadence_rpm = POWER_PLAN[segment.name]
        environment = Environment(
            grade_decimal=segment.grade_decimal,
            wind_speed_mps=0.0,
            air_density_kg_m3=AIR_DENSITY_KG_M3,
        )
        rider_input = RiderInput(power_w=power_w, cadence_rpm=cadence_rpm)
        state = step_simulation(RIDER, environment, rider_input, state, DT_S)
    return state


class TestAlpineJourneyProfile(unittest.TestCase):
    def test_profile_name(self):
        self.assertEqual(ALPINE_JOURNEY.name, "Alpine Journey")

    def test_segment_count_and_order(self):
        self.assertEqual(
            [segment.name for segment in ALPINE_JOURNEY.segments],
            EXPECTED_NAMES,
        )

    def test_exact_total_length(self):
        self.assertEqual(ALPINE_JOURNEY.total_length_m, 10000.0)

    def test_single_six_point_five_percent_segment(self):
        matching = [
            segment
            for segment in ALPINE_JOURNEY.segments
            if abs(segment.grade_decimal - 0.065) < 1e-12
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].name, "Challenge Climb")

    def test_total_ascent_in_range(self):
        ascent = ALPINE_JOURNEY.total_ascent_m
        self.assertGreaterEqual(ascent, 140.0)
        self.assertLessEqual(ascent, 170.0)

    def test_total_descent_in_range(self):
        descent = ALPINE_JOURNEY.total_descent_m
        self.assertGreaterEqual(descent, 60.0)
        self.assertLessEqual(descent, 90.0)

    def test_segment_at_each_midpoint(self):
        for expected, distance in zip(ALPINE_JOURNEY.segments, midpoint_distances_m()):
            with self.subTest(segment=expected.name, distance=distance):
                self.assertIs(ALPINE_JOURNEY.segment_at_distance(distance), expected)

    def test_segment_boundaries_select_next_segment(self):
        boundaries = boundary_distances_m()[:-1]
        for index, distance in enumerate(boundaries):
            with self.subTest(distance=distance):
                self.assertIs(
                    ALPINE_JOURNEY.segment_at_distance(distance),
                    ALPINE_JOURNEY.segments[index + 1],
                )

    def test_end_of_route_selects_last_segment(self):
        self.assertIs(
            ALPINE_JOURNEY.segment_at_distance(10000.0),
            ALPINE_JOURNEY.segments[-1],
        )
        self.assertEqual(ALPINE_JOURNEY.segments[-1].name, "Lakeside Finish")


class TestAlpineJourneyRide(unittest.TestCase):
    def test_route_is_completed_between_20_and_30_minutes(self):
        state = ride_alpine_journey()
        self.assertGreaterEqual(state.distance_m, ALPINE_JOURNEY.total_length_m)
        self.assertGreaterEqual(state.elapsed_time_s, 1200.0)
        self.assertLessEqual(state.elapsed_time_s, 1800.0)


if __name__ == "__main__":
    unittest.main()

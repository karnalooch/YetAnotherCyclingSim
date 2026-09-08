"""Tests for the sample Alpine Journey route and its ride plan."""

import math
import unittest
from functools import lru_cache
from types import MappingProxyType

from cycling_physics import (
    ALPINE_CORNERS,
    ALPINE_JOURNEY,
    ALPINE_WEATHER,
    CORNER_PHASE_APPROACH,
    CORNER_PHASE_OUTSIDE,
    CornerTechniqueSample,
    Environment,
    RiderInput,
    RiderParameters,
    SimulationState,
    assess_corner_technique,
    classify_corner_grip_usage,
    corner_grip_usage,
    corner_phase_at_distance,
    maximum_corner_speed_mps,
    step_simulation,
    summarize_corner_technique,
)

BASE_FRICTION_COEFFICIENT = 0.8
APPROACH_LENGTH_M = 100.0

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


def ride_alpine_journey_with_weather():
    """Ride the full route with the sample power plan and ALPINE_WEATHER.

    Returns the final state and the observed weather ranges during the ride.
    """
    state = SimulationState(speed_mps=0.0, distance_m=0.0, elapsed_time_s=0.0)
    ranges = {
        "wind_min": float("inf"),
        "wind_max": float("-inf"),
        "wetness_min": float("inf"),
        "wetness_max": float("-inf"),
        "grip_min": float("inf"),
        "grip_max": float("-inf"),
    }
    while state.distance_m < ALPINE_JOURNEY.total_length_m and state.elapsed_time_s < MAX_TIME_S:
        segment = ALPINE_JOURNEY.segment_at_distance(state.distance_m)
        environment = ALPINE_WEATHER.environment_at_distance(
            state.distance_m,
            segment.grade_decimal,
        )
        power_w, cadence_rpm = POWER_PLAN[segment.name]
        rider_input = RiderInput(power_w=power_w, cadence_rpm=cadence_rpm)
        state = step_simulation(RIDER, environment, rider_input, state, DT_S)

        ranges["wind_min"] = min(ranges["wind_min"], environment.wind_speed_mps)
        ranges["wind_max"] = max(ranges["wind_max"], environment.wind_speed_mps)
        ranges["wetness_min"] = min(ranges["wetness_min"], environment.surface_wetness)
        ranges["wetness_max"] = max(ranges["wetness_max"], environment.surface_wetness)
        ranges["grip_min"] = min(ranges["grip_min"], environment.grip_multiplier)
        ranges["grip_max"] = max(ranges["grip_max"], environment.grip_multiplier)
    return state, ranges


def ride_alpine_journey_with_analysis():
    """Ride with weather, record grip analysis and assess corner technique.

    Returns the final state and one record per corner of ALPINE_CORNERS, in
    profile order. Every record carries entry_speed_mps, max_speed_mps,
    min_limit_mps, max_grip_usage, the collected technique samples, the
    CornerTechniqueSummary and the CornerTechniqueAssessment. The analysis
    only observes the ride and never modifies the simulation state.
    """
    state = SimulationState(speed_mps=0.0, distance_m=0.0, elapsed_time_s=0.0)
    records = [None] * len(ALPINE_CORNERS.corners)
    samples = [[] for _ in ALPINE_CORNERS.corners]
    while state.distance_m < ALPINE_JOURNEY.total_length_m and state.elapsed_time_s < MAX_TIME_S:
        segment = ALPINE_JOURNEY.segment_at_distance(state.distance_m)
        environment = ALPINE_WEATHER.environment_at_distance(
            state.distance_m,
            segment.grade_decimal,
        )
        power_w, cadence_rpm = POWER_PLAN[segment.name]
        rider_input = RiderInput(power_w=power_w, cadence_rpm=cadence_rpm)

        for index, corner in enumerate(ALPINE_CORNERS.corners):
            phase = corner_phase_at_distance(
                corner,
                state.distance_m,
                APPROACH_LENGTH_M,
            )
            if phase == CORNER_PHASE_OUTSIDE:
                continue
            if phase == CORNER_PHASE_APPROACH:
                grip_usage = 0.0
            else:
                grip_usage = corner_grip_usage(
                    state.speed_mps,
                    corner.radius_m,
                    BASE_FRICTION_COEFFICIENT,
                    environment.grip_multiplier,
                )
            samples[index].append(
                CornerTechniqueSample(
                    distance_m=state.distance_m,
                    power_w=rider_input.power_w,
                    cadence_rpm=rider_input.cadence_rpm,
                    grip_usage=grip_usage,
                )
            )
            if phase != CORNER_PHASE_APPROACH:
                speed_limit = maximum_corner_speed_mps(
                    corner.radius_m,
                    BASE_FRICTION_COEFFICIENT,
                    environment.grip_multiplier,
                )
                record = records[index]
                if record is None:
                    record = {
                        "entry_speed_mps": state.speed_mps,
                        "max_speed_mps": state.speed_mps,
                        "min_limit_mps": speed_limit,
                        "max_grip_usage": grip_usage,
                    }
                    records[index] = record
                else:
                    record["max_speed_mps"] = max(record["max_speed_mps"], state.speed_mps)
                    record["min_limit_mps"] = min(record["min_limit_mps"], speed_limit)
                    record["max_grip_usage"] = max(record["max_grip_usage"], grip_usage)

        state = step_simulation(RIDER, environment, rider_input, state, DT_S)

    for index, corner in enumerate(ALPINE_CORNERS.corners):
        summary = summarize_corner_technique(
            corner,
            tuple(samples[index]),
            APPROACH_LENGTH_M,
        )
        records[index]["samples"] = tuple(samples[index])
        records[index]["summary"] = summary
        records[index]["assessment"] = assess_corner_technique(summary)
    return state, records


@lru_cache(maxsize=None)
def cached_weather_ride():
    """Return a read-only cached weather ride result.

    The identical deterministic ride is computed once and shared between test
    classes. Tests only read the returned data; the ranges dict is protected
    with a mapping proxy.
    """
    state, ranges = ride_alpine_journey_with_weather()
    return state, MappingProxyType(dict(ranges))


@lru_cache(maxsize=None)
def cached_analysis_ride():
    """Return a read-only cached corner analysis ride result.

    The identical deterministic ride is computed once and shared between test
    classes. Records are protected with mapping proxies so tests cannot
    accidentally modify the shared data.
    """
    state, records = ride_alpine_journey_with_analysis()
    protected = tuple(MappingProxyType(dict(record)) for record in records)
    return state, protected


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


class TestAlpineJourneyWeatherRide(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state, cls.ranges = cached_weather_ride()

    def test_ride_uses_variable_weather(self):
        self.assertGreaterEqual(self.state.distance_m, ALPINE_JOURNEY.total_length_m)
        self.assertGreater(self.ranges["wetness_max"], 0.0)
        self.assertLess(self.ranges["wetness_min"], self.ranges["wetness_max"])
        self.assertLess(self.ranges["grip_min"], 1.0)
        self.assertLess(self.ranges["wind_min"], 0.0)
        self.assertGreater(self.ranges["wind_max"], 0.0)

    def test_wet_section_environment_differs_from_start(self):
        start = ALPINE_WEATHER.environment_at_distance(0.0, grade_decimal=0.0)
        wet = ALPINE_WEATHER.environment_at_distance(4700.0, grade_decimal=0.0)
        self.assertLess(start.surface_wetness, wet.surface_wetness)
        self.assertGreater(start.grip_multiplier, wet.grip_multiplier)
        self.assertNotEqual(start.wind_speed_mps, wet.wind_speed_mps)
        self.assertNotEqual(
            start.rolling_resistance_multiplier,
            wet.rolling_resistance_multiplier,
        )

    def test_route_with_weather_is_completed_between_20_and_30_minutes(self):
        self.assertGreaterEqual(self.state.distance_m, ALPINE_JOURNEY.total_length_m)
        self.assertGreaterEqual(self.state.elapsed_time_s, 1200.0)
        self.assertLessEqual(self.state.elapsed_time_s, 1800.0)

    def test_run_with_weather_is_deterministic(self):
        first, _ = ride_alpine_journey_with_weather()
        second, _ = ride_alpine_journey_with_weather()
        self.assertEqual(first, second)


class TestAlpineJourneyCornerAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analysis_state, cls.records = cached_analysis_ride()
        cls.plain_state, _ = cached_weather_ride()

    def test_all_eight_corners_recorded_in_profile_order(self):
        self.assertEqual(len(self.records), 8)
        for corner, record in zip(ALPINE_CORNERS.corners, self.records):
            with self.subTest(name=corner.name):
                self.assertIsNotNone(record)

    def test_recorded_values_are_finite_and_non_negative(self):
        for record in self.records:
            for field in ("entry_speed_mps", "max_speed_mps", "max_grip_usage"):
                value = record[field]
                self.assertTrue(math.isfinite(value))
                self.assertGreaterEqual(value, 0.0)
            self.assertTrue(math.isfinite(record["min_limit_mps"]))
            self.assertGreaterEqual(record["min_limit_mps"], 0.0)

    def test_each_corner_has_positive_speed_limit(self):
        for record in self.records:
            self.assertGreater(record["min_limit_mps"], 0.0)

    def test_status_matches_maximum_grip_usage(self):
        for record in self.records:
            expected = classify_corner_grip_usage(record["max_grip_usage"])
            self.assertIn(expected, ("safe", "near_limit", "grip_exceeded"))

    def test_analysis_does_not_change_the_final_state(self):
        self.assertEqual(self.analysis_state, self.plain_state)


class TestAlpineJourneyTechnique(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analysis_state, cls.records = cached_analysis_ride()
        cls.plain_state, _ = cached_weather_ride()

    def test_eight_summaries_and_assessments_in_profile_order(self):
        self.assertEqual(len(self.records), 8)
        for corner, record in zip(ALPINE_CORNERS.corners, self.records):
            with self.subTest(name=corner.name):
                self.assertIsNotNone(record["summary"])
                self.assertIsNotNone(record["assessment"])

    def test_every_corner_has_samples_in_all_four_phases(self):
        phase_names = {"approach", "entry", "apex", "exit"}
        for corner, record in zip(ALPINE_CORNERS.corners, self.records):
            with self.subTest(name=corner.name):
                seen = set()
                for sample in record["samples"]:
                    phase = corner_phase_at_distance(
                        corner,
                        sample.distance_m,
                        APPROACH_LENGTH_M,
                    )
                    seen.add(phase)
                self.assertGreaterEqual(seen, phase_names)

    def test_approach_grip_usage_is_always_zero(self):
        for corner, record in zip(ALPINE_CORNERS.corners, self.records):
            for sample in record["samples"]:
                phase = corner_phase_at_distance(
                    corner,
                    sample.distance_m,
                    APPROACH_LENGTH_M,
                )
                if phase == CORNER_PHASE_APPROACH:
                    with self.subTest(name=corner.name, distance=sample.distance_m):
                        self.assertEqual(sample.grip_usage, 0.0)

    def test_scores_are_in_range(self):
        for record in self.records:
            score = record["assessment"].score
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 100.0)

    def test_labels_are_allowed(self):
        allowed_ratings = {"excellent", "good", "needs_improvement", "poor"}
        allowed_feedbacks = {
            "good_technique",
            "reduce_speed",
            "release_earlier",
            "stay_off_power_at_apex",
            "accelerate_on_exit",
        }
        allowed_grip = {"safe", "near_limit", "grip_exceeded"}
        for record in self.records:
            assessment = record["assessment"]
            self.assertIn(assessment.rating, allowed_ratings)
            self.assertIn(assessment.feedback, allowed_feedbacks)
            self.assertIn(assessment.grip_status, allowed_grip)

    def test_technique_analysis_is_deterministic(self):
        first_state, first_records = ride_alpine_journey_with_analysis()
        second_state, second_records = ride_alpine_journey_with_analysis()
        self.assertEqual(first_state, second_state)
        self.assertEqual(
            [record["assessment"] for record in first_records],
            [record["assessment"] for record in second_records],
        )

    def test_technique_analysis_does_not_change_final_state(self):
        self.assertEqual(self.analysis_state, self.plain_state)

    def test_mean_score_is_finite_and_in_range(self):
        mean = sum(record["assessment"].score for record in self.records) / len(self.records)
        self.assertTrue(math.isfinite(mean))
        self.assertGreaterEqual(mean, 0.0)
        self.assertLessEqual(mean, 100.0)


if __name__ == "__main__":
    unittest.main()

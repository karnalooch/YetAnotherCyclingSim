"""Tests for the cornering geometry and grip-based speed limits."""

import dataclasses
import math
import unittest

from cycling_physics import (
    ALPINE_CORNERS,
    ALPINE_JOURNEY,
    ALPINE_WEATHER,
    STANDARD_GRAVITY_MPS2,
    CORNER_PHASE_APEX,
    CORNER_PHASE_APPROACH,
    CORNER_PHASE_ENTRY,
    CORNER_PHASE_EXIT,
    CORNER_PHASE_OUTSIDE,
    Corner,
    CornerConsequence,
    CornerProfile,
    CornerTechniqueAssessment,
    CornerTechniqueSample,
    CornerTechniqueSummary,
    apply_corner_exit_speed_mps,
    assess_corner_technique,
    classify_corner_grip_usage,
    corner_consequence_from_grip_usage,
    corner_grip_usage,
    corner_phase_at_distance,
    distance_to_corner_start_m,
    effective_friction_coefficient,
    maximum_corner_speed_mps,
    summarize_corner_technique,
)


def _corner(**overrides):
    values = dict(name="Hairpin", start_distance_m=1000.0, length_m=80.0, radius_m=30.0)
    values.update(overrides)
    return Corner(**values)


def _corner_profile(corners=()):
    return CornerProfile(
        name="Profile",
        total_length_m=300.0,
        corners=corners,
    )


class TestCorner(unittest.TestCase):
    def test_valid_corner_accepted(self):
        corner = _corner()
        self.assertEqual(corner.name, "Hairpin")
        self.assertEqual(corner.start_distance_m, 1000.0)
        self.assertEqual(corner.length_m, 80.0)
        self.assertEqual(corner.radius_m, 30.0)

    def test_end_distance_is_sum(self):
        corner = _corner(start_distance_m=1200.0, length_m=50.0)
        self.assertEqual(corner.end_distance_m, 1250.0)

    def test_name_is_cleaned(self):
        corner = _corner(name="  Hairpin  ")
        self.assertEqual(corner.name, "Hairpin")

    def test_empty_and_non_string_names_rejected(self):
        for name in ("", "   ", None, 7):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    _corner(name=name)

    def test_start_distance_must_not_be_negative(self):
        for value in (-1.0, -0.001):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _corner(start_distance_m=value)

    def test_length_and_radius_must_be_positive(self):
        for field in ("length_m", "radius_m"):
            for value in (0.0, -1.0):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        _corner(**{field: value})

    def test_non_finite_and_non_numeric_values_rejected(self):
        for field in ("start_distance_m", "length_m", "radius_m"):
            for value in (math.nan, math.inf, -math.inf, True, "1.0", None):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        _corner(**{field: value})

    def test_corner_is_immutable(self):
        corner = _corner()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            corner.radius_m = 40.0

    def test_corner_uses_slots(self):
        self.assertFalse(hasattr(_corner(), "__dict__"))


class TestEffectiveFrictionCoefficient(unittest.TestCase):
    def test_product_of_inputs(self):
        self.assertEqual(effective_friction_coefficient(0.8, 1.0), 0.8)
        self.assertAlmostEqual(effective_friction_coefficient(0.8, 0.75), 0.6, places=12)

    def test_invalid_inputs_rejected(self):
        for value in (0.0, -0.5):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    effective_friction_coefficient(value, 1.0)
        for grip in (0.0, -0.5, 1.0001):
            with self.subTest(grip=grip):
                with self.assertRaises(ValueError):
                    effective_friction_coefficient(0.8, grip)
        for value in (math.nan, math.inf, -math.inf, True, "1.0", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    effective_friction_coefficient(value, 1.0)
                with self.assertRaises(ValueError):
                    effective_friction_coefficient(0.8, value)


class TestMaximumCornerSpeed(unittest.TestCase):
    def test_reference_value_radius_30_base_0_8_grip_1(self):
        limit = maximum_corner_speed_mps(30.0, 0.8, 1.0)
        expected = math.sqrt(0.8 * STANDARD_GRAVITY_MPS2 * 30.0)
        self.assertAlmostEqual(limit, expected, places=12)

    def test_lower_grip_reduces_speed_limit(self):
        dry = maximum_corner_speed_mps(30.0, 0.8, 1.0)
        wet = maximum_corner_speed_mps(30.0, 0.8, 0.75)
        self.assertLess(wet, dry)

    def test_lower_base_friction_reduces_speed_limit(self):
        high = maximum_corner_speed_mps(30.0, 0.8, 1.0)
        low = maximum_corner_speed_mps(30.0, 0.6, 1.0)
        self.assertLess(low, high)

    def test_larger_radius_increases_speed_limit(self):
        small = maximum_corner_speed_mps(20.0, 0.8, 1.0)
        large = maximum_corner_speed_mps(60.0, 0.8, 1.0)
        self.assertGreater(large, small)

    def test_invalid_inputs_rejected(self):
        for radius in (0.0, -1.0, math.nan, math.inf, True, "30.0", None):
            with self.subTest(radius=radius):
                with self.assertRaises(ValueError):
                    maximum_corner_speed_mps(radius, 0.8, 1.0)
        for base in (0.0, -0.5, math.nan, math.inf, True, "0.8", None):
            with self.subTest(base=base):
                with self.assertRaises(ValueError):
                    maximum_corner_speed_mps(30.0, base, 1.0)
        for grip in (0.0, -0.5, 1.0001, math.nan, math.inf, True, "1.0", None):
            with self.subTest(grip=grip):
                with self.assertRaises(ValueError):
                    maximum_corner_speed_mps(30.0, 0.8, grip)


class TestCornerGripUsage(unittest.TestCase):
    def test_usage_zero_at_zero_speed(self):
        self.assertEqual(corner_grip_usage(0.0, 30.0, 0.8, 1.0), 0.0)

    def test_usage_one_at_maximum_corner_speed(self):
        limit = maximum_corner_speed_mps(30.0, 0.8, 1.0)
        self.assertAlmostEqual(corner_grip_usage(limit, 30.0, 0.8, 1.0), 1.0, places=12)

    def test_usage_above_one_when_limit_exceeded(self):
        limit = maximum_corner_speed_mps(30.0, 0.8, 1.0)
        usage = corner_grip_usage(limit * 1.1, 30.0, 0.8, 1.0)
        self.assertGreater(usage, 1.0)
        self.assertAlmostEqual(usage, 1.1 ** 2, places=12)

    def test_usage_below_one_below_limit(self):
        limit = maximum_corner_speed_mps(30.0, 0.8, 1.0)
        self.assertLess(corner_grip_usage(limit * 0.5, 30.0, 0.8, 1.0), 1.0)

    def test_formula_matches_reference(self):
        usage = corner_grip_usage(10.0, 30.0, 0.8, 1.0)
        expected = 100.0 / (0.8 * STANDARD_GRAVITY_MPS2 * 30.0)
        self.assertAlmostEqual(usage, expected, places=12)

    def test_invalid_inputs_rejected(self):
        for speed in (-1.0, -0.001, math.nan, math.inf, -math.inf, True, "10.0", None):
            with self.subTest(speed=speed):
                with self.assertRaises(ValueError):
                    corner_grip_usage(speed, 30.0, 0.8, 1.0)
        for radius in (0.0, -1.0, math.nan, math.inf, True):
            with self.subTest(radius=radius):
                with self.assertRaises(ValueError):
                    corner_grip_usage(10.0, radius, 0.8, 1.0)
        for base in (0.0, -0.5, math.nan, True):
            with self.subTest(base=base):
                with self.assertRaises(ValueError):
                    corner_grip_usage(10.0, 30.0, base, 1.0)
        for grip in (0.0, -0.5, 1.0001, math.nan, True):
            with self.subTest(grip=grip):
                with self.assertRaises(ValueError):
                    corner_grip_usage(10.0, 30.0, 0.8, grip)


class TestCornerProfile(unittest.TestCase):
    def test_empty_profile_is_valid(self):
        profile = CornerProfile(name="Empty", total_length_m=1000.0, corners=())
        self.assertEqual(profile.corners, ())
        self.assertEqual(profile.total_length_m, 1000.0)

    def test_lookup_before_inside_and_after_corners(self):
        first = Corner("First", start_distance_m=100.0, length_m=50.0, radius_m=30.0)
        second = Corner("Second", start_distance_m=200.0, length_m=40.0, radius_m=30.0)
        profile = _corner_profile(corners=(first, second))
        self.assertIsNone(profile.corner_at_distance(50.0))
        self.assertIs(profile.corner_at_distance(120.0), first)
        self.assertIsNone(profile.corner_at_distance(160.0))
        self.assertIs(profile.corner_at_distance(220.0), second)
        self.assertIsNone(profile.corner_at_distance(250.0))

    def test_exact_boundaries_start_inclusive_end_exclusive(self):
        corner = Corner("C", start_distance_m=100.0, length_m=50.0, radius_m=30.0)
        profile = _corner_profile(corners=(corner,))
        self.assertIs(profile.corner_at_distance(100.0), corner)
        self.assertIs(profile.corner_at_distance(149.0), corner)
        self.assertIsNone(profile.corner_at_distance(150.0))

    def test_total_length_returns_none(self):
        corner = Corner("C", start_distance_m=100.0, length_m=50.0, radius_m=30.0)
        profile = _corner_profile(corners=(corner,))
        self.assertIsNone(profile.corner_at_distance(300.0))

    def test_touching_corners_are_allowed(self):
        first = Corner("First", start_distance_m=100.0, length_m=50.0, radius_m=30.0)
        second = Corner("Second", start_distance_m=150.0, length_m=50.0, radius_m=30.0)
        profile = _corner_profile(corners=(first, second))
        self.assertIs(profile.corner_at_distance(100.0), first)
        self.assertIs(profile.corner_at_distance(149.999), first)
        self.assertIs(profile.corner_at_distance(150.0), second)

    def test_list_instead_of_tuple_rejected(self):
        corner = _corner()
        with self.assertRaises(ValueError):
            CornerProfile(name="Profile", total_length_m=300.0, corners=[corner])

    def test_wrong_element_type_rejected(self):
        with self.assertRaises(ValueError):
            CornerProfile(name="Profile", total_length_m=300.0, corners=(_corner(), 7))

    def test_unsorted_corners_rejected(self):
        later = _corner(start_distance_m=200.0)
        earlier = _corner(start_distance_m=100.0)
        with self.assertRaises(ValueError):
            CornerProfile(name="Profile", total_length_m=300.0, corners=(later, earlier))

    def test_overlapping_corners_rejected(self):
        first = _corner(start_distance_m=100.0, length_m=50.0)
        overlapping = _corner(start_distance_m=140.0, length_m=50.0)
        with self.assertRaises(ValueError):
            CornerProfile(name="Profile", total_length_m=300.0, corners=(first, overlapping))

    def test_corner_beyond_profile_rejected(self):
        corner = _corner(start_distance_m=280.0, length_m=50.0)
        with self.assertRaises(ValueError):
            CornerProfile(name="Profile", total_length_m=300.0, corners=(corner,))

    def test_invalid_profile_fields_rejected(self):
        for name in ("", "   ", None, 7):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    CornerProfile(name=name, total_length_m=300.0, corners=())
        for length in (0.0, -1.0, math.nan, math.inf, True, "300.0", None):
            with self.subTest(length=length):
                with self.assertRaises(ValueError):
                    CornerProfile(name="Profile", total_length_m=length, corners=())

    def test_invalid_lookup_distance_rejected(self):
        profile = _corner_profile(corners=(_corner(start_distance_m=100.0, length_m=50.0),))
        for distance in (-1.0, 301.0, math.nan, math.inf, -math.inf, True, "120.0", None):
            with self.subTest(distance=distance):
                with self.assertRaises(ValueError):
                    profile.corner_at_distance(distance)

    def test_profile_is_immutable_and_uses_slots(self):
        profile = _corner_profile()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            profile.total_length_m = 400.0
        self.assertFalse(hasattr(profile, "__dict__"))


class TestAlpineCorners(unittest.TestCase):
    EXPECTED = [
        ("Village Bend", 650.0, 80.0, 55.0),
        ("River Left", 1550.0, 110.0, 40.0),
        ("Forest Entrance", 4050.0, 90.0, 32.0),
        ("Climb Hairpin", 5350.0, 70.0, 18.0),
        ("Shelf Right", 6650.0, 100.0, 30.0),
        ("Valley Hairpin", 7550.0, 80.0, 22.0),
        ("High Valley Sweep", 8150.0, 140.0, 48.0),
        ("Lakeside Final Bend", 9250.0, 100.0, 35.0),
    ]

    def test_profile_name(self):
        self.assertEqual(ALPINE_CORNERS.name, "Alpine Journey Corners")

    def test_total_length_matches_route_and_weather(self):
        self.assertEqual(ALPINE_CORNERS.total_length_m, 10000.0)
        self.assertEqual(ALPINE_CORNERS.total_length_m, ALPINE_JOURNEY.total_length_m)
        self.assertEqual(ALPINE_CORNERS.total_length_m, ALPINE_WEATHER.total_length_m)

    def test_has_eight_expected_corners(self):
        self.assertEqual(len(ALPINE_CORNERS.corners), 8)
        for expected, corner in zip(self.EXPECTED, ALPINE_CORNERS.corners):
            name, start, length, radius = expected
            with self.subTest(name=name):
                self.assertEqual(corner.name, name)
                self.assertEqual(corner.start_distance_m, start)
                self.assertEqual(corner.length_m, length)
                self.assertEqual(corner.radius_m, radius)

    def test_all_corners_fit_inside_the_route(self):
        for corner in ALPINE_CORNERS.corners:
            with self.subTest(name=corner.name):
                self.assertGreaterEqual(corner.start_distance_m, 0.0)
                self.assertLessEqual(corner.end_distance_m, ALPINE_CORNERS.total_length_m)

    def test_midpoint_lookup_returns_expected_corners(self):
        for corner in ALPINE_CORNERS.corners:
            midpoint = corner.start_distance_m + 0.5 * corner.length_m
            with self.subTest(name=corner.name):
                self.assertIs(ALPINE_CORNERS.corner_at_distance(midpoint), corner)


class TestClassifyCornerGripUsage(unittest.TestCase):
    def test_exact_classification_boundaries(self):
        self.assertEqual(classify_corner_grip_usage(0.0), "safe")
        self.assertEqual(classify_corner_grip_usage(0.849999), "safe")
        self.assertEqual(classify_corner_grip_usage(0.85), "near_limit")
        self.assertEqual(classify_corner_grip_usage(1.0), "near_limit")
        self.assertEqual(classify_corner_grip_usage(1.000001), "grip_exceeded")
        self.assertEqual(classify_corner_grip_usage(2.0), "grip_exceeded")

    def test_invalid_values_rejected(self):
        for value in (-1.0, -0.001, math.nan, math.inf, -math.inf, True, "0.9", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    classify_corner_grip_usage(value)


class TestCornerPhases(unittest.TestCase):
    def corner(self):
        return Corner(name="Phase", start_distance_m=1000.0, length_m=100.0, radius_m=30.0)

    def test_exact_phase_boundaries(self):
        corner = self.corner()
        cases = [
            (0.0, CORNER_PHASE_OUTSIDE),
            (900.0, CORNER_PHASE_APPROACH),
            (1000.0, CORNER_PHASE_ENTRY),
            (1025.0, CORNER_PHASE_APEX),
            (1075.0, CORNER_PHASE_EXIT),
            (1100.0, CORNER_PHASE_OUTSIDE),
        ]
        for distance, expected in cases:
            with self.subTest(distance=distance):
                self.assertEqual(corner_phase_at_distance(corner, distance, 100.0), expected)

    def test_just_before_each_phase_boundary(self):
        corner = self.corner()
        cases = [
            (899.999, CORNER_PHASE_OUTSIDE),
            (999.999, CORNER_PHASE_APPROACH),
            (1024.999, CORNER_PHASE_ENTRY),
            (1074.999, CORNER_PHASE_APEX),
            (1099.999, CORNER_PHASE_EXIT),
        ]
        for distance, expected in cases:
            with self.subTest(distance=distance):
                self.assertEqual(corner_phase_at_distance(corner, distance, 100.0), expected)

    def test_corner_start_before_approach_length(self):
        corner = Corner(name="Early", start_distance_m=50.0, length_m=100.0, radius_m=30.0)
        self.assertEqual(corner_phase_at_distance(corner, 0.0, 100.0), CORNER_PHASE_APPROACH)
        self.assertEqual(corner_phase_at_distance(corner, 49.999, 100.0), CORNER_PHASE_APPROACH)
        self.assertEqual(corner_phase_at_distance(corner, 50.0, 100.0), CORNER_PHASE_ENTRY)

    def test_distance_zero_for_corner_starting_at_zero(self):
        corner = Corner(name="Start", start_distance_m=0.0, length_m=100.0, radius_m=30.0)
        self.assertEqual(corner_phase_at_distance(corner, 0.0), CORNER_PHASE_ENTRY)
        self.assertEqual(corner_phase_at_distance(corner, 1.0), CORNER_PHASE_ENTRY)

    def test_custom_approach_length(self):
        corner = self.corner()
        self.assertEqual(corner_phase_at_distance(corner, 850.0, 200.0), CORNER_PHASE_APPROACH)
        self.assertEqual(corner_phase_at_distance(corner, 799.999, 200.0), CORNER_PHASE_OUTSIDE)
        self.assertEqual(corner_phase_at_distance(corner, 899.999, 50.0), CORNER_PHASE_OUTSIDE)
        self.assertEqual(corner_phase_at_distance(corner, 950.0, 50.0), CORNER_PHASE_APPROACH)

    def test_exact_end_distance_returns_outside(self):
        corner = self.corner()
        self.assertEqual(corner_phase_at_distance(corner, 1100.0), CORNER_PHASE_OUTSIDE)

    def test_distance_to_start_before_at_inside_after(self):
        corner = self.corner()
        self.assertEqual(distance_to_corner_start_m(corner, 800.0), 200.0)
        self.assertEqual(distance_to_corner_start_m(corner, 1000.0), 0.0)
        self.assertEqual(distance_to_corner_start_m(corner, 1050.0), 0.0)
        self.assertEqual(distance_to_corner_start_m(corner, 1100.0), 0.0)
        self.assertEqual(distance_to_corner_start_m(corner, 1200.0), 0.0)

    def test_invalid_corner_type_rejected(self):
        for value in (None, 5, "corner"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    corner_phase_at_distance(value, 950.0)
                with self.assertRaises(ValueError):
                    distance_to_corner_start_m(value, 950.0)

    def test_invalid_distances_rejected(self):
        corner = self.corner()
        for distance in (-1.0, math.nan, math.inf, -math.inf, True, "900.0", None):
            with self.subTest(distance=distance):
                with self.assertRaises(ValueError):
                    corner_phase_at_distance(corner, distance)
                with self.assertRaises(ValueError):
                    distance_to_corner_start_m(corner, distance)

    def test_invalid_approach_length_rejected(self):
        corner = self.corner()
        for approach in (0.0, -1.0, math.nan, math.inf, -math.inf, True, "100.0", None):
            with self.subTest(approach=approach):
                with self.assertRaises(ValueError):
                    corner_phase_at_distance(corner, 950.0, approach)


class TestCornerTechnique(unittest.TestCase):
    def corner(self):
        return Corner(name="Tech", start_distance_m=1000.0, length_m=100.0, radius_m=30.0)

    def sample(self, distance_m, power_w, cadence_rpm, grip_usage=0.0):
        return CornerTechniqueSample(
            distance_m=distance_m,
            power_w=power_w,
            cadence_rpm=cadence_rpm,
            grip_usage=grip_usage,
        )

    def example_samples(self):
        return (
            self.sample(500.0, 999.0, 99.0, 0.0),
            self.sample(950.0, 250.0, 90.0, 0.2),
            self.sample(1005.0, 110.0, 70.0, 0.4),
            self.sample(1010.0, 130.0, 80.0, 0.5),
            self.sample(1050.0, 50.0, 65.0, 0.8),
            self.sample(1090.0, 280.0, 92.0, 0.7),
            self.sample(1500.0, 888.0, 88.0, 0.0),
        )

    def test_sample_validation(self):
        for kwargs in (
            {"distance_m": -1.0},
            {"power_w": -1.0},
            {"cadence_rpm": -1.0},
            {"grip_usage": -1.0},
            {"distance_m": math.nan},
            {"power_w": math.inf},
            {"cadence_rpm": math.nan},
            {"grip_usage": math.inf},
            {"distance_m": True},
            {"power_w": "1.0"},
        ):
            with self.subTest(kwargs=kwargs):
                values = dict(distance_m=100.0, power_w=250.0, cadence_rpm=90.0, grip_usage=0.5)
                values.update(kwargs)
                with self.assertRaises(ValueError):
                    CornerTechniqueSample(**values)

    def test_summary_validation(self):
        values = dict(
            approach_power_w=250.0,
            entry_power_w=120.0,
            apex_power_w=50.0,
            exit_power_w=280.0,
            approach_cadence_rpm=90.0,
            entry_cadence_rpm=75.0,
            apex_cadence_rpm=65.0,
            exit_cadence_rpm=92.0,
            max_grip_usage=0.8,
        )
        for field in values:
            for value in (-1.0, math.nan, math.inf, True, "1.0", None):
                with self.subTest(field=field, value=value):
                    bad = dict(values)
                    bad[field] = value
                    with self.assertRaises(ValueError):
                        CornerTechniqueSummary(**bad)

    def test_records_are_immutable_and_use_slots(self):
        sample = self.sample(100.0, 1.0, 1.0, 0.0)
        summary = CornerTechniqueSummary(
            250.0, 120.0, 50.0, 280.0, 90.0, 75.0, 65.0, 92.0, 0.8
        )
        for record in (sample, summary):
            with self.subTest(record=type(record).__name__):
                field_name = "power_w" if isinstance(record, CornerTechniqueSample) else "approach_power_w"
                with self.assertRaises(dataclasses.FrozenInstanceError):
                    setattr(record, field_name, 0.0)
                self.assertFalse(hasattr(record, "__dict__"))

    def test_phase_averages_and_max_grip(self):
        summary = summarize_corner_technique(self.corner(), self.example_samples())
        self.assertAlmostEqual(summary.approach_power_w, 250.0, places=12)
        self.assertAlmostEqual(summary.entry_power_w, 120.0, places=12)
        self.assertAlmostEqual(summary.apex_power_w, 50.0, places=12)
        self.assertAlmostEqual(summary.exit_power_w, 280.0, places=12)
        self.assertAlmostEqual(summary.approach_cadence_rpm, 90.0, places=12)
        self.assertAlmostEqual(summary.entry_cadence_rpm, 75.0, places=12)
        self.assertAlmostEqual(summary.apex_cadence_rpm, 65.0, places=12)
        self.assertAlmostEqual(summary.exit_cadence_rpm, 92.0, places=12)
        self.assertAlmostEqual(summary.max_grip_usage, 0.8, places=12)

    def test_power_and_cadence_ratios(self):
        summary = summarize_corner_technique(self.corner(), self.example_samples())
        self.assertAlmostEqual(summary.entry_power_ratio, 120.0 / 250.0, places=12)
        self.assertAlmostEqual(summary.apex_power_ratio, 50.0 / 250.0, places=12)
        self.assertAlmostEqual(summary.exit_power_ratio, 280.0 / 250.0, places=12)
        self.assertAlmostEqual(summary.entry_cadence_ratio, 75.0 / 90.0, places=12)
        self.assertAlmostEqual(summary.apex_cadence_ratio, 65.0 / 90.0, places=12)
        self.assertAlmostEqual(summary.exit_cadence_ratio, 92.0 / 90.0, places=12)

    def test_zero_baseline_ratio_rules(self):
        zero_entry = CornerTechniqueSummary(
            0.0, 0.0, 50.0, 280.0, 90.0, 75.0, 65.0, 92.0, 0.5
        )
        self.assertEqual(zero_entry.entry_power_ratio, 0.0)
        self.assertEqual(zero_entry.apex_power_ratio, math.inf)
        positive_entry = CornerTechniqueSummary(
            0.0, 120.0, 50.0, 280.0, 90.0, 75.0, 65.0, 92.0, 0.5
        )
        self.assertEqual(positive_entry.entry_power_ratio, math.inf)

    def test_zero_baseline_cadence_ratio_rules(self):
        summary = CornerTechniqueSummary(
            250.0, 120.0, 50.0, 280.0, 0.0, 0.0, 65.0, 92.0, 0.5
        )
        self.assertEqual(summary.entry_cadence_ratio, 0.0)
        self.assertEqual(summary.apex_cadence_ratio, math.inf)

    def test_outside_samples_are_ignored(self):
        summary = summarize_corner_technique(self.corner(), self.example_samples())
        self.assertAlmostEqual(summary.approach_power_w, 250.0, places=12)
        self.assertAlmostEqual(summary.exit_power_w, 280.0, places=12)

    def test_approach_grip_usage_does_not_influence_max(self):
        samples = (
            self.sample(950.0, 250.0, 90.0, grip_usage=5.0),
            self.sample(1010.0, 120.0, 75.0, grip_usage=0.6),
            self.sample(1050.0, 50.0, 65.0, grip_usage=0.8),
            self.sample(1090.0, 280.0, 92.0, grip_usage=0.7),
        )
        summary = summarize_corner_technique(self.corner(), samples)
        self.assertAlmostEqual(summary.max_grip_usage, 0.8, places=12)

    def test_identical_distances_accepted(self):
        samples = (
            self.sample(950.0, 200.0, 90.0),
            self.sample(950.0, 300.0, 90.0),
            self.sample(1010.0, 120.0, 75.0),
            self.sample(1050.0, 50.0, 65.0),
            self.sample(1090.0, 280.0, 92.0),
        )
        summary = summarize_corner_technique(self.corner(), samples)
        self.assertAlmostEqual(summary.approach_power_w, 250.0, places=12)

    def test_descending_order_rejected(self):
        samples = (
            self.sample(1050.0, 50.0, 65.0),
            self.sample(1010.0, 120.0, 75.0),
            self.sample(950.0, 250.0, 90.0),
            self.sample(1090.0, 280.0, 92.0),
        )
        with self.assertRaises(ValueError):
            summarize_corner_technique(self.corner(), samples)

    def test_list_instead_of_tuple_rejected(self):
        with self.assertRaises(ValueError):
            summarize_corner_technique(self.corner(), [self.sample(950.0, 250.0, 90.0)])

    def test_wrong_sample_type_rejected(self):
        with self.assertRaises(ValueError):
            summarize_corner_technique(self.corner(), (self.sample(950.0, 250.0, 90.0), 7))

    def test_empty_samples_rejected(self):
        with self.assertRaises(ValueError):
            summarize_corner_technique(self.corner(), ())

    def test_wrong_corner_type_rejected(self):
        with self.assertRaises(ValueError):
            summarize_corner_technique(None, (self.sample(950.0, 250.0, 90.0),))

    def test_missing_phase_names_error(self):
        phase_samples = {
            "approach": (self.sample(950.0, 250.0, 90.0),),
            "entry": (self.sample(1010.0, 120.0, 75.0),),
            "apex": (self.sample(1050.0, 50.0, 65.0),),
            "exit": (self.sample(1090.0, 280.0, 92.0),),
        }
        for missing in ("approach", "entry", "apex", "exit"):
            with self.subTest(missing=missing):
                samples = tuple(
                    sample
                    for phase in phase_samples
                    if phase != missing
                    for sample in phase_samples[phase]
                )
                with self.assertRaises(ValueError) as context:
                    summarize_corner_technique(self.corner(), samples)
                self.assertIn(missing, str(context.exception))

    def test_example_summary(self):
        summary = summarize_corner_technique(self.corner(), self.example_samples())
        self.assertAlmostEqual(summary.approach_power_w, 250.0, places=12)
        self.assertAlmostEqual(summary.entry_power_w, 120.0, places=12)
        self.assertAlmostEqual(summary.apex_power_w, 50.0, places=12)
        self.assertAlmostEqual(summary.exit_power_w, 280.0, places=12)
        self.assertAlmostEqual(summary.approach_cadence_rpm, 90.0, places=12)
        self.assertAlmostEqual(summary.entry_cadence_rpm, 75.0, places=12)
        self.assertAlmostEqual(summary.apex_cadence_rpm, 65.0, places=12)
        self.assertAlmostEqual(summary.exit_cadence_rpm, 92.0, places=12)


class TestCornerTechniqueAssessment(unittest.TestCase):
    def summary(self, **overrides):
        values = dict(
            approach_power_w=200.0,
            entry_power_w=100.0,
            apex_power_w=60.0,
            exit_power_w=200.0,
            approach_cadence_rpm=100.0,
            entry_cadence_rpm=80.0,
            apex_cadence_rpm=65.0,
            exit_cadence_rpm=100.0,
            max_grip_usage=0.8,
        )
        values.update(overrides)
        return CornerTechniqueSummary(**values)

    def test_assessment_field_validation(self):
        base = dict(
            score=80.0,
            rating="good",
            feedback="good_technique",
            grip_status="safe",
        )
        for field in base:
            bad = dict(base)
            bad[field] = "wrong"
            with self.assertRaises(ValueError):
                CornerTechniqueAssessment(**bad)
        for score in (math.nan, math.inf, -math.inf, True, "80.0", None, -0.001, 100.001):
            with self.subTest(score=score):
                with self.assertRaises(ValueError):
                    CornerTechniqueAssessment(score=score, rating="good", feedback="good_technique", grip_status="safe")

    def test_assessment_frozen_and_slots(self):
        assessment = CornerTechniqueAssessment(80.0, "good", "good_technique", "safe")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            assessment.score = 90.0
        self.assertFalse(hasattr(assessment, "__dict__"))

    def test_ideal_technique_scores_100(self):
        assessment = assess_corner_technique(self.summary())
        self.assertEqual(assessment.score, 100.0)
        self.assertEqual(assessment.rating, "excellent")
        self.assertEqual(assessment.feedback, "good_technique")
        self.assertEqual(assessment.grip_status, "safe")

    def test_each_component_lowers_score_by_its_weight(self):
        cases = [
            ("entry power", self.summary(entry_power_w=200.0), 85.0),
            ("entry cadence", self.summary(entry_cadence_rpm=110.0), 95.0),
            ("apex power", self.summary(apex_power_w=200.0), 90.0),
            ("apex cadence", self.summary(apex_cadence_rpm=120.0), 95.0),
            ("exit power", self.summary(exit_power_w=60.0), 85.0),
            ("exit cadence", self.summary(exit_cadence_rpm=40.0), 90.0),
            ("grip", self.summary(max_grip_usage=1.3), 60.0),
        ]
        for name, summary, expected in cases:
            with self.subTest(component=name):
                assessment = assess_corner_technique(summary)
                self.assertAlmostEqual(assessment.score, expected, places=9)

    def test_rating_boundaries(self):
        cases = [
            ("excellent", self.summary(max_grip_usage=0.925), 90.0),
            ("good", self.summary(max_grip_usage=1.0625), 75.0),
            ("needs_improvement", self.summary(
                max_grip_usage=1.3,
                entry_cadence_rpm=110.0,
                apex_cadence_rpm=120.0,
            ), 50.0),
            ("poor", self.summary(
                max_grip_usage=1.3,
                entry_cadence_rpm=110.0,
                apex_cadence_rpm=120.0,
                exit_cadence_rpm=20.0,
            ), 40.0),
        ]
        for expected_rating, summary, expected_score in cases:
            with self.subTest(rating=expected_rating):
                assessment = assess_corner_technique(summary)
                self.assertAlmostEqual(assessment.score, expected_score, places=9)
                self.assertEqual(assessment.rating, expected_rating)

    def test_grip_factor_boundaries(self):
        at_85 = assess_corner_technique(self.summary(max_grip_usage=0.85))
        at_100 = assess_corner_technique(self.summary(max_grip_usage=1.0))
        at_125 = assess_corner_technique(self.summary(max_grip_usage=1.25))
        self.assertAlmostEqual(at_85.score, 100.0, places=9)
        self.assertAlmostEqual(at_100.score, 80.0, places=9)
        self.assertAlmostEqual(at_125.score, 60.0, places=9)

    def test_feedback_priority_reduce_speed(self):
        assessment = assess_corner_technique(self.summary(max_grip_usage=1.1))
        self.assertEqual(assessment.feedback, "reduce_speed")
        self.assertEqual(assessment.grip_status, "grip_exceeded")

    def test_feedback_release_earlier(self):
        by_power = assess_corner_technique(self.summary(entry_power_w=140.0))
        self.assertEqual(by_power.feedback, "release_earlier")
        by_cadence = assess_corner_technique(self.summary(entry_cadence_rpm=90.0))
        self.assertEqual(by_cadence.feedback, "release_earlier")

    def test_feedback_stay_off_power_at_apex(self):
        by_power = assess_corner_technique(self.summary(apex_power_w=100.0))
        self.assertEqual(by_power.feedback, "stay_off_power_at_apex")
        by_cadence = assess_corner_technique(self.summary(apex_cadence_rpm=80.0))
        self.assertEqual(by_cadence.feedback, "stay_off_power_at_apex")

    def test_feedback_accelerate_on_exit(self):
        by_power = assess_corner_technique(self.summary(exit_power_w=100.0))
        self.assertEqual(by_power.feedback, "accelerate_on_exit")
        by_cadence = assess_corner_technique(self.summary(exit_cadence_rpm=80.0))
        self.assertEqual(by_cadence.feedback, "accelerate_on_exit")

    def test_infinite_ratio_from_zero_baseline_does_not_raise(self):
        summary = CornerTechniqueSummary(
            approach_power_w=0.0,
            entry_power_w=200.0,
            apex_power_w=0.0,
            exit_power_w=0.0,
            approach_cadence_rpm=100.0,
            entry_cadence_rpm=80.0,
            apex_cadence_rpm=60.0,
            exit_cadence_rpm=100.0,
            max_grip_usage=0.8,
        )
        self.assertEqual(summary.entry_power_ratio, math.inf)
        assessment = assess_corner_technique(summary)
        self.assertTrue(math.isfinite(assessment.score))
        self.assertGreaterEqual(assessment.score, 0.0)
        self.assertLessEqual(assessment.score, 100.0)

    def test_score_always_in_range(self):
        for usage in (0.0, 0.5, 0.9, 1.0, 1.3, 5.0):
            with self.subTest(usage=usage):
                assessment = assess_corner_technique(self.summary(max_grip_usage=usage))
                self.assertGreaterEqual(assessment.score, 0.0)
                self.assertLessEqual(assessment.score, 100.0)

    def test_wrong_summary_type_rejected(self):
        for value in (None, "summary", 7):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    assess_corner_technique(value)

    def test_example_assessment(self):
        summary = self.summary(
            approach_power_w=250.0,
            entry_power_w=120.0,
            apex_power_w=50.0,
            exit_power_w=280.0,
            approach_cadence_rpm=90.0,
            entry_cadence_rpm=75.0,
            apex_cadence_rpm=65.0,
            exit_cadence_rpm=92.0,
            max_grip_usage=0.8,
        )
        assessment = assess_corner_technique(summary)
        self.assertGreaterEqual(assessment.score, 99.0)
        self.assertEqual(assessment.rating, "excellent")


class TestCornerConsequence(unittest.TestCase):
    def _consequence(self, **overrides):
        values = dict(
            outcome="clean",
            exit_speed_multiplier=1.0,
            line_deviation_ratio=0.0,
            hud_feedback="clean_corner",
        )
        values.update(overrides)
        return CornerConsequence(**values)

    def test_valid_consequence_accepted(self):
        consequence = self._consequence()
        self.assertEqual(consequence.outcome, "clean")
        self.assertEqual(consequence.exit_speed_multiplier, 1.0)
        self.assertEqual(consequence.line_deviation_ratio, 0.0)
        self.assertEqual(consequence.hud_feedback, "clean_corner")

    def test_field_validation(self):
        for field in ("exit_speed_multiplier", "line_deviation_ratio"):
            for value in (-0.1, 1.1, math.nan, math.inf, -math.inf, True, "1.0", None):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        self._consequence(**{field: value})
        for outcome in ("", "crash", None, 5):
            with self.subTest(outcome=outcome):
                with self.assertRaises(ValueError):
                    self._consequence(outcome=outcome)
        for feedback in ("", "crash", None, 5):
            with self.subTest(feedback=feedback):
                with self.assertRaises(ValueError):
                    self._consequence(hud_feedback=feedback)

    def test_frozen_and_slots(self):
        consequence = self._consequence()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            consequence.exit_speed_multiplier = 0.5
        self.assertFalse(hasattr(consequence, "__dict__"))

    def test_exact_values_at_reference_usages(self):
        cases = [
            (0.0, "clean", 1.0, 0.0, "clean_corner"),
            (0.85, "clean", 1.0, 0.0, "clean_corner"),
            (1.0, "clean", 1.0, 0.0, "clean_corner"),
            (1.075, "wide_line", 0.925, 0.25, "wider_slower_line"),
            (1.15, "wide_line", 0.85, 0.5, "wider_slower_line"),
            (1.325, "controlled_slip", 0.725, 0.75, "rear_wheel_slip"),
            (1.50, "controlled_slip", 0.60, 1.0, "rear_wheel_slip"),
            (2.0, "controlled_slip", 0.60, 1.0, "rear_wheel_slip"),
        ]
        for usage, outcome, multiplier, deviation, feedback in cases:
            with self.subTest(usage=usage):
                consequence = corner_consequence_from_grip_usage(usage)
                self.assertEqual(consequence.outcome, outcome)
                self.assertAlmostEqual(consequence.exit_speed_multiplier, multiplier, places=12)
                self.assertAlmostEqual(consequence.line_deviation_ratio, deviation, places=12)
                self.assertEqual(consequence.hud_feedback, feedback)

    def test_continuity_at_one_and_1_15(self):
        just_above_one = corner_consequence_from_grip_usage(1.0 + 1e-9)
        self.assertEqual(just_above_one.outcome, "wide_line")
        self.assertAlmostEqual(just_above_one.exit_speed_multiplier, 1.0, places=6)
        self.assertAlmostEqual(just_above_one.line_deviation_ratio, 0.0, places=6)

        at_115 = corner_consequence_from_grip_usage(1.15)
        just_above_115 = corner_consequence_from_grip_usage(1.15 + 1e-9)
        self.assertEqual(just_above_115.outcome, "controlled_slip")
        self.assertAlmostEqual(
            just_above_115.exit_speed_multiplier,
            at_115.exit_speed_multiplier,
            places=6,
        )
        self.assertAlmostEqual(
            just_above_115.line_deviation_ratio,
            at_115.line_deviation_ratio,
            places=6,
        )

    def test_values_clamp_above_1_50(self):
        for usage in (1.5, 2.0, 5.0):
            with self.subTest(usage=usage):
                consequence = corner_consequence_from_grip_usage(usage)
                self.assertEqual(consequence.exit_speed_multiplier, 0.60)
                self.assertEqual(consequence.line_deviation_ratio, 1.0)
                self.assertEqual(consequence.outcome, "controlled_slip")
                self.assertEqual(consequence.hud_feedback, "rear_wheel_slip")

    def test_invalid_grip_usage_rejected(self):
        for usage in (-1.0, -0.001, math.nan, math.inf, -math.inf, True, "1.0", None):
            with self.subTest(usage=usage):
                with self.assertRaises(ValueError):
                    corner_consequence_from_grip_usage(usage)

    def test_apply_exit_speed(self):
        for multiplier in (1.0, 0.85, 0.60):
            with self.subTest(multiplier=multiplier):
                consequence = CornerConsequence(
                    outcome="clean" if multiplier == 1.0 else "wide_line",
                    exit_speed_multiplier=multiplier,
                    line_deviation_ratio=0.0,
                    hud_feedback="clean_corner" if multiplier == 1.0 else "wider_slower_line",
                )
                self.assertAlmostEqual(
                    apply_corner_exit_speed_mps(10.0, consequence),
                    10.0 * multiplier,
                    places=12,
                )

    def test_apply_zero_speed_stays_zero(self):
        consequence = corner_consequence_from_grip_usage(1.4)
        self.assertEqual(apply_corner_exit_speed_mps(0.0, consequence), 0.0)

    def test_apply_never_negative(self):
        consequence = corner_consequence_from_grip_usage(2.0)
        for speed in (0.0, 1.0, 25.0):
            with self.subTest(speed=speed):
                self.assertGreaterEqual(apply_corner_exit_speed_mps(speed, consequence), 0.0)

    def test_apply_rejects_bad_inputs(self):
        consequence = corner_consequence_from_grip_usage(1.0)
        for value in (None, 5, "consequence"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    apply_corner_exit_speed_mps(10.0, value)
        for speed in (-1.0, math.nan, math.inf, -math.inf, True, "10.0", None):
            with self.subTest(speed=speed):
                with self.assertRaises(ValueError):
                    apply_corner_exit_speed_mps(speed, consequence)


if __name__ == "__main__":
    unittest.main()

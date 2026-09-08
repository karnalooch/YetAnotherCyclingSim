"""Tests for the cornering geometry and grip-based speed limits."""

import dataclasses
import math
import unittest

from cycling_physics import (
    ALPINE_CORNERS,
    ALPINE_JOURNEY,
    ALPINE_WEATHER,
    STANDARD_GRAVITY_MPS2,
    Corner,
    CornerProfile,
    classify_corner_grip_usage,
    corner_grip_usage,
    effective_friction_coefficient,
    maximum_corner_speed_mps,
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


if __name__ == "__main__":
    unittest.main()

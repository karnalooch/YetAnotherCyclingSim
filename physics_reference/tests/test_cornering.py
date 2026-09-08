"""Tests for the cornering geometry and grip-based speed limits."""

import dataclasses
import math
import unittest

from cycling_physics import (
    STANDARD_GRAVITY_MPS2,
    Corner,
    corner_grip_usage,
    effective_friction_coefficient,
    maximum_corner_speed_mps,
)


def _corner(**overrides):
    values = dict(name="Hairpin", start_distance_m=1000.0, length_m=80.0, radius_m=30.0)
    values.update(overrides)
    return Corner(**values)


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


if __name__ == "__main__":
    unittest.main()

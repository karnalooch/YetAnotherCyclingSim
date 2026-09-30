"""Tests for the distance-based weather profile data contracts."""

import dataclasses
import math
import unittest

from cycling_physics import (
    ALPINE_JOURNEY,
    ALPINE_WEATHER,
    Environment,
    WeatherKeyframe,
    WeatherProfile,
)


def _keyframe(distance_m=0.0, **overrides):
    values = dict(
        distance_m=distance_m,
        wind_speed_mps=-1.0,
        air_density_kg_m3=1.225,
        surface_wetness=0.0,
        rolling_resistance_multiplier=1.0,
        grip_multiplier=1.0,
    )
    values.update(overrides)
    return WeatherKeyframe(**values)


def _profile():
    return WeatherProfile(
        name="Test weather",
        keyframes=(
            _keyframe(distance_m=0.0, wind_speed_mps=0.0, air_density_kg_m3=1.2),
            _keyframe(
                distance_m=1000.0,
                wind_speed_mps=2.0,
                air_density_kg_m3=1.0,
                surface_wetness=0.4,
                rolling_resistance_multiplier=1.2,
                grip_multiplier=0.8,
            ),
        ),
    )


class TestWeatherKeyframeValidation(unittest.TestCase):
    def test_valid_keyframe_accepted(self):
        keyframe = _keyframe(
            distance_m=500.0,
            wind_speed_mps=-0.5,
            air_density_kg_m3=1.21,
            surface_wetness=0.3,
            rolling_resistance_multiplier=1.05,
            grip_multiplier=0.9,
        )
        self.assertEqual(keyframe.distance_m, 500.0)
        self.assertEqual(keyframe.wind_speed_mps, -0.5)
        self.assertEqual(keyframe.air_density_kg_m3, 1.21)
        self.assertEqual(keyframe.surface_wetness, 0.3)
        self.assertEqual(keyframe.rolling_resistance_multiplier, 1.05)
        self.assertEqual(keyframe.grip_multiplier, 0.9)

    def test_distance_must_not_be_negative(self):
        with self.assertRaises(ValueError):
            _keyframe(distance_m=-1.0)

    def test_wind_may_be_negative(self):
        keyframe = _keyframe(distance_m=10.0, wind_speed_mps=-5.0)
        self.assertEqual(keyframe.wind_speed_mps, -5.0)

    def test_air_density_must_be_positive(self):
        for density in (0.0, -1.0):
            with self.subTest(density=density):
                with self.assertRaises(ValueError):
                    _keyframe(distance_m=10.0, air_density_kg_m3=density)

    def test_surface_wetness_must_be_in_unit_interval(self):
        for wetness in (-0.1, 1.1):
            with self.subTest(wetness=wetness):
                with self.assertRaises(ValueError):
                    _keyframe(distance_m=10.0, surface_wetness=wetness)

    def test_rolling_multiplier_must_be_positive(self):
        for multiplier in (0.0, -1.0):
            with self.subTest(multiplier=multiplier):
                with self.assertRaises(ValueError):
                    _keyframe(distance_m=10.0, rolling_resistance_multiplier=multiplier)

    def test_grip_must_be_in_open_unit_interval(self):
        for grip in (0.0, -0.5, 1.0001):
            with self.subTest(grip=grip):
                with self.assertRaises(ValueError):
                    _keyframe(distance_m=10.0, grip_multiplier=grip)

    def test_non_numeric_values_rejected(self):
        fields = (
            "distance_m",
            "wind_speed_mps",
            "air_density_kg_m3",
            "surface_wetness",
            "rolling_resistance_multiplier",
            "grip_multiplier",
        )
        for field in fields:
            for value in (math.nan, math.inf, -math.inf, True, "1.0", None):
                with self.subTest(field=field, value=value):
                    values = dict(
                        distance_m=10.0,
                        wind_speed_mps=-1.0,
                        air_density_kg_m3=1.225,
                        surface_wetness=0.0,
                        rolling_resistance_multiplier=1.0,
                        grip_multiplier=1.0,
                    )
                    values[field] = value
                    with self.assertRaises(ValueError):
                        WeatherKeyframe(**values)


class TestWeatherProfileValidation(unittest.TestCase):
    def test_valid_profile_accepted(self):
        profile = _profile()
        self.assertEqual(profile.name, "Test weather")
        self.assertEqual(len(profile.keyframes), 2)

    def test_name_is_cleaned(self):
        profile = WeatherProfile(
            name="  Weather  ",
            keyframes=(_keyframe(distance_m=0.0), _keyframe(distance_m=100.0)),
        )
        self.assertEqual(profile.name, "Weather")

    def test_empty_name_rejected(self):
        with self.assertRaises(ValueError):
            WeatherProfile(name="   ", keyframes=(_keyframe(0.0), _keyframe(100.0)))

    def test_list_instead_of_tuple_rejected(self):
        with self.assertRaises(ValueError):
            WeatherProfile(
                name="Weather",
                keyframes=[_keyframe(0.0), _keyframe(100.0)],
            )

    def test_fewer_than_two_keyframes_rejected(self):
        with self.assertRaises(ValueError):
            WeatherProfile(name="Weather", keyframes=(_keyframe(0.0),))

    def test_wrong_element_type_rejected(self):
        with self.assertRaises(ValueError):
            WeatherProfile(
                name="Weather",
                keyframes=(_keyframe(0.0), 7),
            )

    def test_first_distance_must_be_zero(self):
        with self.assertRaises(ValueError):
            WeatherProfile(
                name="Weather",
                keyframes=(_keyframe(distance_m=100.0), _keyframe(distance_m=200.0)),
            )

    def test_distances_must_be_strictly_increasing(self):
        for first, second in ((0.0, 0.0), (0.0, -5.0)):
            with self.subTest(first=first, second=second):
                with self.assertRaises(ValueError):
                    WeatherProfile(
                        name="Weather",
                        keyframes=(_keyframe(distance_m=first), _keyframe(distance_m=second)),
                    )

    def test_total_length_is_last_keyframe_distance(self):
        self.assertEqual(_profile().total_length_m, 1000.0)


class TestEnvironmentAtDistance(unittest.TestCase):
    def test_zero_distance_returns_first_keyframe_exactly(self):
        profile = _profile()
        environment = profile.environment_at_distance(0.0, grade_decimal=0.0)
        self.assertEqual(environment.wind_speed_mps, 0.0)
        self.assertEqual(environment.air_density_kg_m3, 1.2)
        self.assertEqual(environment.surface_wetness, 0.0)
        self.assertEqual(environment.rolling_resistance_multiplier, 1.0)
        self.assertEqual(environment.grip_multiplier, 1.0)

    def test_exact_keyframe_distance_returns_keyframe_values(self):
        profile = _profile()
        environment = profile.environment_at_distance(1000.0, grade_decimal=0.05)
        self.assertEqual(environment.wind_speed_mps, 2.0)
        self.assertEqual(environment.air_density_kg_m3, 1.0)
        self.assertEqual(environment.surface_wetness, 0.4)
        self.assertEqual(environment.rolling_resistance_multiplier, 1.2)
        self.assertEqual(environment.grip_multiplier, 0.8)

    def test_midpoint_interpolation(self):
        profile = _profile()
        environment = profile.environment_at_distance(500.0, grade_decimal=0.0)
        self.assertAlmostEqual(environment.wind_speed_mps, 1.0, places=12)
        self.assertAlmostEqual(environment.air_density_kg_m3, 1.1, places=12)
        self.assertAlmostEqual(environment.surface_wetness, 0.2, places=12)
        self.assertAlmostEqual(environment.rolling_resistance_multiplier, 1.1, places=12)
        self.assertAlmostEqual(environment.grip_multiplier, 0.9, places=12)

    def test_interior_interpolation_is_linear(self):
        profile = _profile()
        environment = profile.environment_at_distance(250.0, grade_decimal=0.0)
        self.assertAlmostEqual(environment.wind_speed_mps, 0.5, places=12)
        self.assertAlmostEqual(environment.surface_wetness, 0.1, places=12)

    def test_grade_decimal_passed_through(self):
        profile = _profile()
        environment = profile.environment_at_distance(500.0, grade_decimal=-0.04)
        self.assertEqual(environment.grade_decimal, -0.04)

    def test_distance_outside_profile_rejected(self):
        profile = _profile()
        for distance in (-1.0, 1000.1):
            with self.subTest(distance=distance):
                with self.assertRaises(ValueError):
                    profile.environment_at_distance(distance, grade_decimal=0.0)

    def test_non_finite_and_bool_distance_rejected(self):
        profile = _profile()
        for distance in (math.nan, math.inf, -math.inf, True, False, None):
            with self.subTest(distance=distance):
                with self.assertRaises(ValueError):
                    profile.environment_at_distance(distance, grade_decimal=0.0)

    def test_non_finite_and_bool_grade_rejected(self):
        profile = _profile()
        for grade in (math.nan, math.inf, -math.inf, True, None):
            with self.subTest(grade=grade):
                with self.assertRaises(ValueError):
                    profile.environment_at_distance(0.0, grade_decimal=grade)


class TestWeatherImmutability(unittest.TestCase):
    def test_keyframe_is_immutable(self):
        keyframe = _keyframe()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            keyframe.wind_speed_mps = 2.0

    def test_profile_is_immutable(self):
        profile = _profile()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            profile.name = "Other"

    def test_records_use_slots(self):
        for record in (_keyframe(), _profile()):
            with self.subTest(record=type(record).__name__):
                self.assertFalse(hasattr(record, "__dict__"))


class TestAlpineWeather(unittest.TestCase):
    def test_alpine_weather_name(self):
        self.assertEqual(ALPINE_WEATHER.name, "Alpine Journey Scripted Weather")

    def test_alpine_weather_total_length(self):
        self.assertEqual(ALPINE_WEATHER.total_length_m, 10000.0)

    def test_alpine_weather_matches_journey_length(self):
        self.assertEqual(
            ALPINE_WEATHER.total_length_m,
            ALPINE_JOURNEY.total_length_m,
        )

    def test_alpine_weather_wet_peak_matches_plan(self):
        environment = ALPINE_WEATHER.environment_at_distance(6200.0, grade_decimal=0.0)
        self.assertEqual(environment.surface_wetness, 1.0)
        self.assertEqual(environment.grip_multiplier, 0.75)
        self.assertEqual(environment.rolling_resistance_multiplier, 1.12)


if __name__ == "__main__":
    unittest.main()

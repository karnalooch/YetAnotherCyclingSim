"""Unit tests for the segmented route data contracts."""

import dataclasses
import math
import unittest

from cycling_physics import RouteProfile, RouteSegment


def _flat_segment():
    return RouteSegment(name="Flat", length_m=100.0, grade_decimal=0.0)


def _climb_segment():
    return RouteSegment(name="Climb", length_m=200.0, grade_decimal=0.08)


def _descent_segment():
    return RouteSegment(name="Descent", length_m=150.0, grade_decimal=-0.05)


def _profile():
    return RouteProfile(name="Test route", segments=(_flat_segment(), _climb_segment(), _descent_segment()))


def _elevation(length_m, grade_decimal):
    return length_m * math.sin(math.atan(grade_decimal))


class TestRouteSegmentConstruction(unittest.TestCase):
    def test_valid_segment_accepted(self):
        segment = _climb_segment()
        self.assertEqual(segment.name, "Climb")
        self.assertEqual(segment.length_m, 200.0)
        self.assertEqual(segment.grade_decimal, 0.08)

    def test_name_is_stripped(self):
        segment = RouteSegment(name="  Valley road  ", length_m=10.0, grade_decimal=0.01)
        self.assertEqual(segment.name, "Valley road")

    def test_empty_name_rejected(self):
        for name in ("", "   ", "\t\n"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    RouteSegment(name=name, length_m=10.0, grade_decimal=0.0)

    def test_non_string_name_rejected(self):
        for name in (None, 7, True):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    RouteSegment(name=name, length_m=10.0, grade_decimal=0.0)

    def test_length_zero_and_negative_rejected(self):
        for length in (0.0, -1.0):
            with self.subTest(length=length):
                with self.assertRaises(ValueError):
                    RouteSegment(name="Segment", length_m=length, grade_decimal=0.0)

    def test_length_and_grade_non_finite_rejected(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    RouteSegment(name="Segment", length_m=value, grade_decimal=0.0)
                with self.assertRaises(ValueError):
                    RouteSegment(name="Segment", length_m=10.0, grade_decimal=value)

    def test_bool_rejected_as_number(self):
        for value in (True, False):
            with self.subTest(field="length_m", value=value):
                with self.assertRaises(ValueError):
                    RouteSegment(name="Segment", length_m=value, grade_decimal=0.0)
            with self.subTest(field="grade_decimal", value=value):
                with self.assertRaises(ValueError):
                    RouteSegment(name="Segment", length_m=10.0, grade_decimal=value)

    def test_no_arbitrary_grade_limit(self):
        segment = RouteSegment(name="Steep", length_m=10.0, grade_decimal=2.0)
        self.assertEqual(segment.grade_decimal, 2.0)

    def test_fields_stored_as_floats(self):
        segment = RouteSegment(name="Segment", length_m=10, grade_decimal=1)
        self.assertIsInstance(segment.length_m, float)
        self.assertIsInstance(segment.grade_decimal, float)

    def test_elevation_change_climb_is_positive(self):
        segment = _climb_segment()
        self.assertGreater(segment.elevation_change_m, 0.0)
        self.assertAlmostEqual(segment.elevation_change_m, _elevation(200.0, 0.08), places=12)

    def test_elevation_change_descent_is_negative(self):
        segment = _descent_segment()
        self.assertLess(segment.elevation_change_m, 0.0)
        self.assertAlmostEqual(segment.elevation_change_m, _elevation(150.0, -0.05), places=12)

    def test_elevation_change_flat_is_zero(self):
        self.assertEqual(_flat_segment().elevation_change_m, 0.0)


class TestRouteProfileConstruction(unittest.TestCase):
    def test_valid_profile_accepted(self):
        profile = _profile()
        self.assertEqual(profile.name, "Test route")
        self.assertEqual(len(profile.segments), 3)

    def test_name_is_stripped(self):
        profile = RouteProfile(name="  Alpine loop  ", segments=(_flat_segment(),))
        self.assertEqual(profile.name, "Alpine loop")

    def test_empty_name_rejected(self):
        with self.assertRaises(ValueError):
            RouteProfile(name="   ", segments=(_flat_segment(),))

    def test_list_instead_of_tuple_rejected(self):
        with self.assertRaises(ValueError):
            RouteProfile(name="Route", segments=[_flat_segment()])

    def test_empty_tuple_rejected(self):
        with self.assertRaises(ValueError):
            RouteProfile(name="Route", segments=())

    def test_wrong_element_type_rejected(self):
        with self.assertRaises(ValueError):
            RouteProfile(name="Route", segments=(_flat_segment(), 7))


class TestRouteProfileTotals(unittest.TestCase):
    def test_total_length(self):
        self.assertAlmostEqual(_profile().total_length_m, 450.0, places=12)

    def test_total_elevation_change(self):
        profile = _profile()
        expected = (
            _elevation(200.0, 0.08)
            + _elevation(150.0, -0.05)
        )
        self.assertAlmostEqual(profile.total_elevation_change_m, expected, places=12)

    def test_total_ascent_and_descent(self):
        profile = _profile()
        ascent = _elevation(200.0, 0.08)
        descent = -_elevation(150.0, -0.05)
        self.assertAlmostEqual(profile.total_ascent_m, ascent, places=12)
        self.assertAlmostEqual(profile.total_descent_m, descent, places=12)
        self.assertGreater(profile.total_ascent_m, 0.0)
        self.assertGreater(profile.total_descent_m, 0.0)


class TestSegmentAtDistance(unittest.TestCase):
    def test_zero_returns_first_segment(self):
        profile = _profile()
        self.assertIs(profile.segment_at_distance(0.0), profile.segments[0])

    def test_interior_of_first_segment(self):
        profile = _profile()
        self.assertIs(profile.segment_at_distance(50.0), profile.segments[0])

    def test_interior_of_second_segment(self):
        profile = _profile()
        self.assertIs(profile.segment_at_distance(250.0), profile.segments[1])

    def test_exact_boundary_returns_next_segment(self):
        profile = _profile()
        self.assertIs(profile.segment_at_distance(100.0), profile.segments[1])
        self.assertIs(profile.segment_at_distance(300.0), profile.segments[2])

    def test_end_of_route_returns_last_segment(self):
        profile = _profile()
        self.assertIs(profile.segment_at_distance(450.0), profile.segments[2])

    def test_negative_distance_rejected(self):
        with self.assertRaises(ValueError):
            _profile().segment_at_distance(-1.0)

    def test_distance_beyond_route_rejected(self):
        with self.assertRaises(ValueError):
            _profile().segment_at_distance(451.0)

    def test_non_finite_distance_rejected(self):
        for distance in (math.nan, math.inf, -math.inf):
            with self.subTest(distance=distance):
                with self.assertRaises(ValueError):
                    _profile().segment_at_distance(distance)

    def test_bool_distance_rejected(self):
        for distance in (True, False):
            with self.subTest(distance=distance):
                with self.assertRaises(ValueError):
                    _profile().segment_at_distance(distance)


class TestRouteImmutability(unittest.TestCase):
    def test_segment_is_immutable(self):
        segment = _climb_segment()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            segment.name = "Other"

    def test_profile_is_immutable(self):
        profile = _profile()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            profile.name = "Other"

    def test_records_use_slots(self):
        segment = _climb_segment()
        profile = _profile()
        for record in (segment, profile):
            with self.subTest(record=type(record).__name__):
                self.assertFalse(hasattr(record, "__dict__"))


if __name__ == "__main__":
    unittest.main()

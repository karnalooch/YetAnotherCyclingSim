import dataclasses
import math
import unittest

from cycling_physics import (
    ALPINE_SURFACE_GRIP_POLICY,
    ALPINE_WEATHER,
    ResolvedSurfaceGrip,
    SurfaceGripPolicy,
    SurfaceGripRule,
)


class TestSurfaceGripRule(unittest.TestCase):
    def test_trims_surface_id_and_validates_multipliers(self):
        rule = SurfaceGripRule("  asphalt  ", 1.0, 0.75)
        self.assertEqual(rule.surface_id, "asphalt")
        self.assertEqual(rule.dry_grip_multiplier, 1.0)
        self.assertEqual(rule.fully_wet_grip_multiplier, 0.75)

        for values in (
            ("", 1.0, 0.75),
            ("asphalt", 0.0, 0.75),
            ("asphalt", 1.01, 0.75),
            ("asphalt", 1.0, 0.0),
            ("asphalt", 1.0, 1.01),
            ("asphalt", math.nan, 0.75),
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    SurfaceGripRule(*values)

    def test_rule_is_immutable(self):
        rule = SurfaceGripRule("asphalt", 1.0, 0.75)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            rule.surface_id = "paint"


class TestSurfaceGripPolicy(unittest.TestCase):
    def policy(self):
        return SurfaceGripPolicy(
            "test",
            (
                SurfaceGripRule("asphalt", 1.0, 0.75),
                SurfaceGripRule("paint", 0.9, 0.6),
            ),
        )

    def test_resolve_uses_linear_wetness_interpolation(self):
        policy = self.policy()

        dry = policy.resolve("asphalt", 0.0)
        half = policy.resolve("asphalt", 0.5)
        wet = policy.resolve("asphalt", 1.0)

        self.assertEqual(dry.grip_multiplier, 1.0)
        self.assertAlmostEqual(half.grip_multiplier, 0.875, places=12)
        self.assertEqual(wet.grip_multiplier, 0.75)
        self.assertEqual(half.surface_id, "asphalt")
        self.assertEqual(half.wetness, 0.5)

    def test_surface_rules_are_independent(self):
        policy = self.policy()
        asphalt = policy.resolve("asphalt", 0.5)
        paint = policy.resolve("paint", 0.5)
        self.assertNotEqual(asphalt.grip_multiplier, paint.grip_multiplier)
        self.assertAlmostEqual(paint.grip_multiplier, 0.75, places=12)

    def test_unknown_surface_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "not configured"):
            self.policy().resolve("gravel", 0.5)

    def test_invalid_wetness_rejected(self):
        policy = self.policy()
        for value in (-0.01, 1.01, math.nan, math.inf, True, None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    policy.resolve("asphalt", value)

    def test_policy_requires_unique_explicit_rules(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            SurfaceGripPolicy("empty", ())

        with self.assertRaisesRegex(ValueError, "duplicate surface_id"):
            SurfaceGripPolicy(
                "duplicate",
                (
                    SurfaceGripRule("asphalt", 1.0, 0.75),
                    SurfaceGripRule("asphalt", 0.9, 0.7),
                ),
            )

        with self.assertRaises(ValueError):
            SurfaceGripPolicy("wrong container", [SurfaceGripRule("asphalt", 1.0, 0.75)])

    def test_resolved_record_is_immutable(self):
        result = self.policy().resolve("asphalt", 0.5)
        self.assertIsInstance(result, ResolvedSurfaceGrip)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.grip_multiplier = 1.0


class TestAlpineSurfaceGripParity(unittest.TestCase):
    def test_existing_weather_keyframes_match_new_asphalt_policy(self):
        for keyframe in ALPINE_WEATHER.keyframes:
            with self.subTest(distance_m=keyframe.distance_m):
                resolved = ALPINE_SURFACE_GRIP_POLICY.resolve(
                    "asphalt",
                    keyframe.surface_wetness,
                )
                self.assertAlmostEqual(
                    resolved.grip_multiplier,
                    keyframe.grip_multiplier,
                    places=12,
                )

    def test_alpine_policy_has_no_hidden_non_asphalt_rule(self):
        self.assertEqual(len(ALPINE_SURFACE_GRIP_POLICY.rules), 1)
        self.assertEqual(ALPINE_SURFACE_GRIP_POLICY.rules[0].surface_id, "asphalt")


if __name__ == "__main__":
    unittest.main()

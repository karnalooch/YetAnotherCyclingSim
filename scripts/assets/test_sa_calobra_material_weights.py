"""Regression checks for minority loss, overlay erosion and fallback semantics."""

import math
import random
import unittest

from scripts.assets.sa_calobra_material_weights import compose_weights


class MaterialWeightsTests(unittest.TestCase):
    def test_default_preserves_minority_even_on_vertical_surface(self):
        result = compose_weights((0.2, 0, 0.8, 0), 0)
        self.assertAlmostEqual(result["DryGrass"], 0.2)
        self.assertAlmostEqual(result["ExposedRock"], 0.8)

    def test_overlay_is_not_sharpened_or_replaced_by_slope(self):
        for alpha in (0.0, 0.2, 0.5, 1.0):
            result = compose_weights(
                (0.2, 0.3, 0.4, alpha), 0, exponent=2, slope_strength=1
            )
            self.assertAlmostEqual(result["Scree"], alpha)
            self.assertAlmostEqual(result["ExposedRock"], 1 - alpha)

    def test_empty_rgb_is_mineral_not_grass(self):
        self.assertEqual(compose_weights((0, 0, 0, 0))["DryMineral"], 1)
        self.assertEqual(compose_weights((0, 0, 0, 0))["DryGrass"], 0)

    def test_bounded_slope_policy_keeps_vegetation_and_is_continuous(self):
        start = math.cos(math.radians(65))
        end = math.cos(math.radians(85))
        for z, expected in ((start, 1), (end, 0.65), ((start + end) / 2, 0.825)):
            value = compose_weights((1, 0, 0, 0), z, slope_strength=0.35)
            self.assertAlmostEqual(value["DryGrass"], expected)

    def test_random_mixtures_preserve_sum_and_zero_sources(self):
        rng = random.Random(363)
        for _ in range(300):
            rgb = [rng.random() for _ in range(3)]
            rgb = [v / max(1, sum(rgb)) for v in rgb]
            result = compose_weights(
                (*rgb, rng.random()),
                rng.uniform(-1, 1),
                exponent=rng.uniform(1, 2),
                slope_strength=rng.random(),
            )
            self.assertAlmostEqual(sum(result.values()), 1)
            self.assertTrue(
                all(math.isfinite(v) and 0 <= v <= 1 for v in result.values())
            )
        self.assertEqual(
            compose_weights((0, 0.5, 0.5, 0.3), 0, slope_strength=0.35)["DryGrass"], 0
        )

    def test_invalid_inputs_are_rejected(self):
        for channels in (
            (float("nan"), 0, 0, 0),
            (-1, 0, 0, 0),
            (1, 1, 0, 0),
            (0, 0, 0),
        ):
            with self.assertRaises(ValueError):
                compose_weights(channels)
        for kwargs in (
            {"normal_z": 2},
            {"exponent": 0},
            {"slope_strength": 2},
            {"slope_start_degrees": 85, "slope_end_degrees": 65},
        ):
            with self.assertRaises(ValueError):
                compose_weights((0, 0, 0, 0), **kwargs)


if __name__ == "__main__":
    unittest.main()

"""Tests for bounded rider-close world-aligned terrain skin helpers."""

from __future__ import annotations

import math
import unittest

from scripts.geometry.local_terrain_skin import (
    build_terrain_skin_mesh,
    smooth_height_grid,
    terrain_skin_hash,
)


class LocalTerrainSkinTests(unittest.TestCase):
    def test_planar_slope_is_not_smoothed(self) -> None:
        heights = tuple(
            tuple(100.0 + row * 1.2 + column * 0.4 for column in range(9))
            for row in range(9)
        )
        smoothed, metrics = smooth_height_grid(heights)
        self.assertEqual(smoothed, heights)
        self.assertAlmostEqual(metrics.max_abs_adjustment_m, 0.0)
        self.assertAlmostEqual(metrics.rms_adjustment_m, 0.0)

    def test_high_frequency_rib_is_reduced_but_bounded(self) -> None:
        heights = []
        for row in range(11):
            values = []
            for column in range(11):
                planar = 100.0 + row * 0.8 + column * 0.2
                rib = 0.75 if column % 2 == 0 else -0.75
                values.append(planar + rib)
            heights.append(tuple(values))
        heights = tuple(heights)

        smoothed, metrics = smooth_height_grid(heights)
        self.assertLess(
            metrics.max_abs_laplacian_after_m,
            metrics.max_abs_laplacian_before_m,
        )
        self.assertLessEqual(metrics.max_abs_adjustment_m, 0.90 + 1e-9)
        self.assertGreater(metrics.rms_adjustment_m, 0.0)

        for row in range(2):
            self.assertEqual(smoothed[row], heights[row])
            self.assertEqual(smoothed[-1 - row], heights[-1 - row])
        for row in range(len(heights)):
            self.assertEqual(smoothed[row][:2], heights[row][:2])
            self.assertEqual(smoothed[row][-2:], heights[row][-2:])

    def test_mesh_is_upward_wound_and_deterministic(self) -> None:
        xs = (0.0, 4.0, 8.0, 12.0)
        ys = (12.0, 8.0, 4.0, 0.0)
        heights = tuple(
            tuple(20.0 + row * 0.4 + column * 0.2 for column in range(4))
            for row in range(4)
        )
        first = build_terrain_skin_mesh(
            xs,
            ys,
            heights,
            origin_x_m=0.0,
            origin_y_m=12.0,
            origin_z_m=20.0,
        )
        second = build_terrain_skin_mesh(
            xs,
            ys,
            heights,
            origin_x_m=0.0,
            origin_y_m=12.0,
            origin_z_m=20.0,
        )
        self.assertEqual(first, second)
        self.assertEqual(terrain_skin_hash(first), terrain_skin_hash(second))
        self.assertEqual(len(first.vertices), 16)
        self.assertEqual(len(first.triangles), 18)
        self.assertTrue(all(math.isfinite(v.z) for v in first.vertices))

        # Rows descend in UE Y. Unreal's front face therefore uses the
        # clockwise (a,b,c)/(b,d,c) winding when viewed from +Z.
        self.assertEqual(first.triangles[0], (0, 1, 4))
        self.assertEqual(first.triangles[1], (1, 5, 4))
        for triangle in first.triangles:
            a, b, c = (first.vertices[index] for index in triangle)
            ab = b - a
            ac = c - a
            conventional_normal_z = ab.x * ac.y - ab.y * ac.x
            self.assertLess(conventional_normal_z, 0.0)


if __name__ == "__main__":
    unittest.main()

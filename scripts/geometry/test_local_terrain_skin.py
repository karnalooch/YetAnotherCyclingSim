"""Tests for bounded rider-close world-aligned terrain skin helpers."""

from __future__ import annotations

import math
import unittest

from scripts.geometry.local_terrain_skin import (
    apply_corridor_constraints_to_height_grid,
    build_terrain_skin_mesh,
    smooth_height_grid,
    terrain_skin_hash,
)
from scripts.geometry.sp638_local_corridor import (
    CorridorMesh,
    CrossSectionPoint,
    Vec3,
    build_corridor_mesh,
    make_constant_profiles,
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


    def test_native_grid_corridor_constraints_pin_outer_transition(self) -> None:
        xs = tuple(float(value) for value in range(21))
        ys = tuple(float(value) for value in range(20, -1, -1))
        heights = tuple(tuple(100.0 for _ in xs) for _ in ys)
        profile = (
            CrossSectionPoint(-4.0, 0.0, "left_tie"),
            CrossSectionPoint(-2.0, 0.0, "left_road_edge"),
            CrossSectionPoint(2.0, 0.0, "right_road_edge"),
            CrossSectionPoint(4.0, 0.0, "right_tie"),
        )
        centerline = (
            Vec3(2.0, 10.0, 102.0),
            Vec3(18.0, 10.0, 102.0),
        )
        profiles = make_constant_profiles(len(centerline), profile)
        mesh = build_corridor_mesh(centerline, profiles)

        constrained, metrics = apply_corridor_constraints_to_height_grid(
            xs,
            ys,
            heights,
            mesh,
            profiles,
            corridor_origin_m=Vec3(0.0, 0.0, 0.0),
        )

        column = xs.index(10.0)
        self.assertAlmostEqual(constrained[ys.index(10.0)][column], 102.0, places=6)
        self.assertAlmostEqual(constrained[ys.index(6.0)][column], 100.0, places=6)
        self.assertAlmostEqual(constrained[ys.index(14.0)][column], 100.0, places=6)
        self.assertAlmostEqual(constrained[ys.index(5.0)][column], 100.0, places=6)
        self.assertGreater(metrics.constrained_sample_count, 0)
        self.assertAlmostEqual(metrics.max_abs_adjustment_m, 2.0, places=6)

    def test_native_grid_constraints_fail_on_strong_stacked_overlap(self) -> None:
        xs = tuple(float(value) for value in range(9))
        ys = tuple(float(value) for value in range(8, -1, -1))
        heights = tuple(tuple(100.0 for _ in xs) for _ in ys)
        profile = (
            CrossSectionPoint(-2.0, 0.0, "left_tie"),
            CrossSectionPoint(-1.0, 0.0, "left_road_edge"),
            CrossSectionPoint(1.0, 0.0, "right_road_edge"),
            CrossSectionPoint(2.0, 0.0, "right_tie"),
        )
        profiles = make_constant_profiles(4, profile)
        lower = (
            Vec3(1.0, 2.0, 101.0),
            Vec3(1.0, 3.0, 101.0),
            Vec3(1.0, 5.0, 101.0),
            Vec3(1.0, 6.0, 101.0),
            Vec3(7.0, 2.0, 101.0),
            Vec3(7.0, 3.0, 101.0),
            Vec3(7.0, 5.0, 101.0),
            Vec3(7.0, 6.0, 101.0),
        )
        upper = tuple(Vec3(v.x, v.y, v.z + 3.0) for v in lower)
        mesh = CorridorMesh(
            vertices=lower + upper,
            triangles=(
                (0, 1, 4), (1, 5, 4),
                (1, 2, 5), (2, 6, 5),
                (2, 3, 6), (3, 7, 6),
                (8, 9, 12), (9, 13, 12),
                (9, 10, 13), (10, 14, 13),
                (10, 11, 14), (11, 15, 14),
            ),
            station_count=4,
            cross_section_point_count=4,
        )

        with self.assertRaisesRegex(ValueError, "strongly overlap"):
            apply_corridor_constraints_to_height_grid(
                xs,
                ys,
                heights,
                mesh,
                profiles,
                corridor_origin_m=Vec3(0.0, 0.0, 0.0),
            )


if __name__ == "__main__":
    unittest.main()

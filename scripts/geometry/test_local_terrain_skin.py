"""Tests for bounded rider-close world-aligned terrain skin helpers."""

from __future__ import annotations

import math
import unittest

from scripts.geometry.local_terrain_skin import (
    apply_road_clearance_to_height_grid,
    build_terrain_skin_mesh,
    smooth_height_grid,
    terrain_skin_hash,
)
from scripts.geometry.sp638_local_corridor import Vec3


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

    def test_boundary_blend_tapers_smoothing_back_to_macro_height(self) -> None:
        heights = []
        for row in range(17):
            values = []
            for column in range(17):
                planar = 100.0 + row * 0.2
                rib = 0.8 if column % 2 == 0 else -0.8
                values.append(planar + rib)
            heights.append(tuple(values))
        heights = tuple(heights)

        smoothed, _metrics = smooth_height_grid(
            heights,
            pinned_border_cells=2,
            boundary_blend_cells=4,
        )
        near_edge_adjustment = abs(smoothed[2][8] - heights[2][8])
        interior_adjustment = abs(smoothed[8][8] - heights[8][8])
        self.assertEqual(smoothed[0], heights[0])
        self.assertEqual(smoothed[1], heights[1])
        self.assertGreater(interior_adjustment, near_edge_adjustment)

    def test_road_clearance_keeps_terrain_below_protected_surface(self) -> None:
        xs = tuple(float(value) for value in range(-16, 17, 4))
        ys = tuple(float(value) for value in range(16, -17, -4))
        heights = tuple(tuple(10.0 for _ in xs) for _ in ys)
        centerline = (Vec3(-16.0, 0.0, 10.0), Vec3(16.0, 0.0, 10.0))

        cleared, metrics = apply_road_clearance_to_height_grid(
            xs,
            ys,
            heights,
            centerline,
        )
        center_row = ys.index(0.0)
        protected_row = ys.index(4.0)
        transition_outer_row = ys.index(8.0)

        self.assertTrue(all(value <= 9.85 + 1e-9 for value in cleared[center_row]))
        self.assertTrue(all(value <= 9.85 + 1e-9 for value in cleared[protected_row]))
        self.assertEqual(cleared[transition_outer_row], heights[transition_outer_row])
        self.assertGreater(metrics.adjusted_sample_count, 0)
        self.assertGreater(metrics.protected_sample_count, 0)
        self.assertLessEqual(metrics.max_lowering_m, 0.151)
        self.assertGreaterEqual(metrics.minimum_vertical_clearance_m, 0.08 - 1e-9)

    def test_road_clearance_accepts_observed_hairpin_cut_with_four_metre_bound(self) -> None:
        xs = (-4.0, 0.0, 4.0)
        ys = (4.0, 0.0, -4.0)
        heights = tuple(tuple(13.212 for _ in xs) for _ in ys)
        centerline = (Vec3(-4.0, 0.0, 10.0), Vec3(4.0, 0.0, 10.0))

        _, metrics = apply_road_clearance_to_height_grid(
            xs,
            ys,
            heights,
            centerline,
            max_lowering_m=4.0,
        )

        self.assertAlmostEqual(metrics.max_lowering_m, 3.362, places=3)

    def test_road_clearance_fails_closed_above_four_metre_hairpin_bound(self) -> None:
        xs = (-4.0, 0.0, 4.0)
        ys = (4.0, 0.0, -4.0)
        heights = tuple(tuple(14.2 for _ in xs) for _ in ys)
        centerline = (Vec3(-4.0, 0.0, 10.0), Vec3(4.0, 0.0, 10.0))
        with self.assertRaisesRegex(ValueError, "bounded limit"):
            apply_road_clearance_to_height_grid(
                xs,
                ys,
                heights,
                centerline,
                max_lowering_m=4.0,
            )

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


if __name__ == "__main__":
    unittest.main()

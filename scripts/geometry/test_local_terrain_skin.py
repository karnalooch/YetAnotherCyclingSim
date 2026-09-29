"""Tests for bounded rider-close world-aligned terrain skin helpers."""

from __future__ import annotations

import math
import unittest

from scripts.geometry.local_terrain_skin import (
    build_bounded_meso_ground_mesh,
    build_terrain_skin_mesh,
    meso_ground_hash,
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

    def test_bounded_meso_ground_has_irregular_pinned_seam_and_road_cutout(self) -> None:
        xs = tuple(float(index * 2) for index in range(31))
        ys = tuple(float(60 - index * 2) for index in range(31))
        heights = tuple(
            tuple(
                100.0
                + row * 0.35
                + column * 0.12
                + (0.7 if column % 2 == 0 else -0.7)
                for column in range(31)
            )
            for row in range(31)
        )
        smoothed, _ = smooth_height_grid(
            heights,
            iterations=6,
            blend=0.60,
            curvature_threshold_m=0.01,
            max_step_adjustment_m=0.55,
            max_total_adjustment_m=2.5,
            pinned_border_cells=1,
        )
        origin_z = min(min(row) for row in heights)
        kwargs = dict(
            origin_x_m=0.0,
            origin_y_m=60.0,
            origin_z_m=origin_z,
            center_x_m=30.0,
            center_y_m=30.0,
            radius_x_m=24.0,
            radius_y_m=20.0,
            protected_centerline_xy_m=((30.0, 0.0), (30.0, 60.0)),
            protected_half_width_m=3.0,
            seam_rings=3,
            lift_m=0.03,
        )
        first, metrics = build_bounded_meso_ground_mesh(
            xs,
            ys,
            heights,
            smoothed,
            **kwargs,
        )
        second, second_metrics = build_bounded_meso_ground_mesh(
            xs,
            ys,
            heights,
            smoothed,
            **kwargs,
        )

        self.assertEqual(first, second)
        self.assertEqual(metrics, second_metrics)
        self.assertEqual(meso_ground_hash(first), meso_ground_hash(second))
        self.assertGreater(len(first.triangles), 100)
        self.assertLess(len(first.triangles), (31 - 1) * (31 - 1) * 2)
        self.assertGreater(metrics.max_abs_adjustment_m, 0.0)
        self.assertGreaterEqual(metrics.minimum_adjustment_m, 0.0)
        self.assertAlmostEqual(metrics.boundary_max_abs_adjustment_m, 0.0)
        self.assertGreaterEqual(metrics.minimum_protected_distance_m or 0.0, 3.0)

        edge_counts: dict[tuple[int, int], int] = {}
        for triangle in first.triangles:
            for start, end in (
                (triangle[0], triangle[1]),
                (triangle[1], triangle[2]),
                (triangle[2], triangle[0]),
            ):
                edge = (min(start, end), max(start, end))
                edge_counts[edge] = edge_counts.get(edge, 0) + 1
        boundary_vertices = {
            vertex
            for edge, count in edge_counts.items()
            if count == 1
            for vertex in edge
        }
        self.assertEqual(len(boundary_vertices), first.boundary_vertex_count)

        x_to_column = {round(value, 9): index for index, value in enumerate(xs)}
        y_to_row = {round(value, 9): index for index, value in enumerate(ys)}
        for vertex_index in boundary_vertices:
            vertex = first.vertices[vertex_index]
            world_x = vertex.x
            world_y = vertex.y + 60.0
            row = y_to_row[round(world_y, 9)]
            column = x_to_column[round(world_x, 9)]
            self.assertAlmostEqual(
                vertex.z + origin_z,
                heights[row][column],
                places=9,
            )

        for vertex in first.vertices:
            world_x = vertex.x
            world_y = vertex.y + 60.0
            row = y_to_row[round(world_y, 9)]
            column = x_to_column[round(world_x, 9)]
            self.assertGreaterEqual(
                vertex.z + origin_z + 1e-9,
                heights[row][column],
            )

    def test_variable_protected_width_follows_actual_earthwork_envelope(self) -> None:
        xs = tuple(float(index * 2) for index in range(31))
        ys = tuple(float(60 - index * 2) for index in range(31))
        heights = tuple(
            tuple(50.0 + row * 0.1 + column * 0.05 for column in range(31))
            for row in range(31)
        )
        origin_z = min(min(row) for row in heights)
        common = dict(
            origin_x_m=0.0,
            origin_y_m=60.0,
            origin_z_m=origin_z,
            center_x_m=30.0,
            center_y_m=30.0,
            radius_x_m=26.0,
            radius_y_m=26.0,
            protected_centerline_xy_m=(
                (30.0, 0.0),
                (30.0, 30.0),
                (30.0, 60.0),
            ),
            seam_rings=2,
            lift_m=0.03,
        )
        fixed, _ = build_bounded_meso_ground_mesh(
            xs,
            ys,
            heights,
            heights,
            protected_half_width_m=7.0,
            **common,
        )
        adaptive, metrics = build_bounded_meso_ground_mesh(
            xs,
            ys,
            heights,
            heights,
            protected_half_widths_m=(3.0, 7.0, 3.0),
            **common,
        )

        self.assertGreater(len(adaptive.vertices), len(fixed.vertices))
        self.assertAlmostEqual(metrics.minimum_protected_half_width_m or 0.0, 3.0)
        self.assertAlmostEqual(metrics.maximum_protected_half_width_m or 0.0, 7.0)
        self.assertGreaterEqual(metrics.minimum_protected_clearance_m or 0.0, -1e-9)
        self.assertLess(metrics.minimum_protected_distance_m or 99.0, 7.0)

    def test_variable_protected_width_requires_one_width_per_station(self) -> None:
        xs = (0.0, 2.0, 4.0, 6.0, 8.0)
        ys = (8.0, 6.0, 4.0, 2.0, 0.0)
        heights = tuple(tuple(10.0 for _ in xs) for _ in ys)
        with self.assertRaisesRegex(ValueError, "must match protected centerline"):
            build_bounded_meso_ground_mesh(
                xs,
                ys,
                heights,
                heights,
                origin_x_m=0.0,
                origin_y_m=8.0,
                origin_z_m=10.0,
                center_x_m=4.0,
                center_y_m=4.0,
                radius_x_m=4.0,
                radius_y_m=4.0,
                protected_centerline_xy_m=((4.0, 0.0), (4.0, 8.0)),
                protected_half_widths_m=(2.0,),
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

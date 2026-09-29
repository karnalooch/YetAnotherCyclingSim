"""Tests for the presentation-only SP638 local corridor mesh kernel."""

from __future__ import annotations

import math
import unittest

from scripts.geometry.sp638_local_corridor import (
    CrossSectionPoint,
    Vec3,
    build_corridor_mesh,
    corridor_mesh_hash,
    apply_superelevation_to_profiles,
    fit_road_crossfall_from_transect,
    make_constant_profiles,
    make_curvature_adaptive_profiles,
    make_curvature_superelevation_angles,
    minimum_sampled_radius_xy,
    regularize_measured_superelevation_angles,
    triangle_normal,
)


class LocalGroundCorridorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = (
            CrossSectionPoint(-8.0, 3.0, "uphill_tie"),
            CrossSectionPoint(-5.0, 1.2, "cut_to_bench"),
            CrossSectionPoint(-3.8, 0.15, "left_shoulder"),
            CrossSectionPoint(-3.0, 0.0, "left_road_edge"),
            CrossSectionPoint(3.0, 0.0, "right_road_edge"),
            CrossSectionPoint(4.0, -0.1, "right_shoulder"),
            CrossSectionPoint(7.0, -1.0, "embankment"),
            CrossSectionPoint(10.0, -2.0, "downhill_tie"),
        )

    def test_straight_corridor_preserves_width_and_z(self) -> None:
        centerline = (
            Vec3(0.0, 0.0, 100.0),
            Vec3(10.0, 0.0, 101.0),
            Vec3(20.0, 0.0, 102.5),
        )
        mesh = build_corridor_mesh(
            centerline,
            make_constant_profiles(len(centerline), self.profile),
        )

        self.assertEqual(mesh.station_count, 3)
        self.assertEqual(mesh.cross_section_point_count, len(self.profile))
        self.assertEqual(len(mesh.vertices), 3 * len(self.profile))
        self.assertEqual(
            len(mesh.triangles),
            2 * (3 - 1) * (len(self.profile) - 1),
        )

        first_left = mesh.vertices[0]
        first_right = mesh.vertices[len(self.profile) - 1]
        self.assertAlmostEqual(first_left.y, -8.0)
        self.assertAlmostEqual(first_right.y, 10.0)
        self.assertAlmostEqual(first_left.z, 103.0)
        self.assertAlmostEqual(first_right.z, 98.0)

        for triangle in mesh.triangles:
            self.assertGreater(triangle_normal(mesh, triangle).z, 0.0)

    def test_curved_centerline_keeps_finite_non_degenerate_geometry(self) -> None:
        angles = (0.0, 0.12, 0.24, 0.36, 0.48, 0.60, 0.72)
        centerline = tuple(
            Vec3(
                20.0 * math.sin(angle),
                20.0 * (1.0 - math.cos(angle)),
                120.0 + index * 0.35,
            )
            for index, angle in enumerate(angles)
        )
        mesh = build_corridor_mesh(
            centerline,
            make_constant_profiles(len(centerline), self.profile),
        )

        for vertex in mesh.vertices:
            self.assertTrue(math.isfinite(vertex.x))
            self.assertTrue(math.isfinite(vertex.y))
            self.assertTrue(math.isfinite(vertex.z))
        for triangle in mesh.triangles:
            self.assertGreater(triangle_normal(mesh, triangle).z, 0.0)

    def test_vertical_profile_can_change_per_station_without_moving_offsets(self) -> None:
        centerline = (
            Vec3(0.0, 0.0, 50.0),
            Vec3(5.0, 0.0, 51.0),
            Vec3(10.0, 0.0, 52.0),
        )
        profiles = []
        for delta in (0.0, 0.25, 0.5):
            profiles.append(
                tuple(
                    CrossSectionPoint(
                        point.lateral_m,
                        point.vertical_m + delta
                        if point.lateral_m < -3.0
                        else point.vertical_m,
                        point.role,
                    )
                    for point in self.profile
                )
            )
        mesh = build_corridor_mesh(centerline, tuple(profiles))

        width = len(self.profile)
        self.assertAlmostEqual(mesh.vertices[0].z, 53.0)
        self.assertAlmostEqual(mesh.vertices[width].z, 54.25)
        self.assertAlmostEqual(mesh.vertices[2 * width].z, 55.5)

    def test_output_hash_is_deterministic(self) -> None:
        centerline = (
            Vec3(0.0, 0.0, 0.0),
            Vec3(4.0, 1.0, 0.2),
            Vec3(8.0, 3.0, 0.4),
        )
        profiles = make_constant_profiles(len(centerline), self.profile)
        first = corridor_mesh_hash(build_corridor_mesh(centerline, profiles))
        second = corridor_mesh_hash(build_corridor_mesh(centerline, profiles))
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)

    def test_rejects_unordered_lateral_topology(self) -> None:
        centerline = (Vec3(0.0, 0.0, 0.0), Vec3(10.0, 0.0, 0.0))
        bad = list(self.profile)
        bad[2] = CrossSectionPoint(-5.0, 0.15, "overlap")
        with self.assertRaisesRegex(ValueError, "strictly ordered"):
            build_corridor_mesh(centerline, (self.profile, tuple(bad)))

    def test_allows_lateral_earthwork_offsets_to_change_between_stations(self) -> None:
        centerline = (Vec3(0.0, 0.0, 0.0), Vec3(10.0, 0.0, 0.0))
        shifted = tuple(
            CrossSectionPoint(
                point.lateral_m - (0.5 if point.role == "uphill_tie" else 0.0),
                point.vertical_m,
                point.role,
            )
            for point in self.profile
        )
        mesh = build_corridor_mesh(centerline, (self.profile, shifted))
        self.assertEqual(mesh.station_count, 2)

    def test_rejects_role_order_that_changes_between_stations(self) -> None:
        centerline = (Vec3(0.0, 0.0, 0.0), Vec3(10.0, 0.0, 0.0))
        changed = list(self.profile)
        changed[0] = CrossSectionPoint(-8.0, 3.0, "different_role")
        with self.assertRaisesRegex(ValueError, "roles/order must stay stable"):
            build_corridor_mesh(centerline, (self.profile, tuple(changed)))

    def test_rejects_centerline_with_no_horizontal_tangent(self) -> None:
        centerline = (Vec3(0.0, 0.0, 0.0), Vec3(0.0, 0.0, 1.0))
        with self.assertRaisesRegex(ValueError, "stable horizontal tangent"):
            build_corridor_mesh(
                centerline,
                make_constant_profiles(len(centerline), self.profile),
            )

    def test_curvature_superelevation_banks_outside_edge_and_tapers(self) -> None:
        radius = 12.0
        centerline = tuple(
            Vec3(
                radius * math.sin(index * 0.08),
                radius * (1.0 - math.cos(index * 0.08)),
                0.0,
            )
            for index in range(40)
        )
        angles = make_curvature_superelevation_angles(
            centerline,
            max_bank_deg=4.0,
            full_bank_curvature_per_m=0.05,
            max_delta_deg_per_station=0.35,
            curvature_half_window_stations=2,
        )
        self.assertEqual(len(angles), len(centerline))
        self.assertGreater(max(angles), 3.0)
        self.assertLessEqual(max(abs(value) for value in angles), 4.0 + 1e-9)
        self.assertTrue(
            all(
                abs(angles[index + 1] - angles[index]) <= 0.35 + 1e-9
                for index in range(len(angles) - 1)
            )
        )

        road = (
            CrossSectionPoint(-3.0, 0.06, "left_road_surface"),
            CrossSectionPoint(3.0, 0.06, "right_road_surface"),
        )
        profiles = make_constant_profiles(len(centerline), road)
        banked = apply_superelevation_to_profiles(profiles, angles)
        apex = max(range(len(angles)), key=lambda index: angles[index])
        self.assertGreater(banked[apex][0].vertical_m, banked[apex][1].vertical_m)
        self.assertAlmostEqual(banked[apex][0].lateral_m, -3.0)
        self.assertAlmostEqual(banked[apex][1].lateral_m, 3.0)

    def test_lidar_transect_finds_shifted_road_strip_inside_steep_hillside(self) -> None:
        offsets = tuple(float(value) for value in range(-6, 7))
        heights = []
        for offset in offsets:
            if -1.0 <= offset <= 4.0:
                heights.append(100.0 - 0.04 * offset)
            else:
                heights.append(100.0 + 0.45 * offset)

        angle, diagnostics = fit_road_crossfall_from_transect(
            offsets,
            tuple(heights),
            candidate_width_m=5.0,
            max_center_offset_m=1.5,
            max_abs_grade=0.10,
            max_rms_residual_m=0.05,
        )

        self.assertIsNotNone(angle)
        self.assertAlmostEqual(
            angle or 0.0,
            math.degrees(math.atan(0.04)),
            places=6,
        )
        self.assertAlmostEqual(
            float(diagnostics["selected_center_offset_m"] or 0.0),
            1.5,
            places=6,
        )
        self.assertLess(
            float(diagnostics["selected_rms_residual_m"] or 1.0),
            1e-9,
        )

    def test_lidar_transect_rejects_only_steep_mountain_surface(self) -> None:
        offsets = tuple(float(value) for value in range(-6, 7))
        heights = tuple(100.0 + 0.35 * offset for offset in offsets)
        angle, diagnostics = fit_road_crossfall_from_transect(
            offsets,
            heights,
            candidate_width_m=5.0,
            max_abs_grade=0.10,
        )
        self.assertIsNone(angle)
        self.assertEqual(diagnostics["candidate_count"], 0)

    def test_measured_superelevation_keeps_real_signal_and_rejects_raster_spike(self) -> None:
        radius = 10.0
        centerline = tuple(
            Vec3(
                radius * math.sin(index * 0.08),
                radius * (1.0 - math.cos(index * 0.08)),
                0.0,
            )
            for index in range(21)
        )
        measured = [2.4] * len(centerline)
        measured[10] = 12.0
        measured[15] = None

        regularized, diagnostics = regularize_measured_superelevation_angles(
            centerline,
            tuple(measured),
            hard_max_bank_deg=4.0,
            median_radius_stations=2,
            spike_tolerance_deg=1.0,
            max_delta_deg_per_station=0.35,
            curvature_half_window_stations=2,
        )

        self.assertAlmostEqual(regularized[8], 2.4)
        self.assertAlmostEqual(regularized[10], 2.4)
        self.assertAlmostEqual(regularized[15], 2.4)
        self.assertEqual(diagnostics["measured_station_count"], 19)
        self.assertEqual(diagnostics["hard_rejected_station_count"], 1)
        self.assertEqual(diagnostics["fallback_station_count"], 0)
        self.assertLessEqual(max(abs(value) for value in regularized), 4.0)

    def test_measured_superelevation_falls_back_only_without_local_lidar_signal(self) -> None:
        radius = 8.0
        centerline = tuple(
            Vec3(
                radius * math.sin(index * 0.1),
                radius * (1.0 - math.cos(index * 0.1)),
                0.0,
            )
            for index in range(12)
        )
        regularized, diagnostics = regularize_measured_superelevation_angles(
            centerline,
            tuple(None for _ in centerline),
            fallback_max_bank_deg=3.434,
            curvature_half_window_stations=2,
        )
        self.assertGreater(max(abs(value) for value in regularized), 0.5)
        self.assertLessEqual(max(abs(value) for value in regularized), 3.434 + 1e-9)
        self.assertEqual(diagnostics["fallback_station_count"], len(centerline))

    def test_superelevation_flips_with_turn_direction_and_fades_at_ties(self) -> None:
        positive = (
            Vec3(0.0, 0.0, 0.0),
            Vec3(4.0, 0.4, 0.0),
            Vec3(7.5, 1.8, 0.0),
            Vec3(10.0, 4.0, 0.0),
            Vec3(11.0, 7.0, 0.0),
        )
        negative = tuple(Vec3(point.x, -point.y, point.z) for point in positive)
        pos_angles = make_curvature_superelevation_angles(
            positive,
            max_delta_deg_per_station=4.0,
        )
        neg_angles = make_curvature_superelevation_angles(
            negative,
            max_delta_deg_per_station=4.0,
        )
        self.assertGreater(pos_angles[2], 0.0)
        self.assertLess(neg_angles[2], 0.0)

        banked = apply_superelevation_to_profiles(
            make_constant_profiles(len(positive), self.profile),
            pos_angles,
            full_bank_extent_m=4.0,
            zero_bank_extent_m=10.0,
        )
        original_by_role = {point.role: point for point in self.profile}
        apex = banked[2]
        by_role = {point.role: point for point in apex}
        # The -8 m fixture tie is inside the 4..10 m fade band, so it keeps
        # only a residual fraction of the road bank. The +10 m tie is the zero-
        # bank boundary and must remain exactly on its authored elevation.
        self.assertNotAlmostEqual(
            by_role["uphill_tie"].vertical_m,
            original_by_role["uphill_tie"].vertical_m,
        )
        self.assertAlmostEqual(
            by_role["downhill_tie"].vertical_m,
            original_by_role["downhill_tie"].vertical_m,
        )
        left_tie_delta = abs(
            by_role["uphill_tie"].vertical_m
            - original_by_role["uphill_tie"].vertical_m
        )
        left_shoulder_delta = abs(
            by_role["left_shoulder"].vertical_m
            - original_by_role["left_shoulder"].vertical_m
        )
        self.assertLess(left_tie_delta, left_shoulder_delta)
        self.assertNotAlmostEqual(
            by_role["left_shoulder"].vertical_m,
            original_by_role["left_shoulder"].vertical_m,
        )
        self.assertNotAlmostEqual(
            by_role["right_shoulder"].vertical_m,
            original_by_role["right_shoulder"].vertical_m,
        )

    def test_adaptive_inside_offset_preserves_road_and_prevents_hairpin_fold(self) -> None:
        radius = 7.0
        angles = tuple(index * math.radians(8.0) for index in range(24))
        centerline = tuple(
            Vec3(
                radius * math.sin(angle),
                radius * (1.0 - math.cos(angle)),
                index * 0.03,
            )
            for index, angle in enumerate(angles)
        )

        with self.assertRaisesRegex(ValueError, "inverted or folded"):
            build_corridor_mesh(
                centerline,
                make_constant_profiles(len(centerline), self.profile),
            )

        adaptive = make_curvature_adaptive_profiles(centerline, self.profile)
        mesh = build_corridor_mesh(centerline, adaptive)
        self.assertEqual(mesh.station_count, len(centerline))

        original_by_role = {point.role: point.lateral_m for point in self.profile}
        for station_profile in adaptive:
            current_by_role = {
                point.role: point.lateral_m for point in station_profile
            }
            for role in (
                "left_shoulder",
                "left_road_edge",
                "right_road_edge",
                "right_shoulder",
            ):
                self.assertAlmostEqual(
                    current_by_role[role],
                    original_by_role[role],
                )

        self.assertLess(
            min(profile[-1].lateral_m for profile in adaptive),
            self.profile[-1].lateral_m,
        )
        self.assertTrue(
            all(
                math.isclose(profile[0].lateral_m, self.profile[0].lateral_m)
                for profile in adaptive
            )
        )
        for triangle in mesh.triangles:
            self.assertGreater(triangle_normal(mesh, triangle).z, 0.0)

    def test_adaptive_offset_handles_real_hairpin_radius_class(self) -> None:
        radius = 4.35
        angles = tuple(index * math.radians(5.0) for index in range(40))
        centerline = tuple(
            Vec3(
                radius * math.sin(angle),
                radius * (1.0 - math.cos(angle)),
                index * 0.01,
            )
            for index, angle in enumerate(angles)
        )

        adaptive = make_curvature_adaptive_profiles(centerline, self.profile)
        mesh = build_corridor_mesh(centerline, adaptive)

        original_by_role = {point.role: point.lateral_m for point in self.profile}
        for station_profile in adaptive:
            current_by_role = {
                point.role: point.lateral_m for point in station_profile
            }
            self.assertAlmostEqual(
                current_by_role["right_road_edge"],
                original_by_role["right_road_edge"],
            )

        minimum_inside_shoulder = min(
            next(
                point.lateral_m
                for point in station_profile
                if point.role == "right_shoulder"
            )
            for station_profile in adaptive
        )
        minimum_inside_tie = min(profile[-1].lateral_m for profile in adaptive)
        self.assertGreaterEqual(minimum_inside_shoulder, 3.25)
        self.assertLess(minimum_inside_shoulder, 4.0)
        self.assertGreater(minimum_inside_tie, minimum_inside_shoulder)
        self.assertLess(minimum_inside_tie, radius)
        for triangle in mesh.triangles:
            self.assertGreater(triangle_normal(mesh, triangle).z, 0.0)

    def test_adaptive_offset_handles_sub_four_metre_real_apex_class(self) -> None:
        radius = 3.55
        angles = tuple(index * math.radians(5.0) for index in range(44))
        centerline = tuple(
            Vec3(
                radius * math.sin(angle),
                radius * (1.0 - math.cos(angle)),
                index * 0.01,
            )
            for index, angle in enumerate(angles)
        )

        adaptive = make_curvature_adaptive_profiles(centerline, self.profile)
        mesh = build_corridor_mesh(centerline, adaptive)

        for station_profile in adaptive:
            by_role = {point.role: point.lateral_m for point in station_profile}
            self.assertAlmostEqual(by_role["right_road_edge"], 3.0)
            self.assertGreaterEqual(by_role["right_shoulder"], 3.25)
            self.assertGreater(by_role["embankment"], by_role["right_shoulder"])
            self.assertGreater(by_role["downhill_tie"], by_role["embankment"])

        self.assertLess(
            min(
                next(
                    point.lateral_m
                    for point in station_profile
                    if point.role == "right_shoulder"
                )
                for station_profile in adaptive
            ),
            4.0,
        )
        for triangle in mesh.triangles:
            self.assertGreater(triangle_normal(mesh, triangle).z, 0.0)

    def test_adaptive_offset_fails_when_minimum_spans_do_not_fit(self) -> None:
        radius = 3.40
        angles = tuple(index * math.radians(5.0) for index in range(20))
        centerline = tuple(
            Vec3(
                radius * math.sin(angle),
                radius * (1.0 - math.cos(angle)),
                0.0,
            )
            for index, angle in enumerate(angles)
        )

        with self.assertRaisesRegex(ValueError, "cannot preserve"):
            make_curvature_adaptive_profiles(centerline, self.profile)

    def test_source_scale_window_rejects_dense_resample_curvature_noise(self) -> None:
        radius = 12.0
        arc_step_m = 2.0
        centerline = [
            Vec3(
                radius * math.sin(index * arc_step_m / radius),
                radius * (1.0 - math.cos(index * arc_step_m / radius)),
                index * 0.01,
            )
            for index in range(30)
        ]

        noisy_index = 12
        noisy = centerline[noisy_index]
        centerline[noisy_index] = Vec3(noisy.x, noisy.y + 1.5, noisy.z)
        centerline_tuple = tuple(centerline)

        raw_radius = minimum_sampled_radius_xy(
            centerline_tuple,
            half_window_stations=1,
        )
        source_scale_radius = minimum_sampled_radius_xy(
            centerline_tuple,
            half_window_stations=3,
        )
        self.assertIsNotNone(raw_radius)
        self.assertIsNotNone(source_scale_radius)
        self.assertLess(raw_radius, 3.0)
        self.assertGreater(source_scale_radius, 8.0)

        original_centerline = tuple(centerline_tuple)
        adaptive = make_curvature_adaptive_profiles(
            centerline_tuple,
            self.profile,
            curvature_half_window_stations=3,
        )

        self.assertEqual(centerline_tuple, original_centerline)
        original_by_role = {point.role: point.lateral_m for point in self.profile}
        for station_profile in adaptive:
            by_role = {point.role: point.lateral_m for point in station_profile}
            self.assertAlmostEqual(
                by_role["left_road_edge"],
                original_by_role["left_road_edge"],
            )
            self.assertAlmostEqual(
                by_role["right_road_edge"],
                original_by_role["right_road_edge"],
            )

        # Source-scale curvature filtering is not permission to heal a genuinely
        # invalid canonical centerline. Mesh topology validation stays strict.
        with self.assertRaisesRegex(ValueError, "inverted or folded"):
            build_corridor_mesh(
                centerline_tuple,
                adaptive,
                tangent_half_window_stations=3,
            )

    def test_adaptive_profiles_and_mesh_hash_are_deterministic(self) -> None:
        radius = 8.0
        centerline = tuple(
            Vec3(
                radius * math.sin(index * 0.1),
                radius * (1.0 - math.cos(index * 0.1)),
                index * 0.02,
            )
            for index in range(18)
        )
        first_profiles = make_curvature_adaptive_profiles(centerline, self.profile)
        second_profiles = make_curvature_adaptive_profiles(centerline, self.profile)
        self.assertEqual(first_profiles, second_profiles)
        self.assertEqual(
            corridor_mesh_hash(build_corridor_mesh(centerline, first_profiles)),
            corridor_mesh_hash(build_corridor_mesh(centerline, second_profiles)),
        )


if __name__ == "__main__":
    unittest.main()

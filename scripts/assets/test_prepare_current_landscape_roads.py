"""Regressions for network width, folds, counter-turns and source displacement."""

import math
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import numpy as np
from shapely.geometry import LineString

from scripts.assets.prepare_current_landscape_roads import (
    assess_lateral_sweep,
    build_extreme_review,
    inspect_sections,
    measure_cut_envelopes,
    prepare_patch,
    resize_sections_width,
    shift_sections_laterally,
    smooth_axis,
    write_extreme_cut_diagnostic,
    write_extreme_cut_review,
)
from scripts.geometry.network_earthworks_diagnostics import (
    height_fit_bounds,
    uniform_height_candidate,
)
from scripts.geometry.network_pavement import (
    pavement_slab,
    shoulder_sections,
    surface_inspection,
)


def sections(axis):
    axis = np.asarray(axis, dtype=float)
    tangent = np.gradient(axis, axis=0)
    n = np.column_stack([-tangent[:, 1], tangent[:, 0]])
    n /= np.linalg.norm(n, axis=1)[:, None]
    xy = axis[:, None, :] + n[:, None, :] * np.linspace(-2.5, 2.5, 25)[None, :, None]
    return np.dstack([xy, np.ones(xy.shape[:2])])


class NetworkTests(unittest.TestCase):
    def test_extreme_cut_diagnostic_writes_reviewable_png(self):
        cut = {
            "max_cut_m": 11.62,
            "peak_local_xy_m": [15.0, 2.0],
            "peak_base_height_m": 701.4,
            "peak_target_height_m": 689.78,
            "over_cap_cell_count": 587,
        }
        case = {
            "id": "road-0-0",
            "sections": sections([[v, 0] for v in np.linspace(0, 30, 61)]).tolist(),
            "cut_depth": cut,
            "cut_depth_by_envelope": {
                "asphalt": {"max_cut_m": 10.37},
                "asphalt_and_shoulders": {"max_cut_m": 10.65},
                "authored_patch_envelope": cut,
            },
            "width_sensitivity": {
                "candidates": [
                    {"ordinary_cut_pass": False},
                    {"ordinary_cut_pass": False},
                    {"ordinary_cut_pass": False},
                ]
            },
            "lateral_sweep": {
                "candidate_count": 33,
                "locally_numeric_pass_count": 0,
                "best_candidate": {
                    "shift_m": -1.25,
                    "status": "REJECT_LOCAL_NUMERIC_LIMITS",
                },
            },
            "review": {
                "classification": "NATURAL_FEATURE_CONFIRMED",
                "hotspot_wgs84": [2.8167, 39.8304],
                "street_view_url": "https://www.google.com/maps/@?api=1&map_action=pano",
                "peak_distance_from_axis_m": 3.73,
                "peak_beyond_asphalt_edge_m": 1.23,
                "peak_beyond_shoulder_edge_m": 0.73,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "extreme.png"
            write_extreme_cut_diagnostic(case, path)
            self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            self.assertGreater(path.stat().st_size, 10_000)
            review = Path(directory) / "review.md"
            write_extreme_cut_review(case, review)
            text = review.read_text(encoding="utf-8")
            self.assertIn("Interactive Street View", text)
            self.assertIn("No width, height or lateral change was applied", text)

    def test_cut_envelopes_separate_asphalt_shoulders_and_guard(self):
        asphalt = sections([[v, 20] for v in np.linspace(10, 20, 21)])
        shoulders = np.asarray(shoulder_sections(asphalt.tolist()))
        terrain = np.full((64, 64), 32896, dtype=np.uint16)
        terrain[47, 30] = 33792  # 0.5 m beyond the nominal shoulder edge.
        manifest = {"scale_z": 100.0, "location_z_cm": 0.0}
        measured = measure_cut_envelopes(asphalt, shoulders, terrain, manifest)
        self.assertLess(
            measured["asphalt"]["max_cut_m"],
            measured["authored_patch_envelope"]["max_cut_m"],
        )
        self.assertLess(
            measured["asphalt_and_shoulders"]["max_cut_m"],
            measured["authored_patch_envelope"]["max_cut_m"],
        )
        self.assertEqual(measured["admission_envelope"], "authored_patch_envelope")

    def test_width_and_lateral_counterfactuals_preserve_axis_and_do_not_mutate(self):
        original = sections([[v, 0] for v in np.linspace(0, 30, 61)])
        narrower = resize_sections_width(original, 3.0)
        shifted = shift_sections_laterally(original, 1.25)
        np.testing.assert_allclose(
            (narrower[:, 0, :2] + narrower[:, -1, :2]) / 2,
            (original[:, 0, :2] + original[:, -1, :2]) / 2,
        )
        np.testing.assert_allclose(
            np.linalg.norm(narrower[:, -1, :2] - narrower[:, 0, :2], axis=1),
            3.0,
        )
        np.testing.assert_allclose(
            shifted[:, -1, :2] - shifted[:, 0, :2],
            original[:, -1, :2] - original[:, 0, :2],
        )
        np.testing.assert_allclose(shifted[:, :, 1] - original[:, :, 1], 1.25)
        np.testing.assert_array_equal(
            original, sections([[v, 0] for v in np.linspace(0, 30, 61)])
        )

    def test_lateral_sweep_is_diagnostic_and_respects_source_displacement(self):
        asphalt = sections([[v, 20] for v in np.linspace(10, 20, 21)])
        terrain = np.full((64, 64), 32896, dtype=np.uint16)
        manifest = {
            "scale_z": 100.0,
            "location_z_cm": 0.0,
            "origin_epsg_m": [0.0, 0.0],
        }
        result = assess_lateral_sweep(
            asphalt,
            LineString([[10, 20], [20, 20]]),
            terrain,
            manifest,
        )
        self.assertEqual(result["candidate_count"], 33)
        self.assertGreater(result["locally_numeric_pass_count"], 0)
        self.assertFalse(result["lateral_change_applied"])
        self.assertFalse(result["road_admitted"])
        for candidate in result["candidates"]:
            self.assertFalse(candidate["lateral_change_applied"])
            self.assertFalse(candidate["road_admitted"])
            if abs(candidate["shift_m"]) > 1.0:
                self.assertFalse(candidate["local_numeric_checks_pass"])

    def test_extreme_review_resolves_manual_panorama_without_metric_admission(self):
        from pyproj import Transformer

        origin = [483000.25, 4409516.25]
        east, north = Transformer.from_crs(4326, 25831, always_xy=True).transform(
            2.8167622, 39.8304238
        )
        peak = np.array([east - origin[0], origin[1] - north])
        bearing = math.radians(77.4)
        across = np.array([math.sin(bearing), -math.cos(bearing)])
        axis = peak - across * 3.73
        rows = []
        for along in (-0.5, 0.0, 0.5):
            center = axis + np.array([math.cos(bearing), math.sin(bearing)]) * along
            xy = center + across * np.linspace(-2.5, 2.5, 25)[:, None]
            rows.append(np.column_stack([xy, np.ones(25)]))
        review = build_extreme_review(
            {
                "id": "VIAL_TR70190001287-0-4800",
                "sections": np.asarray(rows).tolist(),
                "cut_depth": {
                    "nearest_station_index": 1,
                    "peak_local_xy_m": peak.tolist(),
                },
            },
            {"origin_epsg_m": origin},
        )
        self.assertEqual(review["classification"], "NATURAL_FEATURE_CONFIRMED")
        self.assertIn("Q0IzBsfssGl-EEeEOAGuLA", review["street_view_url"])
        self.assertAlmostEqual(review["peak_distance_from_axis_m"], 3.73)
        self.assertFalse(review["metric_cut_verified_by_street_view"])
        self.assertFalse(review["road_admitted"])

    def test_cut_and_support_bounds_expose_incompatible_translation(self):
        receipt = height_fit_bounds(3.0, 3.0, 3.5, cut_cap_m=1.0, support_cap_m=4.0)
        self.assertEqual(receipt["minimum_lift_for_cut_m"], 2.0)
        self.assertEqual(receipt["maximum_lift_for_support_m"], 0.5)
        self.assertFalse(receipt["bounds_overlap"])
        self.assertFalse(receipt["height_change_applied"])
        self.assertFalse(receipt["road_admitted"])

    def test_overlapping_bounds_do_not_admit_or_apply_height_change(self):
        receipt = height_fit_bounds(1.5, 1.0, 2.0, cut_cap_m=1.0, support_cap_m=4.0)
        self.assertTrue(receipt["bounds_overlap"])
        self.assertEqual(receipt["minimum_lift_for_cut_m"], 0.5)
        self.assertFalse(receipt["source_height_verified"])
        self.assertFalse(receipt["road_admitted"])

    def test_uniform_candidate_uses_middle_of_bounds_but_stays_unapplied(self):
        bounds = height_fit_bounds(3.0, 0.5, 1.0, cut_cap_m=1.0, support_cap_m=4.0)
        receipt = uniform_height_candidate(bounds)
        self.assertEqual(receipt["status"], "CANDIDATE_REQUIRES_LOCAL_REMEASUREMENT")
        self.assertEqual(receipt["candidate_lift_m"], 2.5)
        self.assertFalse(receipt["height_change_applied"])
        self.assertFalse(receipt["source_height_verified"])
        self.assertFalse(receipt["adjacent_joins_verified"])
        self.assertFalse(receipt["road_admitted"])

    def test_uniform_candidate_rejects_incompatible_cut_and_support(self):
        bounds = height_fit_bounds(6.0, 0.5, 1.0, cut_cap_m=1.0, support_cap_m=4.0)
        receipt = uniform_height_candidate(bounds)
        self.assertEqual(receipt["status"], "REJECT_INCOMPATIBLE_CUT_SUPPORT_BOUNDS")
        self.assertIsNone(receipt["candidate_lift_m"])
        self.assertFalse(receipt["height_change_applied"])

    def test_signed_below_terrain_support_gap_is_not_clipped(self):
        receipt = height_fit_bounds(5.0, -3.0, -2.0, cut_cap_m=1.0, support_cap_m=4.0)
        self.assertEqual(receipt["maximum_lift_for_support_m"], 6.0)
        self.assertTrue(receipt["bounds_overlap"])

    def test_height_diagnostic_rejects_nonfinite_or_invalid_evidence(self):
        for value in (math.nan, math.inf, True, -1.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                height_fit_bounds(value, 0.0, 0.0, cut_cap_m=1.0, support_cap_m=4.0)

    def test_failed_raster_cut_retains_measurement_without_writing_patch(self):
        mesh = sections([[v, 20] for v in np.linspace(10, 20, 21)])[:, ::-1]
        original = mesh.copy()
        terrain = np.full((64, 64), 33792, dtype=np.uint16)
        manifest = {"scale_z": 100.0, "location_z_cm": 0.0}
        diagnostics = {"max_core_support_m": 0.0, "max_shoulder_support_m": 0.0}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rejected-cut.json"
            with self.assertRaisesRegex(ValueError, "Ordinary 1 m CUT cap exceeded"):
                prepare_patch(
                    mesh,
                    terrain,
                    manifest,
                    path,
                    diagnostics=diagnostics,
                    asphalt_sections=mesh,
                )
            self.assertGreater(diagnostics["earthworks_fit"]["max_cut_m"], 1.0)
            self.assertGreater(diagnostics["cut_depth"]["over_cap_cell_count"], 0)
            self.assertEqual(
                diagnostics["cut_depth_by_envelope"]["admission_envelope"],
                "authored_patch_envelope",
            )
            self.assertGreater(
                diagnostics["cut_depth"]["peak_base_height_m"],
                diagnostics["cut_depth"]["peak_target_height_m"],
            )
            self.assertEqual(list(Path(directory).iterdir()), [])
        np.testing.assert_array_equal(mesh, original)

    def test_diagnostic_keeps_accepted_patch_bytes_and_cut_depth_unchanged(self):
        mesh = sections([[v, 20] for v in np.linspace(10, 20, 21)])[:, ::-1]
        terrain = np.full((64, 64), 32896, dtype=np.uint16)
        manifest = {"scale_z": 100.0, "location_z_cm": 0.0}
        diagnostics = {"max_core_support_m": 0.0, "max_shoulder_support_m": 0.0}
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "baseline.json"
            second = Path(directory) / "measured.json"
            a = prepare_patch(mesh, terrain, manifest, first)
            b = prepare_patch(mesh, terrain, manifest, second, diagnostics=diagnostics)
            self.assertEqual(
                first.with_suffix(".f32").read_bytes(),
                second.with_suffix(".f32").read_bytes(),
            )
            self.assertEqual(a["max_cut_m"], b["max_cut_m"])
            self.assertEqual(
                diagnostics["earthworks_fit"]["minimum_lift_for_cut_m"], 0.0
            )

    def test_3d_gate_covers_short_network_window(self):
        mesh = sections([[v, 0] for v in np.linspace(0, 30, 61)])
        self.assertEqual(surface_inspection(mesh.tolist())["status"], "PASS")
        mesh[10, :, 2] += 1.0
        self.assertEqual(surface_inspection(mesh.tolist())["status"], "FAIL")

    def test_slab_is_closed_and_directed_edges_cancel(self):
        mesh = sections([[v, 0] for v in np.linspace(0, 30, 61)]).tolist()
        vertices, triangles = pavement_slab(mesh)
        edges = Counter((a, b) for t in triangles for a, b in zip(t, (*t[1:], t[0])))
        for (a, b), count in edges.items():
            self.assertEqual(count, 1)
            self.assertEqual(edges[b, a], 1)
        self.assertAlmostEqual(vertices[0][2] - vertices[len(vertices) // 2][2], 0.08)

    def test_shoulder_miter_preserves_half_metre_perpendicular_extent(self):
        angle = np.linspace(0, math.pi, 121)
        axis = np.column_stack([10 * np.cos(angle), 10 * np.sin(angle)])
        mesh = sections(axis)[:, ::-1].tolist()
        extended = shoulder_sections(mesh)
        for side, outer in ((0, 0), (-1, -1)):
            for i in range(1, len(mesh)):
                a, b = np.array(mesh[i - 1][side][:2]), np.array(mesh[i][side][:2])
                tangent = b - a
                offset = np.array(extended[i][outer][:2]) - b
                extent = abs(
                    tangent[0] * offset[1] - tangent[1] * offset[0]
                ) / np.linalg.norm(tangent)
                self.assertAlmostEqual(extent, 0.5)

    def test_straight_accepts_constant_width(self):
        axis = [[v, 0] for v in np.linspace(0, 30, 61)]
        result = inspect_sections(sections(axis), LineString(axis))
        self.assertAlmostEqual(result["width_min_m"], 5)

    def test_widening_bulge_is_rejected(self):
        axis = [[v, 0] for v in np.linspace(0, 30, 61)]
        mesh = sections(axis)
        mesh[30, 0, 1] += 0.2
        with self.assertRaisesRegex(ValueError, "Nonconstant"):
            inspect_sections(mesh, LineString(axis))

    def test_folded_inner_edge_is_rejected(self):
        angle = np.linspace(0, math.pi, 121)
        axis = np.column_stack([2 * np.cos(angle), 2 * np.sin(angle)])
        with self.assertRaises(ValueError):
            inspect_sections(sections(axis), LineString(axis))

    def test_smooth_single_bend_passes(self):
        angle = np.linspace(0, math.pi, 121)
        axis = np.column_stack([10 * np.cos(angle), 10 * np.sin(angle)])
        inspect_sections(sections(axis), LineString(axis))

    def test_source_displacement_is_rejected(self):
        axis = [[v, 0] for v in np.linspace(0, 30, 61)]
        with self.assertRaisesRegex(ValueError, "displacement"):
            inspect_sections(
                sections(axis), LineString([[v, 2] for v in np.linspace(0, 30, 61)])
            )

    def test_reverse_hook_in_single_source_bend_is_rejected(self):
        angle = np.linspace(0, math.pi, 121)
        source = np.column_stack([10 * np.cos(angle), 10 * np.sin(angle)])
        axis = source.copy()
        axis[20:40, 1] += 0.25 * np.sin(np.linspace(0, 4 * math.pi, 20))
        with self.assertRaises(ValueError):
            inspect_sections(sections(axis), LineString(source))

    def test_cubic_is_deterministic(self):
        line = LineString([(0, 0), (20, 0), (30, 10), (30, 30)])
        a = smooth_axis(line)
        b = smooth_axis(line)
        self.assertTrue(np.array_equal(a[1], b[1]))
        self.assertLessEqual(np.diff(a[0]).max(), 0.5)


if __name__ == "__main__":
    unittest.main()

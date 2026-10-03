"""Regressions for network width, folds, counter-turns and source displacement."""

import math
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import numpy as np
from shapely.geometry import LineString

from scripts.assets.prepare_current_landscape_roads import (
    inspect_sections,
    prepare_patch,
    smooth_axis,
)
from scripts.geometry.network_earthworks_diagnostics import height_fit_bounds
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
                prepare_patch(mesh, terrain, manifest, path, diagnostics=diagnostics)
            self.assertGreater(diagnostics["earthworks_fit"]["max_cut_m"], 1.0)
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

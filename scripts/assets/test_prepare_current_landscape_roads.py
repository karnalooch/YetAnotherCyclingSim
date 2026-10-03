"""Regressions for network width, folds, counter-turns and source displacement."""

import math
import unittest
from collections import Counter

import numpy as np
from shapely.geometry import LineString

from scripts.assets.prepare_current_landscape_roads import inspect_sections, smooth_axis
from scripts.geometry.network_pavement import pavement_slab, shoulder_sections


def sections(axis):
    axis = np.asarray(axis, dtype=float)
    tangent = np.gradient(axis, axis=0)
    n = np.column_stack([-tangent[:, 1], tangent[:, 0]])
    n /= np.linalg.norm(n, axis=1)[:, None]
    xy = axis[:, None, :] + n[:, None, :] * np.linspace(-2.5, 2.5, 25)[None, :, None]
    return np.dstack([xy, np.ones(xy.shape[:2])])


class NetworkTests(unittest.TestCase):
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

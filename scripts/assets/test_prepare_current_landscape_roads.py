"""Regressions for network width, folds, counter-turns and source displacement."""

import math
import unittest

import numpy as np
from shapely.geometry import LineString

from scripts.assets.prepare_current_landscape_roads import inspect_sections, smooth_axis


def sections(axis):
    axis = np.asarray(axis, dtype=float)
    tangent = np.gradient(axis, axis=0)
    n = np.column_stack([-tangent[:, 1], tangent[:, 0]])
    n /= np.linalg.norm(n, axis=1)[:, None]
    xy = axis[:, None, :] + n[:, None, :] * np.linspace(-2.5, 2.5, 25)[None, :, None]
    return np.dstack([xy, np.ones(xy.shape[:2])])


class NetworkTests(unittest.TestCase):
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

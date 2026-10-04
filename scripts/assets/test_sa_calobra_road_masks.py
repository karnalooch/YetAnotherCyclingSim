"""Check clearance conservatism, facet registration and fail-closed sources."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
from shapely.ops import unary_union

from scripts.assets.prepare_sa_calobra_road_masks import (
    distance_lower_bound,
    pavement_polygons,
    prepare,
    squared_distance_axis,
)


class RoadMaskTests(unittest.TestCase):
    def test_euclidean_distance_matches_independent_brute_force(self):
        rng = np.random.default_rng(335)
        for shape in [(1, 6), (6, 1), (9, 13)]:
            mask = rng.random(shape) < 0.15
            mask.flat[0] = True
            points = np.argwhere(mask)
            exact = np.array(
                [min(np.linalg.norm(p - q) for p in points) for q in np.ndindex(shape)]
            ).reshape(shape)
            expected = np.maximum(0, exact * 0.5 - 0.5 / np.sqrt(2))
            actual = distance_lower_bound(mask, 0.5)
            self.assertTrue(np.all(actual <= expected + 1e-7))
            np.testing.assert_allclose(actual, expected, atol=1e-6)

    def test_parabola_envelopes_match_brute_force_nonbinary_costs(self):
        f = np.array([[9, 0, 3, 7], [5, 4, 1, 8]], dtype=np.float64)
        expected = [
            [min(row[i] + (q - i) ** 2 for i in range(4)) for q in range(4)]
            for row in f
        ]
        np.testing.assert_array_equal(squared_distance_axis(f), expected)

    def test_empty_pavement_cannot_grant_infinite_clearance(self):
        with self.assertRaises(ValueError):
            distance_lower_bound(np.zeros((2, 2), dtype=bool), 0.5)

    def test_frozen_facets_map_east_and_south_without_half_pixel_shift(self):
        sections = [[[x, y, 100] for x in np.linspace(0, 5, 25)] for y in [1, 0.5, 0]]
        polygon = unary_union(pavement_polygons(sections))
        np.testing.assert_allclose(
            polygon.bounds, [483000.25, 4409515.25, 483005.25, 4409516.25]
        )
        self.assertAlmostEqual(polygon.area, 5)
        with self.assertRaisesRegex(ValueError, "Folded"):
            pavement_polygons(sections[::-1])

    def test_existing_directory_refused_before_source_access(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            with self.assertRaises(FileExistsError):
                prepare(path / "missing", path, path / "missing", path)


if __name__ == "__main__":
    unittest.main()

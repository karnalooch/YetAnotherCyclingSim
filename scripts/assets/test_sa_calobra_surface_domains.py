"""Prevent shading repair from weakening planting/unknown boundaries."""

import unittest

import numpy as np

from scripts.assets.prepare_sa_calobra_pcg_masks import selectors
from scripts.assets.prepare_sa_calobra_surface_domains import (
    channel_shapes,
    shading_selectors,
)


class SurfaceDomainTests(unittest.TestCase):
    def test_observed_shading_survives_placement_holdback(self):
        counts = np.zeros((6, 1, 2), dtype=np.uint32)
        counts[1, 0, 0] = 1
        quality = np.zeros((1, 2), dtype=np.uint8)
        placement = selectors(counts, quality, np.ones((1, 2), dtype=bool))
        original = placement.copy()
        shading = shading_selectors(counts, quality)
        self.assertEqual(placement[0, 0, 0], 0)
        self.assertEqual(shading[0, 0, 0], 1)
        np.testing.assert_array_equal(shading[:, 0, 1], [255, 255, 255])
        np.testing.assert_array_equal(placement, original)

    def test_invalid_high_height_remains_rejected(self):
        counts = np.zeros((6, 1, 1), dtype=np.uint32)
        counts[3] = 1
        actual = shading_selectors(counts, np.ones((1, 1), dtype=np.uint8))
        np.testing.assert_array_equal(actual[:, 0, 0], [0, 0, 0])

    def test_only_water_lines_become_artistic_dry_channel(self):
        features = [
            {"group": group, "geometry": geometry}
            for group, geometry in (
                ("water", {"type": "LineString", "coordinates": [[0, 0], [0, 10]]}),
                ("water", {"type": "Point", "coordinates": [0, 0]}),
                (
                    "infrastructure",
                    {"type": "LineString", "coordinates": [[0, 0], [0, 10]]},
                ),
            )
        ]
        self.assertEqual(len(channel_shapes(features)), 1)
        with self.assertRaises(ValueError):
            channel_shapes(features, 5)


if __name__ == "__main__":
    unittest.main()

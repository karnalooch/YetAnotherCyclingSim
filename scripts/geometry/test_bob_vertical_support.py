import math
import unittest

from scripts.geometry.bob_vertical_support import (
    build_vertical_support,
    support_sections,
)
from scripts.geometry.smooth_road_ribbon import build_smooth_road_ribbon
from scripts.geometry.test_smooth_road_ribbon import SmoothRoadRibbonTests


class VerticalSupportTests(unittest.TestCase):
    def setUp(self):
        self.profile = SmoothRoadRibbonTests()._profile()
        self.sections = support_sections(self.profile)

    def test_full_profile_shoulders_and_road_underside_match_exactly(self):
        road, _, _ = build_smooth_road_ribbon(self.profile)
        n = len(self.sections) * 25
        for i, section in enumerate(self.sections):
            self.assertAlmostEqual(math.dist(section[0][:2], section[1][:2]), 0.5)
            self.assertAlmostEqual(math.dist(section[-1][:2], section[-2][:2]), 0.5)
            for j, p in enumerate(section[1:-1]):
                for a, b in zip(p, road[n + i * 25 + j]):
                    self.assertAlmostEqual(a, b)
        verts, faces, meta = build_vertical_support(
            self.sections, [[98, 98]] * len(self.sections)
        )
        self.assertEqual(meta["station_count"], len(self.profile["stations"]))
        self.assertGreater(meta["wall_segment_count"], 0)
        self.assertFalse(meta["road_admitted"])
        self.assertTrue(all(math.isfinite(v) for p in verts for v in p))
        self.assertTrue(all(len(set(f)) == 3 for f in faces))
        for face in faces[meta["top_triangle_count"] :]:
            xy = {verts[i][:2] for i in face}
            self.assertLessEqual(len(xy), 2)  # Every wall triangle is vertical.

    def test_uphill_ground_creates_no_inverted_walls(self):
        _, _, meta = build_vertical_support(
            self.sections, [[110, 110]] * len(self.sections)
        )
        self.assertEqual(meta["wall_segment_count"], 0)

    def test_ground_crossing_produces_no_degenerate_wall_triangle(self):
        ground = [[99 if i % 2 else 101] * 2 for i in range(len(self.sections))]
        vertices, faces, meta = build_vertical_support(self.sections, ground)
        for a, b, c in faces[meta["top_triangle_count"] :]:
            u = [x - y for x, y in zip(vertices[b], vertices[a])]
            v = [x - y for x, y in zip(vertices[c], vertices[a])]
            cross = (
                u[1] * v[2] - u[2] * v[1],
                u[2] * v[0] - u[0] * v[2],
                u[0] * v[1] - u[1] * v[0],
            )
            self.assertGreater(sum(x * x for x in cross), 1e-15)

    def test_missing_ground_fails_closed(self):
        with self.assertRaises(ValueError):
            build_vertical_support(
                self.sections, [[98, float("nan")]] * len(self.sections)
            )
        with self.assertRaises(ValueError):
            build_vertical_support(self.sections, [])

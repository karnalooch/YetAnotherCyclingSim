"""Topology regressions for the source-envelope domain; no Blender import."""

from collections import Counter
import unittest

from scripts.blender.build_pcg365_source_envelope import shell


class EnvelopeTopology(unittest.TestCase):
    def closed(self, cells):
        points = {(i, j): (float(i), float(j), 2.0) for i in range(5) for j in range(5)}
        vertices, faces, report = shell(points, cells)
        directed = Counter((f[k], f[(k + 1) % 3]) for f in faces for k in range(3))
        self.assertTrue(
            all(n == 1 and directed[(b, a)] == 1 for (a, b), n in directed.items())
        )
        volume = (
            sum(
                vertices[a][0]
                * (vertices[b][1] * vertices[c][2] - vertices[b][2] * vertices[c][1])
                + vertices[a][1]
                * (vertices[b][2] * vertices[c][0] - vertices[b][0] * vertices[c][2])
                + vertices[a][2]
                * (vertices[b][0] * vertices[c][1] - vertices[b][1] * vertices[c][0])
                for a, b, c in faces
            )
            / 6
        )
        self.assertAlmostEqual(volume, 2 * report["retained_cells"])
        self.assertTrue(all(p[2] == 0 for p in vertices[report["top_vertices"] :]))
        return vertices, faces, report

    def test_hole_remains_open_in_projection_with_closed_walls(self):
        _, _, r = self.closed({(i, j) for i in range(3) for j in range(3)} - {(1, 1)})
        self.assertEqual(r["retained_cells"], 8)
        self.assertEqual(r["boundary_edges"], 16)

    def test_corner_pinches_erode_without_filling_missing_source(self):
        _, _, r = self.closed({(0, 0), (1, 1), (2, 1)})
        self.assertGreater(r["discarded_corner_pinch_cells"], 0)
        self.assertLess(r["retained_cells"], 3)

    def test_largest_edge_connected_component_only(self):
        _, _, r = self.closed({(0, 0), (1, 0), (3, 3)})
        self.assertEqual(r["retained_cells"], 2)
        self.assertEqual(r["discarded_disconnected_cells"], 1)

    def test_order_independent_geometry(self):
        points = {(i, j): (i, j, 2) for i in range(4) for j in range(4)}
        cells = {(0, 0), (1, 0), (1, 1)}
        self.assertEqual(
            shell(points, cells), shell(points, set(reversed(sorted(cells))))
        )


if __name__ == "__main__":
    unittest.main()

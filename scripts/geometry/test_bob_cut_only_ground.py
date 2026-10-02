import unittest

from scripts.geometry.bob_cut_only_ground import (
    build_cut_only_corridor,
    sample_regular_grid_height,
)


class BobCutOnlyGroundTests(unittest.TestCase):
    def _profile(self):
        rows = []
        for index in range(5):
            station = index * 0.5
            lateral = [-2.0 + point * (4.0 / 24.0) for point in range(25)]
            rows.append({
                "station_m": station,
                "lateral_m": lateral,
                "xy_local_m": [[station, offset] for offset in lateral],
                "candidate_ground_m": [99.0 + 0.01 * station for _ in lateral],
            })
        return {"stations": rows}

    def test_corridor_uses_ties_and_preserves_road_edges(self):
        mesh, profiles, bounds = build_cut_only_corridor(self._profile(), falloff_m=1.0)
        self.assertEqual(mesh.station_count, 5)
        self.assertEqual(mesh.cross_section_point_count, 4)
        self.assertEqual(
            [point.role for point in profiles[0]],
            ["left_tie", "left_road_edge", "right_road_edge", "right_tie"],
        )
        self.assertAlmostEqual(profiles[0][0].lateral_m, -3.0)
        self.assertAlmostEqual(profiles[0][-1].lateral_m, 3.0)
        self.assertLess(bounds["min_y_m"], -2.0)
        self.assertGreater(bounds["max_y_m"], 2.0)

    def test_regular_grid_sampling_matches_mesh_diagonal(self):
        xs = (0.0, 1.0)
        ys = (1.0, 0.0)
        heights = ((0.0, 10.0), (20.0, 30.0))
        self.assertAlmostEqual(
            sample_regular_grid_height(xs, ys, heights, x_m=0.25, y_m=0.75), 7.5
        )
        self.assertAlmostEqual(
            sample_regular_grid_height(xs, ys, heights, x_m=0.75, y_m=0.25), 22.5
        )


if __name__ == "__main__":
    unittest.main()

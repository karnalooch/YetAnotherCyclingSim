import unittest

from scripts.geometry.smooth_road_ribbon import build_smooth_road_ribbon


class SmoothRoadRibbonTests(unittest.TestCase):
    def _profile(self):
        rows = []
        for index in range(21):
            station = index * 0.5
            offsets = [-2.5 + point * (5.0 / 24.0) for point in range(25)]
            rows.append(
                {
                    "station_m": station,
                    "lateral_m": offsets,
                    "xy_local_m": [[station, offset] for offset in offsets],
                    "candidate_ground_m": [
                        100.0 + station * 0.01 + offset * 0.02
                        for offset in offsets
                    ],
                }
            )
        return {
            "region_id": "sa_calobra",
            "status": "REVIEW_REQUIRED",
            "source_xy_preserved": True,
            "terrain_modified": False,
            "road_earthworks_modified": False,
            "earthworks_authoring_permitted": False,
            "authoritative_physics": False,
            "geographic_width_admitted": False,
            "road_admitted": False,
            "stations": rows,
        }

    def test_builds_closed_smooth_ribbon(self):
        vertices, triangles, metadata = build_smooth_road_ribbon(self._profile())
        self.assertEqual(metadata["role"], "PRESENTATION_ONLY_SMOOTH_RIBBON")
        self.assertFalse(metadata["contact_authority"])
        self.assertEqual(metadata["station_count"], 21)
        self.assertEqual(metadata["cross_section_point_count"], 25)
        self.assertEqual(len(vertices), 21 * 25 * 2)
        self.assertGreater(len(triangles), metadata["top_triangle_count"] * 2)
        self.assertAlmostEqual(metadata["min_width_m"], 5.0)
        self.assertAlmostEqual(metadata["max_width_m"], 5.0)
        self.assertLess(metadata["center_second_difference_rms_m"], 1e-9)

    def test_rejects_folded_ribbon(self):
        profile = self._profile()
        for point in profile["stations"][10]["xy_local_m"]:
            point[0] = 4.0
        with self.assertRaisesRegex(ValueError, "folded or inverted"):
            build_smooth_road_ribbon(profile)

    def test_rejects_authoritative_promotion(self):
        profile = self._profile()
        profile["road_admitted"] = True
        with self.assertRaisesRegex(ValueError, "Unadmitted"):
            build_smooth_road_ribbon(profile)


if __name__ == "__main__":
    unittest.main()

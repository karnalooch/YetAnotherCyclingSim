import unittest

from scripts.worldgen.bob_terrain_fit_inspector import (
    CONTACT_OK,
    CUT_REQUIRED,
    FILL_REQUIRED,
    STRUCTURE_REVIEW,
    classify_terrain_fit_sample,
    inspect_terrain_fit,
)


SHA = "a" * 40


class BobTerrainFitInspectorTests(unittest.TestCase):
    def test_classifies_contact_cut_fill_and_structure(self):
        common = {
            "contact_band_max_m": 0.08,
            "structure_review_threshold_m": 4.0,
        }
        self.assertEqual(
            classify_terrain_fit_sample(
                road_surface_z_m=100.04,
                landscape_z_m=100.0,
                **common,
            )["action"],
            CONTACT_OK,
        )
        self.assertEqual(
            classify_terrain_fit_sample(
                road_surface_z_m=99.5,
                landscape_z_m=100.0,
                **common,
            )["action"],
            CUT_REQUIRED,
        )
        self.assertEqual(
            classify_terrain_fit_sample(
                road_surface_z_m=100.5,
                landscape_z_m=100.0,
                **common,
            )["action"],
            FILL_REQUIRED,
        )
        structure = classify_terrain_fit_sample(
            road_surface_z_m=105.0,
            landscape_z_m=100.0,
            **common,
        )
        self.assertEqual(structure["action"], STRUCTURE_REVIEW)
        self.assertAlmostEqual(structure["fill_required_m"], 4.92)

    def test_everything_above_ribbon_inside_sampled_footprint_is_cut(self):
        result = inspect_terrain_fit(
            [
                {
                    "station_m": 0.0,
                    "lateral_m": -2.0,
                    "local_xy_m": [0.0, -2.0],
                    "road_surface_z_m": 100.0,
                    "landscape_z_m": 100.25,
                },
                {
                    "station_m": 0.0,
                    "lateral_m": 0.0,
                    "local_xy_m": [0.0, 0.0],
                    "road_surface_z_m": 100.0,
                    "landscape_z_m": 99.96,
                },
                {
                    "station_m": 0.5,
                    "lateral_m": 2.0,
                    "local_xy_m": [0.5, 2.0],
                    "road_surface_z_m": 100.0,
                    "landscape_z_m": 99.0,
                },
            ],
            exact_sha=SHA,
            contact_band_max_m=0.08,
            structure_review_threshold_m=4.0,
        )
        self.assertTrue(result["inspection_complete"])
        self.assertEqual(result["role"], "INSPECTOR_ONLY")
        self.assertEqual(result["class_counts"][CUT_REQUIRED], 1)
        self.assertEqual(result["class_counts"][CONTACT_OK], 1)
        self.assertEqual(result["class_counts"][FILL_REQUIRED], 1)
        self.assertEqual(result["terrain_above_road_sample_count"], 1)
        self.assertFalse(result["earthworks_authoring_permitted"])
        self.assertFalse(result["geometry_repair_executed"])
        self.assertEqual(
            result["cut_intervals_m"],
            [{"start_m": 0.0, "end_m": 0.0}],
        )
        self.assertEqual(
            result["fill_intervals_m"],
            [{"start_m": 0.5, "end_m": 0.5}],
        )

    def test_trace_miss_fails_inspection_closed(self):
        report = inspect_terrain_fit(
            [
                {
                    "station_m": 0.0,
                    "lateral_m": 0.0,
                    "local_xy_m": [0.0, 0.0],
                    "road_surface_z_m": 100.0,
                    "landscape_z_m": None,
                }
            ],
            exact_sha=SHA,
            contact_band_max_m=0.08,
            structure_review_threshold_m=4.0,
        )
        self.assertFalse(report["inspection_complete"])
        self.assertEqual(report["status"], "INSPECTION_INCOMPLETE")
        self.assertEqual(report["trace_miss_count"], 1)


if __name__ == "__main__":
    unittest.main()

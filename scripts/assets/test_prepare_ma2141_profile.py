import copy
import unittest

import numpy as np

from scripts.assets.prepare_ma2141_profile import fit_sections, local_linear_fit
from scripts.worldgen.bob_profile_inspector import inspect_road_profile


class RoadProfileTests(unittest.TestCase):
    def setUp(self):
        self.stations = np.arange(101) * 0.5
        self.lateral = np.tile(np.linspace(-2, 4, 25), (101, 1))

    def test_preserves_grade_and_crossfall_including_endpoints(self):
        ground = 600 + 0.08 * self.stations[:, None] + 0.035 * self.lateral
        fit = fit_sections(self.stations, self.lateral, ground)
        np.testing.assert_allclose(fit["target_ground_m"], ground, atol=1e-9)
        np.testing.assert_allclose(fit["crossfall"], 0.035, atol=1e-10)
        self.assertEqual(fit["review_station_indices"], [])

    def test_reduces_noise_without_erasing_longitudinal_grade(self):
        clean = 600 + 0.08 * self.stations[:, None] + 0.035 * self.lateral
        ground = clean + 0.08 * np.sin(self.stations[:, None] * 4)
        fit = fit_sections(self.stations, self.lateral, ground)
        before = fit["metrics"]["raw_center_second_difference_rms_m"]
        after = fit["metrics"]["candidate_center_second_difference_rms_m"]
        self.assertLess(after, before / 10)
        self.assertLess(np.max(np.abs(fit["target_ground_m"] - clean)), 0.03)

    def test_edge_rock_is_reported_not_silently_excluded_from_cut_fill(self):
        ground = 600 + 0.02 * self.stations[:, None] + 0.03 * self.lateral
        ground[50, 0] += 2
        fit = fit_sections(self.stations, self.lateral, ground)
        self.assertAlmostEqual(fit["metrics"]["max_cut_m"], 2)
        self.assertIn(50, fit["review_station_indices"])

    def test_steep_crossfall_is_flagged_not_clamped(self):
        ground = 600 + 0.3 * self.lateral
        fit = fit_sections(self.stations, self.lateral, ground)
        np.testing.assert_allclose(fit["crossfall"], 0.3, atol=1e-10)
        self.assertEqual(len(fit["review_station_indices"]), 101)

    def test_longitudinal_grade_flags_both_segment_endpoints(self):
        ground = 600 + 0.4 * self.stations[:, None] + 0.03 * self.lateral
        fit = fit_sections(self.stations, self.lateral, ground)
        self.assertEqual(len(fit["review_station_indices"]), 101)

    def test_no_influence_from_distant_chainage(self):
        values = 600 + 0.08 * self.stations
        candidate = local_linear_fit(self.stations, values, 5)
        values[80:] += 100  # A nearby arm in XY must not become a fit neighbour.
        changed = local_linear_fit(self.stations, values, 5)
        np.testing.assert_array_equal(candidate[:70], changed[:70])

    def test_rejects_invalid_data(self):
        for stations, values, radius in [
            ([0, 0, 1], [1, 2, 3], 5),
            ([0, 1, 2], [1, float("nan"), 3], 5),
            ([0, 1, 2], [1, 2, 3], float("inf")),
            ([0, 1, 2], [1, 2, 3], 0.5),
        ]:
            with (
                self.subTest(stations=stations, radius=radius),
                self.assertRaises(ValueError),
            ):
                local_linear_fit(stations, values, radius)
        with self.assertRaises(ValueError):
            fit_sections(self.stations, self.lateral[:, ::-1], self.lateral)


class BobProfileInspectorTests(unittest.TestCase):
    def packet(self):
        return {
            "exact_sha": "a" * 40,
            **{
                key: "b" * 64
                for key in (
                    "source_sha256",
                    "profile_sha256",
                    "heightmap_sha256",
                    "imagery_sha256",
                    "producer_sha256",
                )
            },
            "source_xy_preserved": True,
            "parameters": {
                "station_step_m": 0.5,
                "review_delta_m": 0.5,
                "review_grade": 0.25,
                "review_crossfall": 0.12,
            },
            "stations": [
                {
                    "station_m": i * 0.5,
                    "candidate_center_m": 600.0,
                    "lateral_m": np.linspace(-3, 3, 25).tolist(),
                    "native_ground_m": [600.0] * 25,
                    "candidate_ground_m": [600.0] * 25,
                }
                for i in range(7)
            ],
        }

    def test_flat_profile_never_admits_unverified_road_or_learning(self):
        packet = self.packet()
        before = copy.deepcopy(packet)
        result = inspect_road_profile(packet)
        self.assertEqual(packet, before)
        self.assertEqual(result["status"], "REVIEW_PENDING")
        self.assertTrue(result["inspection_complete"])
        for key in (
            "earthworks_authoring_permitted",
            "geometry_repair_executed",
            "road_admitted",
            "eligible_for_learning",
        ):
            self.assertFalse(result[key])
        self.assertIn("curve_and_edge_smoothness", result["unverified_checks"])

    def test_groups_disjoint_edge_failures_without_trusting_summary(self):
        packet = self.packet()
        packet["metrics"] = {"max_fill_m": 0}
        packet["review_stations_m"] = []
        for i in [1, 2, 5]:
            packet["stations"][i]["native_ground_m"][0] = 598.0 - i / 10
        findings = inspect_road_profile(packet)["findings"]
        self.assertEqual(len(findings), 2)
        self.assertEqual(
            [(f["start_station_m"], f["end_station_m"]) for f in findings],
            [(0.5, 1.0), (2.5, 2.5)],
        )
        self.assertEqual(findings[0]["peak_station_m"], 1.0)
        self.assertEqual(findings[0]["kind"], "FILL_DIFFERENCE")
        self.assertEqual(findings[0]["cause"], "UNRESOLVED")

    def test_cut_crossfall_and_grade_are_separate_findings(self):
        packet = self.packet()
        for i, row in enumerate(packet["stations"]):
            row["candidate_center_m"] = 600 + i * 0.2
            row["candidate_ground_m"] = [
                600 + i * 0.2 + 0.2 * x for x in row["lateral_m"]
            ]
            row["native_ground_m"] = [x + 1 for x in row["candidate_ground_m"]]
        findings = inspect_road_profile(packet)["findings"]
        self.assertEqual(
            {f["kind"] for f in findings}, {"CUT_DIFFERENCE", "CROSSFALL", "GRADE"}
        )
        grade = next(f for f in findings if f["kind"] == "GRADE")
        self.assertEqual(grade["end_station_m"], 3.0)
        self.assertEqual(grade["sample_count"], 6)

    def test_missing_nonfinite_boolean_and_gapped_evidence_fail_closed(self):
        packets = []
        p = self.packet()
        del p["heightmap_sha256"]
        packets.append(p)
        p = self.packet()
        p["stations"][2]["native_ground_m"][0] = float("nan")
        packets.append(p)
        p = self.packet()
        p["parameters"]["review_delta_m"] = True
        packets.append(p)
        p = self.packet()
        del p["stations"][3]
        packets.append(p)
        p = self.packet()
        p["stations"][2]["lateral_m"] = [0.0] * 25
        packets.append(p)
        p = self.packet()
        p["source_xy_preserved"] = False
        packets.append(p)
        for packet in packets:
            with self.subTest(packet=packet):
                result = inspect_road_profile(packet)
                self.assertEqual(result["status"], "INSPECTION_INCOMPLETE")
                self.assertFalse(result["inspection_complete"])
                self.assertFalse(result["earthworks_authoring_permitted"])


if __name__ == "__main__":
    unittest.main()

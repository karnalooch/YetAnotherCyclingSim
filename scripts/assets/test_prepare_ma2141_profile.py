import unittest

import numpy as np

from scripts.assets.prepare_ma2141_profile import fit_sections, local_linear_fit


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


if __name__ == "__main__":
    unittest.main()

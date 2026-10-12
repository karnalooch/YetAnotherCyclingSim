"""Interval fitting checks independent of Unreal and geographic source files."""

import unittest

from scripts.assets.pcg_boulder_support import solve_support


def sample(bottom, top, ground):
    return dict(bottom_z_cm=bottom, top_z_cm=top, ground_z_cm=ground)


class SupportTests(unittest.TestCase):
    def test_flat_planar_contact_has_no_embedding(self):
        result = solve_support([sample(-2, 8, 100)] * 3)
        self.assertEqual(result["root_zero_sampled_air_cm"], 102)
        self.assertEqual(result["root_nonpenetrating_cm"], 102)
        self.assertEqual(result["required_embedding_cm"], 0)
        self.assertEqual(result["exposure_mean_cm"], 10)
        self.assertEqual(result["penetrating_count"], 0)
        self.assertFalse(result["placement"])

    def test_rough_base_embeds_highest_bottom(self):
        result = solve_support([sample(0, 10, 0), sample(3, 12, 0)])
        self.assertEqual(result["root_zero_sampled_air_cm"], -3)
        self.assertEqual(result["root_nonpenetrating_cm"], 0)
        self.assertEqual(result["required_embedding_cm"], 3)
        self.assertEqual([s["bottom_gap_cm"] for s in result["samples"]], [-3, 0])
        self.assertEqual(result["exposure_min_cm"], 7)
        self.assertEqual(result["exposure_max_cm"], 9)
        self.assertEqual(result["exposure_mean_cm"], 8)

    def test_slope_reports_partial_submergence_and_highest_root(self):
        records = [sample(0, 4, 0), sample(0, 4, 2), sample(0, 4, 5)]
        result = solve_support(records)
        self.assertEqual(result["root_zero_sampled_air_cm"], 0)
        self.assertEqual(result["required_embedding_cm"], 5)
        self.assertEqual(result["exposed_count"], 2)
        self.assertEqual(result["penetrating_count"], 2)
        self.assertEqual(result["max_penetration_cm"], 5)
        self.assertEqual([s["exposed_top_cm"] for s in result["samples"]], [4, 2, 0])
        self.assertEqual(max(s["bottom_gap_cm"] for s in result["samples"]), 0)
        self.assertEqual(solve_support(reversed(records))["required_embedding_cm"], 5)

    def test_all_submerged_rejected(self):
        with self.assertRaisesRegex(ValueError, "All sampled.*submerged"):
            solve_support([sample(0, 0, 0)])

    def test_invalid_and_nonfinite_rejected(self):
        with self.assertRaises(ValueError):
            solve_support([])
        with self.assertRaises(ValueError):
            solve_support([sample(2, 1, 0)])
        for value in (float("nan"), float("inf"), -float("inf"), True, "1", None):
            for key in ("bottom_z_cm", "top_z_cm", "ground_z_cm"):
                record = sample(0, 2, 0)
                record[key] = value
                with self.subTest(value=value, key=key), self.assertRaises(ValueError):
                    solve_support([record])
        with self.assertRaises(ValueError):
            solve_support([sample(-1e308, 1e308, 1e308)])


if __name__ == "__main__":
    unittest.main()

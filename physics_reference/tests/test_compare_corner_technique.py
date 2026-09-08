"""Integration tests for the baseline vs technique plan comparison ride."""

import importlib.util
import math
import unittest
from pathlib import Path

from cycling_physics import ALPINE_CORNERS, ALPINE_JOURNEY, ALPINE_WEATHER

_EXAMPLE_PATH = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "compare_corner_technique.py"
)


def _load_compare_module():
    spec = importlib.util.spec_from_file_location(
        "compare_corner_technique_example",
        _EXAMPLE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compare = _load_compare_module()


class TestCompareCornerTechnique(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = compare.ride_and_assess(use_technique=False)
        cls.technique = compare.ride_and_assess(use_technique=True)
        cls.baseline_again = compare.ride_and_assess(use_technique=False)
        cls.technique_again = compare.ride_and_assess(use_technique=True)

    def test_both_rides_finish_the_route(self):
        self.assertGreaterEqual(self.baseline["distance_m"], ALPINE_JOURNEY.total_length_m)
        self.assertGreaterEqual(self.technique["distance_m"], ALPINE_JOURNEY.total_length_m)

    def test_both_rides_take_20_to_30_minutes(self):
        for name, result in (("baseline", self.baseline), ("technique", self.technique)):
            with self.subTest(plan=name):
                self.assertGreaterEqual(result["time_s"], 1200.0)
                self.assertLessEqual(result["time_s"], 1800.0)

    def test_both_rides_produce_eight_assessments(self):
        self.assertEqual(len(self.baseline["assessments"]), 8)
        self.assertEqual(len(self.technique["assessments"]), 8)

    def test_technique_has_higher_mean_score(self):
        self.assertGreater(self.technique["mean_score"], self.baseline["mean_score"])

    def test_technique_has_fewer_low_ratings(self):
        def low_count(result):
            counts = result["rating_counts"]
            return counts["needs_improvement"] + counts["poor"]

        self.assertLess(low_count(self.technique), low_count(self.baseline))

    def test_both_plans_are_deterministic(self):
        self.assertEqual(self.baseline["state"], self.baseline_again["state"])
        self.assertEqual(self.technique["state"], self.technique_again["state"])
        self.assertEqual(
            [a.score for a in self.baseline["assessments"]],
            [a.score for a in self.baseline_again["assessments"]],
        )
        self.assertEqual(
            [a.score for a in self.technique["assessments"]],
            [a.score for a in self.technique_again["assessments"]],
        )

    def test_all_results_are_finite(self):
        for result in (self.baseline, self.technique):
            with self.subTest(plan=result is self.baseline):
                self.assertTrue(math.isfinite(result["time_s"]))
                self.assertTrue(math.isfinite(result["distance_m"]))
                self.assertTrue(math.isfinite(result["avg_kmh"]))
                self.assertTrue(math.isfinite(result["mean_score"]))
                for assessment in result["assessments"]:
                    self.assertTrue(math.isfinite(assessment.score))
                    self.assertGreaterEqual(assessment.score, 0.0)
                    self.assertLessEqual(assessment.score, 100.0)

    def test_plan_acts_only_through_rider_input(self):
        baseline_entry = compare.make_rider_input("Village Start", 660.0, use_technique=False)
        technique_entry = compare.make_rider_input("Village Start", 660.0, use_technique=True)
        self.assertEqual(baseline_entry.power_w, 220.0)
        self.assertEqual(baseline_entry.cadence_rpm, 90.0)
        self.assertAlmostEqual(technique_entry.power_w, 110.0, places=12)
        self.assertAlmostEqual(technique_entry.cadence_rpm, 67.5, places=12)

        baseline_far = compare.make_rider_input("Village Start", 400.0, use_technique=False)
        technique_far = compare.make_rider_input("Village Start", 400.0, use_technique=True)
        self.assertEqual(baseline_far, technique_far)

    def test_exit_minimums_apply_on_high_valley_descent(self):
        baseline_exit = compare.make_rider_input("High Valley Descent", 8270.0, use_technique=False)
        technique_exit = compare.make_rider_input("High Valley Descent", 8270.0, use_technique=True)
        self.assertEqual(baseline_exit.power_w, 0.0)
        self.assertEqual(baseline_exit.cadence_rpm, 0.0)
        self.assertEqual(technique_exit.power_w, 250.0)
        self.assertEqual(technique_exit.cadence_rpm, 90.0)

    def test_alpine_data_is_not_modified(self):
        self.assertEqual(ALPINE_JOURNEY.total_length_m, 10000.0)
        self.assertEqual(ALPINE_WEATHER.total_length_m, 10000.0)
        self.assertEqual(len(ALPINE_CORNERS.corners), 8)


if __name__ == "__main__":
    unittest.main()

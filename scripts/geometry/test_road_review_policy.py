"""The owner width margin allows narrowing without hiding larger deviations."""

import unittest

from scripts.geometry.road_review_policy import width_review


class RoadReviewPolicyTests(unittest.TestCase):
    def test_five_percent_including_local_narrowing(self):
        for width in (4.75, 4.962, 5.0, 5.25):
            rows = [[[i, width * j / 24, 0] for j in range(25)] for i in range(3)]
            self.assertEqual(width_review(rows)["status"], "PASS")
        for width in (4.74, 5.26):
            rows = [[[i, width * j / 24, 0] for j in range(25)] for i in range(3)]
            self.assertEqual(width_review(rows)["status"], "REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()

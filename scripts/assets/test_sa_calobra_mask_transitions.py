"""Check conservative transitions and limited topology repair authority."""

import unittest

import numpy as np

from scripts.assets.prepare_sa_calobra_mask_transitions import (
    audit_network,
    density_weights,
    smoothstep,
    window_sum,
)


def line(identity, coordinates):
    return {
        "source": "regional-provisional-hydrography",
        "object_id": identity,
        "geometry": {"type": "LineString", "coordinates": coordinates},
    }


class TransitionTests(unittest.TestCase):
    def test_window_support_matches_direct_sums(self):
        a = np.arange(35).reshape(5, 7)
        result = window_sum(a, 1)
        for y in range(5):
            for x in range(7):
                self.assertEqual(
                    result[y, x], a[max(0, y - 1) : y + 2, max(0, x - 1) : x + 2].sum()
                )

    def test_density_never_promotes_unknown_or_excluded(self):
        counts = np.zeros((6, 4, 4), dtype=np.uint32)
        counts[1:4] = 1
        bands = np.ones((3, 4, 4), dtype=np.uint8)
        bands[:, 0, 0] = 255
        bands[:, 1, 1] = 0
        distance = np.full((4, 4), 20, dtype=np.float32)
        distance[2, 2] = 0
        weights = density_weights(counts, bands, distance)
        np.testing.assert_array_equal(weights[:, 0, 0], [-32767] * 3)
        np.testing.assert_array_equal(weights[:, 1, 1], [0] * 3)
        np.testing.assert_array_equal(weights[:, 2, 2], [0] * 3)
        np.testing.assert_allclose(weights[:, 3, 3], [1 / 3] * 3)

    def test_only_subpixel_gaps_are_joined(self):
        report = audit_network(
            [
                line(1, [(2, 5), (5, 5)]),
                line(2, [(5.3, 5), (8, 5)]),
                line(3, [(10, 5), (13, 5)]),
            ],
            [0, 0, 20, 20],
        )
        self.assertTrue(report["subpixel_joins"])
        self.assertTrue(report["unverified_gap_candidates"])
        self.assertTrue(all(r["gap_m"] <= 0.5 for r in report["subpixel_joins"]))
        self.assertTrue(
            all(r["gap_m"] > 0.5 for r in report["unverified_gap_candidates"])
        )
        self.assertFalse(report["all_terminals_are_errors"])

    def test_boundary_exit_and_ambiguous_gap_are_not_repaired(self):
        report = audit_network(
            [
                line(1, [(0, 5), (5, 5)]),
                line(2, [(5.3, 4), (5.3, 4.9)]),
                line(3, [(5.3, 5.1), (5.3, 6)]),
            ],
            [0, 0, 10, 10],
        )
        start = report["endpoints"][0]
        self.assertEqual(start["status"], "boundary_exit")
        end = report["endpoints"][1]
        self.assertTrue(end["ambiguous_nearest"])
        self.assertFalse(any(r["object_id"] == 1 for r in report["subpixel_joins"]))

    def test_fade_is_bounded_and_monotonic(self):
        result = smoothstep(np.array([-1, 0, 0.25, 0.5, 0.75, 1, 2]))
        self.assertEqual(result[0], 0)
        self.assertEqual(result[-1], 1)
        self.assertTrue(np.all(np.diff(result) >= 0))


if __name__ == "__main__":
    unittest.main()

"""Verify source identity and metric comparison without road-height admission."""

import unittest

from scripts.assets.audit_current_landscape_road_heights import (
    compare_vertices,
    validate_collection,
)


class SourceHeightAuditTests(unittest.TestCase):
    def test_original_vertices_keep_xy_chainage_and_signed_height_difference(self):
        rows = compare_vertices(
            [[0, 0, 3], [3, 4, 99]], lambda x, y: (x, y), lambda x, y: 5
        )
        self.assertEqual(rows[1]["source_chainage_m"], 5)
        self.assertEqual(rows[0]["source_minus_ground_m"], -2)
        self.assertEqual(rows[1]["source_minus_ground_m"], 94)

    def test_outside_vertices_do_not_shorten_original_chainage(self):
        rows = compare_vertices(
            [[0, 0, 1], [3, 4, 1], [6, 8, 1]],
            lambda x, y: (x, y),
            lambda x, y: None if x < 6 else 0,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_chainage_m"], 10)

    def test_missing_or_nonfinite_z_fails(self):
        for coordinates in ([[0, 0]], [[0, 0, float("nan")]]):
            with self.assertRaises(ValueError):
                compare_vertices(coordinates, lambda x, y: (x, y), lambda x, y: 0)

    def test_incomplete_or_duplicate_collection_fails(self):
        for source in (
            {"features": [{"id": "a"}], "numberMatched": 2, "numberReturned": 1},
            {
                "features": [{"id": "a"}, {"id": "a"}],
                "numberMatched": 2,
                "numberReturned": 2,
            },
        ):
            with self.assertRaises(ValueError):
                validate_collection(source)

    def test_nonfinite_ground_fails(self):
        with self.assertRaises(ValueError):
            compare_vertices(
                [[0, 0, 1]], lambda x, y: (x, y), lambda x, y: float("inf")
            )


if __name__ == "__main__":
    unittest.main()

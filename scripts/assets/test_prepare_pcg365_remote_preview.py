"""CPU footprint regression tests; never admit native contact."""

import unittest

from scripts.assets.prepare_pcg365_remote_preview import footprint_clearance


class Grid:
    shape = (4033, 4033)

    def __init__(self, value):
        self.value = value

    def __getitem__(self, index):
        return self.value


class PreviewExclusions(unittest.TestCase):
    def test_radius_consumes_distance(self):
        self.assertTrue(
            footprint_clearance(Grid(1.5), Grid(0), [181600, 189600], 100)["eligible"]
        )
        self.assertFalse(
            footprint_clearance(Grid(1.499), Grid(0), [181600, 189600], 100)["eligible"]
        )
        self.assertFalse(
            footprint_clearance(Grid(1.5), Grid(0), [181601, 189600], 100)["eligible"]
        )

    def test_unknown_and_every_exclusion_reject(self):
        for bits in (1, 2, 4, 8, 16, 32, 64, 128, 65535):
            self.assertFalse(
                footprint_clearance(Grid(100), Grid(bits), [181600, 189600], 10)[
                    "eligible"
                ]
            )
        self.assertFalse(
            footprint_clearance(Grid(float("nan")), Grid(0), [181600, 189600], 10)[
                "eligible"
            ]
        )

    def test_entire_radius_with_clearance_stays_inside_aoi(self):
        self.assertFalse(
            footprint_clearance(Grid(100), Grid(0), [201600, 189600], 10)["eligible"]
        )
        self.assertFalse(
            footprint_clearance(Grid(100), Grid(0), [-100, 0], 10)["eligible"]
        )

    def test_invalid_geometry_rejects(self):
        for radius in (0, -1, float("nan")):
            with self.assertRaises(ValueError):
                footprint_clearance(Grid(10), Grid(0), [181600, 189600], radius)


if __name__ == "__main__":
    unittest.main()

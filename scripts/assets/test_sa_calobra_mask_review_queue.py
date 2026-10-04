"""Protect review coordinates, overlapping reasons and the no-repair boundary."""

import copy
import unittest

import numpy as np

from scripts.assets.prepare_sa_calobra_mask_review_queue import locate_gap


class MaskReviewQueueTests(unittest.TestCase):
    def setUp(self):
        self.grid = {
            "crs": "EPSG:25831",
            "transform": [0.5, 0.0, 483000.0, 0.0, -0.5, 4409516.5],
            "width": 8,
            "height": 8,
        }
        self.candidate = {
            "object_id": 1,
            "nearest_object_id": 2,
            "end": -1,
            "status": "UNVERIFIED_GAP_CANDIDATE",
            "gap_m": 1.0,
            "geometry": {
                "type": "LineString",
                "coordinates": [[483000.25, 4409516.25], [483001.25, 4409516.25]],
            },
        }
        self.reasons = np.zeros((8, 8), dtype=np.uint16)

    def test_first_pixel_centre_and_south_axis(self):
        report = locate_gap(self.candidate, self.grid, self.reasons)
        np.testing.assert_allclose(report["world_xy_cm"], [[0, 0], [100, 0]])
        np.testing.assert_allclose(report["focus_world_xy_cm"], [50, 0])
        self.candidate["geometry"]["coordinates"][1] = [483000.25, 4409515.25]
        report = locate_gap(self.candidate, self.grid, self.reasons)
        np.testing.assert_allclose(report["world_xy_cm"], [[0, 0], [0, 100]])

    def test_overlapping_flags_do_not_authorize_a_repair(self):
        self.reasons[0, :3] = 1 | 4 | 16 | 128
        before = self.reasons.copy()
        candidate_before = copy.deepcopy(self.candidate)
        report = locate_gap(self.candidate, self.grid, self.reasons)
        self.assertEqual(report["touched_cells"], 3)
        for key in [
            "pavement",
            "conservative_bob",
            "decorative_water_holdback",
            "unknown_samples",
        ]:
            self.assertEqual(report["overlap_cells"][key], 3)
        self.assertFalse(report["repair_authorized"])
        self.assertEqual(report["culvert"], "UNVERIFIED")
        np.testing.assert_array_equal(self.reasons, before)
        self.assertEqual(self.candidate, candidate_before)

    def test_mismatched_length_and_join_status_rejected(self):
        self.candidate["gap_m"] = 2
        with self.assertRaises(ValueError):
            locate_gap(self.candidate, self.grid, self.reasons)
        self.candidate["gap_m"] = 1
        self.candidate["status"] = "DERIVED_SUBPIXEL_TOPOLOGY_JOIN"
        with self.assertRaises(ValueError):
            locate_gap(self.candidate, self.grid, self.reasons)

    def test_grid_or_shape_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            locate_gap(self.candidate, self.grid, self.reasons[:2])
        self.grid["transform"][2] += 0.25
        with self.assertRaises(ValueError):
            locate_gap(self.candidate, self.grid, self.reasons)

    def test_outside_grid_rejected(self):
        self.candidate["geometry"]["coordinates"] = [
            [482000, 4409000],
            [482001, 4409000],
        ]
        with self.assertRaises(ValueError):
            locate_gap(self.candidate, self.grid, self.reasons)

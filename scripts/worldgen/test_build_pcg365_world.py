"""Boundary tests for the PCG365 entry point; no Unreal or source downloads."""

import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

import numpy as np

spec = importlib.util.spec_from_file_location("build_pcg365_world", Path(__file__).with_name("build_pcg365_world.py"))
world = importlib.util.module_from_spec(spec)
spec.loader.exec_module(world)


class ExactGridTests(unittest.TestCase):
    def setUp(self):
        self.cliff = np.zeros((9, 9), dtype=np.uint8)
        self.scree = np.zeros((9, 9), dtype=np.uint8)
        self.reasons = np.zeros((9, 9), dtype=np.uint16)
        self.slope = np.full((9, 9), 30.0)
        self.treatment = np.full((2, 2), 3, dtype=np.uint8)

    def count(self):
        return world.classify_cells(self.cliff, self.scree, self.reasons, self.slope, self.treatment, 10.0)

    def test_planning_bin_does_not_fill_unselected_pixels(self):
        self.scree[8, 8] = 1
        count = self.count()
        self.assertEqual(count["source_cells"], 81)
        self.assertEqual(count["visible_scree_source_cells"], 1)
        self.assertEqual(count["scree_cells_within_existing_slope_policy"], 0)
        self.assertEqual(count["scree_cells_rejected_by_existing_slope_policy"], 1)

    def test_every_technical_exclusion_wins_including_hidden_overlay(self):
        self.scree[0, :] = 1
        self.reasons[0, :8] = [1, 2, 4, 8, 16, 32, 64, 128]
        self.slope[:] = 0
        count = self.count()
        self.assertEqual(count["visible_scree_source_cells"], 1)
        self.assertEqual(count["technical_excluded_cells"], 8)

    def test_nodata_nonfinite_and_negative_slopes_do_not_pass(self):
        self.scree[0, :5] = [1, 1, 1, 255, 1]
        self.slope[0, :5] = [np.nan, np.inf, -32768, 0, 91]
        self.assertEqual(self.count()["visible_scree_source_cells"], 0)

    def test_exact_boundary_and_clipped_last_bin(self):
        self.scree[8, 8] = 1
        self.slope[8, 8] = 10.0
        self.assertEqual(self.count()["scree_cells_within_existing_slope_policy"], 1)
        self.slope[8, 8] = 10.00001
        self.assertEqual(self.count()["scree_cells_within_existing_slope_policy"], 0)

    def test_overlap_and_unknown_class_fail_closed(self):
        self.scree[0, 0] = self.cliff[0, 0] = 1
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            self.count()
        self.cliff[:] = 0
        self.treatment[0, 0] = 7
        with self.assertRaisesRegex(ValueError, "Unknown treatment"):
            self.count()

    def test_same_inputs_are_repeatable_without_mutation(self):
        self.scree[4, 4] = 1
        before = self.scree.copy()
        self.assertEqual(self.count(), self.count())
        np.testing.assert_array_equal(self.scree, before)

    def test_pcgex_adapter_keeps_slope_decision_in_native_nodes(self):
        self.scree[4, 4:7] = 1
        self.slope[4, 4:7] = [42.0, 42.001, 90.0]
        records = world.pcgex_records(self.cliff, self.scree, self.reasons,
                                     self.slope, self.treatment, np.full((9, 9), 100.0))
        self.assertEqual([p[2] for p in records], [42.0, 42.001, 90.0])
        self.assertEqual(records[0][:2], [4, 4])
        self.assertEqual(records[0][3], 225.0)

    def test_pcgex_adapter_preserves_exclusions_and_last_cell_border(self):
        self.scree[4, 4] = self.scree[8, 8] = 1
        self.reasons[4, 4] = 32768
        records = world.pcgex_records(self.cliff, self.scree, self.reasons,
                                     self.slope, self.treatment, np.full((9, 9), 100.0))
        self.assertEqual(records, [[8, 8, 30.0, 25.0]])

    def test_invalid_clearance_does_not_reach_pcg(self):
        self.scree[4, 4] = 1
        for value in (np.nan, np.inf, -1):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "clearance"):
                world.pcgex_records(self.cliff, self.scree, self.reasons,
                                    self.slope, self.treatment, np.full((9, 9), value))

    def test_radius_covers_offset_mesh_pivot_and_tilt(self):
        self.assertAlmostEqual(world.rock_radius([
            {"bounds_cm": {"origin": [-3, 0, 4], "extent": [1, 3, 8]}}
        ]), 13.0)


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.command = {"session": "session-A", "request_id": "request-A", "sequence": 8}
        self.started = {"status": "STARTED_NO_RETRY", "request": self.command, "input": {"bytes": 7, "sha256": "a"}}
        self.result = {"status": "COMPLETED_VISUAL_ONLY", "request_id": "request-A", "sequence": 8,
                       "input": self.started["input"], "readback": {"recipe_revision": "r1",
                       "recipe": "rock_contact_scatter", "native_readback": {"operation_status": "CONTACT_JOB_RUNNING"}}}

    def test_ack_is_not_completion(self):
        value = world.receipt_readback(self.result, self.started, self.command, "r1")
        self.assertEqual(value["operation_status"], "CONTACT_JOB_RUNNING")

    def test_wrong_request_revision_or_input_rejected(self):
        for field, value in [("request_id", "other"), ("sequence", 9), ("input", {}), ("status", "FAILED_NO_RETRY")]:
            result = copy.deepcopy(self.result)
            result[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                world.receipt_readback(result, self.started, self.command, "r1")
        with self.assertRaisesRegex(ValueError, "revision"):
            world.receipt_readback(self.result, self.started, self.command, "other")

    def test_session_is_bound_by_actual_started_record(self):
        started = copy.deepcopy(self.started)
        started["request"]["session"] = "session-B"
        with self.assertRaisesRegex(ValueError, "command differs"):
            world.receipt_readback(self.result, started, self.command, "r1")

    def test_previous_evidence_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            world.write_new(path, {"old": True})
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                world.write_new(path, {"old": False})
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

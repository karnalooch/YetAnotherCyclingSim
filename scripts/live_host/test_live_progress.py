"""Public progress projection: identity, bounded counters and freshness."""

import copy
import unittest
from live_progress import project


class ProgressTest(unittest.TestCase):
    def setUp(self):
        self.request = {
            "session": "s",
            "recipe_revision": "r",
            "recipe": "rock_contact_scatter",
            "action": "run_recipe",
            "request_id": "id",
            "sequence": 7,
            "parameters": {"operation": "status", "manifest_sha256": "m"},
        }
        self.receipt = {
            "request_id": "id",
            "sequence": 7,
            "status": "COMPLETED_VISUAL_ONLY",
            "recorded_utc": "2026-10-13T12:00:00Z",
            "readback": {
                "recipe": "rock_contact_scatter",
                "recipe_revision": "r",
                "native_readback": {
                    "manifest_sha256": "m",
                    "operation_status": "CONTACT_JOB_RUNNING",
                    "phase": "VERIFY_CURRENT_NATIVE_GEOMETRY",
                    "native_geometry_triangle_ids_read": 150,
                    "native_geometry_triangle_ids_per_scan": 100,
                },
            },
        }

    def run_projection(self):
        return project(self.receipt, self.request, "s", "r", "m")

    def test_second_scan_cumulative_counts_preserved(self):
        row = self.run_projection()
        self.assertEqual(row["triangles_read"] - row["triangles_per_scan"], 50)

    def test_unknown_budget_remains_null(self):
        self.assertIsNone(self.run_projection()["maximum_grid_positions"])

    def test_identity_refused(self):
        for key in (
            "session",
            "recipe_revision",
            "recipe",
            "action",
            "request_id",
            "sequence",
        ):
            with self.subTest(key=key):
                saved = copy.deepcopy(self.request)
                self.request[key] = "wrong"
                with self.assertRaises(ValueError):
                    self.run_projection()
                self.request = saved

    def test_failure_sanitized(self):
        self.receipt["status"] = "FAILED_NO_RETRY"
        self.receipt["readback"] = {"error": "private path secret"}
        row = self.run_projection()
        self.assertTrue(row["error"])
        self.assertNotIn("secret", str(row))

    def test_no_refresh_of_native_timestamp(self):
        self.assertEqual(self.run_projection()["observed_utc"], "2026-10-13T12:00:00Z")

    def test_untrusted_counters_and_phase(self):
        job = self.receipt["readback"]["native_readback"]
        job.update(sampled_positions=True, phase="<script>", maximum_grid_positions=-1)
        row = self.run_projection()
        self.assertIsNone(row["sampled_positions"])
        self.assertIsNone(row["maximum_grid_positions"])
        self.assertEqual(row["phase"], "UNKNOWN")

    def test_spatial_and_contact_rejections_count(self):
        self.receipt["readback"]["native_readback"]["cases"] = [
            {"status": "REJECTED_NATIVE_SPATIAL_EXCLUSION"},
            {"decision": {"status": "REJECTED"}},
        ]
        self.assertEqual(self.run_projection()["rejected"], 2)

    def test_job_manifest_refused(self):
        self.receipt["readback"]["native_readback"]["manifest_sha256"] = "other"
        with self.assertRaises(ValueError):
            self.run_projection()


if __name__ == "__main__":
    unittest.main()

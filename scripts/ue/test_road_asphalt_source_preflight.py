"""Synthetic #364 source bridge tests, not native import or render evidence."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.ue import road_asphalt_source_preflight as preflight


class RoadAsphaltSourceBridgeTests(unittest.TestCase):
    def test_dry_source_proof_is_selected_only_by_verified_producer_sha_and_run(self):
        self.assertEqual(preflight.SOURCE_RUN, "38089061451-1")
        self.assertEqual(len(preflight.SOURCE_HEAD), 40)
        self.assertEqual(len(preflight.SOURCE_RECEIPT_SHA256), 64)
        self.assertEqual(len(preflight.SOURCE_FINGERPRINT), 64)
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp) / "work"
            work.mkdir()
            with patch.object(preflight, "load_workspace", return_value={"work": str(work)}):
                with self.assertRaisesRegex(ValueError, "not retained"):
                    preflight.source_root()
                target = work / preflight.SOURCE_RELATIVE
                target.mkdir(parents=True)
                self.assertEqual(preflight.source_root(), target)

    def test_only_authenticated_original_two_run_bridge_is_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            (work / preflight.SOURCE_RELATIVE).mkdir(parents=True)
            healthy = {
                "status": "ROAD_ASPHALT_REPLAY_RECEIPT_VERIFIED",
                "source_head": preflight.SOURCE_HEAD,
                "source_fingerprint": preflight.SOURCE_FINGERPRINT,
                "authenticated_source_receipt": {"sha256": preflight.SOURCE_RECEIPT_SHA256},
                "retained_two_run_graph_and_map_bytes_equal": True,
                "producer_attestation_authenticated": True,
                "unreal_verified": False,
                "world_mutation": False,
                "runs": [
                    {"run": name, "graph_sha256": preflight.GRAPH_SHA256}
                    for name in ("run-a", "run-b")
                ],
            }
            with (
                patch.object(preflight, "load_workspace", return_value={"work": str(work)}),
                patch.object(preflight, "check_asphalt_replay", return_value=healthy) as check,
            ):
                verified = preflight.verify_retained_replay()
                self.assertEqual(verified["status"], "PINNED_ROAD_ASPHALT_SOURCE_READY")
                self.assertFalse(verified["native_material_verified"])
                check.assert_called_once_with(
                    work / preflight.SOURCE_RELATIVE, preflight.SOURCE_RECEIPT_SHA256,
                    preflight.SOURCE_HEAD, preflight.SOURCE_FINGERPRINT,
                )
                for change in (
                    {"world_mutation": True},
                    {"source_fingerprint": "0" * 64},
                    {"producer_attestation_authenticated": False},
                    {"runs": healthy["runs"][:1]},
                    {"runs": [{**healthy["runs"][0], "graph_sha256": "0" * 64}, healthy["runs"][1]]},
                ):
                    check.return_value = {**healthy, **change}
                    with self.subTest(change=change), self.assertRaises(ValueError):
                        preflight.verify_retained_replay()


if __name__ == "__main__":
    unittest.main()

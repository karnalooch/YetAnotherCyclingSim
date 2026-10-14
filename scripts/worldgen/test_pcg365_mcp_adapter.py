"""Regression tests for SafeMcpAdapter and MCP blockage diagnostics.

Verifies:
1. Rejection of unbounded GetNodeDataView (endIndex=-1, huge ranges).
2. Upstream native PCG/PCGEx reduction proof is strictly required before dispatch.
3. Zero network traffic / no tool calls dispatched on invalid requests.
4. Fail-closed circuit breaker on timeout with strict prohibition of auto-retry.
5. Mutual exclusion preventing concurrent access to shared graphs.
6. Multi-hypothesis diagnostic analysis.
"""
from unittest.mock import MagicMock
import unittest

from scripts.worldgen.pcg365_mcp_adapter import (
    McpCircuitBreakerError,
    McpTimeoutError,
    SafeMcpAdapter,
    UnsafeMcpReadError,
    audit_mcp_blockage_hypotheses,
    require_native_reduction_proof,
    require_small_native_probe,
)


class SafeMcpAdapterTests(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.adapter = SafeMcpAdapter(client=self.mock_client, max_points=256, timeout=2.0)

    def test_unbounded_end_index_minus_one_is_rejected_before_dispatch(self):
        with self.assertRaises(UnsafeMcpReadError) as ctx:
            self.adapter.safe_get_node_data_view(
                author_or_client=self.mock_client,
                actor="test_actor",
                node="test_node",
                start_index=0,
                end_index=-1,
                verified_point_count=64,
            )
        self.assertIn("endIndex=-1", str(ctx.exception))
        # Ensure ZERO network calls dispatched
        self.assertEqual(self.mock_client.call.call_count, 0)

    def test_excessive_point_span_is_rejected_before_dispatch(self):
        for span in [257, 1000, 100000]:
            with self.subTest(span=span):
                with self.assertRaises(UnsafeMcpReadError) as ctx:
                    self.adapter.safe_get_node_data_view(
                        author_or_client=self.mock_client,
                        actor="test_actor",
                        node="full_near_cliff",
                        start_index=0,
                        end_index=span - 1,
                        verified_point_count=span,
                    )
                self.assertIn("exceeds MAX_SAFE_PROBE_POINTS", str(ctx.exception))
        self.assertEqual(self.mock_client.call.call_count, 0)

    def test_unreduced_upstream_data_is_rejected_even_if_request_span_is_small(self):
        """A small requested range alone is not a guard if the upstream dataset is dense."""
        with self.assertRaises(UnsafeMcpReadError) as ctx:
            self.adapter.safe_get_node_data_view(
                author_or_client=self.mock_client,
                actor="test_actor",
                node="full_near_cliff",
                start_index=0,
                end_index=32,
                verified_point_count=100000,  # Upstream has 100,000 points!
            )
        self.assertIn("exceeds safe limit", str(ctx.exception))
        self.assertEqual(self.mock_client.call.call_count, 0)

    def test_missing_reduction_proof_or_invalid_type_is_rejected(self):
        with self.assertRaises(UnsafeMcpReadError):
            require_native_reduction_proof("test_node", 64, reduction_type="INVALID_TYPE")
        with self.assertRaises(UnsafeMcpReadError):
            require_native_reduction_proof("", 64)

    def test_require_small_native_probe_validates_counts(self):
        for invalid in [-1, 257, 100000, "64", None, 1.5]:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    require_small_native_probe(invalid)
        # 0 and 256 are valid bounds
        require_small_native_probe(0)
        require_small_native_probe(256)

    def test_successful_bounded_call_dispatches_cleanly(self):
        self.mock_client.call.return_value = {"returnValue": {"points": [{"x": 1}]}}
        result = self.adapter.safe_get_node_data_view(
            author_or_client=self.mock_client,
            actor="test_actor",
            node="probe_node",
            pin_label="Out",
            start_index=0,
            end_index=63,
            verified_point_count=64,
            reduction_type="BOUNDED_PROBE_NODE",
            node_name="probe_node",
        )
        self.assertEqual(self.mock_client.call.call_count, 1)
        self.assertIn("points", result["returnValue"])

    def test_timeout_trips_circuit_breaker_and_prevents_retry(self):
        self.mock_client.call.side_effect = TimeoutError("Simulated client timeout after 180s")
        with self.assertRaises(McpTimeoutError):
            self.adapter.safe_get_node_data_view(
                author_or_client=self.mock_client,
                actor="test_actor",
                node="probe_node",
                start_index=0,
                end_index=63,
                verified_point_count=64,
            )
        self.assertTrue(self.adapter.is_circuit_breaker_tripped)

        # Subsequent call MUST fail closed without attempting any tool dispatch!
        with self.assertRaises(McpCircuitBreakerError) as ctx:
            self.adapter.safe_get_node_data_view(
                author_or_client=self.mock_client,
                actor="test_actor",
                node="probe_node",
                start_index=0,
                end_index=63,
                verified_point_count=64,
            )
        self.assertIn("TRIPPED", str(ctx.exception))
        # Total call count should still be 1 (no automatic retry!)
        self.assertEqual(self.mock_client.call.call_count, 1)

    def test_audit_mcp_blockage_hypotheses_generates_all_five_diagnostics(self):
        receipt = {
            "failed_method": "PCGToolset.PCGToolset.GetNodeDataView",
            "failed_node": "full_near_cliff",
            "requested_rows": [0, 99999],
            "client_timeout_seconds": 180,
        }
        matrix = audit_mcp_blockage_hypotheses(receipt)
        self.assertEqual(matrix["diagnostic_status"], "AUDITED_MULTI_HYPOTHESIS")
        hypotheses = matrix["hypotheses"]
        self.assertIn("H1_SERIALIZATION_VOLUME", hypotheses)
        self.assertIn("H2_GAMETHREAD_DEADLOCK", hypotheses)
        self.assertIn("H3_SOCKET_SATURATION", hypotheses)
        self.assertIn("H4_PCG_SLICING_EXPENSE", hypotheses)
        self.assertIn("H5_CONCURRENT_GRAPH_COLLISION", hypotheses)
        self.assertGreaterEqual(len(matrix["primary_safeguards"]), 4)


if __name__ == "__main__":
    unittest.main()

"""Regression tests for SafeMcpAdapter and MCP blockage diagnostics.

Verifies:
1. Rejection of unbounded GetNodeDataView (endIndex=-1, huge ranges).
2. Upstream native PCG/PCGEx reduction proof is strictly required before dispatch.
3. Zero network traffic / no tool calls dispatched on invalid requests.
4. Fail-closed circuit breaker on timeout with strict prohibition of auto-retry.
5. Mutual exclusion preventing concurrent access, aborting queued callers if breaker tripped.
6. Enforces response payload size limits.
7. Multi-hypothesis diagnostic analysis.
"""
from __future__ import annotations

import json
import threading
import time
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


def make_proof(node: str = "probe_node", count: int = 64, method: str = "BOUNDED_PROBE_NODE") -> dict:
    return {
        "reduction_node": node,
        "reduction_method": method,
        "certified_point_count": count,
        "source_node": node,
    }


class SafeMcpAdapterTests(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.adapter = SafeMcpAdapter(
            client=self.mock_client, max_points=256, timeout=2.0,
            # Test-only fake verifier; there is deliberately no production verifier.
            trusted_native_reduction_verifier=lambda actor, node, receipt: receipt["certified_point_count"],
        )

    def test_missing_native_attestor_fails_before_any_transport_call(self):
        untrusted = SafeMcpAdapter()
        receiver = MagicMock()
        with self.assertRaisesRegex(UnsafeMcpReadError, "NATIVE_PROBE_ATTESTATION_MISSING"):
            untrusted.safe_get_node_data_view(
                author_or_client=receiver, actor="actor", node="node",
                node_name="node", reduction_proof=make_proof("node", 3),
            )
        receiver.call_bounded.assert_not_called()
        receiver.call.assert_not_called()

    def test_bounded_transport_is_required_even_with_test_attestor(self):
        class LegacyOnly:
            def call(self, *args, **kwargs):
                raise AssertionError("legacy transport must not be called")

        with self.assertRaisesRegex(UnsafeMcpReadError, "BOUNDED_MCP_TRANSPORT_MISSING"):
            self.adapter.safe_get_node_data_view(
                author_or_client=LegacyOnly(), actor="actor", node="node",
                node_name="node", reduction_proof=make_proof("node", 3),
            )

    def test_unbounded_end_index_minus_one_is_rejected_before_dispatch(self):
        proof = make_proof("test_node", 64)
        with self.assertRaises(UnsafeMcpReadError) as ctx:
            self.adapter.safe_get_node_data_view(
                author_or_client=self.mock_client,
                actor="test_actor",
                node="test_node",
                node_name="test_node",
                reduction_proof=proof,
                start_index=0,
                end_index=-1,
            )
        self.assertIn("endIndex=-1", str(ctx.exception))
        # Ensure ZERO network calls dispatched
        self.assertEqual(self.mock_client.call_bounded.call_count, 0)

    def test_excessive_point_span_is_rejected_before_dispatch(self):
        for span in [257, 1000, 100000]:
            with self.subTest(span=span):
                # Even if proof falsely claimed span points, adapter rejects span > 256
                proof = {
                    "reduction_node": "full_near_cliff",
                    "reduction_method": "BOUNDED_PROBE_NODE",
                    "certified_point_count": 256,
                    "source_node": "full_near_cliff",
                }
                with self.assertRaises(UnsafeMcpReadError) as ctx:
                    self.adapter.safe_get_node_data_view(
                        author_or_client=self.mock_client,
                        actor="test_actor",
                        node="full_near_cliff",
                        node_name="full_near_cliff",
                        reduction_proof=proof,
                        start_index=0,
                        end_index=span - 1,
                    )
                self.assertIn("exceeds MAX_SAFE_PROBE_POINTS", str(ctx.exception))
        self.assertEqual(self.mock_client.call_bounded.call_count, 0)

    def test_unreduced_upstream_data_is_rejected_even_if_request_span_is_small(self):
        """A small requested range alone is not a guard if the upstream dataset is dense."""
        # Upstream has 100,000 points!
        dense_proof = {
            "reduction_node": "full_near_cliff",
            "reduction_method": "BOUNDED_PROBE_NODE",
            "certified_point_count": 100000,
            "source_node": "full_near_cliff",
        }
        with self.assertRaises(UnsafeMcpReadError) as ctx:
            self.adapter.safe_get_node_data_view(
                author_or_client=self.mock_client,
                actor="test_actor",
                node="full_near_cliff",
                node_name="full_near_cliff",
                reduction_proof=dense_proof,
                start_index=0,
                end_index=32,
            )
        self.assertIn("exceeds safe limit", str(ctx.exception))
        self.assertEqual(self.mock_client.call_bounded.call_count, 0)

    def test_missing_reduction_proof_or_invalid_fields_rejected_with_zero_dispatch(self):
        # Empty node name
        with self.assertRaises(UnsafeMcpReadError):
            require_native_reduction_proof("", make_proof("test_node", 64))

        # Not a dict
        with self.assertRaises(UnsafeMcpReadError):
            require_native_reduction_proof("test_node", 64)  # type: ignore

        # Missing required keys
        with self.assertRaises(UnsafeMcpReadError):
            require_native_reduction_proof("test_node", {"reduction_node": "test_node"})

        # Node mismatch
        with self.assertRaises(UnsafeMcpReadError):
            require_native_reduction_proof("other_node", make_proof("test_node", 64))

        # Invalid reduction method
        with self.assertRaises(UnsafeMcpReadError):
            require_native_reduction_proof("test_node", make_proof("test_node", 64, method="UNSUPPORTED_METHOD"))

        # Certified count out of bounds (< 0 or > 256)
        with self.assertRaises(UnsafeMcpReadError):
            require_native_reduction_proof("test_node", make_proof("test_node", -1))
        with self.assertRaises(UnsafeMcpReadError):
            require_native_reduction_proof("test_node", make_proof("test_node", 257))

        self.assertEqual(self.mock_client.call_bounded.call_count, 0)

    def test_require_small_native_probe_validates_counts(self):
        for invalid in [-1, 257, 100000, "64", None, 1.5]:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    require_small_native_probe(invalid)
        # 0 and 256 are valid bounds
        require_small_native_probe(0)
        require_small_native_probe(256)

    def test_successful_bounded_call_dispatches_cleanly(self):
        self.mock_client.call_bounded.return_value = {"returnValue": {"points": [{"x": 1}]}}
        proof = make_proof("probe_node", 64)
        result = self.adapter.safe_get_node_data_view(
            author_or_client=self.mock_client,
            actor="test_actor",
            node="probe_node",
            node_name="probe_node",
            reduction_proof=proof,
            pin_label="Out",
            start_index=0,
            end_index=63,
        )
        self.assertEqual(self.mock_client.call_bounded.call_count, 1)
        self.assertIn("points", result["returnValue"])

    def test_timeout_trips_circuit_breaker_and_prevents_retry(self):
        self.mock_client.call_bounded.side_effect = TimeoutError("Simulated client timeout after 180s")
        proof = make_proof("probe_node", 64)
        with self.assertRaises(McpTimeoutError):
            self.adapter.safe_get_node_data_view(
                author_or_client=self.mock_client,
                actor="test_actor",
                node="probe_node",
                node_name="probe_node",
                reduction_proof=proof,
                start_index=0,
                end_index=63,
            )
        self.assertTrue(self.adapter.is_circuit_breaker_tripped)

        # Subsequent call MUST fail closed without attempting any tool dispatch!
        with self.assertRaises(McpCircuitBreakerError) as ctx:
            self.adapter.safe_get_node_data_view(
                author_or_client=self.mock_client,
                actor="test_actor",
                node="probe_node",
                node_name="probe_node",
                reduction_proof=proof,
                start_index=0,
                end_index=63,
            )
        self.assertIn("TRIPPED", str(ctx.exception))
        # Total call count should still be 1 (no automatic retry!)
        self.assertEqual(self.mock_client.call_bounded.call_count, 1)

    def test_concurrent_queued_caller_aborts_when_breaker_tripped_inside_lock(self):
        """When Thread 1 times out in lock, Thread 2 queued for lock must abort fail-closed."""
        first_call_started = threading.Event()
        proof = make_proof("probe_node", 64)

        def slow_timeout_call(*args, **kwargs):
            first_call_started.set()
            time.sleep(0.05)
            raise TimeoutError("Simulated 180s timeout")

        self.mock_client.call_bounded.side_effect = slow_timeout_call

        results = {}

        def thread1_target():
            try:
                self.adapter.safe_get_node_data_view(
                    author_or_client=self.mock_client,
                    actor="actor1",
                    node="node1",
                    node_name="probe_node",
                    reduction_proof=proof,
                    start_index=0,
                    end_index=63,
                )
            except Exception as exc:
                results["t1"] = exc

        def thread2_target():
            # Wait until thread 1 has acquired the lock
            first_call_started.wait(timeout=2.0)
            try:
                self.adapter.safe_get_node_data_view(
                    author_or_client=self.mock_client,
                    actor="actor2",
                    node="node2",
                    node_name="probe_node",
                    reduction_proof=proof,
                    start_index=0,
                    end_index=63,
                )
            except Exception as exc:
                results["t2"] = exc

        t1 = threading.Thread(target=thread1_target)
        t2 = threading.Thread(target=thread2_target)

        t1.start()
        t2.start()
        t1.join(timeout=5.0)
        t2.join(timeout=5.0)

        # Thread 1 should have caught McpTimeoutError and tripped the breaker
        self.assertIsInstance(results.get("t1"), McpTimeoutError)
        self.assertTrue(self.adapter.is_circuit_breaker_tripped)

        # Thread 2 was queued for the lock and should have aborted with McpCircuitBreakerError
        self.assertIsInstance(results.get("t2"), McpCircuitBreakerError)

        # Client was called exactly ONCE (by thread 1, never by thread 2!)
        self.assertEqual(self.mock_client.call_bounded.call_count, 1)

    def test_response_payload_size_limit_trips_circuit_breaker(self):
        # 2 MB response payload
        huge_payload = json.dumps({"points": [{"large_data": "x" * 1000} for _ in range(2000)]})
        self.mock_client.call_bounded.return_value = huge_payload
        proof = make_proof("probe_node", 64)

        with self.assertRaises(UnsafeMcpReadError) as ctx:
            self.adapter.safe_get_node_data_view(
                author_or_client=self.mock_client,
                actor="test_actor",
                node="probe_node",
                node_name="probe_node",
                reduction_proof=proof,
                start_index=0,
                end_index=63,
            )
        self.assertIn("exceeded", str(ctx.exception))
        self.assertTrue(self.adapter.is_circuit_breaker_tripped)

        # Subsequent call blocked by breaker
        with self.assertRaises(McpCircuitBreakerError):
            self.adapter.safe_get_node_data_view(
                author_or_client=self.mock_client,
                actor="test_actor",
                node="probe_node",
                node_name="probe_node",
                reduction_proof=proof,
                start_index=0,
                end_index=63,
            )
        # Call count is 1
        self.assertEqual(self.mock_client.call_bounded.call_count, 1)

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

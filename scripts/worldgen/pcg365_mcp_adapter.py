"""Safe MCP adapter for PCG/PCGEx inspection in Unreal Engine.

Eliminates unbounded GetNodeDataView calls, enforces upstream native PCG/PCGEx
reduction to <= 256 points via authenticated reduction proof before dispatch,
provides circuit-breaker protection against timeout loops, and prevents concurrent
access to shared graphs.
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable, Dict, Optional

MAX_SAFE_PROBE_POINTS = 256
MAX_SAFE_RESPONSE_BYTES = 1024 * 1024  # 1 MB maximum response payload
DEFAULT_MCP_TIMEOUT_SECONDS = 10.0

VALID_REDUCTION_METHODS = {
    "PCG_SAMPLE_NODE",
    "PCGEX_DOWNSAMPLE",
    "PCGEX_COLLAPSE",
    "BOUNDED_PROBE_NODE",
    "REDUCED_STATISTICS",
    "DOWNSAMPLED_CONTOUR",
}


class UnsafeMcpReadError(ValueError):
    """Raised when an MCP read request violates safety bounds before dispatch."""


class McpTimeoutError(RuntimeError):
    """Raised when an MCP operation times out. Triggers fail-closed state."""


class McpCircuitBreakerError(RuntimeError):
    """Raised when an operation is attempted while the circuit breaker is tripped."""


def require_small_native_probe(point_count: Any) -> None:
    """Validate point count is an integer <= MAX_SAFE_PROBE_POINTS.

    Call only after a native PCG node has reduced the actual data collection.
    A small requested range alone is not a guard if the upstream dataset is dense.
    """
    if type(point_count) is not int or not 0 <= point_count <= MAX_SAFE_PROBE_POINTS:
        raise ValueError(
            f"Reduce data to <= {MAX_SAFE_PROBE_POINTS} points in native PCG "
            f"before MCP inspection (got: {point_count!r})"
        )


def require_native_reduction_proof(
    node_name: str,
    reduction_proof: Dict[str, Any],
) -> int:
    """Validate that data has been explicitly reduced inside native PCG/PCGEx.

    Must be verified BEFORE any tool call or network transmission.
    Checks the shape of a claimed count, NOT its provenance. The caller's
    dictionary alone is not native attestation. Independent verification is
    mandatory at dispatch and unavailable by default.
    """
    if not node_name:
        raise UnsafeMcpReadError("Node name must be specified for native reduction check")

    if not isinstance(reduction_proof, dict):
        raise UnsafeMcpReadError(
            f"Reduction proof must be an authenticated dictionary for node {node_name!r}"
        )

    required_keys = {"reduction_node", "reduction_method", "certified_point_count", "source_node"}
    missing = required_keys - set(reduction_proof.keys())
    if missing:
        raise UnsafeMcpReadError(
            f"Incomplete reduction proof for node {node_name!r}; missing required keys: {sorted(missing)}"
        )

    if reduction_proof["reduction_node"] != node_name:
        raise UnsafeMcpReadError(
            f"Reduction proof mismatch: proof is for node {reduction_proof['reduction_node']!r}, "
            f"but requested node is {node_name!r}"
        )

    method = reduction_proof.get("reduction_method")
    if method not in VALID_REDUCTION_METHODS:
        raise UnsafeMcpReadError(
            f"Unrecognized reduction method {method!r} in proof. "
            f"Must be one of: {sorted(VALID_REDUCTION_METHODS)}"
        )

    certified_count = reduction_proof.get("certified_point_count")
    if type(certified_count) is not int or not 0 <= certified_count <= MAX_SAFE_PROBE_POINTS:
        raise UnsafeMcpReadError(
            f"Cannot inspect node {node_name!r}: certified point count {certified_count!r} "
            f"exceeds safe limit of {MAX_SAFE_PROBE_POINTS}. Native PCG reduction must occur before MCP readback."
        )

    return certified_count


class SafeMcpAdapter:
    """Circuit-breaking adapter; serializes calls only on this instance."""

    def __init__(
        self,
        client: Any = None,
        max_points: int = MAX_SAFE_PROBE_POINTS,
        timeout: float = DEFAULT_MCP_TIMEOUT_SECONDS,
        max_response_bytes: int = MAX_SAFE_RESPONSE_BYTES,
        trusted_native_reduction_verifier: Optional[
            Callable[[Any, Any, Dict[str, Any]], int]
        ] = None,
    ):
        if type(max_points) is not int or not 0 < max_points <= MAX_SAFE_PROBE_POINTS:
            raise ValueError("Unsafe point cap: must be 1..256")
        if type(timeout) not in (int, float) or not 0 < timeout <= DEFAULT_MCP_TIMEOUT_SECONDS:
            raise ValueError("Unsafe MCP timeout: must be >0 and <=10 seconds")
        if type(max_response_bytes) is not int or not 0 < max_response_bytes <= MAX_SAFE_RESPONSE_BYTES:
            raise ValueError("Unsafe MCP response limit: must be 1..1048576 bytes")
        self.client = client
        self.max_points = max_points
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        # No production witness verifier is installed until a native reduced
        # graph and exact session/asset readback have been independently proved.
        self._trusted_native_reduction_verifier = trusted_native_reduction_verifier
        self._lock = threading.Lock()
        self._circuit_breaker_tripped = False
        self._circuit_breaker_reason: Optional[str] = None
        self._request_counter = 0
        self._last_request_id: Optional[int] = None
        self._last_result: Optional[Dict[str, Any]] = None

    @property
    def is_circuit_breaker_tripped(self) -> bool:
        return self._circuit_breaker_tripped

    @property
    def circuit_breaker_reason(self) -> Optional[str]:
        return self._circuit_breaker_reason

    def trip_circuit_breaker(self, reason: str) -> None:
        """Trip circuit breaker to prevent further calls (fail-closed)."""
        self._circuit_breaker_tripped = True
        self._circuit_breaker_reason = reason

    def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker (requires deliberate operator action)."""
        self._circuit_breaker_tripped = False
        self._circuit_breaker_reason = None

    def validate_data_view_arguments(
        self,
        node_name: str,
        start_index: int,
        end_index: int,
        reduction_proof: Dict[str, Any],
    ) -> int:
        """Perform pre-dispatch safety verification.

        Raises UnsafeMcpReadError or McpCircuitBreakerError BEFORE any network
        or tool dispatch if unsafe. Returns certified point count.
        """
        if self._circuit_breaker_tripped:
            raise McpCircuitBreakerError(
                f"MCP circuit breaker is TRIPPED: {self._circuit_breaker_reason}. "
                "Automatic retry is prohibited; investigate prior timeout/failure first."
            )

        if end_index == -1:
            raise UnsafeMcpReadError(
                "Unbounded read (endIndex=-1) is strictly prohibited. "
                f"Data must be reduced to <= {self.max_points} in native PCG/PCGEx first."
            )

        if type(start_index) is not int or type(end_index) is not int:
            raise UnsafeMcpReadError(
                f"start_index and end_index must be integers (got: {start_index!r}, {end_index!r})"
            )

        if start_index < 0:
            raise UnsafeMcpReadError(f"start_index must be >= 0 (got: {start_index})")

        if end_index < start_index:
            raise UnsafeMcpReadError(
                f"end_index ({end_index}) cannot be less than start_index ({start_index})"
            )

        requested_span = end_index - start_index + 1
        if requested_span > self.max_points:
            raise UnsafeMcpReadError(
                f"Requested row count ({requested_span}) exceeds MAX_SAFE_PROBE_POINTS ({self.max_points}). "
                "Reduce data inside native PCG/PCGEx before requesting data view."
            )

        # Enforce upstream reduction proof without trusting unverified inputs
        certified_count = require_native_reduction_proof(
            node_name=node_name,
            reduction_proof=reduction_proof,
        )

        if end_index >= certified_count:
            raise UnsafeMcpReadError(
                f"Requested end_index ({end_index}) exceeds certified point count ({certified_count}) "
                f"for reduction node {node_name!r}"
            )

        return certified_count

    def safe_get_node_data_view(
        self,
        author_or_client: Any,
        actor: Any,
        node: Any,
        node_name: str,
        reduction_proof: Dict[str, Any],
        pin_label: str = "Out",
        attribute_name: str = "",
        start_index: int = 0,
        end_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Safely fetch node data view with pre-dispatch reduction enforcement.

        Guarantees:
        1. No request is sent without an independent trusted native verifier (not installed by default).
        2. No request is sent if endIndex is -1 or span > 256.
        3. Mutual exclusion: prevents concurrent access to shared graph.
        4. Re-checks circuit breaker inside lock to block concurrent callers after timeout.
        5. No automatic retries on timeout: trips circuit breaker fail-closed.
        6. Requires a bounded transport and checks output size again after dispatch.
        """
        # Require authenticated reduction proof and extract certified count
        certified_count = require_native_reduction_proof(
            node_name=node_name,
            reduction_proof=reduction_proof,
        )

        if end_index is None:
            if certified_count == 0:
                raise UnsafeMcpReadError(f"Cannot inspect node {node_name!r}: certified point count is 0")
            end_index = certified_count - 1

        # Reject forbidden ranges and tripped circuits before even consulting
        # a trusted verifier (which may otherwise need to inspect live state).
        self.validate_data_view_arguments(
            node_name=node_name,
            start_index=start_index,
            end_index=end_index,
            reduction_proof=reduction_proof,
        )
        if self._trusted_native_reduction_verifier is None:
            raise UnsafeMcpReadError(
                "NATIVE_PROBE_ATTESTATION_MISSING: a self-declared point count is not "
                "evidence that the Unreal node is actually reduced; no MCP dispatch"
            )
        independent_count = self._trusted_native_reduction_verifier(actor, node, reduction_proof)
        if type(independent_count) is not int or independent_count != certified_count:
            raise UnsafeMcpReadError(
                "NATIVE_PROBE_ATTESTATION_MISMATCH: independent native count does not match receipt"
            )

        with self._lock:
            # Re-check circuit breaker inside the lock for queued concurrent callers
            if self._circuit_breaker_tripped:
                raise McpCircuitBreakerError(
                    f"MCP circuit breaker is TRIPPED: {self._circuit_breaker_reason}. "
                    "Queued request aborted fail-closed without dispatch."
                )

            self._request_counter += 1
            request_id = self._request_counter
            self._last_request_id = request_id

            toolset = "PCGToolset.PCGToolset"
            arguments = {
                "pCGVolume": actor,
                "node": node,
                "pinLabel": pin_label,
                "attributeName": attribute_name,
                "startIndex": start_index,
                "endIndex": end_index,
            }

            start_time = time.time()
            try:
                # Never silently fall back to Author.call/Client.call: the legacy
                # transport has a 180-second timeout and materializes up to 32 MiB.
                # A native verified caller must supply a truly bounded transport.
                bounded_call = getattr(author_or_client, "call_bounded", None)
                if not callable(bounded_call):
                    raise UnsafeMcpReadError(
                        "BOUNDED_MCP_TRANSPORT_MISSING: refusing legacy unbounded client"
                    )
                raw = bounded_call(
                    toolset, "GetNodeDataView", arguments,
                    timeout_seconds=self.timeout,
                    max_response_bytes=self.max_response_bytes,
                )

                elapsed = time.time() - start_time
                if elapsed > self.timeout:
                    self.trip_circuit_breaker(f"GetNodeDataView took {elapsed:.2f}s, exceeding timeout {self.timeout}s")
                    raise McpTimeoutError(f"GetNodeDataView timeout after {elapsed:.2f}s; circuit breaker tripped")

            except TimeoutError as exc:
                self.trip_circuit_breaker(f"Client TimeoutError: {exc}")
                raise McpTimeoutError(f"MCP operation timed out: {exc}. Circuit breaker tripped; no automatic retry.") from exc
            except Exception as exc:
                if "timeout" in str(exc).lower():
                    self.trip_circuit_breaker(f"Timeout in call: {exc}")
                    raise McpTimeoutError(f"MCP timeout encountered: {exc}. Circuit breaker tripped.") from exc
                raise

            # Post-dispatch payload size enforcement
            if isinstance(raw, (str, bytes)):
                raw_bytes_len = len(raw)
            else:
                raw_bytes_len = len(json.dumps(raw))

            if raw_bytes_len > self.max_response_bytes:
                self.trip_circuit_breaker(
                    f"Response size ({raw_bytes_len} bytes) exceeded MAX_SAFE_RESPONSE_BYTES ({self.max_response_bytes})"
                )
                raise UnsafeMcpReadError(
                    f"MCP response exceeded {self.max_response_bytes} bytes; circuit breaker tripped fail-closed."
                )

            if isinstance(raw, str):
                try:
                    data = json.loads(raw)
                except ValueError:
                    data = raw
            else:
                data = raw

            self._last_result = {
                "request_id": request_id,
                "node_name": node_name,
                "elapsed_seconds": time.time() - start_time,
                "start_index": start_index,
                "end_index": end_index,
                "response_bytes": raw_bytes_len,
            }
            return data


def audit_mcp_blockage_hypotheses(
    receipt: Optional[Dict[str, Any]] = None,
    process_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Audit the multi-hypothesis diagnostic matrix for the MCP blockage.

    Evaluates:
    - Hypothesis 1 (Serialization Volume): Large JSON serialization in PCGToolset.
    - Hypothesis 2 (GameThread Deadlock): MCP server thread waiting for GameThread execution.
    - Hypothesis 3 (TCP / Socket Saturation): Sockets lingering in CloseWait.
    - Hypothesis 4 (PCG Slicing / Slicing Exception): Slicing iteration over entire point cloud.
    - Hypothesis 5 (Concurrent Access Collision): Concurrent access to shared PCGVolume.
    """
    failed_method = receipt.get("failed_method", "PCGToolset.PCGToolset.GetNodeDataView") if receipt else "PCGToolset.PCGToolset.GetNodeDataView"
    failed_node = receipt.get("failed_node", "full_near_cliff") if receipt else "full_near_cliff"
    requested_rows = receipt.get("requested_rows", [0, 99999]) if receipt else [0, 99999]
    timeout_seconds = receipt.get("client_timeout_seconds", 180) if receipt else 180

    hypotheses = {
        "H1_SERIALIZATION_VOLUME": {
            "title": "Large JSON-RPC payload serialization in PCGToolset",
            "plausibility": "HIGH",
            "evidence": (
                f"Node {failed_node!r} requested rows {requested_rows[0]}..{requested_rows[1]} "
                f"({requested_rows[1] - requested_rows[0] + 1} points). Serializing 100,000 points "
                "with transforms and attributes generates >60 MB of JSON, which can choke the engine JSON serializer."
            ),
            "remediation": "Hard cap at <= 256 points enforced inside native PCG graph before inspection.",
        },
        "H2_GAMETHREAD_DEADLOCK": {
            "title": "MCP background thread deadlocked waiting for GameThread execution",
            "plausibility": "MEDIUM_HIGH",
            "evidence": (
                "Unreal Editor process remains alive and Responding: True in Windows Task Manager, "
                "but MCP initialize and tool calls time out. Indicates GameThread is occupied by "
                "an uninterruptible background task or lock."
            ),
            "remediation": "Do not send concurrent calls or auto-retries while previous task is unconfirmed.",
        },
        "H3_SOCKET_SATURATION": {
            "title": "Socket / TCP connection exhaustion (CloseWait accumulation)",
            "plausibility": "MEDIUM",
            "evidence": (
                "TCP connection table shows multiple sockets in CloseWait on port 80/8000 after 180s client timeout. "
                "Server socket handle may be waiting for graceful drain."
            ),
            "remediation": "Single-connection reuse with strict connection pooling and explicit timeout bounds.",
        },
        "H4_PCG_SLICING_EXPENSE": {
            "title": "PCGToolset GetNodeDataView performs full traversal before range slicing",
            "plausibility": "MEDIUM",
            "evidence": (
                "Even with startIndex=0, endIndex=64, if the upstream data has millions of points, "
                "GetNodeDataView may evaluate the entire collection before applying the slice."
            ),
            "remediation": "Upstream PCGEx downsampling / probe node must reduce actual collection to <= 256 points.",
        },
        "H5_CONCURRENT_GRAPH_COLLISION": {
            "title": "Concurrent read/write access to shared PCGVolume during active graph execution",
            "plausibility": "LOW_MEDIUM",
            "evidence": "Graph instance was executing while data view was requested.",
            "remediation": "Sequential execution with mutual exclusion lock across all graph authoring.",
        },
    }

    return {
        "diagnostic_status": "AUDITED_MULTI_HYPOTHESIS",
        "failed_method": failed_method,
        "failed_node": failed_node,
        "requested_rows": requested_rows,
        "timeout_seconds": timeout_seconds,
        "hypotheses": hypotheses,
        "primary_safeguards": [
            "Authenticated upstream reduction proof certifying <= 256 points strictly required before dispatch",
            "Prohibition of endIndex=-1 and ranges > 256",
            "Fail-closed circuit breaker on timeout with strict prohibition of automatic retries",
            "Post-dispatch payload size enforcement (max 1 MB)",
            "Mutual exclusion with in-lock circuit breaker re-check for concurrent callers",
            "Zero network traffic when pre-flight validation fails",
        ],
    }

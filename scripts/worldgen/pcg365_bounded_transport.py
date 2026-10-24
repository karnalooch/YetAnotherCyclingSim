"""Strict loopback HTTP/MCP transport for *read-only* PCG365 node probes.

Separate from pcg365_pcgex_graph.Client (180 s / 32 MiB), which is never
consulted by this class. This transport does not certify a native reduction:
SafeMcpAdapter must obtain an independent node witness before calling it.
"""

from __future__ import annotations

import http.client
import json
import re
import socket
import threading
import time
from typing import Any

HOST = "127.0.0.1"
PORT = 8000
PATH = "/mcp"
PROTOCOL = "2025-06-18"
MAX_TIMEOUT_SECONDS = 10.0
MAX_RESPONSE_BYTES = 1024 * 1024
INITIALIZE_BYTES = 64 * 1024


class BoundedMcpTransportError(RuntimeError):
    """A terminal framing, protocol or transport failure; never retry."""


class BoundedPcgMcpClient:
    """An independent, serial JSON-only MCP client with a hard request deadline.

    Uses a fresh connection per HTTP request and a watchdog that shuts down the
    socket at the absolute deadline. A response is *never* read past the byte cap,
    regardless of Content-Length or transfer encoding. A protocol/transport
    failure poisons this instance; an operator must start a new session.
    """

    def __init__(self) -> None:
        self._session_id: str | None = None
        self._initialized = False
        self._poisoned = False
        self._sequence = 0
        self._lock = threading.RLock()

    @property
    def is_poisoned(self) -> bool:
        return self._poisoned

    def _post(
        self, body: dict[str, Any], deadline: float, cap: int
    ) -> tuple[dict[str, Any] | None, str | None]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Bounded PCG MCP deadline already elapsed")
        raw_request = json.dumps(body, separators=(",", ":"), allow_nan=False).encode(
            "utf-8"
        )
        if len(raw_request) > MAX_RESPONSE_BYTES:
            raise BoundedMcpTransportError("MCP request exceeds 1 MiB")
        conn = http.client.HTTPConnection(HOST, PORT, timeout=remaining)
        expired = threading.Event()
        active_socket: socket.socket | None = None

        def abort_socket() -> None:
            expired.set()
            # HTTPConnection.getresponse() drops conn.sock when the peer sets
            # Connection: close; retain our own handle to interrupt its body read.
            sock = active_socket if active_socket is not None else conn.sock
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            conn.close()

        watchdog = threading.Timer(remaining, abort_socket)
        watchdog.daemon = True
        watchdog.start()
        try:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Connection": "close",
                "Accept-Encoding": "identity",
            }
            if self._session_id is not None:
                headers["Mcp-Session-Id"] = self._session_id
                headers["Mcp-Protocol-Version"] = PROTOCOL
            conn.request("POST", PATH, body=raw_request, headers=headers)
            active_socket = conn.sock
            response = conn.getresponse()
            received: dict[str, str] = {}
            guarded = {
                "content-type",
                "content-length",
                "content-encoding",
                "transfer-encoding",
                "mcp-session-id",
                "mcp-protocol-version",
            }
            for key, value in response.getheaders():
                key = key.casefold()
                if key in guarded:
                    if key in received:
                        raise BoundedMcpTransportError(
                            "Duplicate MCP response header: " + key
                        )
                    received[key] = value

            length = received.get("content-length")
            if length is not None and (
                re.fullmatch(r"[0-9]+", length) is None or int(length) > cap
            ):
                raise BoundedMcpTransportError(
                    "MCP Content-Length exceeds bound or is invalid"
                )
            transfer = received.get("transfer-encoding")
            if transfer is not None and (
                length is not None or transfer.lower() != "chunked"
            ):
                raise BoundedMcpTransportError(
                    "Ambiguous or unsupported HTTP body framing"
                )
            if received.get("content-encoding", "identity").lower() != "identity":
                raise BoundedMcpTransportError("Compressed MCP response is forbidden")

            notification = "id" not in body
            content_type = (
                received.get("content-type", "").split(";", 1)[0].strip().lower()
            )
            if notification:
                if response.status != 202:
                    raise BoundedMcpTransportError(
                        "MCP notification returned non-202 status"
                    )
            elif response.status != 200 or content_type != "application/json":
                raise BoundedMcpTransportError(
                    "MCP response status/content-type differs"
                )

            # HTTPResponse.read(n) consumes at most n decoded payload bytes.
            # The watchdog enforces an *absolute* deadline even for slow trickles.
            if conn.sock is not None:
                conn.sock.settimeout(max(0.001, deadline - time.monotonic()))
            payload = response.read(cap + 1)
            if len(payload) > cap or (
                length is not None and len(payload) != int(length)
            ):
                raise BoundedMcpTransportError("MCP response exceeds byte bound")
            if received.get("mcp-protocol-version", PROTOCOL) != PROTOCOL:
                raise BoundedMcpTransportError("MCP protocol version changed")
            session_id = received.get("mcp-session-id")
            if self._session_id is not None and session_id not in (
                None,
                self._session_id,
            ):
                raise BoundedMcpTransportError("MCP session identity changed")
            if expired.is_set() or time.monotonic() >= deadline:
                raise TimeoutError("Bounded PCG MCP hard deadline exceeded")
            if notification:
                if payload:
                    raise BoundedMcpTransportError(
                        "MCP notification response must be empty"
                    )
                return None, session_id

            try:
                obj = json.loads(payload)
            except (ValueError, UnicodeDecodeError) as exc:
                raise BoundedMcpTransportError("MCP returned invalid JSON") from exc
            if not isinstance(obj, dict) or obj.get("jsonrpc") != "2.0":
                raise BoundedMcpTransportError("MCP returned invalid JSON-RPC envelope")
            if type(obj.get("id")) is not int or obj["id"] != body["id"]:
                raise BoundedMcpTransportError("MCP JSON-RPC request ID differs")
            if "error" in obj or "result" not in obj:
                raise BoundedMcpTransportError("MCP returned error/missing result")
            return obj, session_id
        except (socket.timeout, OSError, http.client.HTTPException) as exc:
            if expired.is_set() or time.monotonic() >= deadline:
                raise TimeoutError("Bounded PCG MCP hard deadline exceeded") from exc
            raise BoundedMcpTransportError("MCP transport failed (no retry)") from exc
        finally:
            watchdog.cancel()
            conn.close()

    def _rpc(
        self,
        method: str,
        params: dict[str, Any] | None,
        deadline: float,
        cap: int,
        notification: bool = False,
    ) -> tuple[dict[str, Any] | None, str | None]:
        body: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not notification:
            self._sequence += 1
            body["id"] = self._sequence
        return self._post(body, deadline, cap)

    def _initialize(self, deadline: float) -> None:
        if self._initialized:
            return
        result, session = self._rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL,
                "capabilities": {},
                "clientInfo": {"name": "YACS-PCG365-Bounded-Probe", "version": "1"},
            },
            deadline,
            INITIALIZE_BYTES,
        )
        negotiated = result["result"]
        if (
            not isinstance(negotiated, dict)
            or negotiated.get("protocolVersion") != PROTOCOL
            or not isinstance(negotiated.get("capabilities"), dict)
            or not isinstance(session, str)
            or not 1 <= len(session) <= 128
            or re.fullmatch(r"[A-Za-z0-9_-]+", session) is None
        ):
            raise BoundedMcpTransportError(
                "MCP initialization/session is not authentic"
            )
        self._session_id = session
        self._rpc(
            "notifications/initialized",
            None,
            deadline,
            INITIALIZE_BYTES,
            notification=True,
        )
        self._initialized = True

    def call_bounded(
        self,
        toolset: str,
        name: str,
        arguments: dict[str, Any],
        *,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> Any:
        """Read one already-certified reduced node (no graph writes, no fallback)."""
        allowed_toolsets = {
            "PCGToolset.PCGToolset",
            "YacsPcgWitness.YacsPcgWitnessToolset",
            "YacsPcgWitnessToolset",
        }
        if toolset not in allowed_toolsets:
            raise ValueError(
                f"PCG365 bounded client permits only PCGToolset or YacsPcgWitnessToolset (got: {toolset!r})"
            )
        if toolset == "PCGToolset.PCGToolset":
            if name != "GetNodeDataView":
                raise ValueError(
                    "PCG365 bounded client permits only GetNodeDataView for PCGToolset"
                )
        elif name != "InspectReducedNodeOutput":
            raise ValueError(
                f"PCG365 bounded client permits only InspectReducedNodeOutput for {toolset!r}"
            )
        if (
            type(timeout_seconds) not in (float, int)
            or not 0 < timeout_seconds <= MAX_TIMEOUT_SECONDS
        ):
            raise ValueError("MCP probe timeout outside 0..10 seconds")
        if (
            type(max_response_bytes) is not int
            or not 0 < max_response_bytes <= MAX_RESPONSE_BYTES
        ):
            raise ValueError("MCP response cap outside 1..1048576 bytes")

        call_args: dict[str, Any]
        if name == "GetNodeDataView":
            if not isinstance(arguments, dict) or set(arguments) != {
                "pCGVolume",
                "node",
                "pinLabel",
                "attributeName",
                "startIndex",
                "endIndex",
            }:
                raise ValueError(
                    "MCP data view arguments do not match the fixed contract"
                )
            if not all(
                isinstance(arguments[key], dict)
                and isinstance(arguments[key].get("refPath"), str)
                and arguments[key]["refPath"].startswith("/")
                for key in ("pCGVolume", "node")
            ):
                raise ValueError(
                    "MCP probe actor/node requires native object references"
                )
            start, end = arguments["startIndex"], arguments["endIndex"]
            if (
                type(start) is not int
                or type(end) is not int
                or start < 0
                or end <= start
                or end > 256
                or end - start > 256
            ):
                raise ValueError(
                    "MCP probe indices exceed native reduced-data safety cap"
                )
            if (
                not isinstance(arguments["pinLabel"], str)
                or not 1 <= len(arguments["pinLabel"]) <= 64
                or not isinstance(arguments["attributeName"], str)
                or len(arguments["attributeName"]) > 128
            ):
                raise ValueError("MCP probe pin/attribute differs from fixed schema")
            call_args = arguments
        elif name == "InspectReducedNodeOutput":
            if not isinstance(arguments, dict):
                raise ValueError("MCP witness arguments must be a dictionary")
            actor = (
                arguments.get("inActorPath")
                or arguments.get("actor_path")
                or arguments.get("InActorPath")
            )
            graph = (
                arguments.get("inGraphPath")
                or arguments.get("graph_path")
                or arguments.get("InGraphPath")
            )
            source = (
                arguments.get("inSourceNodePath")
                or arguments.get("source_node_path")
                or arguments.get("InSourceNodePath")
            )
            reduction = (
                arguments.get("inReductionNodePath")
                or arguments.get("reduction_node_path")
                or arguments.get("InReductionNodePath")
            )
            red_cls = (
                arguments.get("inReductionClass")
                or arguments.get("reduction_class")
                or arguments.get("InReductionClass")
            )
            pin = (
                arguments.get("inOutputPin")
                or arguments.get("output_pin")
                or arguments.get("InOutputPin")
                or "Out"
            )
            max_pts = (
                arguments.get("maxAllowedPoints")
                if "maxAllowedPoints" in arguments
                else arguments.get("max_allowed_points", 256)
            )

            for key, val in (
                ("actor_path", actor),
                ("graph_path", graph),
                ("source_node_path", source),
                ("reduction_node_path", reduction),
            ):
                if not isinstance(val, str) or not val.startswith("/"):
                    raise ValueError(
                        f"MCP witness argument {key} requires absolute Unreal object path (got: {val!r})"
                    )
            if (
                not isinstance(red_cls, str)
                or not red_cls.endswith("Settings")
                or len(red_cls) > 128
            ):
                raise ValueError(
                    f"MCP witness argument reduction_class must end with 'Settings' (got: {red_cls!r})"
                )
            if not isinstance(pin, str) or not (1 <= len(pin) <= 64):
                raise ValueError(
                    f"MCP witness argument output_pin is invalid (got: {pin!r})"
                )
            if type(max_pts) is not int or not (1 <= max_pts <= 256):
                raise ValueError(
                    f"MCP witness argument max_allowed_points must be 1..256 (got: {max_pts!r})"
                )

            call_args = {
                "inActorPath": actor,
                "inGraphPath": graph,
                "inSourceNodePath": source,
                "inReductionNodePath": reduction,
                "inReductionClass": red_cls,
                "inOutputPin": pin,
                "maxAllowedPoints": max_pts,
            }

        deadline = time.monotonic() + timeout_seconds
        with self._lock:
            if self._poisoned:
                raise BoundedMcpTransportError(
                    "MCP transport is poisoned: operator recovery required"
                )
            try:
                self._initialize(deadline)
                result, _ = self._rpc(
                    "tools/call",
                    {
                        "name": "call_tool",
                        "arguments": {
                            "toolset_name": toolset,
                            "tool_name": name,
                            "arguments": call_args,
                        },
                    },
                    deadline,
                    max_response_bytes,
                )
                tool_result = result["result"]
                if not isinstance(tool_result, dict) or tool_result.get("isError"):
                    raise BoundedMcpTransportError(
                        "MCP tool returned error/invalid payload"
                    )
                contents = tool_result.get("content")
                if not isinstance(contents, list) or len(contents) != 1:
                    raise BoundedMcpTransportError(
                        "Expected one bounded MCP text result"
                    )
                item = contents[0]
                if (
                    not isinstance(item, dict)
                    or item.get("type") != "text"
                    or not isinstance(item.get("text"), str)
                ):
                    raise BoundedMcpTransportError("MCP result is not text JSON")
                try:
                    unpacked = json.loads(item["text"])
                except ValueError as exc:
                    raise BoundedMcpTransportError(
                        "PCGToolset returned invalid JSON text"
                    ) from exc
                if isinstance(unpacked, dict) and "returnValue" in unpacked:
                    unpacked = unpacked["returnValue"]
                if isinstance(unpacked, str):
                    try:
                        unpacked = json.loads(unpacked)
                    except ValueError:
                        pass
                return unpacked
            except Exception:
                self._poisoned = True
                raise

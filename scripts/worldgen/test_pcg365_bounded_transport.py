"""Offline, no-UE regression tests of the strict PCG365 HTTP/MCP wire contract."""
from __future__ import annotations

import json
import threading
import unittest
from unittest.mock import patch

from scripts.worldgen.pcg365_bounded_transport import (
    BoundedMcpTransportError,
    BoundedPcgMcpClient,
    MAX_RESPONSE_BYTES,
)

ACTOR = {"refPath": "/Game/PCG365/Test.Test:Actor"}
NODE = {"refPath": "/Game/PCG365/Test.Test:ReducedNode"}
ARGS = {
    "pCGVolume": ACTOR,
    "node": NODE,
    "pinLabel": "Out",
    "attributeName": "",
    "startIndex": 0,
    "endIndex": 256,  # Epic's EndIndex is exclusive.
}


class FakeSocket:
    def __init__(self) -> None:
        self.shutdown_called = threading.Event()
        self.timeouts: list[float] = []

    def settimeout(self, seconds: float) -> None:
        self.timeouts.append(seconds)

    def shutdown(self, how: int) -> None:
        self.shutdown_called.set()


class FakeResponse:
    def __init__(self, status: int, body: bytes, headers: list[tuple[str, str]]) -> None:
        self.status = status
        self.body = body
        self.headers = headers
        self.read_args: list[int] = []

    def getheaders(self) -> list[tuple[str, str]]:
        return self.headers

    def read(self, count: int) -> bytes:
        self.read_args.append(count)
        return self.body[:count]


class FakeWire:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.responses: list[FakeResponse] = []
        self.status_override: int | None = None
        self.duplicate_header = False
        self.oversize_declared = False
        self.oversize_chunked = False
        self.block_until_shutdown = False
        self.bad_request_id = False

    def connection(self, host: str, port: int, timeout: float):
        wire = self

        class Connection:
            def __init__(self):
                self.sock = FakeSocket()
                self.body: dict = {}
                self.closed = False

            def request(self, method, path, body, headers):
                assert host == "127.0.0.1" and port == 8000
                assert method == "POST" and path == "/mcp"
                self.body = json.loads(body)
                wire.calls.append({"method": method, "path": path, "body": self.body,
                                   "headers": headers, "timeout": timeout})

            def getresponse(self):
                if wire.block_until_shutdown:
                    self.sock.shutdown_called.wait(2)
                    raise OSError("interrupted by watchdog")
                body = self.body
                method = body["method"]
                if "id" not in body:
                    status = 202
                    payload = b""
                elif method == "initialize":
                    status = 200
                    payload = json.dumps({
                        "jsonrpc": "2.0", "id": body["id"],
                        "result": {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}},
                    }).encode()
                else:
                    status = 200
                    payload = json.dumps({
                        "jsonrpc": "2.0",
                        "id": body["id"] + (1 if wire.bad_request_id else 0),
                        "result": {"isError": False, "content": [{
                            "type": "text",
                            "text": json.dumps({"returnValue": {"element_0": {"count": 42}}}),
                        }]},
                    }).encode()
                headers = [
                    ("Content-Type", "application/json"),
                    ("Mcp-Session-Id", "a" * 32),
                ]
                if wire.duplicate_header:
                    headers.append(("Content-Type", "application/json"))
                if wire.oversize_declared and method == "tools/call":
                    headers.append(("Content-Length", str(MAX_RESPONSE_BYTES + 1)))
                elif wire.oversize_chunked and method == "tools/call":
                    headers.append(("Transfer-Encoding", "chunked"))
                    payload = b"x" * (MAX_RESPONSE_BYTES + 4096)
                else:
                    headers.append(("Content-Length", str(len(payload))))
                result = FakeResponse(wire.status_override or status, payload, headers)
                wire.responses.append(result)
                return result

            def close(self):
                self.closed = True

        return Connection()


class BoundedTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.wire = FakeWire()
        self.patcher = patch(
            "scripts.worldgen.pcg365_bounded_transport.http.client.HTTPConnection",
            side_effect=self.wire.connection,
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.client = BoundedPcgMcpClient()

    def call(self, **kw):
        return self.client.call_bounded(
            "PCGToolset.PCGToolset", "GetNodeDataView",
            kw.pop("arguments", ARGS.copy()),
            timeout_seconds=kw.pop("timeout_seconds", 0.5),
            max_response_bytes=kw.pop("max_response_bytes", MAX_RESPONSE_BYTES),
        )

    def test_real_mcp_sequence_session_identity_and_exclusive_bound(self):
        self.assertEqual(self.call(), {"element_0": {"count": 42}})
        self.assertFalse(self.client.is_poisoned)
        self.assertEqual(
            [x["body"]["method"] for x in self.wire.calls],
            ["initialize", "notifications/initialized", "tools/call"],
        )
        call = self.wire.calls[-1]
        self.assertEqual(call["body"]["params"]["name"], "call_tool")
        self.assertEqual(call["body"]["params"]["arguments"]["tool_name"], "GetNodeDataView")
        self.assertEqual(call["body"]["params"]["arguments"]["arguments"]["endIndex"], 256)
        self.assertEqual(call["headers"]["Mcp-Session-Id"], "a" * 32)
        self.assertTrue(all(x["timeout"] <= 0.5 for x in self.wire.calls))
        self.assertEqual(self.wire.responses[-1].read_args, [MAX_RESPONSE_BYTES + 1])
        self.assertEqual(self.call(), {"element_0": {"count": 42}})
        self.assertEqual(len(self.wire.calls), 4)  # Same session, new bounded connection.

    def test_invalid_ranges_and_toolnames_do_not_initialize_or_send(self):
        bad = [dict(ARGS, endIndex=-1), dict(ARGS, endIndex=257),
               dict(ARGS, startIndex=255, endIndex=255), dict(ARGS, startIndex=0.0)]
        for args in bad:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.call(arguments=args)
        with self.assertRaises(ValueError):
            self.client.call_bounded(
                "EditorToolset.EditorAppToolset", "GetNodeDataView", ARGS,
                timeout_seconds=0.5, max_response_bytes=1000,
            )
        with self.assertRaises(ValueError):
            self.call(timeout_seconds=180)
        with self.assertRaises(ValueError):
            self.call(max_response_bytes=32 * 1024 * 1024)
        self.assertEqual(self.wire.calls, [])

    def test_reject_declared_oversize_before_body_read_and_poison(self):
        self.wire.oversize_declared = True
        with self.assertRaisesRegex(BoundedMcpTransportError, "Content-Length"):
            self.call()
        self.assertTrue(self.client.is_poisoned)
        self.assertEqual(self.wire.responses[-1].read_args, [])
        calls = len(self.wire.calls)
        with self.assertRaisesRegex(BoundedMcpTransportError, "poisoned"):
            self.call()
        self.assertEqual(len(self.wire.calls), calls)

    def test_reject_chunked_oversize_after_at_most_cap_plus_one_bytes(self):
        self.wire.oversize_chunked = True
        with self.assertRaisesRegex(BoundedMcpTransportError, "byte bound"):
            self.call()
        self.assertTrue(self.client.is_poisoned)
        self.assertEqual(self.wire.responses[-1].read_args, [MAX_RESPONSE_BYTES + 1])

    def test_duplicate_header_is_terminal_and_no_retry(self):
        self.wire.duplicate_header = True
        with self.assertRaisesRegex(BoundedMcpTransportError, "Duplicate"):
            self.call()
        self.assertTrue(self.client.is_poisoned)
        self.assertEqual(len(self.wire.calls), 1)

    def test_json_rpc_identity_mismatch_is_terminal(self):
        self.wire.bad_request_id = True
        with self.assertRaisesRegex(BoundedMcpTransportError, "request ID"):
            self.call()
        self.assertTrue(self.client.is_poisoned)

    def test_non_200_status_is_terminal(self):
        self.wire.status_override = 503
        with self.assertRaisesRegex(BoundedMcpTransportError, "status/content-type"):
            self.call()
        self.assertTrue(self.client.is_poisoned)

    def test_wall_clock_watchdog_interrupts_stalled_initialize(self):
        self.wire.block_until_shutdown = True
        with self.assertRaisesRegex(TimeoutError, "deadline"):
            self.call(timeout_seconds=0.04)
        self.assertTrue(self.client.is_poisoned)
        self.assertEqual(len(self.wire.calls), 1)

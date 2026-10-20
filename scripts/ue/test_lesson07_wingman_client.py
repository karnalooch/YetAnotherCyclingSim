"""Synthetic loopback HTTP fixtures; no Unreal or real credentials are used."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest import mock

from scripts.ue import lesson07_wingman_client as client


TOKEN = "SYNTHETIC_SECRET_7ec473bf_NOT_A_CREDENTIAL"


def identity(port):
    now = datetime.now(timezone.utc)
    return {
        "schema_version": 1,
        "status": "L07_WINGMAN_HOST_IDENTITY_VERIFIED",
        "observed_utc": now.isoformat(),
        "pid": 1234,
        "process_created_utc": (now - timedelta(minutes=4)).isoformat(),
        "executable": client.EXECUTABLE,
        "project": client.PROJECT,
        "canonical_project_argument_matches": True,
        "listener": {"address": "127.0.0.1", "port": port, "pid": 1234},
    }


def config(port):
    return {"url": f"http://127.0.0.1:{port}/loco", "token": TOKEN, "type": "http"}


def default_reply(request):
    method = request["method"]
    if method == "notifications/initialized":
        return 202, {}, b""
    if method == "initialize":
        result = {
            "protocolVersion": client.PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "Synthetic", "version": "1"},
            "instructions": TOKEN,
        }
        headers = {"Mcp-Session-Id": "synthetic-session-1"}
    elif method == "tools/list":
        result = {
            "tools": [
                {
                    "name": "execute_python",
                    "description": TOKEN,
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": TOKEN,
                                "default": TOKEN,
                            }
                        },
                        "required": ["code"],
                        "additionalProperties": False,
                    },
                }
            ]
        }
        headers = {}
    elif method == "session/status":
        result = {
            "signed_in": True,
            "plan": "Premium",
            "email": "synthetic@example.invalid",
            "user_id": TOKEN,
            "token": TOKEN,
        }
        headers = {}
    else:
        raise AssertionError("Unexpected fixture request")
    return (
        200,
        {"Content-Type": "application/json", **headers},
        client.canonical({"jsonrpc": "2.0", "id": request["id"], "result": result}),
    )


@contextmanager
def peer(responder=default_reply):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(
                {"path": self.path, "headers": dict(self.headers), "body": request}
            )
            try:
                status, headers, body = responder(request)
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                if "Content-Length" not in headers:
                    self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    try:
        yield server.server_port, requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def connection(port, timeout=2):
    return client.DiscoveryClient(
        client.Discovery.from_mapping(config(port)), identity(port), timeout=timeout
    )


class AdmissionTests(unittest.TestCase):
    def test_invalid_endpoint_and_header_input_rejected(self):
        invalid = [
            "https://127.0.0.1:19315/loco",
            "http://localhost:19315/loco",
            "http://127.0.0.2:19315/loco",
            "http://127.0.0.1.evil:19315/loco",
            "http://secret@127.0.0.1:19315/loco",
            "http://127.0.0.1:19315/loco?token=x",
            "http://127.0.0.1:19315/loco#x",
            "http://127.0.0.1:19315/loco?",
            "http://127.0.0.1:19315/loco#",
            "http://127.0.0.1:0/loco",
            "http://127.0.0.1:65536/loco",
            "http://127.0.0.1:19315/mcp",
            "http://127.0.0.1:19315/loco/",
            "http://127.0.0.1:19315/loco\n",
        ]
        for url in invalid:
            with self.subTest(url=url), self.assertRaises(client.ProbeError):
                client.Discovery.from_mapping({**config(19315), "url": url})
        for token in (None, "", "x\r\nInjected: yes", "Bearer with spaces", "x" * 4097):
            with (
                self.subTest(token_type=type(token).__name__),
                self.assertRaises(client.ProbeError),
            ):
                client.Discovery.from_mapping({**config(19315), "token": token})

    def test_bad_external_identity_never_opens_connection(self):
        cases = []
        for field, value in (
            ("pid", True),
            ("canonical_project_argument_matches", False),
            ("project", r"D:\other\YetAnotherCyclingSim.uproject"),
            ("executable", r"D:\other\UnrealEditor.exe"),
            ("status", "READ_ONLY_BRIDGE_DISCOVERY_NOT_RUNTIME_PROOF"),
        ):
            cases.append({**identity(19315), field: value})
        cases.append(
            {
                **identity(19315),
                "listener": {"address": "127.0.0.1", "port": 19316, "pid": 1234},
            }
        )
        cases.append(
            {
                **identity(19315),
                "listener": {"address": "127.0.0.1", "port": 19315, "pid": 5678},
            }
        )
        cases.append(
            {
                **identity(19315),
                "observed_utc": (
                    datetime.now(timezone.utc) - timedelta(minutes=3)
                ).isoformat(),
            }
        )
        cases.append(
            {
                **identity(19315),
                "observed_utc": (
                    datetime.now(timezone.utc) + timedelta(minutes=3)
                ).isoformat(),
            }
        )
        with mock.patch.object(client.http.client, "HTTPConnection") as http:
            for value in cases:
                with self.subTest(value=value), self.assertRaises(client.ProbeError):
                    client.DiscoveryClient(
                        client.Discovery.from_mapping(config(19315)), value
                    )
            http.assert_not_called()

    def test_no_tool_call_or_arbitrary_method_surface(self):
        with peer() as (port, requests):
            probe = connection(port)
            for method in (
                "tools/call",
                "execute_python",
                "resources/read",
                "session/logout",
            ):
                with self.subTest(method=method), self.assertRaises(client.ProbeError):
                    probe._post(method)
            self.assertEqual(requests, [])

    def test_duplicate_json_members_rejected_without_value_disclosure(self):
        with self.assertRaises(client.ProbeError) as caught:
            client.parse_json(b'{"token":"' + TOKEN.encode() + b'","token":"x"}')
        self.assertEqual(str(caught.exception), "DUPLICATE_JSON_KEY")
        self.assertNotIn(TOKEN, str(caught.exception))


class WireTests(unittest.TestCase):
    def test_handshake_auth_session_headers_and_sanitized_schema(self):
        with (
            peer() as (port, requests),
            mock.patch.dict(
                os.environ,
                {
                    "HTTP_PROXY": "http://example.invalid:9",
                    "http_proxy": "http://example.invalid:9",
                },
            ),
        ):
            report = connection(port).probe()
        self.assertEqual(report["status"], "DISCOVERY_COMPLETE")
        self.assertEqual(
            [r["body"]["method"] for r in requests],
            ["initialize", "notifications/initialized", "tools/list", "session/status"],
        )
        for number, row in enumerate(requests):
            self.assertEqual(row["path"], "/loco")
            self.assertEqual(row["headers"]["Authorization"], "Bearer " + TOKEN)
            self.assertEqual(
                row["headers"]["Accept"], "application/json, text/event-stream"
            )
            if number:
                self.assertEqual(
                    row["headers"]["Mcp-Session-Id"], "synthetic-session-1"
                )
        schema = report["tools"][0]["inputSchema"]
        self.assertEqual(schema["required"], ["code"])
        self.assertEqual(schema["properties"]["code"], {"type": "string"})
        raw = client.canonical(report)
        self.assertNotIn(TOKEN.encode(), raw)
        self.assertNotIn(b"synthetic@example.invalid", raw)
        self.assertEqual(report["native_tool_calls"], 0)
        self.assertFalse(report["performance_pass"])

    def test_incremental_sse_notifications_and_multiline_data(self):
        def sse(request):
            status, headers, raw = default_reply(request)
            if status == 202:
                return status, headers, raw
            payload = json.loads(raw)
            raw = json.dumps(payload, indent=2).encode()
            event = (
                b": keepalive\n\nid: ignored\ndata: "
                + client.canonical(
                    {
                        "jsonrpc": "2.0",
                        "method": "notifications/message",
                        "params": {"message": TOKEN},
                    }
                )
                + b"\n\n"
            )
            event += (
                b"event: message\n"
                + b"\n".join(b"data: " + line for line in raw.splitlines())
                + b"\n\n"
            )
            return (
                200,
                {**headers, "Content-Type": "text/event-stream; charset=utf-8"},
                event,
            )

        with peer(sse) as (port, requests):
            report = connection(port).probe()
        self.assertEqual(report["status"], "DISCOVERY_COMPLETE")
        self.assertEqual(report["notifications_received"], 3)
        self.assertEqual(len(requests), 4)
        self.assertNotIn(TOKEN.encode(), client.canonical(report))

    def test_redirect_is_not_followed_or_retried(self):
        with peer(
            lambda _request: (307, {"Location": "http://example.invalid/" + TOKEN}, b"")
        ) as (port, requests):
            with self.assertRaises(client.ProbeError) as caught:
                connection(port).probe()
            self.assertEqual(caught.exception.code, "HTTP_REDIRECT_DENIED")
            self.assertEqual(len(requests), 1)
            self.assertNotIn(TOKEN, str(caught.exception))

    def test_timeout_is_bounded_and_not_retried(self):
        def delayed(request):
            time.sleep(0.3)
            return default_reply(request)

        with peer(delayed) as (port, requests):
            started = time.monotonic()
            with self.assertRaises(client.ProbeError) as caught:
                connection(port, timeout=0.08).probe()
            self.assertLess(time.monotonic() - started, 1.0)
            self.assertEqual(caught.exception.code, "REQUEST_TIMEOUT")
            self.assertEqual(len(requests), 1)

    def test_http_error_body_cannot_leak_secret(self):
        with peer(
            lambda _r: (401, {"Content-Type": "application/json"}, TOKEN.encode())
        ) as (port, requests):
            with self.assertRaises(client.ProbeError) as caught:
                connection(port).probe()
            self.assertEqual(str(caught.exception), "HTTP_STATUS")
            self.assertEqual(len(requests), 1)

    def test_protocol_mismatch_stops_before_initialized(self):
        def mismatched(request):
            status, headers, raw = default_reply(request)
            payload = json.loads(raw)
            payload["result"]["protocolVersion"] = "2024-11-05"
            return status, headers, client.canonical(payload)

        with peer(mismatched) as (port, requests):
            with self.assertRaises(client.ProbeError) as caught:
                connection(port).probe()
            self.assertEqual(caught.exception.code, "PROTOCOL_MISMATCH")
            self.assertEqual(len(requests), 1)

    def test_wrong_response_id_stops_without_retry(self):
        def wrong_id(request):
            status, headers, raw = default_reply(request)
            payload = json.loads(raw)
            payload["id"] = request["id"] + 1
            return status, headers, client.canonical(payload)

        with peer(wrong_id) as (port, requests):
            with self.assertRaises(client.ProbeError) as caught:
                connection(port).probe()
            self.assertEqual(caught.exception.code, "RPC_RESPONSE_ID")
            self.assertEqual(len(requests), 1)

    def test_oversized_declared_response_stops_before_body(self):
        with peer(
            lambda _r: (
                200,
                {
                    "Content-Type": "application/json",
                    "Content-Length": str(client.RESPONSE_LIMIT + 1),
                },
                b"",
            )
        ) as (port, requests):
            with self.assertRaises(client.ProbeError) as caught:
                connection(port).probe()
            self.assertEqual(caught.exception.code, "HTTP_DECLARED_SIZE")
            self.assertEqual(len(requests), 1)

    def test_signed_out_zero_tools_is_explicit(self):
        def signed_out(request):
            status, headers, raw = default_reply(request)
            if request["method"] == "tools/list":
                raw = client.canonical(
                    {"jsonrpc": "2.0", "id": request["id"], "result": {"tools": []}}
                )
            elif request["method"] == "session/status":
                raw = client.canonical(
                    {
                        "jsonrpc": "2.0",
                        "id": request["id"],
                        "result": {"signed_in": False},
                    }
                )
            return status, headers, raw

        with peer(signed_out) as (port, _requests):
            report = connection(port).probe()
        self.assertEqual(report["status"], "DISCOVERY_SIGNED_OUT")
        self.assertEqual(report["tools"], [])
        self.assertFalse(report["session"]["signed_in"])

    def test_tool_rpc_error_retains_only_code_and_does_not_retry(self):
        def locked(request):
            if request["method"] == "tools/list":
                return (
                    200,
                    {"Content-Type": "application/json"},
                    client.canonical(
                        {
                            "jsonrpc": "2.0",
                            "id": request["id"],
                            "error": {
                                "code": -32004,
                                "message": TOKEN,
                                "data": {"email": "private@example.invalid"},
                            },
                        }
                    ),
                )
            return default_reply(request)

        with peer(locked) as (port, requests):
            report = connection(port).probe()
        self.assertEqual(
            report["tool_list_error"], {"code": "RPC_ERROR", "rpc_code": -32004}
        )
        self.assertEqual(report["status"], "DISCOVERY_INCOMPLETE")
        self.assertEqual(sum(r["body"]["method"] == "tools/list" for r in requests), 1)
        self.assertNotIn(TOKEN.encode(), client.canonical(report))


class FileTests(unittest.TestCase):
    def test_end_to_end_files_keep_credentials_private_and_output_new(self):
        with tempfile.TemporaryDirectory() as directory, peer() as (port, _requests):
            root = Path(directory)
            config_path, receipt, output = (
                root / "discovery.json",
                root / "identity.json",
                root / "probe.json",
            )
            config_path.write_bytes(client.canonical(config(port)))
            receipt.write_bytes(client.canonical(identity(port)))
            with mock.patch.object(client, "WINDOWS_HOST", True):
                report = client.probe_from_files(receipt, config_path)
            client.write_report(output, report)
            self.assertNotIn(TOKEN.encode(), output.read_bytes())
            self.assertIn(TOKEN.encode(), config_path.read_bytes())
            self.assertEqual(
                report["post_request_host_recheck"], "REQUIRED_FROM_HARNESS"
            )
            with self.assertRaises(client.ProbeError):
                client.write_report(output, {"overwrite": True})

    def test_reparse_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, link = root / "source.json", root / "linked.json"
            source.write_bytes(b"{}")
            try:
                link.symlink_to(source)
            except OSError:
                self.skipTest("Symlink creation not permitted")
            with self.assertRaises(client.ProbeError) as caught:
                client.read_bounded(link, 64)
            self.assertEqual(caught.exception.code, "REPARSE_PATH")

    def test_cli_suppresses_unexpected_exception_message(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "probe.json"
            stdout = io.StringIO()
            with (
                mock.patch.object(
                    client, "probe_from_files", side_effect=ValueError(TOKEN)
                ),
                mock.patch("sys.stdout", stdout),
            ):
                code = client.main(
                    [
                        "--identity-receipt",
                        str(Path(directory) / "identity.json"),
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(code, 1)
            self.assertNotIn(TOKEN, stdout.getvalue())
            self.assertNotIn(TOKEN.encode(), output.read_bytes())
            self.assertEqual(
                json.loads(output.read_bytes())["error_code"],
                "UNEXPECTED_CLIENT_FAILURE",
            )


if __name__ == "__main__":
    unittest.main()

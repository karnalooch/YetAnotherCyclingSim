"""Synthetic loopback HTTP fixtures; no Unreal or real credentials are used."""

from __future__ import annotations

from contextlib import contextmanager
import builtins
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import sys
import unittest
from unittest import mock

from scripts.ue import lesson07_wingman_client as client


TOKEN = "SYNTHETIC_SECRET_7ec473bf_NOT_A_CREDENTIAL"

# Exact raw inputSchema from authenticated discovery run 39515925462, source 96a7.
INSTALLED_PYTHON_SCHEMA = {
    "properties": {
        "code": {
            "description": "Python code to execute. Pass this OR 'file' - at least one is required, and 'file' wins when both are given. Use 'import unreal' for UE APIs. Example: unreal.EditorAssetLibrary.save_asset('/Game/BP_MyActor'). Runs in the editor's PERSISTENT interpreter namespace - globals survive between calls, so any global left holding an unreal.Object pins it for the session and blocks a later delete of its asset. The result carries a 'UObject pin report' footer naming every new holder this call created; 'del <name>' in your NEXT call releases it.",
            "type": "string",
        },
        "file": {
            "description": "Path to a Python 3 script file to execute (absolute, or relative to the project directory; UTF-8; 2 MB cap). A file-only call is fully supported: pass this OR 'code' (at least one is required), and this one wins when both are passed. Use for multi-line scripts - the file path avoids every JSON/transport escaping layer that mangles inline code.",
            "type": "string",
        },
        "mode": {
            "description": "Execution mode: 'file' (default, multi-line script, side effects) or 'eval' (a single expression whose value-repr is returned in command_result with no print needed). Note: 'eval' must be ONE expression; loco helpers / multi-line setup must run in a prior 'file' call (module imports persist in the interpreter).",
            "enum": ["file", "eval"],
            "type": "string",
        },
    },
    "type": "object",
}


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


def observation():
    return {
        "status": client.OBSERVER_STATUS,
        "pid": 1234,
        "project": "D:/yacs/project/",
        "project_file": client.PROJECT,
        "world": client.OBSERVER_WORLD,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "dirty_sets_equal": None,
        "limitations": {
            "mutating_apis_requested": False,
            "asset_loads_requested": False,
            "new_captures": False,
            "visual_acceptance": False,
            "performance_pass": False,
        },
        "validation": {"visual_or_native_graph_acceptance": False},
    }


def tool_result(observed=None):
    envelope = {
        "observer_sha256": client.OBSERVER_SHA256,
        "observation": observation() if observed is None else observed,
    }
    return {
        "isError": False,
        "content": [
            {
                "type": "text",
                "text": client.OBSERVER_TAG + client.canonical(envelope).decode(),
            }
        ],
    }


def observer_reply(request):
    if request["method"] == "tools/call":
        return (
            200,
            {"Content-Type": "application/json"},
            client.canonical(
                {"jsonrpc": "2.0", "id": request["id"], "result": tool_result()}
            ),
        )
    status, headers, raw = default_reply(request)
    if request["method"] == "tools/list":
        payload = json.loads(raw)
        payload["result"]["tools"][0]["inputSchema"] = INSTALLED_PYTHON_SCHEMA
        raw = client.canonical(payload)
    return status, headers, raw


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


def connection(port, timeout=2, state=None):
    return client.DiscoveryClient(
        client.Discovery.from_mapping(config(port)),
        identity(port),
        timeout=timeout,
        observation_state=state,
    )


class AdmissionTests(unittest.TestCase):
    def test_metadata_is_bounded_and_cannot_supply_missing_or_malformed_core(self):
        metadata = {"metadata": {**config(19315), "note": "synthetic metadata"}}
        for key in ("url", "token", "type"):
            missing = {**config(19315), **metadata}
            del missing[key]
            with self.subTest(missing=key), self.assertRaises(client.ProbeError):
                client.Discovery.from_mapping(missing)
        for key, value in (
            ("url", "http://example.invalid:19315/loco"),
            ("url", {"url": config(19315)["url"]}),
            ("token", "bad token with spaces"),
            ("token", None),
            ("type", "sse"),
            ("type", {"type": "http"}),
        ):
            with (
                self.subTest(key=key, value=value),
                self.assertRaises(client.ProbeError),
            ):
                client.Discovery.from_mapping({**config(19315), **metadata, key: value})
        for value in ("x" * client.CONFIG_LIMIT, float("nan"), object()):
            with (
                self.subTest(metadata_type=type(value).__name__),
                self.assertRaises(client.ProbeError),
            ):
                client.Discovery.from_mapping({**config(19315), "metadata": value})

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
    def test_selected_installed_contracts_retain_exact_schemas_and_safe_metadata(self):
        input_schema = {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python source"},
                "mode": {
                    "type": "string",
                    "enum": ["first", "second"],
                    "default": "first",
                },
            },
            "required": ["code"],
            "additionalProperties": False,
        }
        output_schema = {
            "type": "object",
            "properties": {
                "output": {"type": "string"},
                "success": {"type": "boolean"},
            },
        }
        annotations = {
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        }
        selected = {
            "name": "execute_python",
            "inputSchema": input_schema,
            "outputSchema": output_schema,
            "description": "Synthetic installed contract; data only.",
            "annotations": {**annotations, "title": TOKEN, "unrecognized": TOKEN},
            "unknown_metadata": TOKEN,
        }

        def contract_reply(request):
            if request["method"] == "tools/list":
                return (
                    200,
                    {"Content-Type": "application/json"},
                    client.canonical(
                        {
                            "jsonrpc": "2.0",
                            "id": request["id"],
                            "result": {
                                "tools": [
                                    selected,
                                    {
                                        "name": "take_viewport_screenshot",
                                        "inputSchema": {
                                            "type": "object",
                                            "properties": {
                                                "return_image": {
                                                    "type": "boolean",
                                                    "default": True,
                                                }
                                            },
                                        },
                                    },
                                    {
                                        "name": "other_tool",
                                        "inputSchema": input_schema,
                                        "outputSchema": output_schema,
                                        "description": TOKEN,
                                    },
                                ]
                            },
                        }
                    ),
                )
            return default_reply(request)

        with peer(contract_reply) as (port, requests):
            report = connection(port).probe()
        contracts = report["installed_tool_contracts"]
        self.assertEqual(set(contracts), {"execute_python", "take_viewport_screenshot"})
        self.assertEqual(
            contracts["execute_python"],
            {
                "status": "RETAINED",
                "inputSchema": input_schema,
                "outputSchema": output_schema,
                "description": selected["description"],
                "annotations": annotations,
            },
        )
        self.assertIs(
            contracts["take_viewport_screenshot"]["inputSchema"]["properties"][
                "return_image"
            ]["default"],
            True,
        )
        self.assertNotIn("outputSchema", contracts["take_viewport_screenshot"])
        for row in report["tools"]:
            if row["name"] in {"execute_python", "other_tool"}:
                self.assertEqual(
                    row["inputSchema"]["properties"]["mode"], {"type": "string"}
                )
        self.assertEqual(report["status"], "DISCOVERY_COMPLETE")
        self.assertEqual(report["native_tool_calls"], 0)
        self.assertEqual(len(requests), 4)
        self.assertNotIn(TOKEN.encode(), client.canonical(report))

    def test_selected_contract_exclusions_never_expose_credentials_or_large_values(
        self,
    ):
        nested = {"type": "string"}
        for _ in range(13):
            nested = {"items": nested}
        cases = [
            ({"description": TOKEN}, "CONTRACT_CREDENTIAL"),
            (
                {"inputSchema": {"type": "object", "default": {"secret": TOKEN}}},
                "CONTRACT_CREDENTIAL",
            ),
            (
                {
                    "inputSchema": {
                        "type": "object",
                        "enum": ["x" * client.CONTRACT_LIMIT],
                    }
                },
                "CONTRACT_SIZE",
            ),
            (
                {"description": "x" * (client.CONTRACT_DESCRIPTION_LIMIT + 1)},
                "CONTRACT_DESCRIPTION",
            ),
            ({"outputSchema": nested}, "CONTRACT_DEPTH"),
            ({"annotations": {"readOnlyHint": "true"}}, "CONTRACT_ANNOTATIONS"),
        ]
        for fields, reason in cases:

            def excluded_reply(request):
                if request["method"] == "tools/list":
                    return (
                        200,
                        {"Content-Type": "application/json"},
                        client.canonical(
                            {
                                "jsonrpc": "2.0",
                                "id": request["id"],
                                "result": {
                                    "tools": [
                                        {
                                            "name": "execute_python",
                                            "inputSchema": {"type": "object"},
                                            **fields,
                                        }
                                    ]
                                },
                            }
                        ),
                    )
                return default_reply(request)

            with self.subTest(reason=reason), peer(excluded_reply) as (port, requests):
                report = connection(port).probe()
            self.assertEqual(
                report["installed_tool_contracts"]["execute_python"],
                {"status": "EXCLUDED", "reason": reason},
            )
            self.assertEqual(report["status"], "DISCOVERY_COMPLETE")
            self.assertEqual(report["native_tool_calls"], 0)
            self.assertEqual(len(requests), 4)
            self.assertNotIn(TOKEN.encode(), client.canonical(report))

    def test_json_escaped_credential_in_contract_is_excluded(self):
        token = 'synthetic\\secret"value'
        contract = client.installed_tool_contract(
            {
                "inputSchema": {"type": "object", "default": {"note": token}},
            },
            token,
        )
        self.assertEqual(
            contract, {"status": "EXCLUDED", "reason": "CONTRACT_CREDENTIAL"}
        )

    def test_extra_discovery_metadata_never_changes_route_auth_or_report(self):
        ignored_secret = "SYNTHETIC_IGNORED_METADATA_VALUE"
        with peer() as (port, requests):
            discovery = client.Discovery.from_mapping(
                {
                    **config(port),
                    "metadata": {
                        "url": "https://example.invalid/alternate",
                        "token": ignored_secret,
                        "type": "sse",
                    },
                    "headers": {"Authorization": "Bearer " + ignored_secret},
                    "endpoint": "https://example.invalid/alternate",
                    "arbitrary_note": ignored_secret,
                }
            )
            self.assertEqual(discovery, client.Discovery(port, TOKEN))
            report = client.DiscoveryClient(discovery, identity(port)).probe()
        self.assertEqual(report["status"], "DISCOVERY_COMPLETE")
        self.assertEqual(len(requests), 4)
        for request in requests:
            self.assertEqual(request["path"], client.ENDPOINT)
            self.assertEqual(request["headers"]["Authorization"], "Bearer " + TOKEN)
            self.assertNotIn(ignored_secret.encode(), client.canonical(request))
        self.assertNotIn(ignored_secret.encode(), client.canonical(report))
        self.assertNotIn(TOKEN.encode(), client.canonical(report))
        self.assertEqual(report["native_tool_calls"], 0)

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


class ObserverTests(unittest.TestCase):
    def test_one_fixed_call_preserves_partial_findings_and_false_acceptance(self):
        state = client.ObservationState()
        with peer(observer_reply) as (port, requests):
            probe = connection(port, state=state)
            report = probe.probe(observe_lesson07=True)
            with self.assertRaises(client.ProbeError):
                probe._post("tools/call", probe._observer_params)
        self.assertEqual(report["status"], "OBSERVATION_COMPLETE")
        self.assertEqual(report["native_tool_calls"], 1)
        self.assertIs(report["native_tool_attempted"], True)
        self.assertIs(report["native_tool_completed"], True)
        self.assertEqual(report["native_material_readback"], client.OBSERVER_STATUS)
        self.assertIsNone(report["observation"]["dirty_sets_equal"])
        self.assertFalse(report["visual_acceptance"])
        self.assertFalse(report["performance_pass"])
        self.assertFalse(report["plugin_execution_defaults_verified"])
        calls = [r for r in requests if r["body"]["method"] == "tools/call"]
        self.assertEqual(len(calls), 1)
        params = calls[0]["body"]["params"]
        self.assertEqual(set(params), {"name", "arguments"})
        self.assertEqual(params["name"], "execute_python")
        self.assertEqual(set(params["arguments"]), {"code", "mode"})
        self.assertEqual(params["arguments"]["mode"], "file")
        self.assertNotIn("file", params["arguments"])
        self.assertEqual(
            report["observer_input_schema_sha256"], client.OBSERVER_SCHEMA_SHA256
        )
        code = params["arguments"]["code"]
        self.assertIn(client.OBSERVER_SHA256, code)
        self.assertIn("collect_json", code)
        self.assertNotIn(TOKEN, code)
        request_size = len(client.canonical(calls[0]["body"]))
        self.assertGreater(request_size, client.CONFIG_LIMIT)
        self.assertLess(request_size, client.OBSERVER_REQUEST_LIMIT)
        self.assertNotIn(TOKEN.encode(), client.canonical(report))

    def test_raw_defaults_not_sanitized_schema_decide_admission(self):
        def changed_default(request):
            status, headers, raw = observer_reply(request)
            if request["method"] == "tools/list":
                payload = json.loads(raw)
                payload["result"]["tools"][0]["inputSchema"]["properties"]["mode"][
                    "default"
                ] = "eval"
                raw = client.canonical(payload)
            return status, headers, raw

        state = client.ObservationState()
        with peer(changed_default) as (port, requests):
            with self.assertRaises(client.ProbeError) as caught:
                connection(port, state=state).probe(observe_lesson07=True)
        self.assertEqual(caught.exception.code, "OBSERVER_TOOL_SCHEMA_UNSUPPORTED")
        self.assertFalse(state.attempted)
        self.assertIs(state.completed, False)
        self.assertEqual(len(requests), 4)

    def test_unknown_required_optional_or_constraint_arguments_rejected(self):
        base = INSTALLED_PYTHON_SCHEMA
        cases = [
            {**base, "required": []},
            {**base, "required": ["python_code"]},
            {**base, "additionalProperties": True},
            {**base, "default": {}},
            {**base, "oneOf": [base]},
            {**base, "properties": {**base["properties"], "mode": {"type": "string"}}},
            {**base, "properties": {**base["properties"], "file": {"type": "number"}}},
            {
                **base,
                "properties": {**base["properties"], "timeout": {"type": "number"}},
            },
            {
                **base,
                "properties": {
                    **base["properties"],
                    "code": {
                        **base["properties"]["code"],
                        "description": "Changed installed contract",
                    },
                },
            },
            {**base, "properties": {"code": {"type": "string", "enum": ["x"]}}},
            {**base, "properties": {"code": {"type": "string", "maxLength": 1}}},
        ]
        for schema in cases:
            with self.subTest(schema=schema), self.assertRaises(client.ProbeError):
                client.validate_observer_schema(schema)
        self.assertEqual(
            client.validate_observer_schema(base), client.OBSERVER_SCHEMA_SHA256
        )

    def test_signed_out_and_incomplete_or_duplicate_inventory_cannot_call(self):
        for fault in ("signed_out", "pagination", "duplicate", "missing_tool"):

            def changed(request):
                status, headers, raw = observer_reply(request)
                if request["method"] == "session/status" and fault == "signed_out":
                    payload = json.loads(raw)
                    payload["result"]["signed_in"] = False
                    raw = client.canonical(payload)
                if request["method"] == "tools/list":
                    payload = json.loads(raw)
                    if fault == "pagination":
                        payload["result"]["nextCursor"] = "repeated"
                    elif fault == "duplicate":
                        payload["result"]["tools"] *= 2
                    elif fault == "missing_tool":
                        payload["result"]["tools"] = []
                    raw = client.canonical(payload)
                return status, headers, raw

            state = client.ObservationState()
            with self.subTest(fault=fault), peer(changed) as (port, requests):
                with self.assertRaises(client.ProbeError):
                    connection(port, state=state).probe(observe_lesson07=True)
                self.assertFalse(state.attempted)
                self.assertFalse(
                    any(r["body"]["method"] == "tools/call" for r in requests)
                )

    def test_changed_source_refuses_before_native_submission(self):
        state = client.ObservationState()
        with (
            peer(observer_reply) as (port, requests),
            mock.patch.object(client, "OBSERVER_SHA256", "0" * 64),
        ):
            with self.assertRaises(client.ProbeError) as caught:
                connection(port, state=state).probe(observe_lesson07=True)
        self.assertEqual(caught.exception.code, "OBSERVER_SOURCE_HASH")
        self.assertFalse(state.attempted)
        self.assertEqual(len(requests), 4)

    def test_inline_program_uses_verified_snapshot_in_fresh_namespace(self):
        source = (
            b'assert __name__ == "_yacs_lesson07_observer"\n'
            b'assert "existing_private_global" not in globals()\n'
            b'def collect_json():\n    return \'{"status":"synthetic"}\'\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / client.OBSERVER_FILE
            source_path.write_bytes(source)
            digest = hashlib.sha256(source).hexdigest()
            with (
                mock.patch.object(
                    client, "__file__", str(Path(directory) / "client.py")
                ),
                mock.patch.object(client, "OBSERVER_SHA256", digest),
            ):
                code = client.observer_loader()
            namespace = {"existing_private_global": object()}
            stdout = io.StringIO()
            # The remote program must not revisit the host source path.
            source_path.write_text('raise AssertionError("EXECUTED_CHANGED_SOURCE")')
            with (
                mock.patch("sys.stdout", stdout),
                mock.patch.object(
                    Path, "open", side_effect=AssertionError("Native file I/O")
                ),
                mock.patch.object(
                    builtins, "open", side_effect=AssertionError("Native file I/O")
                ),
                mock.patch.object(
                    io, "open", side_effect=AssertionError("Native file I/O")
                ),
            ):
                exec(code, namespace, namespace)
            self.assertEqual(
                set(namespace), {"existing_private_global", "__builtins__"}
            )
            self.assertEqual(stdout.getvalue().count(client.OBSERVER_TAG), 1)
            envelope = json.loads(stdout.getvalue()[len(client.OBSERVER_TAG) :])
            self.assertEqual(envelope["observer_sha256"], digest)
            self.assertEqual(envelope["observation"], {"status": "synthetic"})
            with self.assertRaisesRegex(RuntimeError, "OBSERVER_SOURCE_HASH"):
                exec(code.replace("synthetic", "tampered"), {})
            self.assertNotIn(str(source_path), code)
            # A new request cannot accept the changed local source.
            with (
                mock.patch.object(
                    client, "__file__", str(Path(directory) / "client.py")
                ),
                mock.patch.object(client, "OBSERVER_SHA256", digest),
                self.assertRaisesRegex(client.ProbeError, "OBSERVER_SOURCE_HASH"),
            ):
                client.observer_loader()
            self.assertFalse((Path(directory) / "__pycache__").exists())

    def test_real_pinned_collector_runs_with_fake_unreal_without_file_io(self):
        from scripts.ue.test_lesson07_observe_editor import Fixture

        fixture = Fixture()
        code = client.observer_loader()
        namespace = {"existing_private_global": object()}
        stdout = io.StringIO()
        with (
            mock.patch.dict(sys.modules, {"unreal": fixture.api}),
            mock.patch("sys.stdout", stdout),
            mock.patch.object(
                Path, "open", side_effect=AssertionError("Native file I/O")
            ),
            mock.patch.object(
                builtins, "open", side_effect=AssertionError("Native file I/O")
            ),
            mock.patch.object(
                io, "open", side_effect=AssertionError("Native file I/O")
            ),
            mock.patch.object(
                os, "open", side_effect=AssertionError("Native file I/O")
            ),
        ):
            exec(code, namespace, namespace)
        fixture.forbidden.assert_not_called()
        self.assertEqual(set(namespace), {"existing_private_global", "__builtins__"})
        self.assertNotIn("_yacs_lesson07_observer", sys.modules)
        self.assertEqual(stdout.getvalue().count(client.OBSERVER_TAG), 1)
        envelope = json.loads(stdout.getvalue()[len(client.OBSERVER_TAG) :])
        self.assertEqual(envelope["observer_sha256"], client.OBSERVER_SHA256)
        self.assertEqual(envelope["observation"]["status"], client.OBSERVER_STATUS)
        self.assertEqual(envelope["observation"]["world"], client.OBSERVER_WORLD)
        self.assertIs(envelope["observation"]["limitations"]["new_captures"], False)
        self.assertIs(
            envelope["observation"]["limitations"]["visual_acceptance"], False
        )

    def test_request_caps_remain_fixed_and_oversize_stops_before_send(self):
        with mock.patch.object(client.http.client, "HTTPConnection") as http:
            with self.assertRaisesRegex(client.ProbeError, "REQUEST_SIZE"):
                connection(19315)._post(
                    "tools/list", {"cursor": "x" * client.CONFIG_LIMIT}
                )
            http.assert_not_called()
        state = client.ObservationState()
        with (
            peer(observer_reply) as (port, requests),
            mock.patch.object(
                client,
                "observer_loader",
                return_value="x" * client.OBSERVER_REQUEST_LIMIT,
            ),
        ):
            with self.assertRaisesRegex(client.ProbeError, "REQUEST_SIZE"):
                connection(port, state=state).probe(observe_lesson07=True)
        self.assertFalse(state.attempted)
        self.assertIs(state.completed, False)
        self.assertEqual(len(requests), 4)
        self.assertFalse(any(r["body"]["method"] == "tools/call" for r in requests))

    def test_one_large_sse_result_only_allowed_for_observer_and_total_is_bounded(self):
        def sse(request):
            status, headers, raw = observer_reply(request)
            if request["method"] == "tools/call":
                value = observation()
                value["synthetic_bounded_diagnostic"] = "x" * (client.LINE_LIMIT + 1)
                payload = {
                    "jsonrpc": "2.0",
                    "id": request["id"],
                    "result": tool_result(value),
                }
                return (
                    200,
                    {"Content-Type": "text/event-stream"},
                    b"data: " + client.canonical(payload) + b"\n\n",
                )
            return status, headers, raw

        with peer(sse) as (port, _requests):
            report = connection(port).probe(observe_lesson07=True)
        self.assertEqual(report["status"], "OBSERVATION_COMPLETE")

        def oversized(request):
            if request["method"] == "tools/call":
                return (
                    200,
                    {
                        "Content-Type": "text/event-stream",
                        "Content-Length": str(client.RESPONSE_LIMIT + 1),
                    },
                    b"",
                )
            return observer_reply(request)

        state = client.ObservationState()
        with peer(oversized) as (port, requests):
            with self.assertRaises(client.ProbeError) as caught:
                connection(port, state=state).probe(observe_lesson07=True)
        self.assertEqual(caught.exception.code, "HTTP_DECLARED_SIZE")
        self.assertTrue(state.attempted)
        self.assertIsNone(state.completed)
        self.assertEqual(sum(r["body"]["method"] == "tools/call" for r in requests), 1)

        def large_discovery(request):
            status, headers, raw = default_reply(request)
            if request["method"] == "initialize":
                payload = json.loads(raw)
                payload["result"]["instructions"] = "x" * client.LINE_LIMIT
                return (
                    200,
                    {**headers, "Content-Type": "text/event-stream"},
                    b"data: " + client.canonical(payload) + b"\n\n",
                )
            return status, headers, raw

        with peer(large_discovery) as (port, _requests):
            with self.assertRaises(client.ProbeError) as caught:
                connection(port).probe()
        self.assertEqual(caught.exception.code, "HTTP_BODY_SIZE")

    def test_tool_timeout_is_attempted_unknown_completion_without_retry(self):
        def delayed(request):
            if request["method"] == "tools/call":
                time.sleep(0.3)
            return observer_reply(request)

        state = client.ObservationState()
        with peer(delayed) as (port, requests):
            with self.assertRaises(client.ProbeError) as caught:
                connection(port, timeout=0.08, state=state).probe(observe_lesson07=True)
        self.assertEqual(caught.exception.code, "REQUEST_TIMEOUT")
        self.assertTrue(state.attempted)
        self.assertIsNone(state.completed)
        self.assertFalse(state.response_received)
        self.assertEqual(sum(r["body"]["method"] == "tools/call" for r in requests), 1)

    def test_cli_retains_sanitized_tool_error_and_unknown_completion_without_retry(
        self,
    ):
        cause = "RuntimeError: synthetic plugin execution failure"
        secret = "OTHER_SYNTHETIC_CREDENTIAL"

        def failed(request):
            if request["method"] == "tools/call":
                return (
                    200,
                    {"Content-Type": "application/json"},
                    client.canonical(
                        {
                            "jsonrpc": "2.0",
                            "id": request["id"],
                            "result": {
                                "isError": True,
                                "content": [
                                    {
                                        "type": "text",
                                        "text": cause
                                        + "\nhttps://example.invalid/private "
                                        + TOKEN
                                        + " synthetic-session-1\nBearer "
                                        + secret,
                                    }
                                ],
                            },
                        }
                    ),
                )
            return observer_reply(request)

        with (
            tempfile.TemporaryDirectory() as directory,
            peer(failed) as (port, requests),
        ):
            output = Path(directory) / "report.json"
            stdout = io.StringIO()

            def from_fixture(_path, *, observe_lesson07, observation_state):
                return connection(port, state=observation_state).probe(
                    observe_lesson07=observe_lesson07
                )

            with (
                mock.patch.object(client, "probe_from_files", side_effect=from_fixture),
                mock.patch("sys.stdout", stdout),
            ):
                code = client.main(
                    [
                        "--identity-receipt",
                        str(Path(directory) / "identity.json"),
                        "--output",
                        str(output),
                        "--observe-lesson07",
                    ]
                )
            raw = output.read_text()
            report = json.loads(raw)
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "OBSERVATION_FAILED")
        self.assertEqual(report["error_code"], "OBSERVER_TOOL_ERROR")
        self.assertEqual(report["native_tool_calls"], 1)
        self.assertTrue(report["native_tool_attempted"])
        self.assertTrue(report["native_tool_response_received"])
        self.assertIsNone(report["native_tool_completed"])
        self.assertEqual(report["native_material_readback"], "UNVERIFIED")
        self.assertIn(cause, report["native_tool_error"]["sanitized_text"])
        self.assertEqual(report["native_tool_error"]["retained_text_blocks"], 1)
        self.assertFalse(report["native_tool_error"]["text_truncated"])
        for private in (
            TOKEN,
            secret,
            "synthetic-session-1",
            "example.invalid/private",
        ):
            self.assertNotIn(private, raw)
            self.assertNotIn(private, stdout.getvalue())
        self.assertNotIn(cause, stdout.getvalue())
        self.assertEqual(sum(r["body"]["method"] == "tools/call" for r in requests), 1)

    def test_error_redaction_precedes_truncation_and_removes_credentials_and_controls(
        self,
    ):
        secret = "SYNTHETIC_BOUNDARY_SECRET"
        prefix = "x" * (client.OBSERVER_ERROR_TEXT_LIMIT - 5)
        result = {
            "isError": True,
            "content": [{"type": "text", "text": prefix + secret}],
        }
        report = client.observer_error_diagnostic(result, (secret,))
        self.assertEqual(
            report["sanitized_text"],
            (prefix + "[REDACTED]")[: client.OBSERVER_ERROR_TEXT_LIMIT],
        )
        self.assertTrue(report["text_truncated"])
        for sensitive in (
            "Authorization: Basic " + secret,
            '"api_key": "' + secret + '"',
            "password = 'first line\n" + secret + "'",
            "client-secret=" + secret,
            "access_token=" + secret,
            "to\u200bken=" + secret,
            "Bea\x00rer\t" + secret,
            "https://user:" + secret + "@example.invalid/private",
        ):
            with self.subTest(sensitive=sensitive):
                result["content"][0]["text"] = "Cause: plugin failed\n" + sensitive
                report = client.observer_error_diagnostic(result, ())
                self.assertIn("Cause: plugin failed", report["sanitized_text"])
                self.assertNotIn(secret, report["sanitized_text"])
                self.assertTrue(
                    all(char.isprintable() for char in report["sanitized_text"])
                )

    def test_error_diagnostics_bound_blocks_and_ignore_non_error_and_nontext_values(
        self,
    ):
        result = {
            "isError": True,
            "content": [
                {"type": "image", "text": TOKEN},
                {"type": "text", "text": "\ud800\x1b\x00native cause\n"},
            ]
            + [{"type": "text", "text": "x" * 1000}] * 6
            + [{"type": "text", "text": TOKEN}],
            "structuredContent": {"message": TOKEN},
        }
        report = client.observer_error_diagnostic(result, ())
        self.assertEqual(
            len(report["sanitized_text"]), client.OBSERVER_ERROR_TEXT_LIMIT
        )
        self.assertEqual(report["retained_text_blocks"], 7)
        self.assertTrue(report["content_blocks_truncated"])
        self.assertTrue(report["text_truncated"])
        self.assertTrue(report["sanitized_text"].startswith("native cause"))
        self.assertTrue(all(char.isprintable() for char in report["sanitized_text"]))
        self.assertNotIn(TOKEN.encode(), client.canonical(report))
        for flag in (False, 0, 1, "true", None):
            self.assertIsNone(
                client.observer_error_diagnostic({**result, "isError": flag}, ())
            )
        report = client.observer_error_diagnostic(
            {"isError": True, "content": TOKEN}, ()
        )
        self.assertEqual(report["retained_text_blocks"], 0)
        self.assertEqual(report["sanitized_text"], "")

    def test_unsupported_wrapper_reports_only_shape_and_keeps_attempt_unknown(self):
        def wrapped(request):
            if request["method"] == "tools/call":
                wrapper = {
                    "success": True,
                    "output": tool_result()["content"][0]["text"]
                    + "\nUObject pin report: "
                    + TOKEN,
                    "logs": [TOKEN],
                    TOKEN: {TOKEN: TOKEN},
                }
                return (
                    200,
                    {"Content-Type": "application/json"},
                    client.canonical(
                        {
                            "jsonrpc": "2.0",
                            "id": request["id"],
                            "result": {
                                "isError": False,
                                "content": [
                                    {"type": "text", "text": json.dumps(wrapper)}
                                ],
                                TOKEN: TOKEN,
                            },
                        }
                    ),
                )
            return observer_reply(request)

        with (
            tempfile.TemporaryDirectory() as directory,
            peer(wrapped) as (port, requests),
        ):
            output = Path(directory) / "report.json"
            stdout = io.StringIO()

            def from_fixture(_path, *, observe_lesson07, observation_state):
                return connection(port, state=observation_state).probe(
                    observe_lesson07=observe_lesson07
                )

            with (
                mock.patch.object(client, "probe_from_files", side_effect=from_fixture),
                mock.patch("sys.stdout", stdout),
            ):
                code = client.main(
                    [
                        "--identity-receipt",
                        str(Path(directory) / "identity.json"),
                        "--output",
                        str(output),
                        "--observe-lesson07",
                    ]
                )
            report = json.loads(output.read_bytes())
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "OBSERVATION_FAILED")
        self.assertEqual(report["error_code"], "OBSERVER_RESULT_TAG")
        self.assertEqual(report["native_tool_calls"], 1)
        self.assertTrue(report["native_tool_attempted"])
        self.assertTrue(report["native_tool_response_received"])
        self.assertIsNone(report["native_tool_completed"])
        self.assertEqual(report["native_material_readback"], "UNVERIFIED")
        shape = report["native_tool_result_shape"]
        self.assertEqual(shape["unknown_field_count"], 1)
        block = shape["content_blocks"][0]
        self.assertTrue(block["text_json_parsed"])
        self.assertEqual(block["text_json"]["unknown_field_count"], 1)
        self.assertEqual(block["text_json"]["fields"]["success"], {"type": "boolean"})
        self.assertEqual(
            block["text_json"]["fields"]["logs"], {"type": "array", "count": 1}
        )
        self.assertEqual(block["text_json"]["fields"]["output"]["tag_occurrences"], 1)
        self.assertTrue(
            block["text_json"]["fields"]["output"]["has_uobject_pin_footer"]
        )
        self.assertNotIn(TOKEN.encode(), client.canonical(report))
        self.assertNotIn(TOKEN, stdout.getvalue())
        self.assertEqual(sum(r["body"]["method"] == "tools/call" for r in requests), 1)

    def test_shape_diagnostics_bound_blocks_and_never_echo_unknown_keys_or_types(self):
        shape = client.observer_result_shape(
            {
                "content": [{"type": TOKEN, TOKEN: TOKEN, "text": "\ud800"}] * 20,
                "structuredContent": {"command_result": TOKEN, TOKEN: TOKEN},
                TOKEN: TOKEN,
            }
        )
        self.assertEqual(shape["fields"]["content"], {"type": "array", "count": 20})
        self.assertEqual(len(shape["content_blocks"]), 8)
        self.assertTrue(shape["content_blocks_truncated"])
        self.assertTrue(
            all(block["content_type"] == "other" for block in shape["content_blocks"])
        )
        self.assertTrue(
            all(block["text_json_parsed"] is False for block in shape["content_blocks"])
        )
        self.assertEqual(shape["structured_content"]["unknown_field_count"], 1)
        self.assertEqual(
            shape["structured_content"]["fields"]["command_result"]["type"], "string"
        )
        self.assertNotIn(TOKEN.encode(), client.canonical(shape))
        self.assertLess(len(client.canonical(shape)), 4096)

    def test_untrusted_result_errors_duplicates_wrappers_and_identity_rejected(self):
        bad_results = []
        good = tool_result()
        bad_results.extend(
            [
                {**good, "isError": True},
                {**good, "isError": 0},
                {**good, "content": good["content"] * 2},
                {
                    **good,
                    "content": [
                        {"type": "text", "text": TOKEN + good["content"][0]["text"]}
                    ],
                },
                {**good, "structuredContent": {"output": good["content"][0]["text"]}},
                {
                    **good,
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({"output": good["content"][0]["text"]}),
                        }
                    ],
                },
            ]
        )
        for field, value in (
            ("pid", 1235),
            ("pid", True),
            ("project_file", "D:/other/project.uproject"),
            ("project", "D:/other"),
            ("world", "/Game/Other.Other"),
            ("status", "PASS"),
            (
                "observed_at_utc",
                (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
            ),
            (
                "observed_at_utc",
                (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            ),
            (
                "limitations",
                {**observation()["limitations"], "visual_acceptance": True},
            ),
            ("validation", {"visual_or_native_graph_acceptance": True}),
        ):
            bad_results.append(tool_result({**observation(), field: value}))
        wrong_hash = tool_result()
        wrong_hash["content"][0]["text"] = wrong_hash["content"][0]["text"].replace(
            client.OBSERVER_SHA256, "0" * 64
        )
        bad_results.append(wrong_hash)
        for bad in bad_results:

            def reply(request):
                if request["method"] == "tools/call":
                    return (
                        200,
                        {"Content-Type": "application/json"},
                        client.canonical(
                            {"jsonrpc": "2.0", "id": request["id"], "result": bad}
                        ),
                    )
                return observer_reply(request)

            state = client.ObservationState()
            with self.subTest(result=bad), peer(reply) as (port, requests):
                with self.assertRaises(client.ProbeError) as caught:
                    connection(port, state=state).probe(observe_lesson07=True)
                self.assertTrue(state.attempted)
                self.assertIsNone(state.completed)
                self.assertEqual(
                    sum(r["body"]["method"] == "tools/call" for r in requests), 1
                )
                self.assertNotIn(TOKEN, str(caught.exception))

    def test_cli_keeps_attempt_and_completion_after_post_call_file_recheck_failure(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt, discovery_path, output = (
                root / "identity.json",
                root / "config.json",
                root / "report.json",
            )

            def changed(request):
                if request["method"] == "tools/call":
                    receipt.write_bytes(receipt.read_bytes() + b" ")
                return observer_reply(request)

            with peer(changed) as (port, requests):
                receipt.write_bytes(client.canonical(identity(port)))
                discovery_path.write_bytes(client.canonical(config(port)))
                original = client.probe_from_files

                def from_fixture(path, **kwargs):
                    return original(path, discovery_path, **kwargs)

                stdout = io.StringIO()
                with (
                    mock.patch.object(client, "WINDOWS_HOST", True),
                    mock.patch.object(
                        client, "probe_from_files", side_effect=from_fixture
                    ),
                    mock.patch("sys.stdout", stdout),
                ):
                    code = client.main(
                        [
                            "--identity-receipt",
                            str(receipt),
                            "--output",
                            str(output),
                            "--observe-lesson07",
                        ]
                    )
            report = json.loads(output.read_bytes())
            self.assertEqual(code, 1)
            self.assertEqual(report["status"], "OBSERVATION_FAILED")
            self.assertEqual(report["error_code"], "INPUT_CHANGED")
            self.assertEqual(report["native_tool_calls"], 1)
            self.assertTrue(report["native_tool_attempted"])
            self.assertTrue(report["native_tool_completed"])
            self.assertEqual(report["native_material_readback"], "UNVERIFIED")
            self.assertIn("native_tool_calls=1", stdout.getvalue())
            self.assertEqual(
                sum(r["body"]["method"] == "tools/call" for r in requests), 1
            )
            self.assertNotIn(TOKEN.encode(), output.read_bytes())

    def test_cli_unexpected_failure_after_send_retains_unknown_completion(self):
        def failed(_identity, **kwargs):
            state = kwargs["observation_state"]
            state.attempted = True
            state.completed = None
            raise ValueError(TOKEN)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            stdout = io.StringIO()
            with (
                mock.patch.object(client, "probe_from_files", side_effect=failed),
                mock.patch("sys.stdout", stdout),
            ):
                code = client.main(
                    [
                        "--identity-receipt",
                        str(Path(directory) / "identity.json"),
                        "--output",
                        str(output),
                        "--observe-lesson07",
                    ]
                )
            report = json.loads(output.read_bytes())
            self.assertEqual(code, 1)
            self.assertEqual(report["error_code"], "UNEXPECTED_CLIENT_FAILURE")
            self.assertEqual(report["native_tool_calls"], 1)
            self.assertIsNone(report["native_tool_completed"])
            self.assertNotIn(TOKEN.encode(), output.read_bytes())
            self.assertNotIn(TOKEN, stdout.getvalue())


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

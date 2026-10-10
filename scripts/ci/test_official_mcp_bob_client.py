"""Synthetic MCP HTTP boundaries; never Editor, transport or native admission.

Only scripted stdlib HTTPConnection substitutes run here. The response bodies,
session identifiers and counter observations are explicitly synthetic data.
"""

import json
import tempfile
import unittest
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from unittest import mock

from scripts.ci import official_mcp_bob_client as client
from scripts.ue import test_official_mcp_bob_operation as operation_fixtures


class SyntheticResponse:
    def __init__(self, status=200, document=None, *, raw=None, headers=None):
        self.status = status
        self.reason = "SYNTHETIC_TEST_ONLY"
        self.body = (
            json.dumps(document, allow_nan=False).encode() if raw is None else raw
        )
        self.header_rows = (
            [("Content-Type", "application/json")] if headers is None else list(headers)
        )
        self.read_sizes = []

    def getheaders(self):
        return list(self.header_rows)

    def getheader(self, name, default=None):
        values = [
            value
            for key, value in self.header_rows
            if key.casefold() == name.casefold()
        ]
        return ", ".join(values) if values else default

    def read(self, amount=None):
        self.read_sizes.append(amount)
        selected = self.body if amount is None else self.body[:amount]
        self.body = self.body[len(selected) :]
        return selected


class SyntheticHttpScript:
    """Supply one response per request, recording all attempts and closures."""

    def __init__(self, responses, *, close_error=None):
        self.responses = list(responses)
        self.close_error = close_error
        self.connections = []
        self.requests = []

    def connect(self, host, port=None, **options):
        script = self

        class Connection:
            def __init__(self):
                self.closed = False
                self.request_row = None

            def request(self, method, path, body=None, headers=None):
                self.request_row = {
                    "method": method,
                    "path": path,
                    "body": body,
                    "headers": dict(headers or {}),
                }
                script.requests.append(self.request_row)

            def getresponse(self):
                if not script.responses:
                    raise AssertionError("unexpected retry or extra synthetic request")
                response = script.responses.pop(0)
                if callable(response):
                    response = response(self.request_row)
                if isinstance(response, Exception):
                    raise response
                return response

            def close(self):
                self.closed = True
                if script.close_error is not None:
                    raise script.close_error

        connection = Connection()
        self.connections.append((host, port, options, connection))
        return connection


SESSION_ID = "a" * 32
SYNTHETIC_PACKET = {
    "result": {"status": "REVIEW_REQUIRED", "synthetic_test_only": True},
    "proof": {"synthetic_test_only": True},
    "receipt": {"synthetic_test_only": True},
    "capture": {"synthetic_test_only": True},
}


def rpc_response(result=None, *, error=None, status=200, headers=None):
    def respond(request):
        sent = json.loads(request["body"])
        document = {"jsonrpc": "2.0", "id": sent["id"]}
        document["error" if error is not None else "result"] = (
            error if error is not None else result
        )
        return SyntheticResponse(status, document, headers=headers)

    return respond


def initial_response(**result_changes):
    result = {
        "protocolVersion": "2025-06-18",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "SYNTHETIC_TEST_ONLY", "version": "0"},
        **result_changes,
    }
    return rpc_response(
        result,
        headers=[("Content-Type", "application/json"), ("Mcp-Session-Id", SESSION_ID)],
    )


def fixed_tool():
    return {
        "name": "YacsBobInspection.InspectAcceptedCheckpoint",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
            "maxProperties": 0,
        },
    }


def packet_response(packet):
    return rpc_response({"content": [{"type": "text", "text": json.dumps(packet)}]})


def boundary_denial(name):
    if name != client.TOOL:
        return rpc_response(
            error={"code": -32602, "message": f"Unknown tool: {name}"}, status=400
        )
    return rpc_response(
        {
            "isError": True,
            "content": [
                {
                    "type": "text",
                    "text": "YacsBobInspection requires an explicit empty arguments object.",
                }
            ],
        }
    )


class OfficialMcpBobClientTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.evidence = self.root / client.SESSION_DIR
        self.evidence.mkdir(parents=True)
        (self.root / "Content").mkdir()
        (self.root / "Config").mkdir()
        (self.root / "YetAnotherCyclingSim.uproject").write_bytes(
            b'{"synthetic_test_only":true}'
        )
        for target in (client, client.operation):
            patcher = mock.patch.object(target, "ROOT", self.root)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.context = {
            "exact_sha": "b" * 40,
            "marker": {"owned_editor_pid": 123},
            "sources": {"synthetic_source.py": "c" * 64},
            "operation": {},
        }
        self.write_counter(0)

    def write_counter(self, count, **extra):
        document = {
            "schema_version": 1,
            "exact_sha": self.context["exact_sha"],
            "body_invocation_count": count,
            **extra,
        }
        (self.root / client.COUNTER_FILE).write_text(json.dumps(document))
        return document

    @contextmanager
    def transport(self, responses, *, initialized=False):
        script = SyntheticHttpScript(responses)
        with mock.patch.object(client.http.client, "HTTPConnection", script.connect):
            transport = client._Transport()
            if initialized:
                transport.session_id = SESSION_ID
            try:
                yield transport, script
            finally:
                transport.close()
        self.assertTrue(all(row[3].closed for row in script.connections))

    def fixed_script(self, final=None, *, first_denial=None):
        responses = [
            initial_response(),
            SyntheticResponse(202, raw=b"", headers=[]),
            rpc_response({"tools": [fixed_tool()]}),
        ]
        for index, (_label, name, _arguments) in enumerate(client.DENIAL_CASES):
            if index == 0 and first_denial is not None:
                responses.append(first_denial)
            else:
                responses.append(boundary_denial(name))
        responses.append(final or packet_response(SYNTHETIC_PACKET))
        return SyntheticHttpScript(responses)

    def run_script(self, script, *, unchanged=None):
        # Only host admission/artifact boundaries are substituted here. The
        # actual HTTP sequence and real bounded local native-counter reader run.
        with (
            mock.patch.object(client.http.client, "HTTPConnection", script.connect),
            mock.patch.object(client, "_load_context", return_value=self.context),
            mock.patch.object(client, "_verify_bundle", return_value={}),
            mock.patch.object(client, "_unchanged", side_effect=unchanged),
        ):
            return client.run_fixed_session()

    def blocked_receipt(self):
        document = json.loads((self.root / client.RECEIPT_FILE).read_bytes())
        self.assertEqual(document["status"], "TRANSPORT_BLOCKED")
        for flag in (
            "official_mcp_transport_verified",
            "official_mcp_admitted",
            "native_automation_verified",
            "persistent_world_mutation",
            "performance_pass",
        ):
            self.assertIs(document[flag], False)
        return document

    def test_initialize_list_and_call_use_exact_loopback_sequence(self):
        with self.transport(
            [
                initial_response(),
                SyntheticResponse(202, raw=b"", headers=[]),
                rpc_response({"tools": [fixed_tool()]}),
                packet_response(SYNTHETIC_PACKET),
            ]
        ) as (transport, script):
            transport.initialize()
            self.assertEqual(transport.list_fixed_tool(), fixed_tool())
            packet = client._valid_result(transport.call(client.TOOL, {}))
            self.assertEqual(packet, SYNTHETIC_PACKET)
            self.assertEqual(script.connections[0][:2], ("127.0.0.1", 18784))
            self.assertEqual(script.connections[0][2]["timeout"], 180)
            self.assertEqual(len(script.connections), 1)
            messages = [json.loads(row["body"]) for row in script.requests]
            self.assertEqual(
                [message["method"] for message in messages],
                ["initialize", "notifications/initialized", "tools/list", "tools/call"],
            )
            self.assertEqual(
                [message.get("id") for message in messages], [1, None, 2, 3]
            )
            self.assertEqual(
                messages[-1]["params"], {"name": client.TOOL, "arguments": {}}
            )
            for index, row in enumerate(script.requests):
                self.assertEqual((row["method"], row["path"]), ("POST", "/mcp"))
                self.assertEqual(row["headers"]["Accept"], "application/json")
                if index:
                    self.assertEqual(row["headers"]["Mcp-Session-Id"], SESSION_ID)
                    self.assertEqual(
                        row["headers"]["Mcp-Protocol-Version"], "2025-06-18"
                    )

    def test_initialize_requires_exact_session_and_negotiated_protocol(self):
        for session in (None, "A" * 32, "a" * 31, "a" * 33, "g" * 32):
            with self.subTest(session=session):
                headers = [("Content-Type", "application/json")]
                if session is not None:
                    headers.append(("Mcp-Session-Id", session))
                response = rpc_response(
                    {"protocolVersion": client.PROTOCOL, "capabilities": {"tools": {}}},
                    headers=headers,
                )
                with self.transport([response]) as (transport, script):
                    with self.assertRaises(ValueError):
                        transport.initialize()
                    self.assertEqual(len(script.requests), 1)
        for changes in (
            {"protocolVersion": "2024-11-05"},
            {"capabilities": {}},
            {"capabilities": {"tools": True}},
        ):
            with (
                self.subTest(changes=changes),
                self.transport([initial_response(**changes)]) as (transport, script),
            ):
                with self.assertRaises(ValueError):
                    transport.initialize()
                self.assertEqual(len(script.requests), 1)

    def test_initialized_notification_requires_empty_202_and_stable_headers(self):
        for response in (
            SyntheticResponse(200, raw=b"", headers=[]),
            SyntheticResponse(202, raw=b"{}", headers=[]),
            SyntheticResponse(202, raw=b"", headers=[("Mcp-Session-Id", "b" * 32)]),
            SyntheticResponse(
                202, raw=b"", headers=[("Mcp-Protocol-Version", "foreign")]
            ),
        ):
            with (
                self.subTest(status=response.status, headers=response.header_rows),
                self.transport([initial_response(), response]) as (transport, script),
            ):
                with self.assertRaises(ValueError):
                    transport.initialize()
                self.assertEqual(len(script.requests), 2)

    def test_duplicate_nonfinite_and_nonobject_json_are_rejected_without_retry(self):
        for raw in (
            b'{"jsonrpc":"2.0","id":1,"result":{},"result":{}}',
            b'{"jsonrpc":"2.0","id":1,"result":{"value":NaN}}',
            b'{"jsonrpc":"2.0","id":1,"result":{"value":Infinity}}',
            b"[]",
            b"\xff",
        ):
            with (
                self.subTest(raw=raw),
                self.transport([SyntheticResponse(raw=raw)], initialized=True) as (
                    transport,
                    script,
                ),
            ):
                with self.assertRaises(ValueError):
                    transport.call(client.TOOL, {})
                self.assertEqual(len(script.requests), 1)

    def test_response_identity_requires_integer_id_and_one_result_or_error(self):
        for fields in (
            {"id": True},
            {"id": "1"},
            {"id": 2},
            {"jsonrpc": "1.0"},
            {"error": {"code": -1, "message": "SYNTHETIC ambiguous"}},
        ):
            with self.subTest(fields=fields):
                document = {"jsonrpc": "2.0", "id": 1, "result": {}, **fields}
                with self.transport(
                    [SyntheticResponse(document=document)], initialized=True
                ) as (transport, script):
                    with self.assertRaises(ValueError):
                        transport.call(client.TOOL, {})
                    self.assertEqual(len(script.requests), 1)
        with (
            self.transport(
                [SyntheticResponse(document={"jsonrpc": "2.0", "id": 1})],
                initialized=True,
            ) as (transport, _script),
            self.assertRaises(ValueError),
        ):
            transport.call(client.TOOL, {})

    def test_redirect_error_status_and_event_stream_are_never_followed(self):
        for status, headers in (
            (301, [("Location", "http://synthetic.invalid/")]),
            (302, [("Location", "/other")]),
            (500, [("Content-Type", "application/json")]),
            (200, [("Content-Type", "text/event-stream")]),
            (200, [("Content-Type", "text/plain")]),
        ):
            with self.subTest(status=status, headers=headers):
                response = SyntheticResponse(
                    status, {"jsonrpc": "2.0", "id": 1, "result": {}}, headers=headers
                )
                with self.transport([response], initialized=True) as (
                    transport,
                    script,
                ):
                    with self.assertRaises(ValueError):
                        transport.call(client.TOOL, {})
                    self.assertEqual(len(script.requests), 1)
                    self.assertEqual(len(script.connections), 1)
                    self.assertEqual(response.read_sizes, [])

    def test_response_headers_body_bounds_and_size_consistency_are_enforced(self):
        for headers, raw in (
            (
                [
                    ("Content-Type", "application/json"),
                    ("content-type", "application/json"),
                ],
                b"{}",
            ),
            (
                [("Content-Type", "application/json"), ("Content-Encoding", "gzip")],
                b"{}",
            ),
            ([("Content-Type", "application/json"), ("Content-Length", "-1")], b"{}"),
            ([("Content-Type", "application/json"), ("Content-Length", "129")], b"{}"),
            ([("Content-Type", "application/json"), ("Content-Length", "1")], b"{}"),
            (
                [("Content-Type", "application/json"), ("Transfer-Encoding", "gzip")],
                b"{}",
            ),
            (
                [
                    ("Content-Type", "application/json"),
                    ("Transfer-Encoding", "chunked"),
                    ("Content-Length", "2"),
                ],
                b"{}",
            ),
            ([("Content-Type", "application/json")], b"x" * 129),
            (
                [("Content-Type", "application/json"), ("Mcp-Session-Id", "b" * 32)],
                b"{}",
            ),
            (
                [
                    ("Content-Type", "application/json"),
                    ("Mcp-Protocol-Version", "foreign"),
                ],
                b"{}",
            ),
        ):
            with (
                self.subTest(headers=headers),
                mock.patch.object(client, "MAX_RESPONSE_BYTES", 128),
            ):
                response = SyntheticResponse(raw=raw, headers=headers)
                with self.transport([response], initialized=True) as (
                    transport,
                    script,
                ):
                    with self.assertRaises(ValueError):
                        transport.call(client.TOOL, {})
                    self.assertEqual(len(script.requests), 1)
                    self.assertTrue(all(size == 129 for size in response.read_sizes))

    def test_http400_is_accepted_only_as_explicit_json_rpc_error(self):
        with self.transport(
            [boundary_denial("YacsBobInspection.Unknown")],
            initialized=True,
        ) as (transport, _script):
            self.assertEqual(
                client._explicit_denial(
                    transport.call("YacsBobInspection.Unknown", {}),
                    label="unknown_operation",
                    name="YacsBobInspection.Unknown",
                ),
                "UNKNOWN_TOOL",
            )
        with (
            self.transport([rpc_response({}, status=400)], initialized=True) as (
                transport,
                _script,
            ),
            self.assertRaisesRegex(ValueError, "explicit JSON-RPC error"),
        ):
            transport.call(client.TOOL, {})

    def test_tool_inventory_schema_and_pagination_cannot_expand_fixed_operation(self):
        valid = fixed_tool()
        for tools, extra in (
            ([], {}),
            ([valid, {"name": "execute_python"}], {}),
            ([dict(valid, name="StockTools.Read")], {}),
            ([valid], {"nextCursor": "SYNTHETIC another page"}),
            (
                [
                    dict(
                        valid,
                        inputSchema={
                            **valid["inputSchema"],
                            "additionalProperties": True,
                        },
                    )
                ],
                {},
            ),
            (
                [
                    dict(
                        valid,
                        inputSchema={**valid["inputSchema"], "maxProperties": False},
                    )
                ],
                {},
            ),
            (
                [
                    dict(
                        valid,
                        inputSchema={**valid["inputSchema"], "properties": {"map": {}}},
                    )
                ],
                {},
            ),
        ):
            with (
                self.subTest(tools=tools, extra=extra),
                self.transport(
                    [rpc_response({"tools": tools, **extra})], initialized=True
                ) as (transport, _script),
                self.assertRaises(ValueError),
            ):
                transport.list_fixed_tool()

    def test_unknown_tool_denial_matches_exact_name_and_official_invalid_params(self):
        name = "YacsBobInspection.Unknown"
        valid_error = {"error": {"code": -32602, "message": f"Unknown tool: {name}"}}
        self.assertEqual(
            client._explicit_denial(valid_error, label="unknown_operation", name=name),
            "UNKNOWN_TOOL",
        )
        for response in (
            {"error": {"code": -32603, "message": f"Unknown tool: {name}"}},
            {"error": {"code": -32602.0, "message": f"Unknown tool: {name}"}},
            {"error": {"code": True, "message": f"Unknown tool: {name}"}},
            {
                "error": {
                    "code": -32602,
                    "message": "Unknown tool: YacsBobInspection.Other",
                }
            },
            {"error": {"code": -32602, "message": "SYNTHETIC server is not ready"}},
            {"error": {"code": -32000, "message": "SYNTHETIC invalid session"}},
            {"error": {"code": -32603, "message": "SYNTHETIC internal exception"}},
            {
                "error": {"code": -32602, "message": f"Unknown tool: {name}"},
                "result": {},
            },
            {
                "result": {
                    "isError": True,
                    "content": [
                        {
                            "type": "text",
                            "text": "YacsBobInspection requires an explicit empty arguments object.",
                        }
                    ],
                }
            },
        ):
            with self.subTest(response=response), self.assertRaises(ValueError):
                client._explicit_denial(response, label="unknown_operation", name=name)

    def test_argument_denial_requires_exact_single_native_boundary_text(self):
        text = "YacsBobInspection requires an explicit empty arguments object."
        valid = {
            "result": {"isError": True, "content": [{"type": "text", "text": text}]}
        }
        self.assertEqual(
            client._explicit_denial(valid, label="field", name=client.TOOL),
            "ARGUMENTS_REJECTED",
        )
        for response in (
            {"error": {"code": -32602, "message": f"Unknown tool: {client.TOOL}"}},
            {"error": {"code": -32603, "message": "SYNTHETIC internal error"}},
            {
                "result": {
                    "isError": True,
                    "content": [
                        {
                            "type": "text",
                            "text": "SYNTHETIC native session is not ready",
                        }
                    ],
                }
            },
            {
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": "SYNTHETIC invalid session"}],
                }
            },
            {
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": text.rstrip(".")}],
                }
            },
            {
                "result": {
                    "isError": True,
                    "content": [
                        {"type": "text", "text": text},
                        {"type": "text", "text": "SYNTHETIC extra error"},
                    ],
                }
            },
            {"result": {"isError": True, "content": []}},
            {"result": {"isError": 1, "content": [{"type": "text", "text": text}]}},
            {"result": {"isError": True, "content": [{"type": "image", "text": text}]}},
            {**valid, "error": {"code": -32602, "message": "SYNTHETIC ambiguous"}},
        ):
            with self.subTest(response=response), self.assertRaises(ValueError):
                client._explicit_denial(response, label="field", name=client.TOOL)

    def test_denial_classifier_cannot_accept_label_name_outside_fixed_sequence(self):
        response = {
            "error": {
                "code": -32602,
                "message": "Unknown tool: YacsBobInspection.Unknown",
            }
        }
        for label, name in (
            ("not_a_fixed_case", "YacsBobInspection.Unknown"),
            ("field", "YacsBobInspection.Unknown"),
            ("unknown_operation", "SceneTools.get_current_level"),
        ):
            with self.subTest(label=label, name=name), self.assertRaises(ValueError):
                client._explicit_denial(response, label=label, name=name)

    def test_valid_response_requires_one_text_json_exact_four_artifact_packet(self):
        def response(content, **extra):
            return {"result": {"content": content, **extra}}

        valid = [{"type": "text", "text": json.dumps(SYNTHETIC_PACKET)}]
        self.assertEqual(client._valid_result(response(valid)), SYNTHETIC_PACKET)
        for value in (
            {"error": {"code": -1, "message": "SYNTHETIC denied"}},
            response(valid, isError=True),
            response(valid, isError=0),
            response([]),
            response(valid * 2),
            response([{**valid[0], "type": "image"}]),
            response([{"type": "text", "text": "[]"}]),
            response(
                [
                    {
                        "type": "text",
                        "text": '{"result":{},"result":{},"proof":{},"receipt":{},"capture":{}}',
                    }
                ]
            ),
            response(
                [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {**SYNTHETIC_PACKET, "caller_path": "foreign"}
                        ),
                    }
                ]
            ),
            response(
                [
                    {
                        "type": "text",
                        "text": json.dumps({**SYNTHETIC_PACKET, "capture": None}),
                    }
                ]
            ),
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                client._valid_result(value)

    def test_counter_requires_exact_revision_integer_count_and_closed_fields(self):
        self.assertEqual(client._counter(self.context, 0), self.write_counter(0))
        for document in (
            self.write_counter(True),
            self.write_counter("0"),
            self.write_counter(1),
            self.write_counter(0, exact_sha="0" * 40),
            self.write_counter(0, owned_editor_pid=123),
        ):
            with self.subTest(document=document):
                (self.root / client.COUNTER_FILE).write_text(json.dumps(document))
                with self.assertRaises(ValueError):
                    client._counter(self.context, 0)

    def test_counter_symlink_and_duplicate_json_never_become_native_proof(self):
        counter = self.root / client.COUNTER_FILE
        counter.write_bytes(
            b'{"schema_version":1,"exact_sha":"'
            + b"b" * 40
            + b'","body_invocation_count":0,"body_invocation_count":0}'
        )
        with self.assertRaises(ValueError):
            client._counter(self.context, 0)
        outside = self.root / "SYNTHETIC-outside-counter.json"
        outside.write_text(json.dumps(self.write_counter(0)))
        counter.unlink()
        counter.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink/reparse"):
            client._counter(self.context, 0)

    def test_invalid_trusted_environment_and_marker_reject_before_source_or_network(
        self,
    ):
        script = SyntheticHttpScript([])
        with (
            mock.patch.object(client, "WINDOWS_HOST", False),
            mock.patch.object(client.http.client, "HTTPConnection", script.connect),
            self.assertRaisesRegex(ValueError, "trusted Windows owner host"),
        ):
            client.run_fixed_session()
        marker = {
            "schema_version": 1,
            "exact_sha": self.context["exact_sha"],
            "project_root": str(self.root),
            "owned_editor_pid": 123,
            "source_sha256": {},
            "session_context_sha256": "d" * 64,
        }
        environment = {
            "YACS_MCP_BOB_PROJECT_ROOT": str(self.root),
            "YACS_MCP_BOB_EXPECTED_HEAD": self.context["exact_sha"],
            "YACS_MCP_BOB_OWNED_EDITOR_PID": "123",
        }
        # Session checkout isolation has its own real-Git fixture suite. This
        # unit fixture isolates the client's additional host marker/env gate.
        with (
            mock.patch.object(client, "WINDOWS_HOST", True),
            mock.patch.object(client.session, "ROOT", self.root),
            mock.patch.object(client.session, "_assert_isolated_root"),
            mock.patch.object(client, "_source_hashes") as sources,
            mock.patch.object(client.http.client, "HTTPConnection", script.connect),
        ):
            for changed_env in (
                {"YACS_MCP_BOB_EXPECTED_HEAD": "bad"},
                {"YACS_MCP_BOB_OWNED_EDITOR_PID": "0"},
                {"YACS_MCP_BOB_PROJECT_ROOT": str(self.root / "foreign")},
            ):
                with (
                    self.subTest(environment=changed_env),
                    mock.patch.dict(client.os.environ, {**environment, **changed_env}),
                    self.assertRaises(ValueError),
                ):
                    client.run_fixed_session()
            for fields in (
                {"schema_version": True},
                {"exact_sha": "0" * 40},
                {"project_root": str(self.root / "foreign")},
                {"owned_editor_pid": True},
                {"caller_path": "foreign"},
            ):
                (self.root / client.MARKER_FILE).write_text(
                    json.dumps({**marker, **fields})
                )
                with (
                    self.subTest(marker=fields),
                    mock.patch.dict(client.os.environ, environment),
                    self.assertRaises(ValueError),
                ):
                    client.run_fixed_session()
            sources.assert_not_called()
            sources.return_value = {}
            base_context = {
                "schema_version": 1,
                "exact_sha": self.context["exact_sha"],
                "source_sha256": {},
                "profile_sha256": client.operation.PROFILE_SHA256,
                "profile_source_sha": client.operation.PROFILE_SOURCE_SHA,
                "consumer_source_sha": client.operation.CONSUMER_SOURCE_SHA,
                "consumer_assets": [],
                "landscape": {
                    "path": client.operation.MAP_PACKAGE
                    + ".Map:PersistentLevel.Landscape_SYNTHETIC",
                    "class_path": client.operation.LANDSCAPE_CLASS,
                },
            }
            with mock.patch.object(client.operation, "_sources") as operation_sources:
                for fields in (
                    {"schema_version": True},
                    {
                        "landscape": {
                            "path": "/Game/Foreign.Map:Actor",
                            "class_path": client.operation.LANDSCAPE_CLASS,
                        }
                    },
                    {
                        "landscape": {
                            **base_context["landscape"],
                            "class_path": "/Script/Engine.Actor",
                        }
                    },
                    {
                        "landscape": {
                            **base_context["landscape"],
                            "caller_path": "foreign",
                        }
                    },
                ):
                    context_raw = json.dumps({**base_context, **fields}).encode()
                    (self.evidence / "session-context.json").write_bytes(context_raw)
                    (self.root / client.MARKER_FILE).write_text(
                        json.dumps(
                            {
                                **marker,
                                "session_context_sha256": client._digest(context_raw),
                            }
                        )
                    )
                    with (
                        self.subTest(operation_context=fields),
                        mock.patch.dict(client.os.environ, environment),
                        self.assertRaises(ValueError),
                    ):
                        client.run_fixed_session()
                operation_sources.assert_not_called()
        self.assertEqual(script.connections, [])
        self.assertFalse((self.root / client.RECEIPT_FILE).exists())

    def test_fixed_sequence_keeps_counter_zero_through_denials_and_invokes_once(self):
        def valid(request):
            self.assertEqual(self.write_counter(1)["body_invocation_count"], 1)
            return packet_response(SYNTHETIC_PACKET)(request)

        script = self.fixed_script(final=valid)
        receipt = self.run_script(script)
        self.assertEqual(
            receipt["status"], "LOCAL_TRANSPORT_AND_BOB_ARTIFACTS_VERIFIED"
        )
        self.assertEqual(receipt["body_invocation_count"], 1)
        self.assertEqual(len(receipt["denials"]), 22)
        self.assertTrue(
            all(row["body_invocation_count"] == 0 for row in receipt["denials"])
        )
        for flag in (
            "official_mcp_admitted",
            "native_automation_verified",
            "persistent_world_mutation",
            "performance_pass",
        ):
            self.assertIs(receipt[flag], False)
        requests = [json.loads(row["body"]) for row in script.requests]
        self.assertEqual(len(requests), 3 + 22 + 1)
        for request, (_label, name, arguments) in zip(
            requests[3:-1], client.DENIAL_CASES
        ):
            expected = {"name": name}
            if arguments is not client._MISSING_ARGUMENTS:
                expected["arguments"] = arguments
            self.assertEqual(request["params"], expected)
        for row, (_label, name, _arguments) in zip(
            receipt["denials"], client.DENIAL_CASES
        ):
            self.assertEqual(
                row["expected_category"],
                "UNKNOWN_TOOL" if name != client.TOOL else "ARGUMENTS_REJECTED",
            )
        by_case = {
            row["case"]: request["params"]
            for row, request in zip(receipt["denials"], requests[3:-1])
        }
        self.assertNotIn("arguments", by_case["missing_arguments"])
        self.assertIn("arguments", by_case["null"])
        self.assertIsNone(by_case["null"]["arguments"])
        for case in ("policy", "evidence_root", "receipt_path"):
            self.assertIn(case, by_case[case]["arguments"])
        self.assertEqual(requests[-1]["params"], {"name": client.TOOL, "arguments": {}})
        self.assertTrue(script.connections[0][3].closed)
        self.assertNotIn("SYNTHETIC denied", json.dumps(receipt))

    def test_denial_that_changes_counter_aborts_before_valid_call(self):
        def denial(request):
            self.write_counter(1)
            return boundary_denial("YacsBobInspection.Unknown")(request)

        script = self.fixed_script(first_denial=denial)
        with self.assertRaisesRegex(ValueError, "invocation counter"):
            self.run_script(script)
        receipt = self.blocked_receipt()
        self.assertIs(receipt["valid_call_attempted"], False)
        self.assertEqual(receipt["failure_stage"], "DENIAL_COUNTER")
        self.assertEqual(receipt["failure_denial_case"], "unknown_operation")
        self.assertEqual(receipt["error_code"], "BODY_COUNTER_MISMATCH")
        self.assertEqual(len(script.requests), 4)
        self.assertTrue(script.connections[0][3].closed)

    def test_denial_that_creates_bundle_aborts_even_with_zero_counter(self):
        def denial(request):
            (self.evidence / "bundle").mkdir()
            return boundary_denial("YacsBobInspection.Unknown")(request)

        script = self.fixed_script(first_denial=denial)
        with self.assertRaisesRegex(ValueError, "Denied request entered"):
            self.run_script(script)
        self.assertIs(self.blocked_receipt()["valid_call_attempted"], False)
        self.assertEqual(len(script.requests), 4)

    def test_internal_readiness_or_session_error_with_zero_counter_never_counts_as_denial(
        self,
    ):
        for code, message in (
            (-32603, "SYNTHETIC internal error"),
            (-32602, "SYNTHETIC server not ready"),
            (-32000, "SYNTHETIC invalid session"),
        ):
            with self.subTest(code=code, message=message):
                script = self.fixed_script(
                    first_denial=rpc_response(
                        error={"code": code, "message": message}, status=400
                    )
                )
                with self.assertRaises(ValueError):
                    self.run_script(script)
                receipt = self.blocked_receipt()
                self.assertEqual(receipt["denials"], [])
                self.assertIs(receipt["valid_call_attempted"], False)
                self.assertEqual(
                    client._counter(self.context, 0)["body_invocation_count"], 0
                )
                self.assertEqual(len(script.requests), 4)
                self.assertTrue(script.connections[0][3].closed)
                (self.root / client.RECEIPT_FILE).unlink()

    def test_uncertain_valid_call_is_never_retried_and_records_attempt_before_dispatch(
        self,
    ):
        def uncertain(_request):
            self.write_counter(1)
            raise TimeoutError("SYNTHETIC_PRIVATE_MESSAGE")

        script = self.fixed_script(final=uncertain)
        with self.assertRaises(TimeoutError):
            self.run_script(script)
        receipt = self.blocked_receipt()
        self.assertIs(receipt["valid_call_attempted"], True)
        self.assertEqual(len(script.requests), 26)
        self.assertEqual(len(script.connections), 1)
        self.assertTrue(script.connections[0][3].closed)
        self.assertNotIn("SYNTHETIC_PRIVATE_MESSAGE", json.dumps(receipt))
        self.assertEqual(receipt["failure_stage"], "VALID_CALL")
        self.assertEqual(receipt["error_category"], "TIMEOUT")
        self.assertEqual(receipt["error_code"], "UNCLASSIFIED_LOCAL_CHECK")

    def test_counter_zero_after_valid_response_cannot_certify_capture(self):
        script = self.fixed_script()
        with self.assertRaisesRegex(ValueError, "invocation counter"):
            self.run_script(script)
        receipt = self.blocked_receipt()
        self.assertIs(receipt["valid_call_attempted"], True)
        self.assertEqual(receipt["failure_stage"], "BODY_COUNTER")
        self.assertEqual(receipt["error_code"], "BODY_COUNTER_MISMATCH")
        self.assertEqual(len(script.requests), 26)

    def test_existing_receipt_is_preserved_before_connection_or_request(self):
        path = self.root / client.RECEIPT_FILE
        path.write_bytes(b"SYNTHETIC prior transport evidence")
        script = self.fixed_script()
        with self.assertRaises(FileExistsError):
            self.run_script(script)
        self.assertEqual(path.read_bytes(), b"SYNTHETIC prior transport evidence")
        self.assertEqual(script.connections, [])
        self.assertEqual(script.requests, [])

    def test_nonzero_initial_counter_stops_before_network_and_receipt(self):
        self.write_counter(1)
        script = self.fixed_script()
        with self.assertRaisesRegex(ValueError, "invocation counter"):
            self.run_script(script)
        self.assertEqual(script.connections, [])
        self.assertFalse((self.root / client.RECEIPT_FILE).exists())

    def test_final_counter_drift_cannot_publish_success_after_artifact_validation(self):
        def valid(request):
            self.write_counter(1)
            return packet_response(SYNTHETIC_PACKET)(request)

        script = self.fixed_script(final=valid)
        with self.assertRaisesRegex(ValueError, "invocation counter"):
            self.run_script(script, unchanged=lambda *_: self.write_counter(2))
        receipt = self.blocked_receipt()
        self.assertEqual(receipt["failure_stage"], "FINAL_COUNTER")
        self.assertEqual(receipt["error_code"], "BODY_COUNTER_MISMATCH")
        self.assertEqual(len(script.requests), 26)

    def test_conservation_rejection_after_valid_call_leaves_blocked_receipt(self):
        def valid(request):
            self.write_counter(1)
            return packet_response(SYNTHETIC_PACKET)(request)

        def changed_source(*_args):
            raise ValueError("SYNTHETIC trusted source drift")

        script = self.fixed_script(final=valid)
        with self.assertRaisesRegex(ValueError, "source drift"):
            self.run_script(script, unchanged=changed_source)
        receipt = self.blocked_receipt()
        self.assertEqual(receipt["failure_stage"], "CONSERVATION")
        self.assertEqual(receipt["error_category"], "GUARD_REJECTED")
        self.assertEqual(receipt["error_code"], "UNCLASSIFIED_LOCAL_CHECK")
        self.assertNotIn("SYNTHETIC trusted source drift", json.dumps(receipt))
        self.assertEqual(len(script.requests), 26)

    def test_close_failure_preserves_first_failure_and_never_logs_private_exception(
        self,
    ):
        def valid(request):
            self.write_counter(1)
            return packet_response(SYNTHETIC_PACKET)(request)

        def changed_source(*_args):
            raise ValueError(
                "Persistent project/profile bytes changed during MCP proof"
            )

        script = self.fixed_script(final=valid)
        script.close_error = OSError("SYNTHETIC_SECRET_TOKEN_CLOSE")
        with self.assertRaisesRegex(ValueError, "Persistent project/profile"):
            self.run_script(script, unchanged=changed_source)
        receipt = self.blocked_receipt()
        self.assertEqual(receipt["failure_stage"], "CONSERVATION")
        self.assertEqual(receipt["error_type"], "ValueError")
        self.assertEqual(receipt["error_code"], "PERSISTENT_INPUT_DRIFT")
        self.assertEqual(receipt["secondary_close_error_category"], "HTTP_TRANSPORT")
        self.assertEqual(
            receipt["secondary_close_error_code"], "TRANSPORT_CLOSE_FAILED"
        )
        self.assertNotIn("SYNTHETIC_SECRET_TOKEN_CLOSE", json.dumps(receipt))
        self.assertEqual(len(script.requests), 26)
        self.assertEqual(len(script.connections), 1)
        self.assertTrue(script.connections[0][3].closed)

    def test_close_only_failure_blocks_an_otherwise_verified_session(self):
        def valid(request):
            self.write_counter(1)
            return packet_response(SYNTHETIC_PACKET)(request)

        script = self.fixed_script(final=valid)
        script.close_error = OSError("SYNTHETIC_SECRET_TOKEN_CLOSE_ONLY")
        with self.assertRaises(OSError):
            self.run_script(script)
        receipt = self.blocked_receipt()
        self.assertEqual(receipt["failure_stage"], "TRANSPORT_CLOSE")
        self.assertEqual(receipt["error_category"], "HTTP_TRANSPORT")
        self.assertNotIn("SYNTHETIC_SECRET_TOKEN_CLOSE_ONLY", json.dumps(receipt))
        self.assertEqual(len(script.requests), 26)

    def test_client_uses_one_fresh_source_pass_but_rechecks_executing_file_bytes(self):
        paths = {*client.session.UTILITY_SOURCE_PATHS, client.CLIENT_SOURCE}
        for relative in paths:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"# SYNTHETIC_SOURCE_ONLY " + relative.encode())
        hashes = {
            relative: client._digest((self.root / relative).read_bytes())
            for relative in paths
        }
        session_file = self.root / "scripts/ci/official_mcp_bob_session.py"
        client_file = self.root / client.CLIENT_SOURCE
        with (
            mock.patch.object(
                client.session, "_sources", return_value=hashes
            ) as verified,
            mock.patch.object(client.session, "__file__", str(session_file)),
            mock.patch.object(client, "__file__", str(client_file)),
            mock.patch.object(
                client.operation.adapter,
                "_git",
                side_effect=AssertionError("duplicate Git read"),
            ),
        ):
            self.assertEqual(client._source_hashes(self.context["exact_sha"]), hashes)
            verified.assert_called_once_with(
                self.context["exact_sha"], include_utilities=True
            )
            client_file.write_bytes(
                client_file.read_bytes() + b"\n# SYNTHETIC_CHANGED_AFTER_PASS"
            )
            with self.assertRaisesRegex(ValueError, "Executing client differs"):
                client._source_hashes(self.context["exact_sha"])
            client_file.write_bytes(
                b"# SYNTHETIC_SOURCE_ONLY " + client.CLIENT_SOURCE.encode()
            )
            session_file.write_bytes(
                session_file.read_bytes() + b"\n# SYNTHETIC_MODULE_DRIFT"
            )
            with self.assertRaisesRegex(
                ValueError, "Executing trusted session utility"
            ):
                client._source_hashes(self.context["exact_sha"])
            with (
                mock.patch.object(
                    client.session,
                    "_sources",
                    return_value={client.CLIENT_SOURCE: hashes[client.CLIENT_SOURCE]},
                ),
                self.assertRaisesRegex(ValueError, "lacks fixed client dependencies"),
            ):
                client._source_hashes(self.context["exact_sha"])

    def test_valid_response_framing_failure_has_fixed_code_without_retry(self):
        script = self.fixed_script(
            final=rpc_response(
                {},
                headers=[
                    ("Content-Type", "application/json"),
                    ("Transfer-Encoding", "gzip"),
                ],
            )
        )
        with self.assertRaisesRegex(ValueError, "HTTP body framing"):
            self.run_script(script)
        receipt = self.blocked_receipt()
        self.assertEqual(receipt["failure_stage"], "VALID_CALL")
        self.assertEqual(receipt["error_code"], "HTTP_FRAMING")
        self.assertEqual(len(script.requests), 26)

    def operation_bundle(self):
        fixture = operation_fixtures.OfficialMcpBobOperationTests()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        for name, value in (("ROOT", fixture.root), ("operation", fixture.operation)):
            patcher = mock.patch.object(client, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        persistent = fixture.operation._persistent_snapshot()
        # The actual MCP boundary serializes the producer's tuple observations
        # to JSON arrays before the client receives this packet.
        packet = json.loads(json.dumps(fixture.capture()))
        context = {
            "exact_sha": fixture.exact_sha,
            "operation": fixture.context,
            "context_raw": fixture.context_path.read_bytes(),
        }
        return fixture, context, persistent, packet

    def test_actual_synthetic_bob_bundle_is_reinspected_and_hash_bound(self):
        fixture, context, persistent, packet = self.operation_bundle()
        references = client._verify_bundle(context, packet, persistent)
        self.assertEqual(len(references), 6)
        for name, row in references.items():
            raw = (fixture.session / "bundle" / name).read_bytes()
            self.assertEqual(row["sha256"], client._digest(raw))
            self.assertEqual(row["size_bytes"], len(raw))
        for key in (
            "native_capture_verified",
            "official_mcp_verified",
            "persistent_content_verified",
        ):
            self.assertIs(packet["capture"][key], False)

    def test_real_bundle_authority_rejection_records_fixed_validation_stage(self):
        fixture, context, _persistent, packet = self.operation_bundle()
        context.update(
            marker={"owned_editor_pid": 123}, sources={"synthetic_source.py": "c" * 64}
        )
        counter_path = fixture.root / client.COUNTER_FILE

        def write_counter(count):
            counter_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "exact_sha": context["exact_sha"],
                        "body_invocation_count": count,
                    }
                )
            )

        write_counter(0)
        packet["result"]["status"] = "PASS"
        raw = client.operation.adapter.canonical_json_bytes(packet["result"])
        for name in ("result.json", "direct-inspection.json"):
            (fixture.session / "bundle" / name).write_bytes(raw)
        # Only publish this synthetic native output in the valid-call callback;
        # denied requests must still observe the genuine absent-bundle guard.
        pending_bundle = fixture.session / "pending-bundle"
        (fixture.session / "bundle").rename(pending_bundle)

        def valid(request):
            pending_bundle.rename(fixture.session / "bundle")
            write_counter(1)
            return packet_response(packet)(request)

        script = self.fixed_script(final=valid)
        with (
            mock.patch.object(client, "_load_context", return_value=context),
            mock.patch.object(client.http.client, "HTTPConnection", script.connect),
            self.assertRaisesRegex(ValueError, "authority flags"),
        ):
            client.run_fixed_session()
        receipt = json.loads((fixture.root / client.RECEIPT_FILE).read_bytes())
        self.assertEqual(receipt["failure_stage"], "BUNDLE_VERIFY")
        self.assertEqual(receipt["error_code"], "DOMAIN_AUTHORITY")
        self.assertIs(receipt["official_mcp_transport_verified"], False)
        self.assertIs(receipt["official_mcp_admitted"], False)
        self.assertEqual(len(script.requests), 26)

    def test_saved_bundle_cannot_outlive_its_tracked_source_revision(self):
        fixture, context, persistent, packet = self.operation_bundle()
        relative = client.operation.adapter.SOURCE_PATHS[0]
        source = fixture.root / relative
        source.write_bytes(
            source.read_bytes() + b"\n# SYNTHETIC tracked source drift\n"
        )
        with self.assertRaises(ValueError):
            client._verify_bundle(context, packet, persistent)

    def test_matching_transported_and_saved_tampering_still_fails_domain_validation(
        self,
    ):
        fixture, context, persistent, original = self.operation_bundle()
        files = {
            name: path.read_bytes()
            for name in (
                "result.json",
                "direct-inspection.json",
                "proof.json",
                "receipt.json",
                "capture-proof.json",
            )
            for path in [fixture.session / "bundle" / name]
        }
        for artifact, key, value in (
            ("result", "status", "PASS"),
            ("proof", "synthetic_fabricated_proof", True),
            ("receipt", "synthetic_fabricated_receipt", True),
            ("capture", "native_capture_verified", True),
            ("capture", "persistent_inventory_sha256", "0" * 64),
            ("capture", "sample_count", True),
        ):
            with self.subTest(artifact=artifact, key=key):
                packet = deepcopy(original)
                packet[artifact][key] = value
                name = (
                    "capture-proof.json"
                    if artifact == "capture"
                    else artifact + ".json"
                )
                raw = client.operation.adapter.canonical_json_bytes(packet[artifact])
                (fixture.session / "bundle" / name).write_bytes(raw)
                if artifact == "result":
                    (fixture.session / "bundle/direct-inspection.json").write_bytes(raw)
                with self.assertRaises(ValueError):
                    client._verify_bundle(context, packet, persistent)
                for restored, raw in files.items():
                    (fixture.session / "bundle" / restored).write_bytes(raw)
        extra = fixture.session / "bundle/unrecorded.json"
        extra.write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "artifact inventory bound"):
            client._verify_bundle(context, original, persistent)


if __name__ == "__main__":
    unittest.main()

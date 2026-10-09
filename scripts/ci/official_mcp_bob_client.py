"""Trusted, fixed loopback proof client for the bounded #384 BOB session.

No endpoint, tool, arguments or paths come from an MCP caller. This client does
not launch an editor, register tools, start a server or stage project content.
The owned Windows harness supplies the private marker and native counter. The
final host/Automation admission remains separate from this transport receipt.
Offline test fixtures are synthetic and never establish native admission.
"""

from __future__ import annotations

import hashlib
import http.client
import os
import re
import stat
from pathlib import Path
from typing import Any

from scripts.ci import official_mcp_bob_session as session
from scripts.ue import official_mcp_bob_operation as operation

ROOT = Path(__file__).resolve().parents[2]
CLIENT_SOURCE = "scripts/ci/official_mcp_bob_client.py"
SESSION_DIR = operation.SESSION_DIR
HOST = "127.0.0.1"
PORT = 18784
ENDPOINT = "/mcp"
TOOL = "YacsBobInspection.InspectAcceptedCheckpoint"
PROTOCOL = "2025-06-18"
SERVER_SOURCE_SHA256 = (
    "56e519b8a956a1d916f421781767f85a999d02b9e02f806b3594d96b96d2a104"
)
MARKER_FILE = SESSION_DIR + "/transport-context.json"
COUNTER_FILE = SESSION_DIR + "/native-counter.json"
RECEIPT_FILE = SESSION_DIR + "/transport-receipt.json"
WINDOWS_HOST = os.name == "nt"
MAX_RESPONSE_BYTES = operation.adapter.MAX_INPUT_BYTES
MAX_METADATA_BYTES = 256 * 1024
REQUEST_TIMEOUT_SECONDS = 180
# JSON-RPC2.0 InvalidParams; installed ProcessToolCallJsonRpcCall uses that
# named error for the exact unknown-tool message before native dispatch.
INVALID_PARAMS = -32602
ARGUMENTS_REJECTED_TEXT = (
    "YacsBobInspection requires an explicit empty arguments object."
)
MARKER_FIELDS = {
    "schema_version",
    "exact_sha",
    "project_root",
    "owned_editor_pid",
    "source_sha256",
    "session_context_sha256",
}
COUNTER_FIELDS = {"schema_version", "exact_sha", "body_invocation_count"}
ENV_FIELDS = {
    "project_root": "YACS_MCP_BOB_PROJECT_ROOT",
    "exact_sha": "YACS_MCP_BOB_EXPECTED_HEAD",
    "owned_editor_pid": "YACS_MCP_BOB_OWNED_EDITOR_PID",
}

# These are requests to denied names/inputs, never caller-selected operations.
# Case aliases are intentionally absent: the installed module lookup ignores
# case and resolves them to the same fixed operation.
# Candidate names do not assert the installed stock registry's canonical names;
# the exact-one tools/list gate establishes absence of every stock tool.
_MISSING_ARGUMENTS = object()
DENIAL_CASES = (
    ("unknown_operation", "YacsBobInspection.Unknown", {}),
    ("unknown_scene_candidate", "SceneTools.get_current_level", {}),
    ("unknown_actor_candidate", "ActorTools.get_label", {}),
    ("unknown_object_candidate", "ObjectTools.get_class", {}),
    ("unknown_automation_candidate", "AutomationTestToolset.RunTests", {}),
    ("unknown_dispatch_candidate", "call_tool", {}),
    ("unknown_python_candidate", "execute_python", {}),
    ("field", TOOL, {"unexpected": True}),
    ("policy", TOOL, {"policy": {}}),
    ("evidence_root", TOOL, {"evidence_root": SESSION_DIR}),
    ("receipt_path", TOOL, {"receipt_path": RECEIPT_FILE}),
    ("map", TOOL, {"map": "/Engine/Maps/Entry"}),
    ("object_path", TOOL, {"path": "/Engine/Maps/Entry.Entry"}),
    ("test", TOOL, {"test": "CyclingPhysics.RoadPhysics.ProfileInterpolation"}),
    ("body", TOOL, {"body": "pass"}),
    ("mixed_fields", TOOL, {"map": operation.MAP_PACKAGE, "unexpected": True}),
    ("null", TOOL, None),
    ("array", TOOL, []),
    ("scalar_string", TOOL, "{}"),
    ("scalar_number", TOOL, 1),
    ("scalar_boolean", TOOL, False),
    ("missing_arguments", TOOL, _MISSING_ARGUMENTS),
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_object(raw: bytes) -> dict[str, Any]:
    value = operation.adapter._json(raw)
    _require(isinstance(value, dict), "MCP JSON must be one object")
    return value


def _read(relative: str, *, limit: int = MAX_METADATA_BYTES) -> bytes:
    path = operation._safe_path(ROOT, relative)
    before = path.stat()
    _require(
        stat.S_ISREG(before.st_mode) and before.st_size <= limit,
        "Fixed transport input exceeds its regular-file bound",
    )
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    after = path.stat()
    identity = lambda info: (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )
    _require(
        identity(before) == identity(after)
        and len(raw) == before.st_size
        and len(raw) <= limit,
        "Fixed transport input changed while being read",
    )
    return raw


def _source_hashes(exact_sha: str) -> dict[str, str]:
    sources = session._sources(exact_sha)
    for relative in session.UTILITY_SOURCE_PATHS:
        raw = _read(relative)
        _require(
            raw == operation.adapter._git(ROOT, "show", f"{exact_sha}:{relative}"),
            "Trusted session dependency differs from its committed source",
        )
        sources[relative] = _digest(raw)
    _require(
        _digest(Path(session.__file__).read_bytes())
        == sources["scripts/ci/official_mcp_bob_session.py"],
        "Executing trusted session utility differs from the pinned source",
    )
    path = operation._safe_path(ROOT, CLIENT_SOURCE)
    raw = _read(CLIENT_SOURCE)
    _require(
        raw == operation.adapter._git(ROOT, "show", f"{exact_sha}:{CLIENT_SOURCE}")
        and _digest(Path(__file__).read_bytes()) == _digest(raw)
        and path.resolve() == Path(__file__).resolve(),
        "Executing client differs from its committed exact-SHA source",
    )
    return {**sources, CLIENT_SOURCE: _digest(raw)}


def _load_context() -> dict[str, Any]:
    _require(
        WINDOWS_HOST, "Fixed MCP proof client requires the trusted Windows owner host"
    )
    session._assert_isolated_root()
    _require(
        ROOT.resolve() == session.ROOT.resolve() == operation.ROOT.resolve(),
        "Client and fixed session must execute in the same isolated checkout",
    )
    operation._safe_path(ROOT, "YetAnotherCyclingSim.uproject")
    expected_sha = os.environ.get(ENV_FIELDS["exact_sha"], "")
    project_root = os.environ.get(ENV_FIELDS["project_root"], "")
    editor_pid = os.environ.get(ENV_FIELDS["owned_editor_pid"], "")
    _require(
        bool(operation.adapter.SHA40.fullmatch(expected_sha))
        and bool(re.fullmatch(r"[1-9][0-9]{0,9}", editor_pid)),
        "Client lacks the exact revision and owned editor process context",
    )
    _require(
        project_root == str(ROOT),
        "Trusted client project root differs from the executing checkout",
    )
    marker_raw = _read(MARKER_FILE)
    marker = _json_object(marker_raw)
    operation.adapter._fields(marker, MARKER_FIELDS, "trusted MCP transport context")
    _require(
        type(marker["schema_version"]) is int
        and marker["schema_version"] == 1
        and marker["exact_sha"] == expected_sha
        and marker["project_root"] == project_root
        and type(marker["owned_editor_pid"]) is int
        and marker["owned_editor_pid"] == int(editor_pid),
        "Trusted MCP transport marker differs from the fixed host/source context",
    )
    sources = _source_hashes(expected_sha)
    _require(
        marker["source_sha256"] == sources,
        "Transport marker source inventory differs from exact HEAD",
    )
    context_raw = _read(SESSION_DIR + "/session-context.json", limit=MAX_RESPONSE_BYTES)
    _require(
        _digest(context_raw) == marker["session_context_sha256"],
        "Trusted operation context hash differs",
    )
    context = _json_object(context_raw)
    operation.adapter._fields(
        context, operation.CONTEXT_FIELDS, "trusted BOB session context"
    )
    _require(
        type(context["schema_version"]) is int
        and context["schema_version"] == 1
        and context["exact_sha"] == expected_sha
        and context["profile_sha256"] == operation.PROFILE_SHA256
        and context["profile_source_sha"] == operation.PROFILE_SOURCE_SHA
        and context["consumer_source_sha"] == operation.CONSUMER_SOURCE_SHA,
        "Operation context provenance differs from fixed approved inputs",
    )
    operation.adapter._fields(
        context["landscape"], {"path", "class_path"}, "trusted Landscape identity"
    )
    _require(
        context["landscape"]["class_path"] == operation.LANDSCAPE_CLASS
        and isinstance(context["landscape"]["path"], str)
        and context["landscape"]["path"].startswith(operation.MAP_PACKAGE + "."),
        "Transport Landscape identity is outside the fixed accepted map",
    )
    operation._sources(context)
    operation._consumer_assets(context)
    _require(
        _digest(_read(SESSION_DIR + "/profile.json", limit=MAX_RESPONSE_BYTES))
        == operation.PROFILE_SHA256,
        "Transport profile differs from the retained fixed profile",
    )
    _require(
        not operation._safe_path(ROOT, SESSION_DIR + "/bundle").exists(),
        "Client requires a fresh BOB capture; preserve existing bundle",
    )
    _require(
        not operation._safe_path(ROOT, RECEIPT_FILE).exists(),
        "Client cannot replace an existing transport receipt",
    )
    operation.adapter._git(
        ROOT, "check-ignore", "--no-index", "--quiet", "--", RECEIPT_FILE
    )
    return {
        "marker": marker,
        "marker_raw": marker_raw,
        "operation": context,
        "context_raw": context_raw,
        "exact_sha": expected_sha,
        "sources": sources,
    }


def _counter(context: dict, expected: int) -> dict[str, Any]:
    value = _json_object(_read(COUNTER_FILE))
    operation.adapter._fields(
        value, COUNTER_FIELDS, "fixed native BOB invocation counter"
    )
    _require(
        type(value["schema_version"]) is int
        and value["schema_version"] == 1
        and value["exact_sha"] == context["exact_sha"]
        and type(value["body_invocation_count"]) is int
        and value["body_invocation_count"] == expected,
        "Native BOB body invocation counter differs from the fixed request sequence",
    )
    return value


class _Transport:
    """One serial, bounded JSON-only connection; never retry an uncertain call."""

    def __init__(self) -> None:
        self.connection = http.client.HTTPConnection(
            HOST, PORT, timeout=REQUEST_TIMEOUT_SECONDS
        )
        self.session_id: str | None = None
        self.request_id = 0

    def close(self) -> None:
        self.connection.close()

    def _post(
        self, method: str, params: Any, *, notification: bool = False
    ) -> dict | None:
        body: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not notification:
            self.request_id += 1
            body["id"] = self.request_id
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.session_id is not None:
            headers["Mcp-Session-Id"] = self.session_id
            headers["Mcp-Protocol-Version"] = PROTOCOL
        self.connection.request(
            "POST", ENDPOINT, operation.adapter.canonical_json_bytes(body), headers
        )
        response = self.connection.getresponse()
        received_headers: dict[str, str] = {}
        for key, value in response.getheaders():
            key = key.casefold()
            if key in {
                "content-type",
                "content-length",
                "mcp-session-id",
                "mcp-protocol-version",
                "content-encoding",
                "transfer-encoding",
            }:
                _require(
                    key not in received_headers,
                    "MCP response contains duplicate transport headers",
                )
                received_headers[key] = value
        length = received_headers.get("content-length")
        if length is not None:
            _require(
                bool(re.fullmatch(r"[0-9]+", length))
                and int(length) <= MAX_RESPONSE_BYTES,
                "MCP response exceeds its declared body bound",
            )
        transfer = received_headers.get("transfer-encoding")
        _require(
            transfer is None or (transfer.casefold() == "chunked" and length is None),
            "MCP response has unsupported or ambiguous HTTP body framing",
        )
        _require(
            received_headers.get("content-encoding", "identity").casefold()
            == "identity",
            "Compressed MCP responses are outside the fixed client contract",
        )
        content_type = (
            received_headers.get("content-type", "").split(";", 1)[0].strip().casefold()
        )
        if notification:
            _require(
                response.status == 202 and content_type in {"", "application/json"},
                "Initialized notification returned an unsupported response",
            )
        else:
            _require(
                response.status in {200, 400},
                "MCP request returned an unsupported HTTP status; no retry is permitted",
            )
            _require(
                content_type == "application/json",
                "MCP request did not return bounded JSON; event streams are not accepted",
            )
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        _require(
            len(raw) <= MAX_RESPONSE_BYTES
            and (length is None or len(raw) == int(length)),
            "MCP response body exceeds its bound or declared size",
        )
        returned_protocol = received_headers.get("mcp-protocol-version")
        _require(
            returned_protocol is None or returned_protocol == PROTOCOL,
            "MCP response changed the negotiated protocol",
        )
        if notification:
            _require(
                response.status == 202 and raw == b"",
                "Initialized notification did not return202 with an empty body",
            )
            returned_session = received_headers.get("mcp-session-id")
            _require(
                returned_session is None or returned_session == self.session_id,
                "MCP notification changed the session",
            )
            return None
        returned_session = received_headers.get("mcp-session-id")
        if method == "initialize":
            _require(
                response.status == 200
                and isinstance(returned_session, str)
                and bool(re.fullmatch(r"[0-9a-f]{32}", returned_session)),
                "Initialize did not establish the installed server's fixed session identity",
            )
            self.session_id = returned_session
        else:
            _require(
                returned_session is None or returned_session == self.session_id,
                "MCP response changed the negotiated session",
            )
        value = _json_object(raw)
        _require(
            value.get("jsonrpc") == "2.0"
            and type(value.get("id")) is int
            and value["id"] == self.request_id
            and (("result" in value) != ("error" in value)),
            "MCP response has an invalid JSON-RPC identity/result contract",
        )
        if response.status == 400:
            _require("error" in value, "HTTP400 must carry an explicit JSON-RPC error")
        return value

    def initialize(self) -> dict:
        value = self._post(
            "initialize",
            {
                "protocolVersion": PROTOCOL,
                "capabilities": {},
                "clientInfo": {"name": "YacsOfficialMcpBobProof", "version": "1"},
            },
        )
        _require(
            "error" not in value and isinstance(value.get("result"), dict),
            "MCP initialization failed",
        )
        result = value["result"]
        _require(
            result.get("protocolVersion") == PROTOCOL
            and isinstance(result.get("capabilities"), dict)
            and isinstance(result["capabilities"].get("tools"), dict),
            "MCP did not negotiate the requested stable tool protocol",
        )
        self._post("notifications/initialized", None, notification=True)
        return result

    def list_fixed_tool(self) -> dict:
        value = self._post("tools/list", {})
        _require(
            "error" not in value and isinstance(value.get("result"), dict),
            "MCP tools/list failed",
        )
        result = value["result"]
        tools = result.get("tools")
        _require(
            isinstance(tools, list)
            and len(tools) == 1
            and isinstance(tools[0], dict)
            and tools[0].get("name") == TOOL
            and "nextCursor" not in result,
            "Official MCP must expose only the single fixed YACS domain operation",
        )
        schema = tools[0].get("inputSchema")
        _require(
            isinstance(schema, dict)
            and schema.get("type") == "object"
            and schema.get("properties") == {}
            and schema.get("additionalProperties") is False
            and type(schema.get("maxProperties")) is int
            and schema["maxProperties"] == 0,
            "Fixed YACS operation must advertise the empty-object caller contract",
        )
        return tools[0]

    def call(self, name: str, arguments: Any) -> dict:
        # Private testable primitive; only the fixed sequence below calls it.
        params = {"name": name}
        if arguments is not _MISSING_ARGUMENTS:
            params["arguments"] = arguments
        return self._post("tools/call", params)


def _explicit_denial(response: dict, *, label: str, name: str) -> str:
    _require(
        any(
            label == case and name == candidate
            for case, candidate, _arguments in DENIAL_CASES
        ),
        "Denial classifier received a case outside the fixed proof sequence",
    )
    if name != TOOL:
        error = response.get("error")
        _require(
            isinstance(error, dict)
            and type(error.get("code")) is int
            and error["code"] == INVALID_PARAMS
            and error.get("message") == f"Unknown tool: {name}"
            and "result" not in response,
            "Unknown-name denial must match the exact official InvalidParams error",
        )
        return "UNKNOWN_TOOL"
    result = response.get("result")
    _require(
        "error" not in response
        and isinstance(result, dict)
        and result.get("isError") is True,
        "Malformed arguments must be denied by the fixed native argument boundary",
    )
    content = result.get("content")
    _require(
        isinstance(content, list)
        and len(content) == 1
        and isinstance(content[0], dict)
        and content[0].get("type") == "text"
        and content[0].get("text") == ARGUMENTS_REJECTED_TEXT,
        "Malformed argument denial must match the exact native boundary text",
    )
    return "ARGUMENTS_REJECTED"


def _valid_result(response: dict) -> dict:
    _require("error" not in response, "Fixed BOB call returned a JSON-RPC error")
    result = response.get("result")
    _require(
        isinstance(result, dict) and result.get("isError", False) is False,
        "Fixed BOB call returned an MCP tool error",
    )
    content = result.get("content")
    _require(
        isinstance(content, list)
        and len(content) == 1
        and isinstance(content[0], dict)
        and content[0].get("type") == "text"
        and isinstance(content[0].get("text"), str),
        "Fixed BOB result must contain exactly one text JSON domain result",
    )
    raw = content[0]["text"].encode("utf-8")
    _require(len(raw) <= MAX_RESPONSE_BYTES, "Fixed BOB text JSON exceeds its bound")
    packet = _json_object(raw)
    operation.adapter._fields(
        packet, {"result", "proof", "receipt", "capture"}, "fixed BOB transport packet"
    )
    _require(
        all(isinstance(value, dict) for value in packet.values()),
        "Fixed BOB packet artifacts must be JSON objects",
    )
    return packet


def _verify_bundle(context: dict, packet: dict, persistent_before: list[dict]) -> dict:
    adapter = operation.adapter
    bundle = operation._safe_path(ROOT, SESSION_DIR + "/bundle")
    names = {
        "native-samples.json",
        "direct-inspection.json",
        "result.json",
        "proof.json",
        "capture-proof.json",
        "receipt.json",
    }
    observed = set()
    _require(bundle.is_dir(), "Fixed BOB capture bundle is missing")
    for item in bundle.iterdir():
        observed.add(item.name)
        _require(
            len(observed) <= len(names),
            "Fixed BOB bundle exceeds its artifact inventory bound",
        )
    _require(
        observed == names,
        "Fixed BOB bundle must contain exactly the actual operation artifacts",
    )
    raw = {
        name: _read(SESSION_DIR + "/bundle/" + name, limit=MAX_RESPONSE_BYTES)
        for name in names
    }
    values = {name: _json_object(value) for name, value in raw.items()}
    result, receipt, proof, capture = (
        values[name]
        for name in ("result.json", "receipt.json", "proof.json", "capture-proof.json")
    )
    adapter._fields(
        capture,
        {
            "schema_version",
            "exact_sha",
            "scope",
            "context_sha256",
            "source_sha256",
            "profile",
            "consumer",
            "scene",
            "sample_count",
            "native_sample_sha256",
            "direct_invocation_matches",
            "persistent_inventory_sha256",
            "persistent_files_unchanged",
            "scene_snapshot_unchanged",
            "native_capture_verified",
            "official_mcp_verified",
            "persistent_content_verified",
            *adapter.FALSE_FLAGS,
        },
        "fixed capture proof",
    )
    _require(
        packet
        == {"result": result, "proof": proof, "receipt": receipt, "capture": capture}
        and result == values["direct-inspection.json"],
        "Transported BOB packet differs from saved/direct artifacts",
    )
    _require(
        result.get("exact_sha") == context["exact_sha"]
        and result.get("role") == "INSPECTOR_ONLY"
        and result.get("status") in {"REVIEW_REQUIRED", "INSPECTION_INCOMPLETE"}
        and all(result.get(flag) is False for flag in adapter.FALSE_FLAGS),
        "BOB domain status or authority flags were changed",
    )
    domain_hashes = {
        path: context["operation"]["source_sha256"][path]
        for path in adapter.SOURCE_PATHS
    }
    delegated = adapter.inspect_bob_request(
        {
            "exact_sha": context["exact_sha"],
            "native_samples_path": "native-samples.json",
            "native_samples_sha256": _digest(raw["native-samples.json"]),
            "source_sha256": domain_hashes,
        },
        evidence_root=bundle,
        repository_root=ROOT,
    )
    _require(
        delegated["result"] == result and delegated["proof"] == proof,
        "Actual adapter reinspection differs from saved domain proof",
    )
    expected_receipt = delegated["receipt"]
    _require(
        set(receipt) == set(expected_receipt)
        and isinstance(receipt.get("timestamp_utc"), str)
        and {k: v for k, v in receipt.items() if k != "timestamp_utc"}
        == {k: v for k, v in expected_receipt.items() if k != "timestamp_utc"},
        "Saved BOB receipt differs from its actual result/proof references",
    )
    _require(
        receipt["result"]["sha256"] == _digest(raw["result.json"])
        and receipt["proof"]["sha256"] == _digest(raw["proof.json"]),
        "Saved BOB receipt artifact byte hashes differ",
    )
    _require(
        type(capture.get("schema_version")) is int
        and capture["schema_version"] == 1
        and capture.get("scope")
        == "BOB_CAPTURE_AND_DOMAIN_COMPARISON; HOST_ADMISSION_PENDING"
        and capture.get("exact_sha") == context["exact_sha"]
        and capture.get("context_sha256") == _digest(context["context_raw"])
        and capture.get("source_sha256") == context["operation"]["source_sha256"]
        and capture.get("profile")
        == {
            "sha256": operation.PROFILE_SHA256,
            "source_exact_sha": operation.PROFILE_SOURCE_SHA,
        }
        and capture.get("consumer")
        == {
            "source_exact_sha": operation.CONSUMER_SOURCE_SHA,
            "asset_inventory_sha256": _digest(
                adapter.canonical_json_bytes(context["operation"]["consumer_assets"])
            ),
        }
        and capture.get("native_sample_sha256") == _digest(raw["native-samples.json"])
        and type(capture.get("sample_count")) is int
        and capture["sample_count"] == len(values["native-samples.json"]["samples"])
        and capture.get("persistent_inventory_sha256")
        == _digest(adapter.canonical_json_bytes(persistent_before))
        and all(
            capture.get(flag) is True
            for flag in (
                "direct_invocation_matches",
                "persistent_files_unchanged",
                "scene_snapshot_unchanged",
            )
        )
        and all(
            capture.get(flag) is False
            for flag in (
                "native_capture_verified",
                "official_mcp_verified",
                "persistent_content_verified",
                *adapter.FALSE_FLAGS,
            )
        ),
        "Capture proof input/conservation or pending-admission claims differ",
    )
    _require(
        isinstance(capture.get("scene"), dict)
        and capture["scene"].get("map_package") == operation.MAP_PACKAGE
        and capture["scene"].get("landscape") == context["operation"]["landscape"],
        "Actual captured Landscape identity differs from the fixed context",
    )
    return {
        name: {
            "path": SESSION_DIR + "/bundle/" + name,
            "sha256": _digest(value),
            "size_bytes": len(value),
        }
        for name, value in sorted(raw.items())
    }


def _unchanged(context: dict, persistent_before: list[dict]) -> None:
    _require(
        _read(MARKER_FILE) == context["marker_raw"]
        and _read(SESSION_DIR + "/session-context.json", limit=MAX_RESPONSE_BYTES)
        == context["context_raw"]
        and _source_hashes(context["exact_sha"]) == context["sources"],
        "Trusted client inputs changed during the fixed request sequence",
    )
    operation._sources(context["operation"])
    operation._consumer_assets(context["operation"])
    _require(
        _digest(_read(SESSION_DIR + "/profile.json", limit=MAX_RESPONSE_BYTES))
        == operation.PROFILE_SHA256
        and operation._persistent_snapshot() == persistent_before,
        "Persistent project/profile bytes changed during MCP proof",
    )


def run_fixed_session() -> dict:
    context = _load_context()
    persistent_before = operation._persistent_snapshot()
    _counter(context, 0)
    receipt = {
        "schema_version": 1,
        "exact_sha": context["exact_sha"],
        "status": "TRANSPORT_BLOCKED",
        "endpoint": f"http://{HOST}:{PORT}{ENDPOINT}",
        "requested_protocol": PROTOCOL,
        "owned_editor_pid": context["marker"]["owned_editor_pid"],
        "source_sha256": context["sources"],
        "expected_server_source_sha256": SERVER_SOURCE_SHA256,
        "denials": [],
        "valid_call_attempted": False,
        "official_mcp_transport_verified": False,
        "official_mcp_admitted": False,
        "native_automation_verified": False,
        "persistent_world_mutation": False,
        "performance_pass": False,
    }
    # Reserve before network activity so two trusted invocations cannot race.
    path = operation._safe_path(ROOT, RECEIPT_FILE)
    receipt_stream = path.open("xb")
    transport = None
    try:
        transport = _Transport()
        initialized = transport.initialize()
        receipt["negotiated_protocol"] = initialized["protocolVersion"]
        receipt["session_id_sha256"] = _digest(transport.session_id.encode("ascii"))
        receipt["tool"] = transport.list_fixed_tool()
        for label, name, arguments in DENIAL_CASES:
            response = transport.call(name, arguments)
            category = _explicit_denial(response, label=label, name=name)
            _counter(context, 0)
            _require(
                not operation._safe_path(ROOT, SESSION_DIR + "/bundle").exists(),
                "Denied request entered the BOB capture body",
            )
            receipt["denials"].append(
                {
                    "case": label,
                    "expected_category": category,
                    "explicit_error": True,
                    "body_invocation_count": 0,
                }
            )
        # Set before dispatch: an uncertain request must never be retried.
        receipt["valid_call_attempted"] = True
        response = transport.call(TOOL, {})
        packet = _valid_result(response)
        _counter(context, 1)
        receipt["bundle"] = _verify_bundle(context, packet, persistent_before)
        _unchanged(context, persistent_before)
        _counter(context, 1)
        receipt["body_invocation_count"] = 1
        receipt["domain_status"] = packet["result"]["status"]
        receipt["persistent_files_unchanged"] = True
        receipt["status"] = "LOCAL_TRANSPORT_AND_BOB_ARTIFACTS_VERIFIED"
        receipt["official_mcp_transport_verified"] = True
    except Exception as exc:
        # Keep bounded local evidence; no raw request/session/error payload is logged.
        receipt["error_type"] = type(exc).__name__
        receipt["error"] = (
            "Fixed MCP proof failed; inspect the owned native session and saved bundle."
        )
        raise
    finally:
        try:
            if transport is not None:
                transport.close()
        except Exception:
            receipt["status"] = "TRANSPORT_BLOCKED"
            receipt["official_mcp_transport_verified"] = False
            raise
        finally:
            try:
                receipt_stream.write(operation.adapter.canonical_json_bytes(receipt))
            finally:
                receipt_stream.close()
    return receipt


def main() -> int:
    try:
        receipt = run_fixed_session()
    except (OSError, ValueError, RuntimeError, http.client.HTTPException) as exc:
        print("YACS_MCP_BOB_CLIENT TRANSPORT_BLOCKED error_type=" + type(exc).__name__)
        return 1
    print(
        "YACS_MCP_BOB_CLIENT "
        + receipt["status"]
        + " domain_status="
        + receipt["domain_status"]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

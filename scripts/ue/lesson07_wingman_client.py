"""Bounded host-local Wingman discovery for the existing Lesson07 Editor.

This client only initializes MCP, lists tool schemas and reads session/status.
It cannot call a tool, start an Editor, expose a listener or change an asset.
The Windows harness must supply a fresh OS identity receipt and recheck that
identity after this process exits. The receipt is not an active-world readback.

Wire contracts: https://ai.locodev.dev/docs/developers/antigravity and
https://modelcontextprotocol.io/specification/2025-03-26/basic/transports .
The existing fixed BOB client admits JSON only and another protocol/toolset;
this small adapter adds the vendor's JSON/SSE discovery, without changing it.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import http.client
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import socket
import stat
import threading
import time
from urllib.parse import urlsplit


PROTOCOL = "2025-03-26"
HOST = "127.0.0.1"
ENDPOINT = "/loco"
PROJECT = r"D:\yacs\project\YetAnotherCyclingSim.uproject"
EXECUTABLE = r"D:\yacs\engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
DISCOVERY_PATH = Path(r"D:\yacs\project\Saved\LocoAI\external-mcp-config.json")
WINDOWS_HOST = os.name == "nt"
CONFIG_LIMIT = 16 * 1024
RESPONSE_LIMIT = 2 * 1024 * 1024
LINE_LIMIT = 128 * 1024
TIMEOUT_SECONDS = 20.0
IDENTITY_MAX_AGE_SECONDS = 120
MAX_PAGES = 4
MAX_TOOLS = 256
MAX_EVENTS = 512
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_.:-]{0,127}\Z")
SCHEMA_TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}
METHODS = {"initialize", "tools/list", "session/status"}


class ProbeError(Exception):
    """Only constant codes and numeric protocol codes may leave the client."""

    def __init__(self, code: str, rpc_code: int | None = None):
        self.code = code
        self.rpc_code = rpc_code
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise ProbeError(code)


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def parse_json(raw, limit=RESPONSE_LIMIT):
    require(type(raw) is bytes and 0 < len(raw) <= limit, "JSON_SIZE")

    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def bad_constant(_value):
        raise ProbeError("NONFINITE_JSON")

    try:
        return json.loads(
            raw.decode("utf-8-sig"),
            object_pairs_hook=pairs,
            parse_constant=bad_constant,
        )
    except ProbeError:
        raise
    except (UnicodeError, ValueError, RecursionError):
        raise ProbeError("INVALID_JSON") from None


def plain_path(path):
    """Do not read/write a credential or receipt through a link or junction."""
    path = Path(path)
    for entry in (path, *path.parents):
        try:
            info = entry.lstat()
        except FileNotFoundError:
            continue
        require(
            not stat.S_ISLNK(info.st_mode)
            and not (getattr(info, "st_file_attributes", 0) & 0x400),
            "REPARSE_PATH",
        )
    return path


def read_bounded(path, limit):
    try:
        path = plain_path(path)
        before = path.stat()
        require(
            stat.S_ISREG(before.st_mode) and 0 < before.st_size <= limit, "INPUT_SIZE"
        )
        with path.open("rb") as stream:
            raw = stream.read(limit + 1)
        after = path.stat()
        require(
            len(raw) == before.st_size == after.st_size
            and before.st_mtime_ns == after.st_mtime_ns,
            "INPUT_CHANGED",
        )
        return raw
    except ProbeError:
        raise
    except OSError:
        raise ProbeError("INPUT_UNAVAILABLE") from None


@dataclass(frozen=True)
class Discovery:
    port: int
    token: str = field(repr=False)

    @classmethod
    def from_mapping(cls, value):
        require(
            type(value) is dict and set(value) == {"url", "token", "type"},
            "DISCOVERY_SCHEMA",
        )
        require(value["type"] == "http", "DISCOVERY_TRANSPORT")
        url, token = value["url"], value["token"]
        require(
            type(url) is str
            and len(url) <= 128
            and not any(c.isspace() or c == "\\" for c in url),
            "DISCOVERY_ENDPOINT",
        )
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError:
            raise ProbeError("DISCOVERY_ENDPOINT") from None
        require(
            parsed.scheme == "http"
            and parsed.hostname == HOST
            and type(port) is int
            and 0 < port < 65536
            and parsed.netloc == f"{HOST}:{port}"
            and parsed.path == ENDPOINT
            and url == f"http://{HOST}:{port}{ENDPOINT}"
            and not parsed.query
            and not parsed.fragment
            and not parsed.username
            and not parsed.password,
            "DISCOVERY_ENDPOINT",
        )
        require(
            type(token) is str
            and 0 < len(token) <= 4096
            and all(0x21 <= ord(c) <= 0x7E for c in token),
            "DISCOVERY_TOKEN",
        )
        return cls(port=port, token=token)


def utc(value):
    require(type(value) is str and len(value) <= 40, "IDENTITY_TIMESTAMP")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(
            parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0,
            "IDENTITY_TIMESTAMP",
        )
        return parsed
    except (ValueError, OverflowError):
        raise ProbeError("IDENTITY_TIMESTAMP") from None


def validate_identity(value, discovery, now=None):
    require(
        type(value) is dict
        and type(value.get("schema_version")) is int
        and value["schema_version"] == 1
        and value.get("status") == "L07_WINGMAN_HOST_IDENTITY_VERIFIED",
        "IDENTITY_SCHEMA",
    )
    pid = value.get("pid")
    require(type(pid) is int and 0 < pid < 2**32, "IDENTITY_PID")
    for key, expected in (("executable", EXECUTABLE), ("project", PROJECT)):
        actual = value.get(key)
        require(
            type(actual) is str
            and PureWindowsPath(actual) == PureWindowsPath(expected),
            "IDENTITY_PATH",
        )
    require(value.get("canonical_project_argument_matches") is True, "IDENTITY_PROJECT")
    listener = value.get("listener")
    require(
        type(listener) is dict
        and listener.get("address") == HOST
        and type(listener.get("port")) is int
        and listener["port"] == discovery.port
        and type(listener.get("pid")) is int
        and listener["pid"] == pid,
        "IDENTITY_LISTENER",
    )
    observed = utc(value.get("observed_utc"))
    created = utc(value.get("process_created_utc"))
    age = ((now or datetime.now(timezone.utc)) - observed).total_seconds()
    require(
        -5 <= age <= IDENTITY_MAX_AGE_SECONDS and created <= observed, "IDENTITY_STALE"
    )
    return {
        "pid": pid,
        "process_created_utc": created.isoformat(),
        "observed_utc": observed.isoformat(),
        "executable": EXECUTABLE,
        "project": PROJECT,
        "listener": {"address": HOST, "port": discovery.port, "pid": pid},
    }


def schema_structure(schema, token, depth=0):
    """Retain argument shape; omit free text, defaults, examples and enum values."""
    require(depth <= 12, "SCHEMA_DEPTH")
    if type(schema) is bool:
        return schema
    require(type(schema) is dict and len(schema) <= 256, "SCHEMA_SHAPE")
    result = {}
    kind = schema.get("type")
    if type(kind) is str and kind in SCHEMA_TYPES:
        result["type"] = kind
    elif (
        type(kind) is list
        and len(kind) <= 7
        and all(type(k) is str and k in SCHEMA_TYPES for k in kind)
    ):
        result["type"] = kind
    for keyword in ("properties", "$defs", "definitions"):
        if keyword in schema:
            mapping = schema[keyword]
            require(type(mapping) is dict and len(mapping) <= 128, "SCHEMA_PROPERTIES")
            result[keyword] = {
                name: schema_structure(item, token, depth + 1)
                for name, item in mapping.items()
                if IDENTIFIER.fullmatch(name) and token not in name
            }
    if "required" in schema:
        required = schema["required"]
        require(type(required) is list and len(required) <= 128, "SCHEMA_REQUIRED")
        result["required"] = [
            name
            for name in required
            if type(name) is str and IDENTIFIER.fullmatch(name) and token not in name
        ]
    for keyword in ("items", "additionalProperties", "not", "if", "then", "else"):
        if keyword in schema:
            result[keyword] = schema_structure(schema[keyword], token, depth + 1)
    for keyword in ("allOf", "anyOf", "oneOf", "prefixItems"):
        if keyword in schema:
            items = schema[keyword]
            require(type(items) is list and len(items) <= 32, "SCHEMA_ALTERNATIVES")
            result[keyword] = [
                schema_structure(item, token, depth + 1) for item in items
            ]
    reference = schema.get("$ref")
    if (
        type(reference) is str
        and token not in reference
        and re.fullmatch(
            r"#/(?:\$defs|definitions)/[A-Za-z_][A-Za-z0-9_.-]{0,127}", reference
        )
    ):
        result["$ref"] = reference
    for keyword in (
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
    ):
        number = schema.get(keyword)
        if type(number) in (int, float) and math.isfinite(number):
            result[keyword] = number
    return result


class DiscoveryClient:
    def __init__(self, discovery, identity, timeout=TIMEOUT_SECONDS):
        require(
            type(timeout) in (int, float) and 0 < timeout <= TIMEOUT_SECONDS,
            "TIMEOUT_BOUND",
        )
        validate_identity(identity, discovery)
        self.discovery = discovery
        self.identity = identity
        self.timeout = timeout
        self.session_id = None
        self.next_id = 1
        self.requests = 0
        self.notifications_received = 0

    def _message(self, value, request_id):
        messages = value if type(value) is list else [value]
        require(0 < len(messages) <= 64, "RPC_BATCH_SIZE")
        found = None
        for message in messages:
            require(
                type(message) is dict and message.get("jsonrpc") == "2.0", "RPC_SHAPE"
            )
            if "method" in message:
                require("id" not in message, "SERVER_REQUEST_UNSUPPORTED")
                self.notifications_received += 1
                require(self.notifications_received <= MAX_EVENTS, "NOTIFICATION_LIMIT")
                continue
            require(
                type(message.get("id")) is int and message["id"] == request_id,
                "RPC_RESPONSE_ID",
            )
            require(found is None, "RPC_DUPLICATE_RESPONSE")
            if "error" in message:
                error = message["error"]
                number = error.get("code") if type(error) is dict else None
                raise ProbeError("RPC_ERROR", number if type(number) is int else None)
            require("result" in message, "RPC_RESULT_MISSING")
            found = message["result"]
        return found

    def _read_result(self, response, request_id, wire, deadline):
        content_type = (
            (response.getheader("Content-Type") or "").split(";", 1)[0].strip().lower()
        )
        require(
            content_type in {"application/json", "text/event-stream"},
            "HTTP_CONTENT_TYPE",
        )
        total = 0
        if content_type == "application/json":
            chunks = []
            while True:
                remaining = deadline - time.monotonic()
                require(remaining > 0, "REQUEST_TIMEOUT")
                wire.settimeout(remaining)
                part = response.read1(min(65536, RESPONSE_LIMIT + 1 - total))
                if not part:
                    break
                chunks.append(part)
                total += len(part)
                require(total <= RESPONSE_LIMIT, "HTTP_BODY_SIZE")
            result = self._message(parse_json(b"".join(chunks)), request_id)
            require(result is not None, "RPC_RESULT_MISSING")
            return result
        data = []
        events = 0
        while True:
            remaining = deadline - time.monotonic()
            require(remaining > 0, "REQUEST_TIMEOUT")
            wire.settimeout(remaining)
            line = response.readline(LINE_LIMIT + 1)
            total += len(line)
            require(
                len(line) <= LINE_LIMIT and total <= RESPONSE_LIMIT, "HTTP_BODY_SIZE"
            )
            if not line:
                raise ProbeError("SSE_RESULT_MISSING")
            if line in (b"\n", b"\r\n"):
                if data:
                    events += 1
                    require(events <= MAX_EVENTS, "SSE_EVENT_LIMIT")
                    result = self._message(parse_json(b"\n".join(data)), request_id)
                    if result is not None:
                        return result
                data = []
            elif line.startswith(b"data:"):
                value = line[5:].rstrip(b"\r\n")
                data.append(value[1:] if value.startswith(b" ") else value)
            # SSE comments, id/retry/event fields are ignored; never reconnect.

    def _post(self, method, params=None, notification=False):
        require(
            method in METHODS
            or (notification and method == "notifications/initialized"),
            "METHOD_NOT_ALLOWED",
        )
        require(
            not notification or method == "notifications/initialized",
            "METHOD_NOT_ALLOWED",
        )
        validate_identity(self.identity, self.discovery)
        request_id = None if notification else self.next_id
        payload = {"jsonrpc": "2.0", "method": method}
        if not notification:
            payload["id"] = request_id
            self.next_id += 1
        if params is not None:
            payload["params"] = params
        raw = canonical(payload)
        require(len(raw) <= CONFIG_LIMIT, "REQUEST_SIZE")
        headers = {
            "Authorization": "Bearer " + self.discovery.token,
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": PROTOCOL,
            "Connection": "close",
        }
        if self.session_id is not None:
            headers["Mcp-Session-Id"] = self.session_id
        # HTTPConnection has no proxy/environment lookup and never follows a redirect.
        connection = http.client.HTTPConnection(
            HOST, self.discovery.port, timeout=self.timeout
        )
        deadline = time.monotonic() + self.timeout
        expired = threading.Event()
        watchdog = None
        self.requests += 1
        try:
            connection.connect()
            wire = connection.sock
            require(wire is not None, "HTTP_CONNECTION")

            def expire():
                expired.set()
                try:
                    wire.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

            remaining = deadline - time.monotonic()
            require(remaining > 0, "REQUEST_TIMEOUT")
            watchdog = threading.Timer(remaining, expire)
            watchdog.daemon = True
            watchdog.start()
            connection.request("POST", ENDPOINT, body=raw, headers=headers)
            response = connection.getresponse()
            require(not 300 <= response.status < 400, "HTTP_REDIRECT_DENIED")
            require(response.status == (202 if notification else 200), "HTTP_STATUS")
            header_names = [name.lower() for name, _ in response.getheaders()]
            for name in (
                "content-length",
                "content-type",
                "mcp-session-id",
                "content-encoding",
                "transfer-encoding",
            ):
                require(header_names.count(name) <= 1, "DUPLICATE_HTTP_HEADER")
            require(not response.getheader("Content-Encoding"), "HTTP_ENCODING")
            length = response.getheader("Content-Length")
            transfer = response.getheader("Transfer-Encoding")
            require(
                not (length and transfer)
                and (not transfer or transfer.lower() == "chunked"),
                "HTTP_FRAMING",
            )
            if length is not None:
                require(
                    re.fullmatch(r"[0-9]{1,10}", length) is not None
                    and int(length) <= RESPONSE_LIMIT,
                    "HTTP_DECLARED_SIZE",
                )
            session_id = response.getheader("Mcp-Session-Id")
            if session_id is not None:
                require(
                    0 < len(session_id) <= 1024
                    and all(0x21 <= ord(c) <= 0x7E for c in session_id),
                    "SESSION_HEADER",
                )
                if method == "initialize":
                    self.session_id = session_id
                else:
                    require(session_id == self.session_id, "SESSION_CHANGED")
            if notification:
                require(
                    not transfer and (length is None or int(length) == 0),
                    "NOTIFICATION_BODY",
                )
                require(response.read(1) == b"", "NOTIFICATION_BODY")
                return None
            return self._read_result(response, request_id, wire, deadline)
        except ProbeError:
            if expired.is_set():
                raise ProbeError("REQUEST_TIMEOUT") from None
            raise
        except (TimeoutError, socket.timeout):
            raise ProbeError("REQUEST_TIMEOUT") from None
        except (OSError, http.client.HTTPException, ValueError):
            raise ProbeError(
                "REQUEST_TIMEOUT" if expired.is_set() else "HTTP_TRANSPORT"
            ) from None
        finally:
            if watchdog is not None:
                watchdog.cancel()
            connection.close()

    def probe(self):
        initialization = self._post(
            "initialize",
            {
                "protocolVersion": PROTOCOL,
                "capabilities": {},
                "clientInfo": {"name": "YACS-Lesson07-discovery", "version": "1"},
            },
        )
        require(
            type(initialization) is dict
            and initialization.get("protocolVersion") == PROTOCOL,
            "PROTOCOL_MISMATCH",
        )
        self._post("notifications/initialized", notification=True)
        tools = []
        cursor = None
        seen_cursors = set()
        tool_error = None
        try:
            for _page in range(MAX_PAGES):
                listing = self._post(
                    "tools/list", {"cursor": cursor} if cursor is not None else {}
                )
                require(
                    type(listing) is dict and type(listing.get("tools")) is list,
                    "TOOLS_RESULT",
                )
                for tool in listing["tools"]:
                    require(
                        type(tool) is dict and type(tool.get("name")) is str,
                        "TOOL_SCHEMA",
                    )
                    name = tool["name"]
                    require(
                        IDENTIFIER.fullmatch(name) is not None
                        and self.discovery.token not in name,
                        "TOOL_NAME_UNSAFE",
                    )
                    require(
                        len(tools) < MAX_TOOLS
                        and name not in {t["name"] for t in tools},
                        "TOOL_COUNT_OR_DUPLICATE",
                    )
                    tools.append(
                        {
                            "name": name,
                            "inputSchema": schema_structure(
                                tool.get("inputSchema"), self.discovery.token
                            ),
                        }
                    )
                cursor = listing.get("nextCursor")
                if cursor is None:
                    break
                require(
                    type(cursor) is str
                    and 0 < len(cursor) <= 4096
                    and cursor not in seen_cursors,
                    "TOOLS_CURSOR",
                )
                seen_cursors.add(cursor)
            require(cursor is None, "TOOLS_PAGE_LIMIT")
        except ProbeError as error:
            tool_error = {"code": error.code}
            if error.rpc_code is not None:
                tool_error["rpc_code"] = error.rpc_code
        session = self._post("session/status")
        require(
            type(session) is dict and type(session.get("signed_in")) is bool,
            "SESSION_STATUS_SCHEMA",
        )
        safe_session = {"signed_in": session["signed_in"]}
        plan = session.get("plan")
        if type(plan) is str and plan.lower() in {
            "free",
            "premium",
            "pro",
            "enterprise",
        }:
            safe_session["plan"] = plan.lower()
        return {
            "status": "DISCOVERY_INCOMPLETE"
            if tool_error
            else (
                "DISCOVERY_COMPLETE" if session["signed_in"] else "DISCOVERY_SIGNED_OUT"
            ),
            "protocol_version": PROTOCOL,
            "session": safe_session,
            "tools": tools,
            "tool_list_complete": tool_error is None,
            "tool_list_error": tool_error,
            "schema_fidelity": "STRUCTURE_ONLY_FREE_TEXT_DEFAULTS_ENUMS_OMITTED",
            "http_requests": self.requests,
            "notifications_received": self.notifications_received,
            "native_tool_calls": 0,
            "native_material_readback": "NOT_RUN",
            "performance_pass": False,
        }


def probe_from_files(identity_path, discovery_path=DISCOVERY_PATH):
    require(WINDOWS_HOST, "WINDOWS_HOST_REQUIRED")
    discovery_raw = read_bounded(discovery_path, CONFIG_LIMIT)
    discovery = Discovery.from_mapping(parse_json(discovery_raw, CONFIG_LIMIT))
    identity_raw = read_bounded(identity_path, CONFIG_LIMIT)
    identity = parse_json(identity_raw, CONFIG_LIMIT)
    safe_identity = validate_identity(identity, discovery)
    client = DiscoveryClient(discovery, identity)
    report = client.probe()
    require(
        read_bounded(discovery_path, CONFIG_LIMIT) == discovery_raw
        and read_bounded(identity_path, CONFIG_LIMIT) == identity_raw,
        "INPUT_CHANGED",
    )
    report.update(
        {
            "schema_version": 1,
            "observed_utc": datetime.now(timezone.utc).isoformat(),
            "external_host_identity": safe_identity,
            "post_request_host_recheck": "REQUIRED_FROM_HARNESS",
            "client_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
    )
    require(
        discovery.token.encode() not in canonical(report), "SECRET_REDACTION_FAILURE"
    )
    return report


def write_report(path, report):
    try:
        path = plain_path(path)
        require(path.is_absolute() and path.suffix == ".json", "OUTPUT_PATH")
        raw = canonical(report) + b"\n"
        require(len(raw) <= RESPONSE_LIMIT, "REPORT_SIZE")
        # Dedicated, new output only. Never overwrite a credential/identity file.
        with path.open("xb") as stream:
            stream.write(raw)
    except ProbeError:
        raise
    except OSError:
        raise ProbeError("OUTPUT_UNAVAILABLE") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = probe_from_files(args.identity_receipt)
    except ProbeError as error:
        report = {
            "schema_version": 1,
            "status": "DISCOVERY_FAILED",
            "error_code": error.code,
            "native_tool_calls": 0,
            "native_material_readback": "NOT_RUN",
            "performance_pass": False,
        }
        if error.rpc_code is not None:
            report["rpc_code"] = error.rpc_code
    except Exception:
        # Do not print a traceback, response body, file contents or exception text.
        report = {
            "schema_version": 1,
            "status": "DISCOVERY_FAILED",
            "error_code": "UNEXPECTED_CLIENT_FAILURE",
            "native_tool_calls": 0,
            "native_material_readback": "NOT_RUN",
            "performance_pass": False,
        }
    try:
        write_report(args.output, report)
    except ProbeError:
        print("L07_WINGMAN_DISCOVERY OUTPUT_UNAVAILABLE")
        return 1
    print("L07_WINGMAN_DISCOVERY " + report["status"] + " native_tool_calls=0")
    return 0 if report["status"] == "DISCOVERY_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())

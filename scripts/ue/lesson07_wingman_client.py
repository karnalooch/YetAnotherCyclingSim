"""Bounded host-local Wingman discovery and fixed Lesson07 operations.

Discovery is the default. Opt-in observation admits one hash-pinned adjacent
collector through the exact observed execute_python contract, in file mode.
The separate capture mode requests one current viewport JPEG through the
dedicated screenshot tool, with no camera arguments or Python fallback.
There is no arbitrary code/tool argument, Editor startup or retry surface.
The Windows harness must supply a fresh OS identity receipt and recheck that
identity after this process exits. The receipt is not an active-world readback.

Wire contracts: https://ai.locodev.dev/docs/developers/antigravity and
https://modelcontextprotocol.io/specification/2025-03-26/basic/transports .
The existing fixed BOB client admits JSON only and another protocol/toolset;
this small adapter adds the vendor's JSON/SSE transport, without changing it.
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
CONTRACT_TOOLS = {
    "execute_python",
    "take_viewport_screenshot",
    "read_bp",
    "explore",
    "code_search",
    "edit_texture",
    "edit_material_instance",
    "edit_asset",
    "edit_material",
    "edit_material_function",
    "edit_data_asset",
    "download_asset",
    "vault_asset",
}
CONTRACT_LIMIT = 32 * 1024
CONTRACT_DESCRIPTION_LIMIT = 16 * 1024
CONTRACT_BOOLEAN_ANNOTATIONS = {
    "readOnlyHint",
    "destructiveHint",
    "idempotentHint",
    "openWorldHint",
}
OBSERVER_TOOL = "execute_python"
OBSERVER_FILE = "lesson07_observe_editor.py"
OBSERVER_SHA256 = "033301fa3cd9e35ba68b3ab15754772ba2dcfb2e2dc3aa8b7d01615c60f13bd5"
OBSERVER_SCHEMA_SHA256 = (
    "021f8f2a2f45d8e2047a61d14f619f302ba99f981925b0c6d7b2c3eed4bd6e08"
)
OBSERVER_SOURCE_LIMIT = 64 * 1024
OBSERVER_REQUEST_LIMIT = 64 * 1024
OBSERVER_OUTPUT_LIMIT = 1024 * 1024
OBSERVER_ERROR_TEXT_LIMIT = 2048
OBSERVER_ERROR_BLOCK_LIMIT = 8
OBSERVER_TAG = "YACS_LESSON07_OBSERVATION_V1:"
OBSERVER_STATUS = "OBSERVED_PARTIAL_DIAGNOSIS_NOT_ACCEPTANCE"
OBSERVER_WORLD = (
    "/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.L_SaCalobra_Lesson07"
)
CAPTURE_TOOL = "take_viewport_screenshot"
CAPTURE_SCHEMA_SHA256 = (
    "4ef41b0bf0c6c93d64a049687e0e43565fb351cd484169b58473801840b3dcdc"
)
CAPTURE_TEXT_LIMIT = 16 * 1024
CAPTURE_BLOCK_LIMIT = 8
INSPECTION_RESPONSE_LIMIT = 64 * 1024
INSPECTION_AGGREGATE_LIMIT = 512 * 1024
INSPECTION_SCHEMA_SHA256 = {
    "explore": "76151450f64d19071b12a41adf92d369f749445e78431ccfb0a54e8491dda9b8",
    "edit_material": "69806bca4ebfc563e5b00cd0467cb512c2b968a22359828da7b3c830c4c719f4",
    "edit_material_instance": "f55278fdd0e125dfd8a9844a3508b85ba6f210e3491542dab7239215e2ed73e8",
    "edit_texture": "be32c9649f13ed736dc2ccfb743c2f5c1f11dab9389b707594cef4d309d08a37",
    "edit_asset": "1a12cb39dc34abd43c69e54e9e91e3e5cc4f90dfdcfc55dd945cfc79ead695ba",
    "code_search": "5a8d65250ba94c62dd2cd1be3e622828cd72465d2acf64332f5bee655dd6e7d8",
}
INSPECTION_ROOT = "/Game/Generated/YACS/Lesson07_Unified"
INSPECTION_TARGETS = {
    INSPECTION_ROOT + "/Materials/M_Landscape_YACS": "Material",
    INSPECTION_ROOT
    + "/Materials/MI_Landscape_Instance_YACS": "MaterialInstanceConstant",
    **{
        INSPECTION_ROOT + "/Materials/TA_" + channel + "_Unified": "Texture2DArray"
        for channel in ("Colour", "Normal", "Masks")
    },
    **{
        INSPECTION_ROOT + "/Textures/Slices/T_" + name: "Texture2D"
        for name in ("Grass_Normal", "Grass_Masks", "Cliffs_Normal", "Cliffs_Masks")
    },
    INSPECTION_ROOT + "/Textures/T_PE_Terrain_IDMap": "Texture2D",
    INSPECTION_ROOT + "/Textures/T_PE_Terrain_Color": "Texture2D",
}


def inspection_plan():
    """Only six reviewed dedicated read modes; no caller-supplied arguments."""
    paths = list(INSPECTION_TARGETS)
    return (
        {
            "name": "explore",
            "arguments": {
                "path": INSPECTION_ROOT,
                "limit": 200,
                "offset": 0,
                "recursive": True,
            },
        },
        {"name": "edit_material_instance", "arguments": {"name": paths[1]}},
        {"name": "edit_texture", "arguments": {"names": paths[2:]}},
        {
            "name": "edit_material",
            "arguments": {
                "name": paths[0],
                "save": False,
                "section": "properties",
                "limit": 1000,
                "offset": 0,
            },
        },
        {
            "name": "edit_asset",
            "arguments": {"save_assets": {"paths": paths, "dry_run": True}},
        },
        {
            "name": "code_search",
            "arguments": {
                "operation": "grep",
                "scope": "engine",
                "file_glob": "**/Texture2DArray.cpp",
                "pattern": "PostEditChangeProperty|UpdateSourceFromSourceTextures",
                "context_lines": 12,
                "max_results": 50,
            },
        },
    )


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
            type(value) is dict
            and {"url", "token", "type"} <= set(value)
            and all(type(key) is str for key in value),
            "DISCOVERY_SCHEMA",
        )
        # Installed releases may include metadata. Bound the entire JSON value,
        # then ignore all extra fields: only the three core fields below may
        # select transport, endpoint or credentials. Metadata is never reported.
        try:
            require(len(canonical(value)) <= CONFIG_LIMIT, "DISCOVERY_SIZE")
        except (TypeError, ValueError, RecursionError):
            raise ProbeError("DISCOVERY_SCHEMA") from None
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


def installed_tool_contract(tool, token):
    """Retain selected authenticated metadata as data, without broadening calls."""

    def bounded_json(value, depth=0):
        require(depth <= 12, "CONTRACT_DEPTH")
        if type(value) is dict:
            for key, item in value.items():
                require(type(key) is str, "CONTRACT_JSON")
                require(token not in key, "CONTRACT_CREDENTIAL")
                bounded_json(item, depth + 1)
        elif type(value) is list:
            for item in value:
                bounded_json(item, depth + 1)
        elif type(value) is str:
            require(token not in value, "CONTRACT_CREDENTIAL")
        elif type(value) is float:
            require(math.isfinite(value), "CONTRACT_JSON")
        else:
            require(value is None or type(value) in (bool, int), "CONTRACT_JSON")

    try:
        contract = {"status": "RETAINED", "inputSchema": tool.get("inputSchema")}
        require(type(contract["inputSchema"]) in (dict, bool), "CONTRACT_SCHEMA")
        if "outputSchema" in tool:
            require(type(tool["outputSchema"]) in (dict, bool), "CONTRACT_SCHEMA")
            contract["outputSchema"] = tool["outputSchema"]
        if "description" in tool:
            require(
                type(tool["description"]) is str
                and len(tool["description"]) <= CONTRACT_DESCRIPTION_LIMIT,
                "CONTRACT_DESCRIPTION",
            )
            contract["description"] = tool["description"]
        if "annotations" in tool:
            annotations = tool["annotations"]
            require(type(annotations) is dict, "CONTRACT_ANNOTATIONS")
            retained = {}
            for key in CONTRACT_BOOLEAN_ANNOTATIONS & set(annotations):
                require(type(annotations[key]) is bool, "CONTRACT_ANNOTATIONS")
                retained[key] = annotations[key]
            contract["annotations"] = retained
        bounded_json(contract)
        serialized = canonical(contract)
        require(len(serialized) <= CONTRACT_LIMIT, "CONTRACT_SIZE")
        require(token.encode() not in serialized, "CONTRACT_CREDENTIAL")
        return contract
    except ProbeError as error:
        return {"status": "EXCLUDED", "reason": error.code}
    except (TypeError, ValueError, RecursionError):
        return {"status": "EXCLUDED", "reason": "CONTRACT_JSON"}


@dataclass
class ObservationState:
    """Attempt accounting survives errors after submission and file rechecks."""

    attempted: bool = False
    completed: bool | None = False
    response_received: bool = False
    started_utc: datetime | None = None
    response_received_utc: datetime | None = None
    tool_name: str | None = None
    source_verified: bool = False
    schema_sha256: str | None = None
    result_shape: dict | None = None
    tool_error: dict | None = None
    capture_requested: bool = False
    capture_result: dict | None = None
    installed_tool_contracts: dict | None = None
    tool_list_complete: bool | None = None
    inspection_requested: bool = False
    inspection_results: list = field(default_factory=list)
    inspection_schema_sha256: dict = field(default_factory=dict)
    inspection_registry_verified: bool = False

    def report_fields(self):
        report = {
            # This is a wire-attempt count, not a count of completed evaluations.
            "native_tool_calls": (
                sum(row["attempted"] for row in self.inspection_results)
                if self.inspection_requested
                else int(self.attempted)
            ),
            "native_tool_attempted": self.attempted,
            "native_tool_completed": self.completed,
            "native_tool_response_received": (
                len(self.inspection_results) == 6
                and all(row["response_received"] for row in self.inspection_results)
                if self.inspection_requested
                else self.response_received
            ),
            "native_tool_started_utc": (
                self.started_utc.isoformat() if self.started_utc else None
            ),
            "native_tool_response_received_utc": (
                self.response_received_utc.isoformat()
                if self.response_received_utc
                else None
            ),
            "native_tool_name": self.tool_name,
            "native_tool_result_shape": self.result_shape,
            "native_tool_error": self.tool_error,
        }
        if self.installed_tool_contracts is not None:
            report["installed_tool_contracts"] = self.installed_tool_contracts
            report["tool_list_complete"] = self.tool_list_complete
        if self.inspection_requested:
            report.update(
                {
                    "inspection_results": self.inspection_results,
                    "inspection_schema_sha256": self.inspection_schema_sha256,
                    "inspection_registry_verified": self.inspection_registry_verified,
                }
            )
        elif self.capture_requested:
            report.update(
                {
                    "capture_input_schema_sha256": self.schema_sha256,
                    "capture_arguments": {"return_image": False},
                    "capture_result": self.capture_result,
                }
            )
        else:
            report.update(
                {
                    "observer_source_sha256": OBSERVER_SHA256,
                    "observer_source_verified_before_call": self.source_verified,
                    "observer_input_schema_sha256": self.schema_sha256,
                }
            )
        return report


def validate_observer_schema(schema):
    """Pin the raw installed contract from discovery run 39515925462, source 96a7."""
    require(
        type(schema) is dict
        and set(schema) == {"type", "properties"}
        and schema.get("type") == "object"
        and type(schema.get("properties")) is dict
        and set(schema["properties"]) == {"code", "file", "mode"},
        "OBSERVER_TOOL_SCHEMA_UNSUPPORTED",
    )
    # Full canonical hash includes descriptions, enum ordering and all defaults
    # or constraints. Any installed drift needs a newly reviewed discovery.
    digest = hashlib.sha256(canonical(schema)).hexdigest()
    require(
        digest == OBSERVER_SCHEMA_SHA256,
        "OBSERVER_TOOL_SCHEMA_UNSUPPORTED",
    )
    return digest


def observer_result_shape(result):
    """Bounded fixed-key diagnostics only; never retain native text or values."""
    mcp_fields = {"content", "isError", "structuredContent"}
    wrapper_fields = {
        "success",
        "output",
        "logs",
        "command_result",
        "error",
        "message",
        "result",
    }

    def describe(value):
        names = {
            dict: "object",
            list: "array",
            str: "string",
            bool: "boolean",
            int: "integer",
            float: "number",
            type(None): "null",
        }
        info = {"type": names.get(type(value), "unsupported")}
        if type(value) is str:
            info.update(
                {
                    "characters": len(value),
                    "tag_occurrences": value.count(OBSERVER_TAG),
                    "has_uobject_pin_footer": "UObject pin report" in value,
                }
            )
        elif type(value) in (dict, list):
            info["count"] = len(value)
        return info

    def known_fields(value, allowed):
        summary = describe(value)
        if type(value) is dict:
            summary["fields"] = {
                key: describe(value[key]) for key in sorted(allowed & set(value))
            }
            summary["unknown_field_count"] = len(set(value) - allowed)
        return summary

    summary = known_fields(result, mcp_fields | wrapper_fields)
    if type(result) is not dict:
        return summary
    if "structuredContent" in result:
        summary["structured_content"] = known_fields(
            result["structuredContent"], wrapper_fields
        )
    content = result.get("content")
    if type(content) is list:
        blocks = []
        for block in content[:8]:
            row = describe(block)
            if type(block) is dict:
                kind = block.get("type")
                row["content_type"] = (
                    kind
                    if type(kind) is str
                    and kind in {"text", "image", "audio", "resource", "resource_link"}
                    else "other"
                )
                if type(block.get("text")) is str:
                    text = block["text"]
                    row["text"] = describe(text)
                    try:
                        parsed = parse_json(text.encode("utf-8"))
                    except (ProbeError, UnicodeError):
                        row["text_json_parsed"] = False
                    else:
                        row["text_json_parsed"] = True
                        row["text_json"] = known_fields(parsed, wrapper_fields)
            blocks.append(row)
        summary["content_blocks"] = blocks
        summary["content_blocks_truncated"] = len(content) > 8
    return summary


def sanitize_native_text(text, secrets, *, preserve_newlines=False):
    """Remove credentials and control characters before applying output caps."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    text = "".join(
        char if char.isprintable() or char in "\r\n" else " " if char.isspace() else ""
        for char in text
    )
    # Conservatively discard the remainder after a credential assignment or
    # Bearer value, including quoted/multiline values, before any output limit.
    text = re.sub(
        r"\b(?:authorization|proxy[-_]authorization|password|passwd|pwd|secret|"
        r"(?:access|refresh|id|auth)[-_ ]?token|token|api[-_ ]?key|"
        r"client[-_ ]?secret|credentials?|cookie|set[-_]cookie|"
        r"(?:mcp[-_])?session[-_ ]?(?:id|token))\b[\"']?\s*[:=].*"
        r"|\bbearer\s+.*",
        "[REDACTED_CREDENTIAL]",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = re.sub(
        r"\b[a-z][a-z0-9+.-]*://[^\s<>\"']+",
        "[REDACTED_URL]",
        text,
        flags=re.IGNORECASE,
    )
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return (
        re.sub(r"\r\n?", "\n", text)
        if preserve_newlines
        else re.sub(r"[\r\n]+", " | ", text)
    )


def observer_error_diagnostic(result, secrets):
    """Retain bounded standard MCP error text, sanitized before truncation."""
    if type(result) is not dict or result.get("isError") is not True:
        return None
    content = result.get("content")
    blocks = content if type(content) is list else []
    texts = [
        block["text"]
        for block in blocks[:OBSERVER_ERROR_BLOCK_LIMIT]
        if type(block) is dict
        and block.get("type") == "text"
        and type(block.get("text")) is str
    ]
    text = sanitize_native_text("\n".join(texts), secrets)
    return {
        "sanitized_text": text[:OBSERVER_ERROR_TEXT_LIMIT],
        "retained_text_blocks": len(texts),
        "content_blocks_truncated": len(blocks) > OBSERVER_ERROR_BLOCK_LIMIT,
        "text_truncated": len(text) > OBSERVER_ERROR_TEXT_LIMIT,
    }


def validate_capture_schema(schema):
    """Pin the complete screenshot schema retained by authenticated discovery."""
    require(type(schema) is dict, "CAPTURE_TOOL_SCHEMA_UNSUPPORTED")
    digest = hashlib.sha256(canonical(schema)).hexdigest()
    require(digest == CAPTURE_SCHEMA_SHA256, "CAPTURE_TOOL_SCHEMA_UNSUPPORTED")
    return digest


def retain_capture_result(result, state, secrets):
    """Keep standard text only; the host separately verifies the returned JPEG."""
    require(type(result) is dict, "CAPTURE_RESULT_SHAPE")
    if "isError" in result:
        require(type(result["isError"]) is bool, "CAPTURE_RESULT_SHAPE")
        require(not result["isError"], "CAPTURE_TOOL_ERROR")
    require("structuredContent" not in result, "CAPTURE_RESULT_WRAPPER_UNSUPPORTED")
    content = result.get("content")
    require(
        type(content) is list and 0 < len(content) <= CAPTURE_BLOCK_LIMIT,
        "CAPTURE_RESULT_SHAPE",
    )
    texts = []
    for block in content:
        require(
            type(block) is dict
            and block.get("type") == "text"
            and type(block.get("text")) is str,
            "CAPTURE_RESULT_SHAPE",
        )
        texts.append(block["text"])
    text = "\n".join(texts)
    require(
        re.search(r"IMAGE_BASE64:|data:image/", text, re.IGNORECASE) is None,
        "CAPTURE_INLINE_IMAGE_DENIED",
    )
    text = sanitize_native_text(text, secrets, preserve_newlines=True)
    state.capture_result = {
        "text": text[:CAPTURE_TEXT_LIMIT],
        "text_truncated": len(text) > CAPTURE_TEXT_LIMIT,
        "text_block_count": len(texts),
        "response_sha256": hashlib.sha256(canonical(result)).hexdigest(),
    }
    require(0 < len(text) <= CAPTURE_TEXT_LIMIT, "CAPTURE_RESULT_TEXT_SIZE")
    return state.capture_result


def validate_inspection_schemas(schemas):
    """Validate every installed raw input schema before the first native call."""
    hashes = {}
    for name, expected in INSPECTION_SCHEMA_SHA256.items():
        schema = schemas.get(name)
        require(type(schema) is dict, "INSPECTION_TOOL_SCHEMA_UNSUPPORTED")
        digest = hashlib.sha256(canonical(schema)).hexdigest()
        require(digest == expected, "INSPECTION_TOOL_SCHEMA_UNSUPPORTED")
        hashes[name] = digest
    return hashes


def retain_inspection_result(result, row, secrets):
    """Retain bounded standard text without interpreting vendor result wrappers."""
    require(type(result) is dict, "INSPECTION_RESULT_SHAPE")
    require(
        "isError" not in result or type(result["isError"]) is bool,
        "INSPECTION_RESULT_SHAPE",
    )
    content = result.get("content")
    require(type(content) is list and 0 < len(content) <= 16, "INSPECTION_RESULT_SHAPE")
    require(
        all(
            type(block) is dict
            and block.get("type") == "text"
            and type(block.get("text")) is str
            for block in content
        ),
        "INSPECTION_RESULT_SHAPE",
    )
    text = sanitize_native_text(
        "\n".join(block["text"] for block in content), secrets, preserve_newlines=True
    )
    require(
        re.search(r"IMAGE_BASE64:|data:image/", text, re.IGNORECASE) is None,
        "INSPECTION_INLINE_IMAGE_DENIED",
    )
    # Budget serialized JSON bytes (including escapes), leaving room for the
    # fixed arguments/timing fields. Redaction happens before this truncation.
    low, high = 0, min(len(text), INSPECTION_RESPONSE_LIMIT - 4096)
    while low < high:
        middle = (low + high + 1) // 2
        if len(canonical(text[:middle])) <= INSPECTION_RESPONSE_LIMIT - 4096:
            low = middle
        else:
            high = middle - 1
    row["result"] = {
        "text": text[:low],
        "text_truncated": low < len(text),
        "text_block_count": len(content),
        "response_sha256": hashlib.sha256(canonical(result)).hexdigest(),
    }
    require(len(canonical(row)) <= INSPECTION_RESPONSE_LIMIT, "INSPECTION_RESULT_SIZE")
    require(not result.get("isError", False), "INSPECTION_TOOL_ERROR")
    require(0 < len(text) and low == len(text), "INSPECTION_RESULT_SIZE")


def verify_inspection_registry(text):
    """Validate the observed assets footer; each row names a directory + asset."""
    lines = re.findall(r"(?m)^#json-explore:([^\r\n]+)$", text)
    require(
        text.count("#json-explore:") == 1 and len(lines) == 1,
        "INSPECTION_REGISTRY_FORMAT",
    )
    registry = parse_json(lines[0].encode("utf-8"), INSPECTION_RESPONSE_LIMIT)
    require(
        type(registry) is dict
        and set(registry) == {
            "mode", "scope", "shown", "total", "offset", "limit", "truncated",
            "raw_from_registry", "loaded_in_shown", "filters", "rows",
        }
        and registry["mode"] == "assets"
        and registry["scope"] == INSPECTION_ROOT,
        "INSPECTION_REGISTRY_FORMAT",
    )
    require(
        all(type(registry[key]) is int for key in (
            "shown", "total", "offset", "limit", "raw_from_registry", "loaded_in_shown"
        ))
        and type(registry["rows"]) is list
        and 0 < len(registry["rows"]) <= 200
        and registry["shown"] == registry["total"] == registry["raw_from_registry"] == len(registry["rows"])
        and registry["offset"] == 0
        and registry["limit"] == 200
        and registry["truncated"] is False
        and 0 <= registry["loaded_in_shown"] <= registry["shown"],
        "INSPECTION_REGISTRY_INCOMPLETE",
    )
    filters = registry["filters"]
    require(
        type(filters) is dict
        and filters == {
            "pattern": "", "query": "", "type": "", "class_path": "",
            "class_filter_recursive": False,
        }
        and filters["class_filter_recursive"] is False,
        "INSPECTION_REGISTRY_FORMAT",
    )
    headers = re.findall(
        r"(?m)^# ASSETS " + re.escape(INSPECTION_ROOT)
        + r" shown=([0-9]{1,3}) total=([0-9]{1,3}) offset=([0-9]{1,3})"
        + r" limit=([0-9]{1,3}) loaded=([0-9]{1,3})/([0-9]{1,3})$",
        text,
    )
    require(
        len(headers) == 1
        and tuple(map(int, headers[0])) == (
            registry["shown"], registry["total"], registry["offset"], registry["limit"],
            registry["loaded_in_shown"], registry["shown"],
        ),
        "INSPECTION_REGISTRY_INCOMPLETE",
    )
    seen = set()
    loaded = 0
    for row in registry["rows"]:
        require(
            type(row) is dict
            and set(row) == {"name", "path", "class", "class_path", "loaded"}
            and all(type(row[key]) is str for key in ("name", "path", "class", "class_path"))
            and type(row["loaded"]) is bool
            and re.fullmatch(r"[A-Za-z0-9_]{1,128}", row["name"]) is not None
            and re.fullmatch(re.escape(INSPECTION_ROOT) + r"(?:/[A-Za-z0-9_]{1,128})*", row["path"]) is not None,
            "INSPECTION_REGISTRY_FORMAT",
        )
        require(
            re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,127}", row["class"]) is not None
            and row["class_path"] == "/Script/Engine." + row["class"],
            "INSPECTION_REGISTRY_CLASS",
        )
        package = row["path"] + "/" + row["name"]
        require(package not in seen, "INSPECTION_REGISTRY_AMBIGUOUS")
        seen.add(package)
        if package in INSPECTION_TARGETS:
            require(row["class"] == INSPECTION_TARGETS[package], "INSPECTION_REGISTRY_CLASS")
        loaded += row["loaded"]
    require(loaded == registry["loaded_in_shown"], "INSPECTION_REGISTRY_INCOMPLETE")
    require(set(INSPECTION_TARGETS) <= seen, "INSPECTION_REGISTRY_TARGET_MISSING")


def observer_loader():
    """Embed only the locally verified collector; the native side reads no file."""
    source_path = Path(__file__).absolute().with_name(OBSERVER_FILE)
    source = read_bounded(source_path, OBSERVER_SOURCE_LIMIT)
    require(
        hashlib.sha256(source).hexdigest() == OBSERVER_SHA256,
        "OBSERVER_SOURCE_HASH",
    )
    # Plain Python source bytes, never compressed or encoded as an opaque blob.
    # Both namespaces are fresh. The native side hashes and executes the same
    # embedded bytes; no source path, import cache, run_path, or file I/O.
    body = f"""import hashlib
import json
source = {source!r}
if hashlib.sha256(source).hexdigest() != {OBSERVER_SHA256!r}:
    raise RuntimeError("OBSERVER_SOURCE_HASH")
scope = {{"__name__": "_yacs_lesson07_observer"}}
exec(compile(source, "<yacs_lesson07_observer>", "exec"), scope, scope)
collected = scope["collect_json"]()
if type(collected) is not str or not 0 < len(collected.encode("utf-8")) <= {OBSERVER_OUTPUT_LIMIT}:
    raise RuntimeError("OBSERVER_OUTPUT_SIZE")
envelope = {{"observer_sha256": {OBSERVER_SHA256!r}, "observation": json.loads(collected)}}
print({OBSERVER_TAG!r} + json.dumps(envelope, ensure_ascii=True, allow_nan=False, separators=(",", ":")))
"""
    return f"exec({body!r}, {{'__name__': '_yacs_lesson07_loader'}})"


def extract_observation(result, identity, state):
    """Accept one exact tagged envelope in standard MCP text, never raw logs."""
    require(type(result) is dict, "OBSERVER_RESULT_SHAPE")
    if "isError" in result:
        require(type(result["isError"]) is bool, "OBSERVER_RESULT_SHAPE")
        require(not result["isError"], "OBSERVER_TOOL_ERROR")
    # No undocumented vendor wrapper or structured output interpretation.
    require("structuredContent" not in result, "OBSERVER_RESULT_WRAPPER_UNSUPPORTED")
    content = result.get("content")
    require(
        type(content) is list and 0 < len(content) <= 16,
        "OBSERVER_RESULT_SHAPE",
    )
    texts = []
    for block in content:
        require(
            type(block) is dict
            and block.get("type") == "text"
            and type(block.get("text")) is str,
            "OBSERVER_RESULT_SHAPE",
        )
        texts.append(block["text"])
    text = "\n".join(texts).strip()
    require(
        text.count(OBSERVER_TAG) == 1 and text.startswith(OBSERVER_TAG),
        "OBSERVER_RESULT_TAG",
    )
    envelope = parse_json(
        text[len(OBSERVER_TAG) :].encode("utf-8"), OBSERVER_OUTPUT_LIMIT
    )
    require(
        type(envelope) is dict
        and set(envelope) == {"observer_sha256", "observation"}
        and envelope["observer_sha256"] == OBSERVER_SHA256,
        "OBSERVER_RESULT_SOURCE",
    )
    observed = envelope["observation"]
    require(
        type(observed) is dict and observed.get("status") == OBSERVER_STATUS,
        "OBSERVER_RESULT_STATUS",
    )
    require(
        type(observed.get("pid")) is int and observed["pid"] == identity["pid"],
        "OBSERVER_RESULT_PID",
    )
    for key, expected in (
        ("project", str(PureWindowsPath(PROJECT).parent)),
        ("project_file", PROJECT),
    ):
        require(
            type(observed.get(key)) is str
            and PureWindowsPath(observed[key]) == PureWindowsPath(expected),
            "OBSERVER_RESULT_PROJECT",
        )
    require(observed.get("world") == OBSERVER_WORLD, "OBSERVER_RESULT_WORLD")
    observed_at = utc(observed.get("observed_at_utc"))
    require(
        state.started_utc is not None
        and (observed_at - state.started_utc).total_seconds() >= -5
        and (datetime.now(timezone.utc) - observed_at).total_seconds() >= -5,
        "OBSERVER_RESULT_STALE",
    )
    limitations = observed.get("limitations")
    require(
        type(limitations) is dict
        and all(
            limitations.get(key) is False
            for key in (
                "mutating_apis_requested",
                "asset_loads_requested",
                "new_captures",
                "visual_acceptance",
                "performance_pass",
            )
        )
        and type(observed.get("validation")) is dict
        and observed["validation"].get("visual_or_native_graph_acceptance") is False,
        "OBSERVER_RESULT_ACCEPTANCE",
    )
    return observed


class DiscoveryClient:
    def __init__(
        self, discovery, identity, timeout=TIMEOUT_SECONDS, observation_state=None
    ):
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
        self.observation_state = observation_state or ObservationState()
        self._observer_params = None
        self._capture_params = None
        self._inspection_params = None
        self._inspection_row = None

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

    def _read_result(self, response, request_id, wire, deadline, line_limit=LINE_LIMIT):
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
            line = response.readline(line_limit + 1)
            total += len(line)
            require(
                len(line) <= line_limit and total <= RESPONSE_LIMIT, "HTTP_BODY_SIZE"
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
        observing = (
            method == "tools/call"
            and self._observer_params is not None
            and params is self._observer_params
            and not self.observation_state.attempted
            and not notification
        )
        capturing = (
            method == "tools/call"
            and self._capture_params is not None
            and params is self._capture_params
            and not self.observation_state.attempted
            and not notification
        )
        if capturing:
            require(
                params == {"name": CAPTURE_TOOL, "arguments": {"return_image": False}}
                and params["arguments"]["return_image"] is False,
                "CAPTURE_ARGUMENTS",
            )
        inspecting = (
            method == "tools/call"
            and self._inspection_params is not None
            and params is self._inspection_params
            and self._inspection_row is not None
            and not self._inspection_row["attempted"]
            and not notification
        )
        if inspecting:
            state = self.observation_state
            index = len(state.inspection_results) - 1
            require(
                state.inspection_requested
                and 0 <= index < 6
                and self._inspection_row is state.inspection_results[index]
                and all(
                    row["completed"] is True for row in state.inspection_results[:index]
                )
                and (index == 0 or state.inspection_registry_verified)
                and state.inspection_schema_sha256 == INSPECTION_SCHEMA_SHA256
                and canonical(params) == canonical(inspection_plan()[index]),
                "INSPECTION_ARGUMENTS",
            )
        native_call = observing or capturing or inspecting
        require(
            method in METHODS
            or (notification and method == "notifications/initialized")
            or native_call,
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
        require(
            len(raw) <= (OBSERVER_REQUEST_LIMIT if observing else CONFIG_LIMIT),
            "REQUEST_SIZE",
        )
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
            if native_call:
                # request() may partially send and then raise. Never retry it.
                self.observation_state.attempted = True
                self.observation_state.completed = None
                self.observation_state.started_utc = datetime.now(timezone.utc)
                if inspecting:
                    self._inspection_row.update(
                        {
                            "attempted": True,
                            "completed": None,
                            "started_utc": self.observation_state.started_utc.isoformat(),
                        }
                    )
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
            result = self._read_result(
                response,
                request_id,
                wire,
                deadline,
                RESPONSE_LIMIT if observing else LINE_LIMIT,
            )
            if native_call:
                self.observation_state.response_received = True
                self.observation_state.response_received_utc = datetime.now(
                    timezone.utc
                )
                if inspecting:
                    self._inspection_row.update(
                        {
                            "response_received": True,
                            "response_received_utc": self.observation_state.response_received_utc.isoformat(),
                        }
                    )
            return result
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

    def probe(
        self, observe_lesson07=False, capture_lesson07=False, inspect_lesson07=False
    ):
        require(
            sum((observe_lesson07, capture_lesson07, inspect_lesson07)) <= 1,
            "NATIVE_MODES_MUTUALLY_EXCLUSIVE",
        )
        self.observation_state.capture_requested = capture_lesson07
        self.observation_state.inspection_requested = inspect_lesson07
        if capture_lesson07 or observe_lesson07:
            self.observation_state.tool_name = (
                CAPTURE_TOOL if capture_lesson07 else OBSERVER_TOOL
            )
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
        contracts = {}
        cursor = None
        seen_cursors = set()
        tool_error = None
        observer_schema = None
        capture_schema = None
        inspection_schemas = {}
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
                    if name in CONTRACT_TOOLS:
                        contracts[name] = installed_tool_contract(
                            tool, self.discovery.token
                        )
                    tools.append(
                        {
                            "name": name,
                            "inputSchema": schema_structure(
                                tool.get("inputSchema"), self.discovery.token
                            ),
                        }
                    )
                    if name == OBSERVER_TOOL:
                        observer_schema = tool.get("inputSchema")
                    if name == CAPTURE_TOOL:
                        capture_schema = tool.get("inputSchema")
                    if name in INSPECTION_SCHEMA_SHA256:
                        inspection_schemas[name] = tool.get("inputSchema")
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
        # Preserve only the already bounded/credential-checked descriptors if a
        # later native call fails. No discovery replay or raw listing is kept.
        self.observation_state.installed_tool_contracts = contracts
        self.observation_state.tool_list_complete = tool_error is None
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
        report = {
            "status": "DISCOVERY_INCOMPLETE"
            if tool_error
            else (
                "DISCOVERY_COMPLETE" if session["signed_in"] else "DISCOVERY_SIGNED_OUT"
            ),
            "protocol_version": PROTOCOL,
            "session": safe_session,
            "tools": tools,
            "installed_tool_contracts": contracts,
            "tool_list_complete": tool_error is None,
            "tool_list_error": tool_error,
            "schema_fidelity": "STRUCTURE_ONLY_FREE_TEXT_DEFAULTS_ENUMS_OMITTED",
            "http_requests": self.requests,
            "notifications_received": self.notifications_received,
            "native_tool_calls": 0,
            "native_material_readback": "NOT_RUN",
            "performance_pass": False,
        }
        if observe_lesson07:
            require(tool_error is None, "OBSERVER_INCOMPLETE_TOOL_LIST")
            require(session["signed_in"], "OBSERVER_SIGNED_OUT")
            state = self.observation_state
            state.schema_sha256 = validate_observer_schema(observer_schema)
            code = observer_loader()
            state.source_verified = True
            self._observer_params = {
                "name": OBSERVER_TOOL,
                "arguments": {"code": code, "mode": "file"},
            }
            result = self._post("tools/call", self._observer_params)
            state.result_shape = observer_result_shape(result)
            state.tool_error = observer_error_diagnostic(
                result, (self.discovery.token, self.session_id)
            )
            observed = extract_observation(result, self.identity, state)
            state.completed = True
            report.update(
                {
                    "status": "OBSERVATION_COMPLETE",
                    "http_requests": self.requests,
                    "notifications_received": self.notifications_received,
                    "native_material_readback": OBSERVER_STATUS,
                    "observation": observed,
                    "observer_contract": "PINNED_INSTALLED_SCHEMA_INLINE_CODE_EXPLICIT_FILE_MODE",
                    "plugin_execution_defaults_verified": False,
                    "visual_acceptance": False,
                    **state.report_fields(),
                }
            )
        if capture_lesson07:
            require(tool_error is None, "CAPTURE_INCOMPLETE_TOOL_LIST")
            require(session["signed_in"], "CAPTURE_SIGNED_OUT")
            state = self.observation_state
            state.schema_sha256 = validate_capture_schema(capture_schema)
            self._capture_params = {
                "name": CAPTURE_TOOL,
                "arguments": {"return_image": False},
            }
            result = self._post("tools/call", self._capture_params)
            state.result_shape = observer_result_shape(result)
            state.tool_error = observer_error_diagnostic(
                result, (self.discovery.token, self.session_id)
            )
            retain_capture_result(
                result, state, (self.discovery.token, self.session_id)
            )
            state.completed = True
            report.update(
                {
                    "status": "CAPTURE_RESPONSE_RECEIVED",
                    "http_requests": self.requests,
                    "notifications_received": self.notifications_received,
                    "native_material_readback": "NOT_RUN",
                    "capture_file_verified": False,
                    "visual_acceptance": False,
                    **state.report_fields(),
                }
            )
        if inspect_lesson07:
            require(tool_error is None, "INSPECTION_INCOMPLETE_TOOL_LIST")
            require(session["signed_in"], "INSPECTION_SIGNED_OUT")
            state = self.observation_state
            state.inspection_schema_sha256 = validate_inspection_schemas(
                inspection_schemas
            )
            for index, params in enumerate(inspection_plan(), 1):
                row = {
                    "index": index,
                    "tool_name": params["name"],
                    "arguments": params["arguments"],
                    "input_schema_sha256": state.inspection_schema_sha256[
                        params["name"]
                    ],
                    "attempted": False,
                    "completed": False,
                    "response_received": False,
                    "started_utc": None,
                    "response_received_utc": None,
                    "result": None,
                    "error_code": None,
                }
                state.inspection_results.append(row)
                self._inspection_params, self._inspection_row = params, row
                state.tool_name = params["name"]
                state.tool_error = state.result_shape = None
                try:
                    result = self._post("tools/call", params)
                    retain_inspection_result(
                        result, row, (self.discovery.token, self.session_id)
                    )
                    row["completed"] = True
                    if index == 1:
                        verify_inspection_registry(row["result"]["text"])
                        state.inspection_registry_verified = True
                    require(
                        len(canonical(state.inspection_results))
                        <= INSPECTION_AGGREGATE_LIMIT,
                        "INSPECTION_AGGREGATE_SIZE",
                    )
                except ProbeError as error:
                    row["error_code"] = error.code
                    raise
            state.completed = True
            report.update(
                {
                    "status": "INSPECTION_RESPONSES_RECEIVED",
                    "http_requests": self.requests,
                    "notifications_received": self.notifications_received,
                    "native_material_readback": "RAW_RESPONSES_REVIEW_PENDING",
                    "visual_acceptance": False,
                    **state.report_fields(),
                }
            )
        return report


def probe_from_files(
    identity_path,
    discovery_path=DISCOVERY_PATH,
    *,
    observe_lesson07=False,
    capture_lesson07=False,
    inspect_lesson07=False,
    observation_state=None,
):
    require(WINDOWS_HOST, "WINDOWS_HOST_REQUIRED")
    discovery_raw = read_bounded(discovery_path, CONFIG_LIMIT)
    discovery = Discovery.from_mapping(parse_json(discovery_raw, CONFIG_LIMIT))
    identity_raw = read_bounded(identity_path, CONFIG_LIMIT)
    identity = parse_json(identity_raw, CONFIG_LIMIT)
    safe_identity = validate_identity(identity, discovery)
    client = DiscoveryClient(discovery, identity, observation_state=observation_state)
    report = client.probe(
        observe_lesson07=observe_lesson07,
        capture_lesson07=capture_lesson07,
        inspect_lesson07=inspect_lesson07,
    )
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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--observe-lesson07", action="store_true")
    mode.add_argument("--capture-lesson07", action="store_true")
    mode.add_argument("--inspect-lesson07", action="store_true")
    args = parser.parse_args(argv)
    state = ObservationState(
        capture_requested=args.capture_lesson07,
        inspection_requested=args.inspect_lesson07,
    )
    error_code = None
    rpc_code = None
    try:
        options = {
            "observe_lesson07": args.observe_lesson07,
            "observation_state": state,
        }
        if args.capture_lesson07:
            options["capture_lesson07"] = True
        if args.inspect_lesson07:
            options["inspect_lesson07"] = True
        report = probe_from_files(args.identity_receipt, **options)
    except ProbeError as error:
        error_code, rpc_code = error.code, error.rpc_code
    except Exception:
        # Do not print a traceback, response body, file contents or exception text.
        error_code = "UNEXPECTED_CLIENT_FAILURE"
    if error_code is not None:
        report = {
            "schema_version": 1,
            "status": "INSPECTION_FAILED"
            if args.inspect_lesson07
            else "CAPTURE_FAILED"
            if args.capture_lesson07
            else "OBSERVATION_FAILED"
            if args.observe_lesson07
            else "DISCOVERY_FAILED",
            "error_code": error_code,
            "native_tool_calls": 0,
            "native_material_readback": (
                "RAW_RESPONSES_REVIEW_PENDING"
                if args.inspect_lesson07 and state.attempted
                else "UNVERIFIED"
                if state.attempted and not args.capture_lesson07
                else "NOT_RUN"
            ),
            "visual_acceptance": False,
            "performance_pass": False,
        }
        if args.observe_lesson07 or args.capture_lesson07 or args.inspect_lesson07:
            report.update(state.report_fields())
        if rpc_code is not None:
            report["rpc_code"] = rpc_code
    prefix = (
        "L07_WINGMAN_INSPECTION"
        if args.inspect_lesson07
        else "L07_WINGMAN_CAPTURE"
        if args.capture_lesson07
        else "L07_WINGMAN_OBSERVATION"
        if args.observe_lesson07
        else "L07_WINGMAN_DISCOVERY"
    )
    try:
        write_report(args.output, report)
    except ProbeError:
        print(
            prefix
            + f" OUTPUT_UNAVAILABLE native_tool_calls={state.report_fields()['native_tool_calls']}"
        )
        return 1
    print(
        prefix
        + " "
        + report["status"]
        + f" native_tool_calls={report['native_tool_calls']}"
    )
    expected = (
        "INSPECTION_RESPONSES_RECEIVED"
        if args.inspect_lesson07
        else "CAPTURE_RESPONSE_RECEIVED"
        if args.capture_lesson07
        else "OBSERVATION_COMPLETE"
        if args.observe_lesson07
        else "DISCOVERY_COMPLETE"
    )
    return 0 if report["status"] == expected else 1


if __name__ == "__main__":
    raise SystemExit(main())

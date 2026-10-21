"""Bounded host-local Wingman discovery and fixed Lesson07 operations.

Discovery is the default. Opt-in observation admits one hash-pinned adjacent
collector through the exact observed execute_python contract, in file mode.
The separate capture mode requests one current viewport JPEG through the
dedicated screenshot tool, with no camera arguments or Python fallback.
Vault inspection lists only three fixed name filters in the already-owned
local cache; it cannot install, download or execute code.
Surface import executes one pinned project-local importer between two native
captures at the same camera, then three fixed review views; normal tool safety
review remains active.
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
import io
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
import struct
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
VAULT_TOOL = "vault_asset"
VAULT_SCHEMA_SHA256 = "13ca66118e6fa53a0c8e1651374d001f756f7f0633d374bc5367336f06519ebf"
VAULT_FILTERS = ("limestone", "cliff", "rock")
VAULT_PUBLIC_SHORTLIST = (
    "Mediterranean Karst Biome", "Quarry Cliff", "Layered Rock Cliff",
    "Limestone Rock Strata", "Dolomites", "Shore lime rocks",
)
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
TRIAL_MI = INSPECTION_ROOT + "/Materials/MI_Landscape_Instance_YACS"
TRIAL_BACKUP = INSPECTION_ROOT + "/RepairBackups/MI_PreMacroTrial_20261021"
# Complete ordered #json-mi snapshot observed in run 39530647438. Repeated
# layer parameter names are intentional; never collapse these lists to maps.
TRIAL_BASELINE_SHA256 = "0b082e2e99bd7d12c307309a34704c4290eda073c6c895b8cdb3e91d4ded3bdd"
TRIAL_VALUE = 0.05
TRIAL_VALUE_F32 = struct.unpack("<f", struct.pack("<f", TRIAL_VALUE))[0]
TRIAL_SCHEMA_SHA256 = {
    name: INSPECTION_SCHEMA_SHA256[name]
    for name in ("explore", "edit_material_instance", "edit_asset")
}
TRIAL_SCHEMA_SHA256[CAPTURE_TOOL] = CAPTURE_SCHEMA_SHA256
TRIAL_SECONDS = 300
# Admit the mutation only with all remaining planned requests plus a full
# three-call recovery allowance, capture spacing and local checks reserved.
TRIAL_MUTATION_RESERVE_SECONDS = 9 * TIMEOUT_SECONDS + 3 + 10
TRIAL_CAPTURE_STAGES = ("A_baseline", "B_macro_005", "A_restored")
APPLY_CAPTURE_STAGE = "B_applied_macro_005"
APPLY_REVIEWED_TRIAL_PATH = Path(r"D:\yacs\lesson07-remote\reports\39532652532-1\bridge.json")
APPLY_REVIEWED_TRIAL_SHA256 = "e901c56e83821e771816be8f4dff49cfdad21c015f0b516cd06368cce9d072f4"
APPLY_REVIEWED_TRIAL_SOURCE = "71914188cbdaeac200074b8a070e2f44ed50e501"


# This is a new bounded material import, not a replay of the frozen observer.
# The vendor execute_python safety gate remains active and sees the clear file path.
SURFACE_IMPORT_FILE = "apply_lesson07_surface_repair.py"
SURFACE_IMPORT_SHA256 = "6c824070afe0ecc178dfa96d5f5fdef44d8b83168250a3917bc7c4c6da85d78e"
SURFACE_ROOT = Path("D:/yacs/project/Saved/RuntimeProof/Lesson07SurfaceRepair-20261021")
SURFACE_TAG = "YACS_L07_SURFACE_IMPORT="
SURFACE_TIMEOUT_SECONDS = 180.0


def surface_stage(run_token):
    require(type(run_token) is str and re.fullmatch(r"[1-9][0-9]{0,19}-[1-9][0-9]{0,4}", run_token),
            "SURFACE_RUN_TOKEN")
    return SURFACE_ROOT / run_token


def surface_plan(run_token):
    stage = surface_stage(run_token)
    captures = surface_capture_specs()
    return [
        {"name": CAPTURE_TOOL, "arguments": captures[1][1]},
        {"name": OBSERVER_TOOL, "arguments": {"file": str(stage / SURFACE_IMPORT_FILE).replace("\\", "/"), "mode": "file"}},
    ] + [{"name": CAPTURE_TOOL, "arguments": captures[index][1]} for index in (3, 4, 5, 6)]


def surface_capture_specs():
    return {
        1: ("surface-before.jpg", trial_capture_arguments()),
        3: ("surface-after.jpg", trial_capture_arguments()),
        4: ("surface-panorama.jpg", {
            "return_image": False, "camera_location": [-810000, -900000, 724000],
            "camera_rotation": [-29.462259194079675, 48.01278750418334, 0], "fov": 75}),
        5: ("surface-puig-major.jpg", {
            "return_image": False, "camera_location": [-278375, 199525, 180000],
            "camera_rotation": [-9.706195089959548, 45, 0], "fov": 50}),
        6: ("surface-scree.jpg", {
            "return_image": False, "camera_location": [-250925, -184475, 33571],
            "camera_rotation": [-89.90162277905554, 90, 0], "fov": 50}),
    }


def verify_surface_source(run_token):
    source = read_bounded(surface_stage(run_token) / SURFACE_IMPORT_FILE, 256 * 1024)
    require(hashlib.sha256(source).hexdigest() == SURFACE_IMPORT_SHA256,
            "SURFACE_IMPORT_SOURCE_HASH")


def verify_surface_summary(text):
    require(text.count(SURFACE_TAG) == 1, "SURFACE_RECEIPT_TAG")
    raw = text.split(SURFACE_TAG, 1)[1].splitlines()[0]
    summary = parse_json(raw.encode(), 16 * 1024)
    require(type(summary) is dict and summary.get("status") == "SURFACE_REPAIR_SAVED_NATIVE_READBACK_PENDING_VISUAL"
            and summary.get("saved") is True and summary.get("changed_slots") == [0, 3]
            and type(summary.get("changed_slots")) is list
            and all(type(slot) is int for slot in summary["changed_slots"])
            and summary.get("classification_changed") is False
            and summary.get("terrain_changed") is False
            and summary.get("normal_flatten_preserved") is True
            and type(summary.get("failure_count")) is int and summary["failure_count"] == 0,
            "SURFACE_NATIVE_READBACK")
    return summary


def read_surface_receipt(run_token, row):
    path = plain_path(surface_stage(run_token) / "live-import.json")
    before = path.stat()
    started = utc(row["started_utc"]).timestamp()
    require(started - 2 <= before.st_mtime <= datetime.now(timezone.utc).timestamp() + 2,
            "SURFACE_RECEIPT_STALE")
    raw = read_bounded(path, 256 * 1024)
    after = path.stat()
    require(before.st_size == after.st_size == len(raw) and before.st_mtime_ns == after.st_mtime_ns,
            "SURFACE_RECEIPT_CHANGED")
    receipt = parse_json(raw, 256 * 1024)
    require(type(receipt) is dict, "SURFACE_SAVED_RECEIPT")
    return receipt


def retain_surface_capture(run_token, row):
    """Read only the exact returned native JPEG; never manufacture a preview."""
    from PIL import Image

    require(row["index"] in surface_capture_specs(), "SURFACE_CAPTURE_INDEX")
    filename, camera = surface_capture_specs()[row["index"]]
    require(canonical(row["arguments"]) == canonical(camera), "SURFACE_CAPTURE_CAMERA")
    path = plain_path(Path(verify_trial_capture(row["result"]["text"], expected=camera)))
    before = path.stat()
    started = utc(row["started_utc"]).timestamp()
    require(started - 2 <= before.st_mtime <= datetime.now(timezone.utc).timestamp() + 2,
            "SURFACE_CAPTURE_STALE")
    data = read_bounded(path, 32 * 1024 * 1024)
    after = path.stat()
    require(before.st_size == after.st_size == len(data) and before.st_mtime_ns == after.st_mtime_ns,
            "SURFACE_CAPTURE_CHANGED")
    with Image.open(io.BytesIO(data)) as picture:
        require(picture.format == "JPEG" and 0 < picture.width <= 16384 and 0 < picture.height <= 16384,
                "SURFACE_CAPTURE_FORMAT")
        size = list(picture.size)
        picture.verify()
    dest = surface_stage(run_token) / filename
    plain_path(dest.parent)
    with dest.open("xb") as stream:
        stream.write(data)
    require(dest.read_bytes() == data, "SURFACE_CAPTURE_COPY")
    return {"file": filename, "sha256": hashlib.sha256(data).hexdigest(),
            "byte_count": len(data), "size": size, "native_path": str(path),
            "camera": camera}


def trial_capture_arguments():
    return {
        "return_image": False,
        "camera_location": [-16145.268182324218, 84377.62518478667, 49067.09993071173],
        "camera_rotation": [-18.85209781522559, 165.400053560734, 0],
        "fov": 90,
    }


def trial_plan():
    """One reversible, source-mapped scalar experiment; no caller input."""
    read = {"name": "edit_material_instance", "arguments": {"name": TRIAL_MI}}
    restore = {
        "name": "edit_material_instance",
        "arguments": {"name": TRIAL_MI, "scalars": [{"name": "Macro Tiling", "value": 0.25}]},
    }
    capture = {"name": CAPTURE_TOOL, "arguments": trial_capture_arguments()}
    return {
        "registry": inspection_plan()[0],
        "baseline_mi": read,
        "baseline_clean": {"name": "edit_asset", "arguments": {"save_assets": {"paths": [TRIAL_MI], "dry_run": True}}},
        "A_baseline": capture,
        "backup_create": {"name": "edit_asset", "arguments": {"duplicate_asset": {"from": TRIAL_MI, "to": TRIAL_BACKUP}}},
        "backup_mi": {"name": "edit_material_instance", "arguments": {"name": TRIAL_BACKUP}},
        "apply_macro": {"name": "edit_material_instance", "arguments": {"name": TRIAL_MI, "scalars": [{"name": "Macro Tiling", "value": TRIAL_VALUE}]}},
        "candidate_mi": read,
        "B_macro_005": capture,
        "restore_macro": restore,
        "restored_mi": read,
        "A_restored": capture,
        "recovery_read": read,
        "recovery_restore": restore,
        "recovery_verify": read,
    }


def apply_reviewed_macro_plan():
    """Only the reviewed scalar delta, using the already verified backup."""
    trial = trial_plan()
    return {
        **{stage: trial[stage] for stage in (
            "registry", "baseline_mi", "baseline_clean", "backup_mi",
            "apply_macro", "candidate_mi",
        )},
        APPLY_CAPTURE_STAGE: trial["B_macro_005"],
        **{stage: trial[stage] for stage in (
            "recovery_read", "recovery_restore", "recovery_verify",
        )},
    }


def verify_reviewed_macro_receipt():
    """Admit this exact reviewed remote A/B/A receipt, never a substitute."""
    try:
        raw = read_bounded(APPLY_REVIEWED_TRIAL_PATH, RESPONSE_LIMIT)
    except ProbeError:
        raise ProbeError("APPLY_REVIEWED_TRIAL_UNAVAILABLE") from None
    require(hashlib.sha256(raw).hexdigest() == APPLY_REVIEWED_TRIAL_SHA256,
            "APPLY_REVIEWED_TRIAL_HASH")


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


def vault_inspection_plan():
    """Three fixed local inventory reads, never an install or caller query."""
    return tuple(
        {"name": VAULT_TOOL, "arguments": {"action": "list", "filter": name}}
        for name in VAULT_FILTERS
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
    vault_requested: bool = False
    vault_results: list = field(default_factory=list)
    vault_schema_sha256: str | None = None
    vault_host_checks: list = field(default_factory=list)
    vault_external_host_identity: dict | None = None
    surface_requested: bool = False
    surface_results: list = field(default_factory=list)
    surface_host_checks: list = field(default_factory=list)
    surface_captures: list = field(default_factory=list)
    surface_summary: dict | None = None
    surface_verified: bool = False
    trial_requested: bool = False
    trial_results: list = field(default_factory=list)
    trial_schema_sha256: dict = field(default_factory=dict)
    trial_captures: dict = field(default_factory=dict)
    trial_host_checks: list = field(default_factory=list)
    trial_registry_verified: bool = False
    trial_backup_attempted: bool = False
    trial_backup_verified: bool = False
    trial_mutation_attempted: bool = False
    trial_restore_attempted: bool = False
    trial_restore_verified: bool = False
    trial_denied_tools: list = field(default_factory=list)
    trial_recovery_error: str | None = None
    trial_external_host_identity: dict | None = None
    apply_requested: bool = False
    apply_reviewed_trial_verified: bool = False
    apply_candidate_verified: bool = False
    apply_verified: bool = False

    def report_fields(self):
        if self.surface_requested:
            return {
                "native_tool_calls": sum(row["attempted"] for row in self.surface_results),
                "native_tool_attempted": self.attempted,
                "native_tool_completed": self.completed,
                "native_tool_response_received": len(self.surface_results) == 6 and all(row["response_received"] for row in self.surface_results),
                "surface_results": self.surface_results,
                "surface_host_checks": self.surface_host_checks,
                "surface_captures": self.surface_captures,
                "surface_summary": self.surface_summary,
                "surface_verified": self.surface_verified,
                "surface_import_source_sha256": SURFACE_IMPORT_SHA256,
                "native_tool_error": self.tool_error,
            }
        macro_mode = self.trial_requested or self.apply_requested
        normal_count = 7 if self.apply_requested else 12
        fixed_plan = apply_reviewed_macro_plan() if self.apply_requested else trial_plan()
        report = {
            # This is a wire-attempt count, not a count of completed evaluations.
            "native_tool_calls": (
                sum(row["attempted"] for row in self.trial_results)
                if macro_mode
                else
                sum(row["attempted"] for row in self.vault_results)
                if self.vault_requested
                else
                sum(row["attempted"] for row in self.inspection_results)
                if self.inspection_requested
                else int(self.attempted)
            ),
            "native_tool_attempted": self.attempted,
            "native_tool_completed": self.completed,
            "native_tool_response_received": (
                len(self.trial_results) >= normal_count
                and all(row["response_received"] for row in self.trial_results[:normal_count])
                and [row["stage"] for row in self.trial_results[:normal_count]] == list(fixed_plan)[:normal_count]
                if macro_mode
                else
                len(self.vault_results) == 3
                and all(row["response_received"] for row in self.vault_results)
                if self.vault_requested
                else
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
        if macro_mode:
            macro_fields = {
                "trial_results": self.trial_results,
                "trial_schema_sha256": self.trial_schema_sha256,
                "trial_captures": self.trial_captures,
                "trial_host_checks": self.trial_host_checks,
                "trial_registry_verified": self.trial_registry_verified,
                "trial_backup_path": TRIAL_BACKUP,
                "trial_backup_attempted": self.trial_backup_attempted,
                "trial_backup_verified": self.trial_backup_verified,
                "trial_mutation_attempted": self.trial_mutation_attempted,
                "trial_restore_attempted": self.trial_restore_attempted,
                "trial_restore_verified": self.trial_restore_verified,
                "trial_denied_tools": self.trial_denied_tools,
                "trial_recovery_error": self.trial_recovery_error,
                "trial_baseline_sha256": TRIAL_BASELINE_SHA256,
                "external_host_identity": self.trial_external_host_identity,
                "trial_manual_restore": (
                    {"tool": "edit_material_instance", **trial_plan()["restore_macro"]["arguments"],
                     "reason": "Current state must be reviewed before manual restoration; no automatic retry is authorized."}
                    if self.trial_mutation_attempted and not self.trial_restore_verified
                    and not (self.apply_requested and self.apply_verified)
                    else None
                ),
            }
            if self.apply_requested:
                macro_fields = {
                    ("apply_" + key[6:] if key.startswith("trial_") else key): value
                    for key, value in macro_fields.items()
                }
                macro_fields.update({
                    "apply_verified": self.apply_verified,
                    "apply_candidate_verified": self.apply_candidate_verified,
                    "apply_reviewed_trial_verified": self.apply_reviewed_trial_verified,
                    "apply_reviewed_trial_path": str(APPLY_REVIEWED_TRIAL_PATH),
                    "apply_reviewed_trial_sha256": APPLY_REVIEWED_TRIAL_SHA256,
                    "apply_reviewed_trial_source_commit": APPLY_REVIEWED_TRIAL_SOURCE,
                })
            report.update(macro_fields)
        elif self.vault_requested:
            report.update({
                "vault_results": self.vault_results,
                "vault_schema_sha256": self.vault_schema_sha256,
                "vault_host_checks": self.vault_host_checks,
                "external_host_identity": self.vault_external_host_identity,
                "vault_inventory_accepted": False,
                "vault_license_verified": False,
            })
        elif self.inspection_requested:
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


def verify_trial_mi(text, path, macro):
    """Pin every typed value/override, including ordered layer duplicates."""
    require(text.splitlines()[:1] == ["# MATERIAL INSTANCE " + path.rsplit("/", 1)[1]], "TRIAL_MI_IDENTITY")
    require(re.findall(r"(?m)^parent = (.+)$", text) == ["M_Landscape_YACS"], "TRIAL_MI_PARENT")
    require(text.count("= saved=false (read-only call - asset untouched, not saved)") == 1, "TRIAL_MI_READ_MODE")
    markers = re.findall(r"(?m)^\s*#json-mi:(.*)$", text)
    require(len(markers) == 1, "TRIAL_MI_FORMAT")
    snapshot = parse_json(markers[0].encode(), INSPECTION_RESPONSE_LIMIT)
    require(type(snapshot) is dict and set(snapshot) == {"scalars", "vectors", "textures", "static_switches"}, "TRIAL_MI_FORMAT")
    for kind, count in (("scalars", 61), ("vectors", 1), ("textures", 5), ("static_switches", 3)):
        rows = snapshot[kind]
        require(type(rows) is list and len(rows) == count, "TRIAL_MI_FORMAT")
        for row in rows:
            require(type(row) is dict and set(row) == {"name", "value", "overridden"}
                    and type(row["name"]) is str and type(row["overridden"]) is bool, "TRIAL_MI_FORMAT")
            value = row["value"]
            require((type(value) in (int, float) and math.isfinite(value)) if kind == "scalars"
                    else type(value) is bool if kind == "static_switches" else type(value) is str,
                    "TRIAL_MI_FORMAT")
    entries = [row for row in snapshot["scalars"] if row["name"] == "Macro Tiling"]
    require(len(entries) == 1 and entries[0]["overridden"] is True and entries[0]["value"] == macro, "TRIAL_MACRO_DRIFT")
    entries[0]["value"] = 0.25
    require(hashlib.sha256(canonical(snapshot)).hexdigest() == TRIAL_BASELINE_SHA256, "TRIAL_BASELINE_DRIFT")
    return snapshot


def verify_trial_clean(text):
    require(re.fullmatch(
        r"# EDIT ASSET\s+~ would save " + re.escape(TRIAL_MI)
        + r" \(dirty=0\)\s+= save_assets dry_run: 1 package\(s\) considered, nothing written\s+= failures=0\s*",
        text) is not None, "TRIAL_DIRTY_OR_UNKNOWN")


def verify_trial_capture(text, expected=None):
    for key, value in (("viewport_type", "LevelEditor"), ("world_name", "L_SaCalobra_Lesson07"),
                       ("is_pie_running", "0"), ("black_frame_detected", "0")):
        require(re.findall(r"\b" + key + r"=([^\s|]+)", text) == [value], "TRIAL_CAPTURE_CONTEXT")
    if expected is not None:
        for key in ("camera_override", "camera_restored"):
            require(re.findall(r"\b" + key + r"=([^\s|]+)", text) == ["1"], "SURFACE_CAPTURE_CAMERA")
        number = r"(-?\d+(?:\.\d+)?)"
        fields = (
            (r"\bapplied_location=\(" + ",".join([number] * 3) + r"\)", expected["camera_location"]),
            (r"\bapplied_rotation=\(P=" + number + ",Y=" + number + ",R=" + number + r"\)", expected["camera_rotation"]),
            (r"\bapplied_fov=" + number + r"(?=\s|\||$)", [expected["fov"]]),
        )
        for pattern, values in fields:
            matches = re.findall(pattern, text)
            require(len(matches) == 1, "SURFACE_CAPTURE_CAMERA")
            actual = matches[0] if isinstance(matches[0], tuple) else (matches[0],)
            # Vendor metadata rounds every camera component to one decimal.
            require(all(math.isfinite(float(got)) and abs(float(got) - want) <= 0.051
                        for got, want in zip(actual, values)), "SURFACE_CAPTURE_CAMERA")
    paths = re.findall(r"D:/yacs/project/Saved/LocoHelperAI/ViewportShots/Viewport_LevelEditor_[0-9]{8}_[0-9]{6}\.jpg", text)
    require(len(paths) == 1, "TRIAL_CAPTURE_PATH")
    return paths[0]


def verify_trial_host_identity(identity, discovery):
    """Read the same Windows PID/FILETIME/executable and IPv4 listener only.

    Microsoft GetProcessTimes, QueryFullProcessImageNameW and
    GetExtendedTcpTable (TCP_TABLE_OWNER_PID_LISTENER). This never starts,
    stops, injects into or changes the Editor. The initial harness proof owns
    command-line/project and SID checks; the immutable process identity binds
    every subsequent trial request to that same process.
    """
    require(WINDOWS_HOST, "TRIAL_IDENTITY_WINDOWS_REQUIRED")
    import ctypes
    from ctypes import wintypes

    expected = identity.get("process_start_filetime_utc")
    require(type(expected) is str and re.fullmatch(r"[0-9]{1,20}", expected) is not None, "TRIAL_IDENTITY_FILETIME")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    ip = ctypes.WinDLL("iphlpapi", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x1000, False, identity["pid"])
    require(bool(handle), "TRIAL_IDENTITY_PROCESS")
    try:
        times = [wintypes.FILETIME() for _ in range(4)]
        require(bool(kernel.GetProcessTimes(handle, *(ctypes.byref(x) for x in times))), "TRIAL_IDENTITY_PROCESS")
        created = times[0].dwLowDateTime | (times[0].dwHighDateTime << 32)
        require(str(created) == expected, "TRIAL_IDENTITY_CHANGED")
        size = wintypes.DWORD(32768)
        image = ctypes.create_unicode_buffer(size.value)
        require(bool(kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)))
                and PureWindowsPath(image.value) == PureWindowsPath(EXECUTABLE), "TRIAL_IDENTITY_CHANGED")
        status = wintypes.DWORD()
        require(bool(kernel.GetExitCodeProcess(handle, ctypes.byref(status))) and status.value == 259, "TRIAL_IDENTITY_CHANGED")
        ip.GetExtendedTcpTable.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL, wintypes.ULONG, ctypes.c_int, wintypes.ULONG]
        ip.GetExtendedTcpTable.restype = wintypes.DWORD
        length = wintypes.DWORD()
        require(ip.GetExtendedTcpTable(None, ctypes.byref(length), False, 2, 3, 0) == 122
                and 4 <= length.value <= 1024 * 1024, "TRIAL_IDENTITY_LISTENER")
        capacity = length.value
        data = ctypes.create_string_buffer(capacity)
        require(ip.GetExtendedTcpTable(data, ctypes.byref(length), False, 2, 3, 0) == 0
                and 4 <= length.value <= capacity, "TRIAL_IDENTITY_LISTENER")
        raw = data.raw[:length.value]
        count = struct.unpack_from("<I", raw)[0]
        require(count <= 16384 and 4 + count * 24 <= len(raw), "TRIAL_IDENTITY_LISTENER")
        listeners = []
        for index in range(count):
            state, address, port, _remote, _remote_port, pid = struct.unpack_from("<6I", raw, 4 + index * 24)
            if state == 2 and socket.ntohs(port & 0xFFFF) == discovery.port:
                listeners.append((socket.inet_ntoa(struct.pack("<I", address)), pid))
        require(listeners == [(HOST, identity["pid"])], "TRIAL_IDENTITY_LISTENER")
    finally:
        kernel.CloseHandle(handle)
    return {"verified_utc": datetime.now(timezone.utc).isoformat(), "pid": identity["pid"],
            "process_start_filetime_utc": expected, "executable": EXECUTABLE,
            "listener": {"address": HOST, "port": discovery.port, "pid": identity["pid"]}}


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
        self._surface_params = None
        self._surface_row = None
        self._surface_run_token = None
        self._surface_files_guard = None
        self._vault_params = None
        self._vault_row = None
        self._vault_files_guard = None
        self._trial_params = None
        self._trial_row = None
        self._trial_recovering = False
        self._trial_recovery_candidate = False
        self._trial_started = None
        self._trial_last_capture = None
        self._trial_files_guard = None

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
        if self.observation_state.apply_requested:
            self.observation_state.apply_reviewed_trial_verified = False
            verify_reviewed_macro_receipt()
            self.observation_state.apply_reviewed_trial_verified = True
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
        vault_inspecting = (
            method == "tools/call" and self._vault_params is not None
            and params is self._vault_params and self._vault_row is not None
            and not self._vault_row["attempted"] and not notification
        )
        if vault_inspecting:
            state = self.observation_state
            index = len(state.vault_results) - 1
            require(
                state.vault_requested and 0 <= index < 3
                and self._vault_row is state.vault_results[index]
                and all(row["completed"] is True for row in state.vault_results[:index])
                and state.vault_schema_sha256 == VAULT_SCHEMA_SHA256
                and canonical(params) == canonical(vault_inspection_plan()[index]),
                "VAULT_INSPECTION_ARGUMENTS",
            )
        trialing = (
            method == "tools/call" and self._trial_params is not None
            and params is self._trial_params and self._trial_row is not None
            and not self._trial_row["attempted"] and not notification
        )
        if trialing:
            state = self.observation_state
            rows, stage = state.trial_results, self._trial_row["stage"]
            plan = apply_reviewed_macro_plan() if state.apply_requested else trial_plan()
            normal_count = 7 if state.apply_requested else 12
            require(state.trial_requested != state.apply_requested
                    and 0 < len(rows) <= normal_count + 3
                    and rows[-1] is self._trial_row
                    and stage in plan and canonical(params) == canonical(plan[stage])
                    and state.trial_schema_sha256 == TRIAL_SCHEMA_SHA256
                    and stage not in [row["stage"] for row in rows[:-1]], "TRIAL_ARGUMENTS")
            if self._trial_recovering:
                recovery = [row["stage"] for row in rows if row["stage"].startswith("recovery_")]
                require(recovery == list(plan)[normal_count:normal_count + len(recovery)]
                        and state.trial_mutation_attempted and not state.trial_restore_verified
                        and "edit_material_instance" not in state.trial_denied_tools,
                        "TRIAL_RECOVERY_DENIED")
                if stage == "recovery_restore":
                    require(self._trial_recovery_candidate and not state.trial_restore_attempted,
                            "TRIAL_RECOVERY_DENIED")
            else:
                require(len(rows) <= normal_count and stage == list(plan)[len(rows) - 1]
                        and all(row["validated"] for row in rows[:-1]), "TRIAL_SEQUENCE")
                if stage == "apply_macro":
                    require(state.trial_backup_verified and state.trial_registry_verified,
                            "TRIAL_BACKUP_REQUIRED")
        surfacing = (
            method == "tools/call" and self._surface_params is not None
            and params is self._surface_params and self._surface_row is not None
            and not self._surface_row["attempted"] and not notification
        )
        if surfacing:
            state = self.observation_state
            index = len(state.surface_results) - 1
            require(state.surface_requested and 0 <= index < 6
                    and state.surface_results[index] is self._surface_row
                    and all(row["completed"] is True for row in state.surface_results[:index])
                    and canonical(params) == canonical(surface_plan(self._surface_run_token)[index]),
                    "SURFACE_ARGUMENTS")
            self._surface_host_check("before")
        native_call = observing or capturing or inspecting or trialing or vault_inspecting or surfacing
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
        if surfacing:
            pass  # The fresh host check above is required for every surface operation.
        elif vault_inspecting:
            self._vault_host_check("before")
        elif trialing:
            require(self._trial_started is not None
                    and time.monotonic() - self._trial_started <= TRIAL_SECONDS, "TRIAL_INTERVAL")
            if self._trial_row["stage"] == "apply_macro":
                require(TRIAL_SECONDS - (time.monotonic() - self._trial_started)
                        >= TRIAL_MUTATION_RESERVE_SECONDS, "TRIAL_RESTORE_BUDGET")
            if self._trial_files_guard is not None:
                self._trial_files_guard()
            check = verify_trial_host_identity(self.identity, self.discovery)
            validate_identity({**self.identity, "observed_utc": check["verified_utc"]}, self.discovery)
            self.observation_state.trial_host_checks.append({"stage": self._trial_row["stage"], **check})
        else:
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
        request_timeout = SURFACE_TIMEOUT_SECONDS if surfacing and self._surface_row["index"] == 2 else self.timeout
        connection = http.client.HTTPConnection(
            HOST, self.discovery.port, timeout=request_timeout
        )
        deadline = time.monotonic() + request_timeout
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
                if surfacing:
                    self._surface_row.update({
                        "attempted": True, "completed": None,
                        "started_utc": self.observation_state.started_utc.isoformat(),
                    })
                if vault_inspecting:
                    self._vault_row.update({
                        "attempted": True, "completed": None,
                        "started_utc": self.observation_state.started_utc.isoformat(),
                    })
                if trialing:
                    self._trial_row.update({
                        "attempted": True, "completed": None,
                        "started_utc": self.observation_state.started_utc.isoformat(),
                    })
                    stage = self._trial_row["stage"]
                    if stage == "backup_create":
                        self.observation_state.trial_backup_attempted = True
                    if stage == "apply_macro":
                        self.observation_state.trial_mutation_attempted = True
                    if stage in ("restore_macro", "recovery_restore"):
                        self.observation_state.trial_restore_attempted = True
                        self.observation_state.apply_candidate_verified = False
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
                if surfacing:
                    self._surface_row.update({
                        "response_received": True,
                        "response_received_utc": self.observation_state.response_received_utc.isoformat(),
                    })
                if vault_inspecting:
                    self._vault_row.update({
                        "response_received": True,
                        "response_received_utc": self.observation_state.response_received_utc.isoformat(),
                    })
                if trialing:
                    self._trial_row.update({
                        "response_received": True,
                        "response_received_utc": self.observation_state.response_received_utc.isoformat(),
                    })
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

    def _surface_host_check(self, phase):
        verify_surface_source(self._surface_run_token)
        if self._surface_files_guard is not None:
            self._surface_files_guard()
        check = verify_trial_host_identity(self.identity, self.discovery)
        validate_identity({**self.identity, "observed_utc": check["verified_utc"]}, self.discovery)
        self.observation_state.surface_host_checks.append({
            "index": self._surface_row["index"], "phase": phase, **check,
        })

    def _run_surface_import(self, python_schema, capture_schema, run_token):
        state = self.observation_state
        validate_observer_schema(python_schema)  # Same installed Python schema; no observer execution.
        validate_capture_schema(capture_schema)
        self._surface_run_token = run_token
        verify_surface_source(run_token)
        for index, params in enumerate(surface_plan(run_token), 1):
            row = {"index": index, "tool_name": params["name"], "arguments": params["arguments"],
                   "attempted": False, "completed": False, "response_received": False,
                   "started_utc": None, "response_received_utc": None, "result": None, "error_code": None}
            state.surface_results.append(row)
            self._surface_params, self._surface_row = params, row
            state.tool_name = params["name"]
            try:
                try:
                    result = self._post("tools/call", params)
                finally:
                    # Also recheck after a denial or timeout; never replay the call.
                    self._surface_host_check("after")
                state.tool_error = observer_error_diagnostic(result, (self.discovery.token, self.session_id))
                retain_inspection_result(result, row, (self.discovery.token, self.session_id))
                if index == 2:
                    state.surface_summary = verify_surface_summary(row["result"]["text"])
                    receipt = read_surface_receipt(run_token, row)
                    require(all(receipt.get(key) == value and type(receipt.get(key)) is type(value)
                                for key, value in state.surface_summary.items()), "SURFACE_SAVED_RECEIPT")
                else:
                    state.surface_captures.append(retain_surface_capture(run_token, row))
                row["completed"] = True
            except ProbeError as error:
                row["error_code"] = error.code
                raise  # Never retry or select another tool/transport after rejection.
        state.completed = state.surface_verified = True

    def _vault_host_check(self, phase):
        if self._vault_files_guard is not None:
            self._vault_files_guard()
        # Reuse the existing OS-only proof. The harness owns SID/project proof;
        # immutable PID/FILETIME/executable and listener bind each read to it.
        check = verify_trial_host_identity(self.identity, self.discovery)
        validate_identity({**self.identity, "observed_utc": check["verified_utc"]}, self.discovery)
        self.observation_state.vault_host_checks.append({
            "filter": self._vault_row["arguments"]["filter"], "phase": phase, **check,
        })

    def _run_vault_inspection(self, schema):
        require(type(schema) is dict and hashlib.sha256(canonical(schema)).hexdigest() == VAULT_SCHEMA_SHA256,
                "VAULT_TOOL_SCHEMA_UNSUPPORTED")
        state = self.observation_state
        state.vault_schema_sha256 = VAULT_SCHEMA_SHA256
        for index, params in enumerate(vault_inspection_plan(), 1):
            row = {
                "index": index, "tool_name": VAULT_TOOL, "arguments": params["arguments"],
                "input_schema_sha256": VAULT_SCHEMA_SHA256,
                "attempted": False, "completed": False, "response_received": False,
                "started_utc": None, "response_received_utc": None,
                "result": None, "error_code": None,
            }
            state.vault_results.append(row)
            self._vault_params, self._vault_row = params, row
            state.tool_name = VAULT_TOOL
            try:
                result = self._post("tools/call", params)
                retain_inspection_result(result, row, (self.discovery.token, self.session_id))
                self._vault_host_check("after")
                require(len(canonical(state.vault_results)) <= INSPECTION_AGGREGATE_LIMIT,
                        "VAULT_INSPECTION_AGGREGATE_SIZE")
                row["completed"] = True
            except ProbeError as error:
                row["error_code"] = error.code
                raise
        state.completed = True

    def _trial_call(self, stage):
        state = self.observation_state
        plan = apply_reviewed_macro_plan() if state.apply_requested else trial_plan()
        params = plan[stage]
        capture = stage in TRIAL_CAPTURE_STAGES or stage == APPLY_CAPTURE_STAGE
        if capture and self._trial_last_capture is not None:
            remaining = 1.1 - (time.monotonic() - self._trial_last_capture)
            if remaining > 0:
                time.sleep(remaining)
        row = {"index": len(state.trial_results) + 1, "stage": stage,
               "tool_name": params["name"], "arguments": params["arguments"],
               "input_schema_sha256": state.trial_schema_sha256[params["name"]],
               "attempted": False, "completed": False, "validated": False,
               "response_received": False, "started_utc": None,
               "response_received_utc": None, "result": None, "error_code": None}
        state.trial_results.append(row)
        self._trial_params, self._trial_row = params, row
        state.tool_name = params["name"]
        state.tool_error = state.result_shape = None
        try:
            result = self._post("tools/call", params)
            if type(result) is dict and result.get("isError") is True:
                state.trial_denied_tools.append(params["name"])
            retain_inspection_result(result, row, (self.discovery.token, self.session_id))
            row["completed"] = True
            if capture:
                temporary = ObservationState()
                retain_capture_result(result, temporary, (self.discovery.token, self.session_id))
                row["result"] = temporary.capture_result
                self._trial_last_capture = time.monotonic()
            require(len(canonical(state.trial_results)) <= INSPECTION_AGGREGATE_LIMIT,
                    "TRIAL_AGGREGATE_SIZE")
            return row
        except ProbeError as error:
            if error.code == "RPC_ERROR" and params["name"] not in state.trial_denied_tools:
                state.trial_denied_tools.append(params["name"])
            row["error_code"] = error.code
            raise

    def _trial_validate(self, row):
        state, stage = self.observation_state, row["stage"]
        text = row["result"]["text"]
        if stage == "registry":
            verify_inspection_registry(text)
            registry = parse_json(re.findall(r"(?m)^#json-explore:(.*)$", text)[0].encode())
            backups = [asset for asset in registry["rows"]
                       if asset["path"] + "/" + asset["name"] == TRIAL_BACKUP]
            if state.apply_requested:
                require(len(backups) == 1 and backups[0]["class"] == "MaterialInstanceConstant",
                        "APPLY_EXISTING_BACKUP_REQUIRED")
            else:
                require(not backups, "TRIAL_BACKUP_EXISTS")
            state.trial_registry_verified = True
        elif stage in ("baseline_mi", "backup_mi", "restored_mi", "recovery_verify"):
            verify_trial_mi(text, TRIAL_BACKUP if stage == "backup_mi" else TRIAL_MI, 0.25)
            if stage == "backup_mi":
                state.trial_backup_verified = True
            if stage in ("restored_mi", "recovery_verify"):
                state.trial_restore_verified = True
                state.apply_candidate_verified = False
        elif stage == "candidate_mi":
            verify_trial_mi(text, TRIAL_MI, TRIAL_VALUE_F32)
            if state.apply_requested:
                state.apply_candidate_verified = True
        elif state.apply_requested and stage in ("apply_macro", "recovery_restore"):
            value = "0.05" if stage == "apply_macro" else "0.25"
            require(re.fullmatch(r"~ scalar Macro Tiling = " + re.escape(value)
                    + r"\s+= parent=M_Landscape_YACS; saved=true; failures=0\s*", text)
                    is not None, "APPLY_SAVE_UNCONFIRMED")
        elif stage == "baseline_clean":
            verify_trial_clean(text)
        elif stage == "backup_create":
            require(re.findall(r"(?m)^= failures=([0-9]+)\s*$", text) == ["0"]
                    and TRIAL_BACKUP in text, "TRIAL_BACKUP_UNCONFIRMED")
        elif stage in TRIAL_CAPTURE_STAGES or stage == APPLY_CAPTURE_STAGE:
            path = verify_trial_capture(text)
            previous = [verify_trial_capture(item["capture_result"]["text"])
                        for item in state.trial_captures.values()]
            require(path not in previous, "TRIAL_CAPTURE_PATH_REUSED")
            state.trial_captures[stage] = {
                "capture_arguments": row["arguments"], "capture_result": row["result"],
                "native_tool_started_utc": row["started_utc"],
                "native_tool_response_received_utc": row["response_received_utc"],
            }
        row["validated"] = True

    def _trial_recover(self):
        state = self.observation_state
        if not state.trial_mutation_attempted or state.trial_restore_verified:
            return
        require("edit_material_instance" not in state.trial_denied_tools, "TRIAL_RECOVERY_DENIED")
        self._trial_recovering = True
        row = self._trial_call("recovery_read")
        text = row["result"]["text"]
        try:
            verify_trial_mi(text, TRIAL_MI, 0.25)
        except ProbeError:
            verify_trial_mi(text, TRIAL_MI, TRIAL_VALUE_F32)
            require(not state.trial_restore_attempted, "TRIAL_RESTORE_ALREADY_ATTEMPTED")
            row["validated"] = True
            self._trial_recovery_candidate = True
            self._trial_validate(self._trial_call("recovery_restore"))
            self._trial_validate(self._trial_call("recovery_verify"))
        else:
            row["validated"] = True
            state.trial_restore_verified = True
            state.apply_candidate_verified = False

    def _run_trial(self, schemas):
        state = self.observation_state
        for name, expected in TRIAL_SCHEMA_SHA256.items():
            schema = schemas.get(name)
            require(type(schema) is dict and hashlib.sha256(canonical(schema)).hexdigest() == expected,
                    "TRIAL_TOOL_SCHEMA_UNSUPPORTED")
        state.trial_schema_sha256 = dict(TRIAL_SCHEMA_SHA256)
        plan = apply_reviewed_macro_plan() if state.apply_requested else trial_plan()
        normal_count = 7 if state.apply_requested else 12
        try:
            for stage in list(plan)[:normal_count]:
                self._trial_validate(self._trial_call(stage))
        except Exception as failure:
            error = failure if isinstance(failure, ProbeError) else ProbeError("UNEXPECTED_TRIAL_FAILURE")
            if state.trial_results:
                state.trial_results[-1]["error_code"] = error.code
            try:
                if error.code.startswith(("TRIAL_IDENTITY", "APPLY_REVIEWED_TRIAL")) or error.code in ("INPUT_CHANGED", "TRIAL_INTERVAL"):
                    raise ProbeError("TRIAL_RECOVERY_IDENTITY_UNSAFE")
                self._trial_recover()
            except Exception as recovery_error:
                state.trial_recovery_error = recovery_error.code if isinstance(recovery_error, ProbeError) else "UNEXPECTED_RECOVERY_FAILURE"
                if state.trial_results and state.trial_results[-1]["stage"].startswith("recovery_"):
                    state.trial_results[-1]["error_code"] = state.trial_recovery_error
            state.completed = None
            state.apply_verified = False
            raise error
        state.completed = True
        if state.apply_requested:
            state.apply_verified = True

    def probe(
        self, observe_lesson07=False, capture_lesson07=False, inspect_lesson07=False,
        trial_macro=False, apply_reviewed_macro=False, inspect_vault=False, import_surfaces=False, surface_run_token=None,
    ):
        require(
            sum((observe_lesson07, capture_lesson07, inspect_lesson07, trial_macro, apply_reviewed_macro, inspect_vault, import_surfaces)) <= 1,
            "NATIVE_MODES_MUTUALLY_EXCLUSIVE",
        )
        self.observation_state.surface_requested = import_surfaces
        self.observation_state.capture_requested = capture_lesson07
        self.observation_state.inspection_requested = inspect_lesson07
        self.observation_state.vault_requested = inspect_vault
        self.observation_state.trial_requested = trial_macro
        self.observation_state.apply_requested = apply_reviewed_macro
        if trial_macro or apply_reviewed_macro:
            self._trial_started = time.monotonic()
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
        vault_schema = None
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
                    if name == VAULT_TOOL:
                        vault_schema = tool.get("inputSchema")
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
        if import_surfaces:
            require(tool_error is None, "SURFACE_INCOMPLETE_TOOL_LIST")
            require(session["signed_in"], "SURFACE_SIGNED_OUT")
            self._run_surface_import(observer_schema, capture_schema, surface_run_token)
            report.update({
                "status": "SURFACE_IMPORT_SAVED_IMAGES_REVIEW_PENDING",
                "http_requests": self.requests,
                "native_material_readback": "SURFACE_IMPORT_SAVED_IMAGES_REVIEW_PENDING",
                "visual_acceptance": False,
                **self.observation_state.report_fields(),
            })
        if inspect_vault:
            require(tool_error is None, "VAULT_INCOMPLETE_TOOL_LIST")
            require(session["signed_in"], "VAULT_SIGNED_OUT")
            self._run_vault_inspection(vault_schema)
            report.update({
                "status": "VAULT_INSPECTION_RESPONSES_RECEIVED",
                "http_requests": self.requests,
                "notifications_received": self.notifications_received,
                "native_material_readback": "NOT_RUN",
                "visual_acceptance": False,
                **self.observation_state.report_fields(),
            })
        if trial_macro or apply_reviewed_macro:
            require(tool_error is None, "TRIAL_INCOMPLETE_TOOL_LIST")
            require(session["signed_in"], "TRIAL_SIGNED_OUT")
            self._run_trial({**inspection_schemas, CAPTURE_TOOL: capture_schema})
            report.update({
                "status": "APPLY_REVIEWED_MACRO_VERIFIED_REVIEW_PENDING"
                if apply_reviewed_macro else "TRIAL_MACRO_RESTORED_REVIEW_PENDING",
                "http_requests": self.requests,
                "notifications_received": self.notifications_received,
                "native_material_readback": "REVIEWED_MACRO_APPLIED_CAPTURE_REVIEW_PENDING"
                if apply_reviewed_macro else "TRIAL_BASELINE_RESTORED_CAPTURE_REVIEW_PENDING",
                "visual_acceptance": False,
                **self.observation_state.report_fields(),
            })
        return report


def probe_from_files(
    identity_path,
    discovery_path=DISCOVERY_PATH,
    *,
    observe_lesson07=False,
    capture_lesson07=False,
    inspect_lesson07=False,
    trial_macro=False,
    apply_reviewed_macro=False,
    inspect_vault=False,
    import_surfaces=False,
    observation_state=None,
):
    require(WINDOWS_HOST, "WINDOWS_HOST_REQUIRED")
    discovery_raw = read_bounded(discovery_path, CONFIG_LIMIT)
    discovery = Discovery.from_mapping(parse_json(discovery_raw, CONFIG_LIMIT))
    identity_raw = read_bounded(identity_path, CONFIG_LIMIT)
    identity = parse_json(identity_raw, CONFIG_LIMIT)
    safe_identity = validate_identity(identity, discovery)
    client = DiscoveryClient(discovery, identity, observation_state=observation_state)
    if trial_macro or apply_reviewed_macro or inspect_vault or import_surfaces:
        if inspect_vault:
            client.observation_state.vault_external_host_identity = safe_identity
        else:
            client.observation_state.trial_external_host_identity = safe_identity

        def trial_files_guard():
            require(read_bounded(discovery_path, CONFIG_LIMIT) == discovery_raw
                    and read_bounded(identity_path, CONFIG_LIMIT) == identity_raw,
                    "INPUT_CHANGED")

        if import_surfaces:
            client._surface_files_guard = trial_files_guard
        elif inspect_vault:
            client._vault_files_guard = trial_files_guard
        else:
            client._trial_files_guard = trial_files_guard
    report = client.probe(
        observe_lesson07=observe_lesson07,
        capture_lesson07=capture_lesson07,
        inspect_lesson07=inspect_lesson07,
        **({"trial_macro": True} if trial_macro else {}),
        **({"apply_reviewed_macro": True} if apply_reviewed_macro else {}),
        **({"inspect_vault": True} if inspect_vault else {}),
        **({"import_surfaces": True, "surface_run_token": Path(identity_path).parent.name} if import_surfaces else {}),
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


def vault_public_report(report):
    """Only proof metadata may leave the host; owned-pack text stays private."""
    fields = (
        "schema_version", "observed_utc", "status", "error_code", "rpc_code",
        "native_tool_calls", "native_tool_attempted", "native_tool_completed",
        "native_tool_response_received", "native_material_readback",
        "vault_schema_sha256", "vault_host_checks", "external_host_identity",
        "client_sha256", "vault_inventory_accepted", "vault_license_verified",
        "visual_acceptance", "performance_pass",
    )
    public = {key: report[key] for key in fields if key in report}
    public["raw_responses"] = "RETAINED_ON_HOST_NOT_PUBLISHED"
    texts = [(row.get("result") or {}).get("text", "").casefold()
             for row in report.get("vault_results", [])]
    public["shortlisted_candidate_text_observed"] = {
        name: any(name.casefold() in text for text in texts)
        for name in VAULT_PUBLIC_SHORTLIST
    }
    public["shortlist_observation_basis"] = "CASE_INSENSITIVE_TEXT_SUBSTRING_NOT_OWNERSHIP_LICENSE_OR_COMPLETENESS_PROOF"
    public["vault_results"] = []
    for row in report.get("vault_results", []):
        safe = {key: row[key] for key in (
            "index", "tool_name", "arguments", "input_schema_sha256", "attempted",
            "completed", "response_received", "started_utc", "response_received_utc", "error_code",
        )}
        result = row.get("result")
        safe["result"] = None if result is None else {
            key: result[key] for key in ("response_sha256", "text_truncated", "text_block_count")
        }
        public["vault_results"].append(safe)
    return public


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--observe-lesson07", action="store_true")
    mode.add_argument("--capture-lesson07", action="store_true")
    mode.add_argument("--inspect-lesson07", action="store_true")
    mode.add_argument("--inspect-vault", action="store_true")
    mode.add_argument("--import-surfaces", action="store_true")
    mode.add_argument("--trial-macro", action="store_true")
    mode.add_argument("--apply-reviewed-macro", action="store_true")
    args = parser.parse_args(argv)
    state = ObservationState(
        capture_requested=args.capture_lesson07,
        inspection_requested=args.inspect_lesson07,
        vault_requested=args.inspect_vault,
        surface_requested=args.import_surfaces,
        trial_requested=args.trial_macro,
        apply_requested=args.apply_reviewed_macro,
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
        if args.inspect_vault:
            options["inspect_vault"] = True
        if args.import_surfaces:
            options["import_surfaces"] = True
        if args.trial_macro:
            options["trial_macro"] = True
        if args.apply_reviewed_macro:
            options["apply_reviewed_macro"] = True
        report = probe_from_files(args.identity_receipt, **options)
    except ProbeError as error:
        error_code, rpc_code = error.code, error.rpc_code
    except Exception:
        # Do not print a traceback, response body, file contents or exception text.
        error_code = "UNEXPECTED_CLIENT_FAILURE"
    if error_code is not None:
        state.apply_verified = False
        report = {
            "schema_version": 1,
            "status": "SURFACE_IMPORT_FAILED"
            if args.import_surfaces
            else "APPLY_REVIEWED_MACRO_FAILED"
            if args.apply_reviewed_macro
            else "TRIAL_MACRO_FAILED"
            if args.trial_macro
            else "INSPECTION_FAILED"
            if args.inspect_lesson07
            else "VAULT_INSPECTION_FAILED"
            if args.inspect_vault
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
                if state.attempted and not (args.capture_lesson07 or args.inspect_vault)
                else "NOT_RUN"
            ),
            "visual_acceptance": False,
            "performance_pass": False,
        }
        if args.observe_lesson07 or args.capture_lesson07 or args.inspect_lesson07 or args.trial_macro or args.apply_reviewed_macro or args.inspect_vault or args.import_surfaces:
            report.update(state.report_fields())
        if rpc_code is not None:
            report["rpc_code"] = rpc_code
    prefix = (
        "L07_WINGMAN_SURFACE_IMPORT"
        if args.import_surfaces
        else "L07_WINGMAN_APPLY_REVIEWED_MACRO"
        if args.apply_reviewed_macro
        else "L07_WINGMAN_TRIAL_MACRO"
        if args.trial_macro
        else "L07_WINGMAN_INSPECTION"
        if args.inspect_lesson07
        else "L07_WINGMAN_VAULT_INSPECTION"
        if args.inspect_vault
        else "L07_WINGMAN_CAPTURE"
        if args.capture_lesson07
        else "L07_WINGMAN_OBSERVATION"
        if args.observe_lesson07
        else "L07_WINGMAN_DISCOVERY"
    )
    try:
        write_report(args.output, report)
        if args.inspect_vault:
            write_report(args.output.with_name("vault-summary.json"), vault_public_report(report))
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
        "SURFACE_IMPORT_SAVED_IMAGES_REVIEW_PENDING"
        if args.import_surfaces
        else "APPLY_REVIEWED_MACRO_VERIFIED_REVIEW_PENDING"
        if args.apply_reviewed_macro
        else "TRIAL_MACRO_RESTORED_REVIEW_PENDING"
        if args.trial_macro
        else "INSPECTION_RESPONSES_RECEIVED"
        if args.inspect_lesson07
        else "VAULT_INSPECTION_RESPONSES_RECEIVED"
        if args.inspect_vault
        else "CAPTURE_RESPONSE_RECEIVED"
        if args.capture_lesson07
        else "OBSERVATION_COMPLETE"
        if args.observe_lesson07
        else "DISCOVERY_COMPLETE"
    )
    return 0 if report["status"] == expected else 1


if __name__ == "__main__":
    raise SystemExit(main())

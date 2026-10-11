"""One bounded paint request to an already owned Level Editor session.

This host client starts no editor, server, build or cleanup and never saves an
asset. It reuses the admitted JSON-only official MCP transport. The current
client checkout must match the launcher's exact SHA; the retained scene remains
the separately pinned b9 checkpoint. A failed/uncertain tools/call is not retried.
Offline tests are synthetic and cannot establish native or visual acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import math
import os
import re
import struct
import subprocess
import time
from pathlib import Path, PureWindowsPath

from scripts import committed_git_blobs as committed_git
from scripts.ci import official_mcp_bob_client as official_client
from scripts.ci import official_mcp_bob_session as session
from scripts.ue import level_editor_material_bridge as bridge
from scripts.ue import prepare_level_editor_review as preparation

ROOT = Path(__file__).resolve().parents[2]
WINDOWS_HOST = os.name == "nt"
REVIEW_ROOT = preparation.REVIEW_ROOT
SESSION_RECEIPT = "level-editor-stream-session.json"
CLIENT_RECEIPT = "level-editor-material-client.json"
REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}\Z")
JSON_LIMIT = 2 * 1024 * 1024
HISTORY_LIMIT = 256
HISTORY_BYTES = 64 * 1024 * 1024
POLL_SECONDS = 180.0
ENDPOINT = "http://127.0.0.1:18784/mcp"
COMMON_REQUEST = {"schema_version", "session_id", "request_id", "action", "expected_sequence"}
IDENTITY_KEYS = ("session_id", "editor_pid", "editor_start_filetime_utc", "project_root",
                 "map_package", "runtime_source_sha", "launcher_sha", "launcher_root")
OBSERVATION_KEYS = {"paint_roughness", "paint_color", "binding_count", "binding_sha256",
                    "bindings", "bound_material", "parent_material", "transient_mid"}
# Directly used private helpers are authenticated as committed bytes, without
# invoking the older BOB-specific operation, admission or session controller.
SOURCE_MODULES = {
    "scripts/committed_git_blobs.py": committed_git,
    "scripts/ci/official_mcp_bob_client.py": official_client,
    "scripts/ci/official_mcp_bob_session.py": session,
    "scripts/ue/official_mcp_bob_operation.py": official_client.operation,
    "scripts/worldgen/bob_mcp_inspection.py": official_client.operation.adapter,
    "scripts/ue/prepare_level_editor_review.py": preparation,
    "scripts/ue/level_editor_material_bridge.py": bridge,
    "scripts/ue/level_editor_camera_presets.py": bridge.camera_presets,
}
CLIENT_SOURCE = "scripts/ue/level_editor_material_client.py"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "Duplicate JSON member")
        value[key] = item
    return value


def _finite_float(raw):
    value = float(raw)
    require(math.isfinite(value), "Non-finite JSON number")
    return value


def _json(raw, limit=JSON_LIMIT):
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    require(type(raw) is bytes and 0 < len(raw) <= limit, "JSON exceeds its byte bound")

    def reject(_value):
        raise ValueError("Non-finite JSON constant")

    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_pairs,
                      parse_float=_finite_float, parse_constant=reject)


def _object(raw, limit=JSON_LIMIT):
    value = _json(raw, limit)
    require(type(value) is dict, "JSON must contain one object")
    return value


def _read(path, limit=JSON_LIMIT):
    identity = session._identity(path, limit)
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    require(len(raw) == identity["size_bytes"] and digest(raw) == identity["sha256"],
            "Input changed while being read")
    return raw


def _path(root, relative):
    return preparation._path(root, relative)


def _same_path(value, expected):
    return preparation._same_path(value, expected)


def _sources(launcher_sha):
    require(isinstance(launcher_sha, str) and preparation.SHA40.fullmatch(launcher_sha),
            "Launcher SHA is invalid")
    head = committed_git._git_bounded(
        ROOT, ("rev-parse", "--verify", "HEAD"), 64,
        deadline=time.monotonic() + 20).decode("ascii").strip()
    require(head == launcher_sha, "Actual client HEAD differs from the session launcher SHA")
    target = os.environ.get("TARGET_SHA")
    require(target is None or target == head, "TARGET_SHA differs from the actual client HEAD")
    paths = (*SOURCE_MODULES, CLIENT_SOURCE)
    blobs = committed_git._read_exact_blobs(
        ROOT, head, paths, blob_limit=JSON_LIMIT, total_limit=16 * JSON_LIMIT,
        timeout_seconds=30, path_validator=_path)
    sources = {}
    for relative in paths:
        path = _path(ROOT, relative)
        executing = Path(__file__) if relative == CLIENT_SOURCE else Path(SOURCE_MODULES[relative].__file__)
        require(executing.resolve() == path.resolve(), "Executing helper belongs to another checkout")
        raw = _read(path)
        require(raw == blobs[relative], "Executing client/helper differs from committed launcher bytes")
        sources[relative] = digest(raw)
    return sources


def _windows_observation(editor_pid):
    """Read OS process creation time, executable and the fixed listener owner.

    Only a checked integer is inserted into this fixed read-only PowerShell
    program. No receipt, request, executable path or tool text is executable.
    The process list is capped in the producer; no general command API exists.
    """
    require(WINDOWS_HOST and type(editor_pid) is int and 0 < editor_pid < 2**32,
            "Owned editor identity requires the Windows host")
    program = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$native = Get-Process -Id EDITOR_ID -ErrorAction Stop
if ($native.HasExited) { throw 'Owned editor exited.' }
$cim = Get-CimInstance -ClassName Win32_Process -Filter 'ProcessId=EDITOR_ID' -ErrorAction Stop
$listeners = @(Get-NetTCPConnection -State Listen -LocalPort 18784 -ErrorAction Stop | Select-Object -First 2)
$value = [ordered]@{
    editor_pid = $native.Id
    editor_start_filetime_utc = $native.StartTime.ToUniversalTime().ToFileTimeUtc().ToString()
    editor_executable_path = $native.Path
    command_line = $cim.CommandLine
    listeners = @($listeners | ForEach-Object {
        [ordered]@{ address = $_.LocalAddress; port = $_.LocalPort; pid = $_.OwningProcess }
    })
}
[Console]::Out.Write(($value | ConvertTo-Json -Depth 5 -Compress))
""".replace("EDITOR_ID", str(editor_pid))
    executable = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    result = subprocess.run(
        [str(executable), "-NoProfile", "-NonInteractive", "-Command", program],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20)
    return _object(result.stdout, 16 * 1024)


def _verify_process(host):
    observed = _windows_observation(host["editor_pid"])
    require(type(observed.get("editor_pid")) is int
            and observed["editor_pid"] == host["editor_pid"]
            and observed.get("editor_start_filetime_utc") == host["editor_start_filetime_utc"]
            and _same_path(observed.get("editor_executable_path"), host["editor_executable_path"]),
            "Live editor PID, creation time or executable differs from the owned launch")
    require(observed.get("listeners") == [{"address": "127.0.0.1", "port": 18784, "pid": host["editor_pid"]}],
            "Fixed MCP listener is not exclusively loopback and owned by this editor")
    # Start-YacsLevelEditorStream launches an absolute executable followed by
    # the quoted project and fixed map. Validate those first arguments, not an
    # occurrence hidden inside an unrelated command-line option or script.
    def token(path):
        text = str(path).replace("\\", "/")
        expression = "[\\\\/]".join(re.escape(part) for part in text.split("/"))
        quoted = '"' + expression + '"'
        return quoted if any(char.isspace() for char in text) else "(?:" + quoted + "|" + expression + ")"

    project = str(Path(host["session_root"]) / "YetAnotherCyclingSim.uproject")
    prefix = r"\A" + token(host["editor_executable_path"]) + r"\s+" + token(project)
    prefix += r"\s+" + re.escape(preparation.MAP_PACKAGE) + r"(?=\s|$)"
    command_line = observed.get("command_line")
    require(isinstance(command_line, str) and len(command_line) <= 16000
            and re.match(prefix, command_line, re.IGNORECASE),
            "Live editor command line does not open the owned project and fixed map")
    return {key: value for key, value in observed.items() if key != "command_line"} | {
        "project_argument": project, "project_argument_verified": True}


def _identity(value, context):
    require(type(value.get("schema_version")) is int and value["schema_version"] == 1,
            "Native receipt schema differs")
    for key in IDENTITY_KEYS:
        expected = context["identity"][key]
        equal = _same_path(value.get(key), expected) if key in {"project_root", "launcher_root"} else value.get(key) == expected
        require(equal and (key != "editor_pid" or type(value[key]) is int),
                "Native receipt identity differs from the owned session")
    require(value.get("source_world_saved") is False and value.get("performance_pass") is False
            and value.get("owner_visual_status") == "PENDING_FINAL_M3",
            "Native receipt changed preservation or acceptance flags")


def _values(value):
    require(type(value) is dict, "Native material observation is not an object")
    color = value.get("paint_color")
    require(type(color) is list and len(color) == 4, "Native paint color shape differs")
    values = [value.get("paint_roughness"), *color]
    require(all(type(item) in (int, float) and math.isfinite(item) and 0 <= item <= 1 for item in values)
            and color[3] == 1, "Native paint readback is outside its finite range")


def _observation(value, initial=None):
    _values(value)
    require(set(value) == OBSERVATION_KEYS and type(value.get("transient_mid")) is bool
            and type(value.get("binding_count")) is int and value["binding_count"] == 370,
            "Native material observation contract differs")
    rows = value["bindings"]
    require(type(rows) is list and len(rows) == 370 and digest(canonical(rows)) == value["binding_sha256"],
            "Native binding census or digest differs")
    material = value["bound_material"]
    require(isinstance(material, str) and 0 < len(material) <= 1024,
            "Native bound material identity is invalid")
    if value["transient_mid"]:
        require(material != bridge.PAINT_MATERIAL and value["parent_material"] == bridge.PAINT_MATERIAL,
                "Transient MID parent differs from the retained paint instance")
    else:
        require(material == bridge.PAINT_MATERIAL and value["parent_material"] == bridge.PAINT_MASTER,
                "Original paint binding/parent differs")
    identities = []
    for row in rows:
        require(type(row) is dict and set(row) == {"actor", "component", "slot", "material", "original_material"},
                "Native binding row fields differ")
        require(type(row["slot"]) is int and row["slot"] == 0 and row["material"] == material
                and row["original_material"] == bridge.PAINT_MATERIAL
                and all(isinstance(row[key], str) and len(row[key]) <= 1024
                        and row[key].startswith(preparation.MAP_PACKAGE + ".") for key in ("actor", "component")),
                "Native actor/component/slot/material binding differs")
        identities.append((row["actor"], row["component"], row["slot"], row["original_material"]))
    require(len(set(identities)) == 370, "Native binding identities are duplicated")
    if initial is not None:
        wanted = [(row["actor"], row["component"], row["slot"], row["original_material"])
                  for row in initial["bindings"]]
        require(identities == wanted, "Native binding targets differ from the initial scene readback")


def _load_context(receipt_path):
    require(WINDOWS_HOST and receipt_path.is_absolute(), "Session receipt requires an absolute owned Windows path")
    require(receipt_path.name == SESSION_RECEIPT and preparation.SESSION_NAME.fullmatch(receipt_path.parent.name),
            "Session receipt is outside the fixed retained checkpoint")
    root = _path(REVIEW_ROOT, receipt_path.parent.name)
    expected = _path(root, SESSION_RECEIPT)
    require(_same_path(str(receipt_path), expected), "Session receipt is not the fixed owned path")
    host_raw = _read(expected)
    host = _object(host_raw)
    token = host.get("session_id")
    require(isinstance(token, str) and SESSION_ID.fullmatch(token)
            and root.name == preparation.RUNTIME_SHA[:12] + "-" + token,
            "Session token differs from its fixed project root")
    launcher_root = _path(preparation.SOURCE_ROOT.parent, "_level-editor-review-" + token)
    require(_same_path(host.get("launcher_root"), launcher_root),
            "Retained launcher root differs from the fixed launch-session path")
    handoff = ((host.get("status") in {"HTTP_READY_CLIENT_PENDING", "BROWSER_VIDEO_RECEIVED"}
                and host.get("owner_handoff") is True)
               or (host.get("status") == "MATERIAL_BRIDGE_QUALIFICATION_PENDING"
                   and host.get("owner_handoff") is False))
    require(type(host.get("schema_version")) is int and host["schema_version"] == 1
            and handoff and host.get("source_world_saved") is False
            and host.get("runtime_source_sha") == preparation.RUNTIME_SHA
            and _same_path(host.get("session_root"), root)
            and host.get("stream_source") == "LevelEditorViewport",
            "Launcher did not hand off this retained Level Editor session")
    require(type(host.get("editor_pid")) is int and 0 < host["editor_pid"] < 2**32
            and isinstance(host.get("editor_start_filetime_utc"), str)
            and re.fullmatch(r"[1-9][0-9]{0,19}", host["editor_start_filetime_utc"])
            and isinstance(host.get("editor_start_time_utc"), str)
            and isinstance(host.get("editor_executable_path"), str)
            and PureWindowsPath(host["editor_executable_path"]).is_absolute()
            and PureWindowsPath(host["editor_executable_path"]).name.casefold() == "unrealeditor.exe",
            "Launcher lacks a complete owned process identity")
    sources = _sources(host.get("launcher_sha"))
    context = {"root": root, "host": host, "sources": sources, "launcher_root": launcher_root,
               "identity": {"session_id": token, "editor_pid": host["editor_pid"],
                            "editor_start_filetime_utc": host["editor_start_filetime_utc"],
                            "project_root": str(root), "map_package": preparation.MAP_PACKAGE,
                            "runtime_source_sha": preparation.RUNTIME_SHA, "launcher_sha": host["launcher_sha"],
                            "launcher_root": str(launcher_root)},
               "immutable": {SESSION_RECEIPT: host_raw}}
    _verify_process(host)
    ready_raw = _read(_path(root, bridge.READY_RELATIVE))
    require(host.get("material_bridge_ready_sha256") == digest(ready_raw),
            "Native ready bytes differ from the launcher readback")
    ready = _object(ready_raw)
    _identity(ready, context)
    require(ready.get("status") == "MATERIAL_BRIDGE_READY" and type(ready.get("sequence")) is int
            and ready["sequence"] == 0 and ready.get("endpoint") == ENDPOINT
            and ready.get("bridge_source_sha256") == sources["scripts/ue/level_editor_material_bridge.py"]
            and ready.get("camera_source_sha256") == sources["scripts/ue/level_editor_camera_presets.py"],
            "Native material bridge is not ready at the exact launcher source")
    _schema(ready)
    initial = ready.get("initial_state")
    _observation(initial)
    require(initial["transient_mid"] is False and _close_values(initial, {
        "paint_roughness": 0.90, "paint_color": [0.64, 0.63, 0.59, 1.0]}),
        "Native initial paint state differs from retained b9 defaults")
    prep_raw = _read(_path(root, preparation.RECEIPT_NAME))
    prep = _object(prep_raw)
    require(prep.get("status") == "READY_FOR_EDITOR_LAUNCH"
            and prep.get("launcher_sha") == host["launcher_sha"]
            and prep.get("runtime_source_sha") == preparation.RUNTIME_SHA
            and prep.get("synthetic") is False
            and _same_path(prep.get("snapshot_root"), root)
            and _same_path(prep.get("runtime_source_root"), preparation.SOURCE_ROOT)
            and prep.get("map_package") == preparation.MAP_PACKAGE
            and prep.get("map_sha256") == preparation.MAP_SHA256,
            "Prepared snapshot belongs to another launch")
    rows = prep.get("snapshot_files")
    require(type(rows) is list and len(rows) == 278, "Prepared snapshot inventory differs")
    saved, originals, retained_project_inputs = [], [], {}
    for row in rows:
        require(type(row) is dict and isinstance(row.get("path"), str), "Invalid prepared snapshot row")
        _path(root, row["path"])
        saved.append({"path": row["path"], **preparation._expected(row, allow_empty=True)})
        require(isinstance(row.get("source_path"), str), "Prepared original source path is missing")
        source = Path(row["source_path"])
        base = preparation.SOURCE_ROOT if source.is_relative_to(preparation.SOURCE_ROOT) else launcher_root
        require(source.is_absolute() and source.is_relative_to(base), "Prepared original source escapes its fixed roots")
        relative = source.relative_to(base).as_posix()
        source = _path(base, relative)
        if base == launcher_root:
            require(relative == row["path"] and relative in preparation.PINNED_PROJECT_FILES,
                    "Retained launcher source is outside the six pinned project inputs")
            expected_input = preparation._anchor(preparation.PINNED_PROJECT_FILES[relative])
            require(preparation._expected(row, allow_empty=True) == expected_input
                    and preparation._file_identity(source) == expected_input,
                    "Retained launcher project input bytes differ from the pinned checkpoint")
            retained_project_inputs[relative] = expected_input
        originals.append({"path": str(source), **preparation._expected(row, allow_empty=True)})
    require(len({row["path"] for row in saved}) == 278
            and set(retained_project_inputs) == set(preparation.PINNED_PROJECT_FILES)
            and ready.get("saved_inputs_sha256") == digest(canonical(saved))
            and ready.get("source_inputs_sha256") == digest(canonical(originals)),
            "Native saved-input readback differs from the prepared snapshot inventory")
    context.update({"ready": ready, "initial": initial, "saved_digest": ready["saved_inputs_sha256"],
                    "source_digest": ready["source_inputs_sha256"], "retained_project_inputs": retained_project_inputs})
    context["immutable"].update({bridge.READY_RELATIVE: ready_raw, preparation.RECEIPT_NAME: prep_raw})
    return context


def _schema(ready):
    toolset_name = bridge.validate_preview_toolset_identity(ready.get("toolset_identity"))
    tool = ready.get("tool_schema")
    require(type(tool) is dict and tool.get("name") in {
        toolset_name + ".preview", toolset_name + ".Preview"},
        "Native registry tool differs from its authenticated generated class")
    parameter = ready.get("wire_parameter")
    require(parameter in {"request_json", "RequestJson"}, "Unexpected preview wire parameter")
    inputs = tool.get("inputSchema")
    require(type(inputs) is dict and inputs.get("type") == "object"
            and type(inputs.get("properties")) is dict and set(inputs["properties"]) == {parameter}
            and type(inputs["properties"][parameter]) is dict
            and inputs["properties"][parameter].get("type") == "string"
            and inputs.get("required") == [parameter], "Preview must expose exactly one required string input")
    return tool, parameter


def _close_values(first, second):
    return abs(first["paint_roughness"] - second["paint_roughness"]) <= 1e-6 and all(
        abs(a - b) <= 1e-6 for a, b in zip(first["paint_color"], second["paint_color"], strict=True))


def _receipt(value, context, request_id):
    _identity(value, context)
    require(value.get("request_id") == request_id and value.get("action") in {"set", "restore", "inspect", "camera"}
            and type(value.get("sequence")) is int and 0 <= value["sequence"] <= HISTORY_LIMIT
            and value.get("receipt_relative_path") == bridge.REQUEST_ROOT + "/" + request_id + "/receipt.json",
            "Native request identity, action, sequence or receipt path differs")
    _observation(value.get("before"), context["initial"])
    _observation(value.get("after"), context["initial"])
    action = value["action"]
    if action == "set":
        require(value["after"]["transient_mid"] is True, "Set did not read back a bound transient MID")
        if value["before"]["transient_mid"]:
            require(value["after"]["bound_material"] == value["before"]["bound_material"],
                    "Set replaced the already bound preview MID")
    elif action == "restore":
        require(value["after"] == context["initial"], "Restore did not read back the original bindings and values")
    else:
        require(value["before"] == value["after"], "Inspect changed the native material state")
    if action == "camera":
        bridge.camera_presets.validate_receipt(value)
    require(value.get("saved_inputs_before_sha256") == context["saved_digest"]
            and value.get("source_inputs_before_sha256") == context["source_digest"],
            "Native saved-input fingerprint differs before the request")


def _completed(value, context, request_id):
    _receipt(value, context, request_id)
    require(value.get("status") == "COMPLETED" and value.get("capture_pending") is False
            and value.get("saved_inputs_after_sha256") == context["saved_digest"]
            and value.get("source_inputs_after_sha256") == context["source_digest"]
            and type(value.get("dirty_before")) is dict and value.get("dirty_after") == value["dirty_before"],
            "Native request is incomplete, blocked or changed saved/dirty state")
    captures = value.get("captures")
    expected_count = 4 if value["action"] == "set" else 0
    require(type(captures) is list and len(captures) == expected_count,
            "Native capture inventory differs from the fixed request")
    for index, row in enumerate(captures):
        name = f"priming-{index}.png" if index < 3 else "preview.png"
        require(type(row) is dict and set(row) == {"path", "sha256", "size_bytes", "priming"}
                and row["path"] == bridge.REQUEST_ROOT + "/" + request_id + "/" + name
                and row["priming"] is (index < 3)
                and type(row["size_bytes"]) is int and 4096 < row["size_bytes"] <= bridge.PNG_LIMIT
                and isinstance(row["sha256"], str) and preparation.SHA256.fullmatch(row["sha256"]),
                "Native PNG record differs from the fixed bounded capture paths")


def _history(context):
    directory = _path(context["root"], bridge.REQUEST_ROOT)
    entries = []
    if directory.exists():
        with os.scandir(directory) as iterator:
            for entry in iterator:
                require(len(entries) < HISTORY_LIMIT and REQUEST_ID.fullmatch(entry.name),
                        "Native request history exceeds its inventory or name bound")
                path = _path(directory, entry.name)
                require(path.is_dir(), "Native request history contains an unexpected entry")
                entries.append(path)
    receipts, total = {}, 0
    for path in entries:
        receipt_path = _path(path, "receipt.json")
        require(receipt_path.exists(), "A previous native request is pending or uncertain; do not retry")
        raw = _read(receipt_path)
        total += len(raw)
        require(total <= HISTORY_BYTES, "Native request history exceeds its byte bound")
        value = _object(raw)
        _completed(value, context, path.name)
        receipts[path.name] = value
    changes = sorted((value for value in receipts.values() if value["action"] != "inspect"),
                     key=lambda value: value["sequence"])
    states = [context["initial"]]
    for index, value in enumerate(changes, 1):
        require(value["sequence"] == index and value["before"] == states[-1],
                "Native material history has a gap, duplicate sequence or stale before-state")
        states.append(value["after"])
    for value in receipts.values():
        if value["action"] == "inspect":
            require(value["sequence"] < len(states) and value["after"] == states[value["sequence"]],
                    "Native inspection differs from its preceding material state")
    return {"receipts": receipts, "sequence": len(changes), "current": states[-1]}


def _request(raw, context, history):
    value = _object(raw, bridge.REQUEST_LIMIT)
    action = value.get("action")
    require(action in {"set", "restore", "inspect", "camera"}, "Unknown material preview action")
    require(set(value) == COMMON_REQUEST | ({"paint_roughness", "paint_color"} if action == "set" else {"preset"} if action == "camera" else set()),
            "Unknown or missing material request field")
    require(type(value["schema_version"]) is int and value["schema_version"] == 1
            and value["session_id"] == context["identity"]["session_id"], "Material request belongs to another schema/session")
    require(type(value["expected_sequence"]) is int and value["expected_sequence"] == history["sequence"],
            "Material request sequence is stale")
    name = value["request_id"]
    require(isinstance(name, str) and REQUEST_ID.fullmatch(name), "Invalid material request identity")
    require(name not in history["receipts"] and len(history["receipts"]) < HISTORY_LIMIT
            and not _path(context["root"], bridge.REQUEST_ROOT + "/" + name).exists(),
            "Material request identity was already used; do not retry")
    require(action == "restore" or len(history["receipts"]) < HISTORY_LIMIT - 1,
            "The last bounded request slot is reserved for restoring the original material")
    if action == "set":
        _values(value)
    if action == "camera":
        bridge.camera_presets.preset(value["preset"])
    return value


class _Transport(official_client._Transport):
    def initialize(self):
        value = self._post("initialize", {"protocolVersion": official_client.PROTOCOL, "capabilities": {},
                                         "clientInfo": {"name": "YacsLevelEditorMaterialPreview", "version": "1"}})
        result = value.get("result")
        require("error" not in value and type(result) is dict
                and result.get("protocolVersion") == official_client.PROTOCOL
                and type(result.get("capabilities")) is dict
                and type(result["capabilities"].get("tools")) is dict, "Official MCP initialization failed")
        self._post("notifications/initialized", None, notification=True)


def _tools(transport, ready):
    tool, parameter = _schema(ready)
    response = transport._post("tools/list", {})
    result = response.get("result")
    require("error" not in response and type(result) is dict and "nextCursor" not in result
            and result.get("tools") == [tool], "Actual MCP tools/list differs from the single native reflected tool")
    return tool["name"], parameter, response


def _domain_result(response):
    result = response.get("result")
    require("error" not in response and type(result) is dict and result.get("isError", False) is False,
            "Material tools/call failed; uncertain calls are never retried")
    content = result.get("content")
    require(type(content) is list and len(content) == 1 and type(content[0]) is dict
            and content[0].get("type") == "text" and isinstance(content[0].get("text"), str),
            "Material result must be one bounded text result")
    # Installed UE 5.8.2 ObjectFunctionToolCall::MakeResult always wraps the
    # reflected return value in this exact object (source run 38137155495).
    # Our declared FString contains one canonical domain JSON object. The MCP
    # MakeTextResult helper preserves the serialized wrapper as its text.
    envelope = _object(content[0]["text"])
    require(set(envelope) == {"returnValue"} and type(envelope["returnValue"]) is str,
            "Material result must contain exactly one reflected returnValue string")
    return _object(envelope["returnValue"])


def _immutable(context):
    for relative, raw in context["immutable"].items():
        require(_read(_path(context["root"], relative)) == raw, "Owned session inputs changed during the request")
    for relative, expected in context["sources"].items():
        require(digest(_read(_path(ROOT, relative))) == expected, "Client/native helper source changed during the request")
    for relative, expected in context["retained_project_inputs"].items():
        require(preparation._file_identity(_path(context["launcher_root"], relative)) == expected,
                "Retained launcher project input changed during the request")


def _png_bytes(path, row):
    raw = _read(path, bridge.PNG_LIMIT)
    require(len(raw) == row["size_bytes"] and digest(raw) == row["sha256"]
            and raw[:8] == b"\x89PNG\r\n\x1a\n" and raw[12:16] == b"IHDR"
            and len(raw) >= 24 and struct.unpack(">II", raw[16:24]) == (1280, 720),
            "Captured PNG bytes, hash or 1280x720 dimensions differ")
    return raw


def _write(output, name, raw):
    with _path(output, name).open("xb") as stream:
        stream.write(raw)


def _retain_mcp_response(output, response):
    # This is the parsed JSON-RPC object in canonical form, not raw HTTP bytes.
    # Preserve it before domain validation, including responses we reject.
    raw = canonical(response) + b"\n"
    require(len(raw) <= JSON_LIMIT, "MCP response exceeds its diagnostic byte bound")
    name = "mcp-response.json"
    _write(output, name, raw)
    return {"path": name, "format": "canonical_parsed_json_rpc",
            "sha256": digest(raw), "size_bytes": len(raw)}


def _retain_native_diagnostic(context, request, output):
    # Only the independently validated request ID supplies this fixed path.
    # Read once, without waiting for captures or interpreting unvalidated data.
    relative = bridge.REQUEST_ROOT + "/" + request["request_id"] + "/receipt.json"
    observation = {"path": relative, "status": "NOT_OBSERVED"}
    try:
        path = _path(context["root"], relative)
        if path.exists():
            raw = _read(path)
            name = "native-diagnostic-receipt.json"
            _write(output, name, raw)
            observation.update({"status": "RETAINED_UNVALIDATED", "client_path": name,
                                "sha256": digest(raw), "size_bytes": len(raw)})
    except (ValueError, OSError, RuntimeError, TypeError, KeyError) as error:
        observation.update({"status": "NOT_RETAINED", "diagnostic_error_type": type(error).__name__,
                            "diagnostic_error": str(error)[:500]})
    return observation


def run(session_receipt, request_path, output):
    """Make at most one domain call and preserve independent native readbacks."""
    started = time.monotonic()
    require(output.is_absolute(), "Client output must be an absolute fresh directory")
    _path(output.parent, output.name)
    require(not output.exists(), "Client output already exists; preserve earlier evidence")
    output.mkdir(parents=True)
    receipt = {"schema_version": 1, "status": "BLOCKED", "tool_call_attempted": False,
               "tools_call_count": 0, "retry_permitted": False, "source_world_saved": False,
               "performance_pass": False, "owner_visual_status": "PENDING_FINAL_M3"}
    transport = context = request = None
    try:
        context = _load_context(session_receipt)
        receipt.update(context["identity"])
        require(request_path.is_absolute(), "Material request file must be absolute")
        raw_request = _read(request_path, bridge.REQUEST_LIMIT)
        history = _history(context)
        request = _request(raw_request, context, history)
        receipt.update({"request_id": request["request_id"], "action": request["action"],
                        "expected_sequence": request["expected_sequence"], "source_sha256": context["sources"]})
        _write(output, "request.json", raw_request)
        _write(output, "native-ready.json", context["immutable"][bridge.READY_RELATIVE])
        _write(output, SESSION_RECEIPT, context["immutable"][SESSION_RECEIPT])
        transport = _Transport()
        transport.initialize()
        name, parameter, inventory = _tools(transport, context["ready"])
        _write(output, "tools-list.json", canonical(inventory) + b"\n")
        _immutable(context)
        _verify_process(context["host"])
        # Recheck local sequence/pending state after HTTP negotiation. Native
        # validation still owns the atomic refusal of competing/stale calls.
        latest = _history(context)
        _request(raw_request, context, latest)
        require(latest == history, "Material history changed before dispatch")
        receipt["tool_call_attempted"], receipt["tools_call_count"] = True, 1
        response = transport.call(name, {parameter: canonical(request).decode("utf-8")})
        receipt["mcp_response"] = _retain_mcp_response(output, response)
        value = _domain_result(response)
        _receipt(value, context, request["request_id"])
        expected_sequence = history["sequence"] + (request["action"] != "inspect")
        require(value["action"] == request["action"] and value["sequence"] == expected_sequence
                and value["before"] == history["current"], "Native call did not observe the preceding material state")
        if request["action"] == "set":
            require(_close_values(value["after"], request), "Native effective paint values differ from the requested values")
        if request["action"] == "camera":
            require(value["camera_preset"]["preset"] == request["preset"],
                    "Native camera receipt belongs to another requested preset")
        require((value.get("status") == "ACCEPTED" and value.get("capture_pending") is True
                 and request["action"] == "set")
                or (value.get("status") == "COMPLETED" and value.get("capture_pending") is False),
                "Native call returned an invalid completion state")
        _write(output, "tool-result.json", canonical(value) + b"\n")
        final_path = _path(context["root"], value["receipt_relative_path"])
        deadline = time.monotonic() + POLL_SECONDS
        while not final_path.exists():
            require(time.monotonic() < deadline, "Native completion timed out; keep the request ID and do not retry")
            time.sleep(0.25)
            _path(context["root"], value["receipt_relative_path"])
        final_raw = _read(final_path)
        final = _object(final_raw)
        _completed(final, context, request["request_id"])
        for key in (*IDENTITY_KEYS, "request_id", "action", "sequence", "before", "after", "dirty_before",
                    "saved_inputs_before_sha256", "source_inputs_before_sha256", "receipt_relative_path"):
            require(final.get(key) == value.get(key), "Native final receipt differs from the accepted call")
        if value["status"] == "COMPLETED":
            require(final == value, "Synchronous native result differs from its saved receipt")
        captures = []
        for row in final["captures"]:
            raw = _png_bytes(_path(context["root"], row["path"]), row)
            filename = row["path"].rsplit("/", 1)[-1]
            _write(output, filename, raw)
            captures.append({**row, "client_path": filename})
        _immutable(context)
        process = _verify_process(context["host"])
        latest = _history(context)
        require(latest["sequence"] == expected_sequence and latest["current"] == final["after"],
                "Another material request changed the session before final readback")
        _write(output, "native-receipt.json", final_raw)
        receipt.update({"status": "COMPLETED", "sequence": expected_sequence, "before": final["before"],
                        "after": final["after"], "process_readback": process, "captures": captures,
                        "native_receipt": {"path": value["receipt_relative_path"], "sha256": digest(final_raw),
                                           "size_bytes": len(final_raw)},
                        "saved_inputs_before_sha256": final["saved_inputs_before_sha256"],
                        "saved_inputs_after_sha256": final["saved_inputs_after_sha256"],
                        "source_inputs_before_sha256": final["source_inputs_before_sha256"],
                        "source_inputs_after_sha256": final["source_inputs_after_sha256"]})
        if request["action"] == "camera":
            receipt.update({key: final[key] for key in
                            ("camera_before", "camera_after", "camera_preset")})
    except (ValueError, OSError, RuntimeError, TypeError, KeyError, subprocess.SubprocessError,
            http.client.HTTPException) as error:
        receipt.update({"status": "BLOCKED", "error_type": type(error).__name__, "error": str(error)[:500]})
    finally:
        if transport is not None:
            try:
                transport.close()
            except (OSError, http.client.HTTPException) as error:
                receipt.update({"status": "BLOCKED", "close_error_type": type(error).__name__})
        if (receipt["status"] == "BLOCKED" and receipt["tool_call_attempted"]
                and context is not None and request is not None):
            receipt["native_diagnostic"] = _retain_native_diagnostic(context, request, output)
        receipt["elapsed_seconds"] = time.monotonic() - started
        _write(output, CLIENT_RECEIPT, canonical(receipt) + b"\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-receipt", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run(args.session_receipt, args.request, args.output)
    print("YACS_LEVEL_EDITOR_MATERIAL " + json.dumps({
        key: receipt[key] for key in ("status", "tool_call_attempted", "tools_call_count", "elapsed_seconds")}))
    return 0 if receipt["status"] == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())

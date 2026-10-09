"""Fixed Python binding proof in the marked, isolated native BOB HostProject.

Run beside InputBoundary in the same fresh editor. Automation owns editor exit.
This verifies real reflected rejection on Entry, never an owned Landscape hit.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path

MARKER_NAME = ".yacs-mcp-native-reflection-proof.json"
RECEIPT_NAME = "native-python-reflection.json"
SCRIPT_NAME = "probe_official_mcp_bob_reflection.py"
ENTRY_MAP = "/Engine/Maps/Entry"
LIBRARY_CLASS = "/Script/YacsBobInspection.YacsBobLandscapeHitLibrary"
WRONG_MAP_ERROR = "Current map is outside the accepted BOB inspection checkpoint."
ENV_FIELDS = {
    "host_project_root": "YACS_MCP_NATIVE_HOST_PROJECT_ROOT",
    "artifact_root": "YACS_MCP_NATIVE_ARTIFACT_ROOT",
    "exact_sha": "YACS_MCP_NATIVE_EXPECTED_HEAD",
}
MARKER_FIELDS = {
    "schema_version", "exact_sha", "host_project_root", "artifact_root",
    "script_sha256", "public_header_sha256", "plugin_descriptor_sha256",
    "host_project_descriptor_sha256", "host_engine_config_sha256",
}
RESULT_FIELDS = (
    "accepted", "status", "error", "blocking_hit", "impact_point", "map_package",
    "actor_path", "actor_class_path", "component_path", "component_class_path",
    "hit_actor", "hit_component",
)
FALSE_CLAIMS = (
    "native_bob_capture_verified", "native_registry_dispatch_verified",
    "official_mcp_transport_verified", "official_mcp_admitted",
    "accepted_checkpoint_verified", "persistent_world_mutation", "performance_pass",
)


def _plain_path(path: Path) -> None:
    for candidate in (path, *path.parents):
        try:
            details = candidate.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(details.st_mode) or getattr(details, "st_file_attributes", 0) & 0x400:
            raise RuntimeError("Reflection proof cannot use symlink or junction paths")


def _root(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise RuntimeError("Reflection proof roots must be absolute canonical paths")
    _plain_path(path)
    resolved = path.resolve(strict=True)
    if not resolved.is_dir():
        raise RuntimeError("Reflection proof root is not an existing directory")
    return resolved


def _bytes(path: Path) -> bytes:
    _plain_path(path)
    with path.open("rb") as stream:
        details = os.fstat(stream.fileno())
        if not stat.S_ISREG(details.st_mode) or details.st_size > 65536:
            raise RuntimeError("Reflection proof input exceeds its fixed regular-file bound")
        value = stream.read(65537)
    if len(value) > 65536:
        raise RuntimeError("Reflection proof input changed beyond its fixed file bound")
    return value


def _json_object(value: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise RuntimeError("Reflection proof metadata contains duplicate keys")
            result[key] = item
        return result

    def nonfinite(_value):
        raise RuntimeError("Reflection proof metadata contains a non-finite number")

    result = json.loads(value, object_pairs_hook=pairs, parse_constant=nonfinite)
    if not isinstance(result, dict):
        raise RuntimeError("Reflection proof metadata must be an object")
    return result


def _load_context(script: Path, environment: dict) -> dict:
    """Only the trusted launcher supplies this fixed private context."""
    _plain_path(script)
    script = script.resolve(strict=True)
    if script.name != SCRIPT_NAME or script.parent.name != "ue" or script.parent.parent.name != "scripts":
        raise RuntimeError("Reflection proof requires its fixed repository-owned script")
    for name in ENV_FIELDS.values():
        if not isinstance(environment.get(name), str) or not environment[name]:
            raise RuntimeError("Reflection proof is missing trusted launcher context")
    exact_sha = environment[ENV_FIELDS["exact_sha"]]
    if not re.fullmatch(r"[0-9a-f]{40}", exact_sha):
        raise RuntimeError("Reflection proof revision is not an exact SHA")
    host = _root(environment[ENV_FIELDS["host_project_root"]])
    artifacts = _root(environment[ENV_FIELDS["artifact_root"]])
    if host.name != "HostProject":
        raise RuntimeError("Reflection proof requires the isolated BuildPlugin HostProject")
    expected_artifact_parent = script.parents[2] / "Saved/RuntimeProof/OfficialMcpNativeProbe"
    if artifacts.parent != expected_artifact_parent.resolve(strict=True) or not re.fullmatch(
        r"(?:[0-9]+-[0-9]+|[0-9a-f]{32})", artifacts.name
    ):
        raise RuntimeError("Reflection receipt must use this run's fixed ignored artifact root")
    receipt = artifacts / RECEIPT_NAME
    _plain_path(receipt)
    if receipt.exists():
        raise RuntimeError("Reflection proof cannot replace an existing receipt")

    marker_path = host / MARKER_NAME
    marker_bytes = _bytes(marker_path)
    marker = _json_object(marker_bytes)
    if set(marker) != MARKER_FIELDS or type(marker["schema_version"]) is not int or marker["schema_version"] != 1:
        raise RuntimeError("Reflection proof marker does not match its fixed contract")
    if marker["exact_sha"] != exact_sha or _root(marker["host_project_root"]) != host or _root(marker["artifact_root"]) != artifacts:
        raise RuntimeError("Reflection proof marker disagrees with its trusted launcher context")
    plugin_root = host / "Plugins/YacsBobInspection"
    sources = {
        "script_sha256": script,
        "public_header_sha256": plugin_root / "Source/YacsBobInspection/Public/YacsBobLandscapeHit.h",
        "plugin_descriptor_sha256": plugin_root / "YacsBobInspection.uplugin",
        "host_project_descriptor_sha256": host / "HostProject.uproject",
        "host_engine_config_sha256": host / "Config/DefaultEngine.ini",
    }
    snapshots = {}
    for name, path in sources.items():
        expected = marker[name]
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise RuntimeError("Reflection proof marker contains an invalid source hash")
        value = _bytes(path)
        observed = hashlib.sha256(value).hexdigest()
        if observed != expected:
            raise RuntimeError(
                "Reflection proof source differs from its trusted marker: "
                f"field={name}, expected_sha256={expected}, observed_sha256={observed}"
            )
        snapshots[name] = value

    plugin = _json_object(snapshots["plugin_descriptor_sha256"])
    modules = plugin.get("Modules")
    if (plugin.get("EnabledByDefault") is not False or plugin.get("CanContainContent") is not False
            or not isinstance(modules, list) or len(modules) != 1
            or modules[0].get("Name") != "YacsBobInspection" or modules[0].get("Type") != "Editor"
            or modules[0].get("LoadingPhase") != "PostEngineInit"):
        raise RuntimeError("Reflection proof plugin metadata is outside the opt-in Editor contract")
    project = _json_object(snapshots["host_project_descriptor_sha256"])
    if project.get("DisableEnginePluginsByDefault", False) is not False or project.get("Modules", []) != []:
        raise RuntimeError("Reflection proof requires the minimal bare HostProject")
    enabled = {}
    for entry in project.get("Plugins", []):
        if (not isinstance(entry, dict) or not isinstance(entry.get("Name"), str)
                or type(entry.get("Enabled")) is not bool or entry["Name"] in enabled):
            raise RuntimeError("Reflection proof HostProject plugin metadata is malformed")
        enabled[entry["Name"]] = entry["Enabled"]
    if (enabled.get("YacsBobInspection") is not True or enabled.get("PythonScriptPlugin") is not True
            or enabled.get("ModelContextProtocol") is not False
            or any(name not in {"YacsBobInspection", "PythonScriptPlugin", "ToolsetRegistry", "ModelContextProtocol"}
                   for name in enabled)
            or ("ToolsetRegistry" in enabled and enabled["ToolsetRegistry"] is not True)):
        raise RuntimeError("Reflection proof may enable only its fixed generated-project dependencies")

    header = snapshots["public_header_sha256"].decode("utf-8")
    header = re.sub(r"/\*.*?\*/|//[^\n]*", "", header, flags=re.S)
    if re.search(r"\bAICallable\b", header) or len(re.findall(r"\bUFUNCTION\s*\(", header)) != 2:
        raise RuntimeError("Reflection helpers must remain two non-AICallable source declarations")
    for method in ("InspectAcceptedCheckpointIdentity", "InspectAcceptedLandscapeHit"):
        if not re.search(r"\bstatic\s+FYacsBobLandscapeHit\s+" + method + r"\s*\(", header):
            raise RuntimeError("Reflection proof public header does not contain its fixed helper declarations")
    return {
        "exact_sha": exact_sha, "host": host, "artifacts": artifacts, "receipt": receipt,
        "marker_path": marker_path, "marker_bytes": marker_bytes, "marker": marker,
        "sources": sources,
        "module_metadata": {"enabled_by_default": False, "can_contain_content": False,
                            "module": "YacsBobInspection", "type": "Editor", "loading_phase": "PostEngineInit",
                            "ai_callable": False, "evidence_kind": "hashed_public_source_declarations"},
    }


def _unchanged(context: dict) -> None:
    if _bytes(context["marker_path"]) != context["marker_bytes"]:
        raise RuntimeError("Reflection proof context changed during execution")
    for name, path in context["sources"].items():
        if hashlib.sha256(_bytes(path)).hexdigest() != context["marker"][name]:
            raise RuntimeError("Reflection proof source changed during execution")


def _write_receipt(context: dict, receipt: dict) -> None:
    _plain_path(context["artifacts"])
    _plain_path(context["receipt"])
    with context["receipt"].open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _rejected_result(result, result_class) -> dict:
    if not isinstance(result, result_class):
        raise RuntimeError("Native reflection returned an unexpected struct binding")
    actual = {name: result.get_editor_property(name) for name in RESULT_FIELDS}
    if (actual["accepted"] is not False or actual["blocking_hit"] is not False
            or actual["status"] != "REJECTED" or actual["error"] != WRONG_MAP_ERROR
            or any(actual[name] != "" for name in ("map_package", "actor_path", "actor_class_path", "component_path", "component_class_path"))
            or actual["hit_actor"] is not None or actual["hit_component"] is not None):
        raise RuntimeError("Native reflection did not reject Entry with empty collision identity")
    point = actual["impact_point"]
    coordinates = [float(point.x), float(point.y), float(point.z)]
    if coordinates != [0.0, 0.0, 0.0]:
        raise RuntimeError("Rejected native reflection supplied an impact measurement")
    actual["impact_point"] = coordinates
    return {"struct_binding": type(result).__name__, "fields": actual}


def _raw_hit_properties(hit) -> dict:
    """Record real binding availability; unavailable raw owners are not invented."""
    actual = {}
    for name in ("blocking_hit", "impact_point", "hit_actor", "hit_component"):
        try:
            value = hit.get_editor_property(name)
        except Exception as error:
            # Property lookup on native UStruct raises an engine binding error.
            actual[name] = {"available": False, "error_type": type(error).__name__, "error": str(error)[:512]}
            continue
        if name == "impact_point":
            value = [float(value.x), float(value.y), float(value.z)]
            if value != [0.0, 0.0, 0.0]:
                raise RuntimeError("Default native HitResult supplied an impact measurement")
        elif name == "blocking_hit":
            if value is not False:
                raise RuntimeError("Default native HitResult is unexpectedly blocking")
        elif value is not None:
            raise RuntimeError("Default native HitResult supplied collision ownership")
        actual[name] = {"available": True, "value": value}
    return actual


def main() -> None:
    context = _load_context(Path(__file__), os.environ)
    receipt = {
        "schema_version": 1, "exact_sha": context["exact_sha"], "status": "BLOCKED",
        "reflection_verified": False, "source_unchanged": False,
        "performance_status": "DEFERRED_AFTER_M3", "error": None,
        **dict.fromkeys(FALSE_CLAIMS, False),
    }
    try:
        import unreal

        project_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        if _root(project_dir) != context["host"]:
            raise RuntimeError("Current Unreal project is outside the trusted bare HostProject")
        python_settings = unreal.get_default_object(unreal.PythonScriptPluginSettings)
        if python_settings.get_editor_property("remote_execution") is not False:
            raise RuntimeError("Native reflection proof requires Python remote execution disabled")
        # Proven API from texture_material_prep_ue_smoke.py; Automation owns exit.
        unreal.EditorPythonScripting.set_keep_python_script_alive(True)
        engine_version = unreal.SystemLibrary.get_engine_version()
        if not re.match(r"^5[.]8[.]2-56702186(?:[+]|\s|$)", engine_version):
            raise RuntimeError("Reflection proof requires the admitted exact engine")
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        current_map = world.get_path_name().split(".", 1)[0] if world is not None else ""
        if current_map != ENTRY_MAP:
            raise RuntimeError("Reflection proof requires the fixed bare Entry map")
        library = unreal.YacsBobLandscapeHitLibrary
        class_path = library.static_class().get_path_name()
        if class_path != LIBRARY_CLASS:
            raise RuntimeError("Reflection proof loaded an unexpected native helper class")
        result_class = unreal.YacsBobLandscapeHit
        identity = _rejected_result(library.inspect_accepted_checkpoint_identity(), result_class)
        hit = unreal.HitResult()
        raw_properties = _raw_hit_properties(hit)
        collision = _rejected_result(library.inspect_accepted_landscape_hit(hit), result_class)
        _unchanged(context)
        receipt.update({
            "status": "NATIVE_PYTHON_REFLECTION_VERIFIED", "reflection_verified": True,
            "source_unchanged": True, "engine_version": engine_version, "current_map_package": current_map,
            "python_remote_execution": False,
            "helper_class_path": class_path, "reflected_fields": list(RESULT_FIELDS),
            "checkpoint_identity": identity, "default_hit_identity": collision,
            "raw_hit_result_binding": type(hit).__name__, "raw_hit_result_properties": raw_properties,
            "source_sha256": {name: context["marker"][name] for name in context["sources"]},
            "module_metadata": context["module_metadata"],
        })
        _write_receipt(context, receipt)
        unreal.log("YACS_BOB_NATIVE_REFLECTION_VERIFIED " + str(context["receipt"]))
    except Exception as error:
        receipt["error"] = str(error)[:1024]
        if not context["receipt"].exists():
            _write_receipt(context, receipt)
        # -ScriptErrorsAreFatal and the launcher's own-PID timeout own failure.
        # Do not invent a request_exit binding or interfere with other editors.
        raise


if __name__ == "__main__":
    main()

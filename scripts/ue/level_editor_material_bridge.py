"""One owned, transient paint preview in the existing official UE MCP server.

This module is loaded by the retained Level Editor bootstrap, never remotely as
Python. Requests cannot choose an object, asset, parameter name, script or path.
The b9 saved scene remains immutable. A preview changes only the existing paint
slots to a transient MID and reads the effective native values back from those
slots. The original bindings are retained for an explicit restore.
"""

import ctypes
import hashlib
import json
import logging
import math
import os
import re
import struct
import time
from pathlib import Path

if __package__:
    from . import level_editor_camera_presets as camera_presets
    from . import level_editor_surface_preview as surface_preview
    from . import level_editor_shoulder_repair as shoulder_repair
    from . import level_editor_script_reload as script_reload
else:
    import level_editor_camera_presets as camera_presets
    import level_editor_surface_preview as surface_preview
    import level_editor_shoulder_repair as shoulder_repair
    import level_editor_script_reload as script_reload

RUNTIME_SHA = "b9fddea3f6023239da98bec7a5107ed1124cf52e"
MAP_PACKAGE = "/Game/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview"
MAP_SHA256 = "cbbf374309508fdb2c6f86c6324af4a3824a0c5ed32a4bfc29200ad3b29da183"
PAINT_MATERIAL = "/Game/Generated/YACS/RoadAsphaltConsumer/EdgeMarkings/MI_RoadEdgeMarkings.MI_RoadEdgeMarkings"
PAINT_MASTER = "/Game/Generated/YACS/RoadAsphaltConsumer/EdgeMarkings/M_RoadEdgeMarkings.M_RoadEdgeMarkings"
MANIFEST_SHA256 = "974c86813d2ee95d4f3cc244fd3590f7f9711506973c10544f6ede954557344a"
ENGINE_VERSION = "5.8.2-56702186+++UE5+Release-5.8"
PORT = 18784
REQUEST_LIMIT = 4096
PREFLIGHT_LIMIT = 16 * 1024
NATIVE_CENSUS_LIMIT = 32768
PNG_LIMIT = 8 * 1024 * 1024
CAPTURE_SECONDS = 150.0
PRIMING_COUNT = 3
READY_RELATIVE = "Saved/LevelEditorStream/material-bridge-ready.json"
REQUEST_ROOT = "Saved/LevelEditorStream/material-preview"
ALLOWED_NAMES = (
    "/^PythonTypes[.]YacsRoadMaterialPreview_0x[0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F]$/",
    "/^PythonTypes[.]YacsRoadMaterialPreview_0x[0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F][.][Pp]review$/",
)
LEGACY_BASE_CLASS = "/Script/ModelContextProtocolEngine.ModelContextProtocolToolLibrary"
ABSTRACT_LEGACY_CLASSES = {
    LEGACY_BASE_CLASS,
    "/Script/ModelContextProtocolEditor.ModelContextProtocolEditorToolLibrary",
}
BRIDGE = None
LOGGER = logging.getLogger(__name__)

# Actual installed UE 5.8.2 source, retained by #384 declaration/control-flow
# runs 37990333833/37993672276 and #364 runs 38044121552, 38133509018 and
# 38137155495. No Epic source is copied.
ENGINE_PINS = {
    "Plugins/Experimental/ToolsetRegistry/ToolsetRegistry.uplugin": "2dfc01159b54daea67c62966a48b78254d1d848d84e8df48c708c7a69d3f2062",
    "Plugins/Experimental/ModelContextProtocol/ModelContextProtocol.uplugin": "74420534edcd6baafcb48e0af919d53b84891bdade7b97869b0ef485c3ea1518",
    "Plugins/Experimental/ToolsetRegistry/Content/Python/toolset_registry/__init__.py": "df6a65bc5740271dcd989a1df3208b40282323015ec1aa586895fffb1e97abbb",
    "Plugins/Experimental/ToolsetRegistry/Content/Python/toolset_registry/tool_call_impl.py": "e2925fc50b1526be5556a3266a32e543cb802bac0ca6942ff0fec15a837f86e4",
    "Plugins/Experimental/ToolsetRegistry/Source/ToolsetRegistry/Private/ToolsetRegistry/FunctionLibraryToolset.cpp": "246db3d9f86652f5cbafe07f10caf1a85dcd091877f5e9c2100e0a27972234ea",
    "Plugins/Experimental/ToolsetRegistry/Source/ToolsetRegistry/Private/ToolsetRegistry/ObjectFunctionToolCall.cpp": "c4fe4757cadeb38cb9d359a81c046d173447b1625f7400ad123d7ca44eb4e56b",
    "Plugins/Experimental/ToolsetRegistry/Source/ToolsetRegistry/Private/ToolsetRegistry/ToolsetJson.cpp": "a168e4b6888b8f1111800337fa3a1886ffe0ee670add8c9ef5a30399e6a213b4",
    "Plugins/Experimental/ToolsetRegistry/Source/ToolsetRegistry/Public/ToolsetRegistry/UToolsetRegistry.h": "03e3abeec87a10ff1b099cdbdfba9d65349409af49e7d2a1688bb78c77f59d6b",
    "Plugins/Experimental/ToolsetRegistry/Source/ToolsetRegistry/Public/ToolsetRegistry/ToolsetRegistry.h": "e80e4fe2c7cb3f63f9bab387eb48194f90d245263e534165eaf7c572f1842152",
    "Plugins/Experimental/ModelContextProtocol/Source/ModelContextProtocol/Private/ModelContextProtocolModule.cpp": "86ee49f40a61e754040b72b8f618fa464542881ac04b0723fc3f68f5438880ee",
    "Plugins/Experimental/ModelContextProtocol/Source/ModelContextProtocol/Public/ModelContextProtocolToolResults.h": "b5a9cdeac174739aba689639b39f1ba328d05a1d5886323fb66ad37f149f60d3",
    "Plugins/Experimental/ModelContextProtocol/Source/ModelContextProtocolEngine/Public/ModelContextProtocolToolLibrary.h": "5b1536eaa8e5bfdf7508801d32f75f03fb683b69850733a39f6b003b2d565b42",
    "Plugins/Experimental/ModelContextProtocol/Source/ModelContextProtocolEngine/Private/ModelContextProtocolToolLibrary.cpp": "c350ebeb1ad3b541d089269724bc79bf2c397b61aeea07e1be99e6b9ca47c885",
    "Plugins/Experimental/ModelContextProtocol/Source/ModelContextProtocolEditor/Public/ModelContextProtocolEditorToolLibrary.h": "75ebf03c7ea948b85c4926d5fd222e2bbdcf8ba94311c41a9fb919a6988b67f4",
    "Plugins/Experimental/ModelContextProtocol/Source/ModelContextProtocolEngine/Public/ModelContextProtocolSettings.h": "589492fd7156c9b21e5cfa8e60787b45b0464801565a07657f35a995559fbdcf",
    "Plugins/Experimental/ToolsetRegistry/Source/ToolsetRegistry/Public/ToolsetRegistry/ToolsetRegistrySubsystem.h": "30d55774b884de722e7452517d8320234daeb221035541de43b2406469a23984",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON member")
        result[key] = value
    return result


def strict_json(raw, limit, *, expected_type=dict):
    require(isinstance(raw, (bytes, str)), "JSON must be UTF-8 text")
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")
    require(len(raw.encode("utf-8")) <= limit, "JSON exceeds its bound")
    value = json.loads(
        raw,
        object_pairs_hook=_object_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON")),
    )
    require(
        type(value) is expected_type,
        "JSON must be one object"
        if expected_type is dict
        else "JSON must be one array",
    )
    return value


def validate_request(raw, session_id, sequence, used):
    request = strict_json(raw, REQUEST_LIMIT)
    common = {
        "schema_version",
        "session_id",
        "request_id",
        "action",
        "expected_sequence",
    }
    action = request.get("action")
    require(action in ("set", "restore", "inspect", "camera", "surface", "repair", "reload", "checkpoint"), "Unknown preview action")
    expected = common | (
        {"paint_roughness", "paint_color"}
        if action == "set"
        else {"preset"}
        if action in ("camera", "surface")
        else set()
    )
    if "capture" in request:
        require(action in ("set", "surface") and type(request["capture"]) is bool, "Capture flag requires a material action and boolean")
        expected.add("capture")
    require(set(request) == expected, "Unknown or missing preview field")
    require(
        type(request["schema_version"]) is int and request["schema_version"] == 1,
        "Preview schema differs",
    )
    require(request["session_id"] == session_id, "Preview belongs to another session")
    require(
        type(request["expected_sequence"]) is int
        and request["expected_sequence"] == sequence,
        "Preview sequence is stale",
    )
    name = request["request_id"]
    require(
        isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name),
        "Invalid request identity",
    )
    require(
        name not in used,
        "Request identity was already used; uncertain calls are never retried",
    )
    require(len(used) < 256, "The bounded preview session request limit was reached")
    if action == "surface":
        require(type(request["preset"]) is str and request["preset"] in surface_preview.PRESETS, "Unknown surface preset")
    if action == "camera":
        camera_presets.preset(request["preset"])
    if action == "set":
        color = request["paint_color"]
        values = [request["paint_roughness"]]
        require(
            type(color) is list and len(color) == 4,
            "Paint color must have four channels",
        )
        values.extend(color)
        require(
            all(
                type(value) in (int, float)
                and math.isfinite(value)
                and 0.0 <= value <= 1.0
                for value in values
            )
            and color[3] == 1.0,
            "Paint controls require finite [0,1] values and opaque alpha",
        )
    return request


def safe_path(root, relative):
    require(
        isinstance(relative, str)
        and 0 < len(relative) <= 512
        and "\\" not in relative
        and ":" not in relative,
        "Invalid owned relative path",
    )
    parts = relative.split("/")
    require(
        all(
            part not in ("", ".", "..") and not part.endswith((".", " "))
            for part in parts
        ),
        "Owned path traversal or alias",
    )
    path = root.joinpath(*parts)
    require(
        path.resolve().is_relative_to(root.resolve()), "Owned path escapes the session"
    )
    for entry in (path, *path.parents):
        require(
            not entry.is_symlink()
            and not (hasattr(entry, "is_junction") and entry.is_junction()),
            "Owned path is redirected",
        )
        if entry == root:
            break
    return path


def file_identity(path, limit=512 * 1024 * 1024):
    before = path.stat()
    require(
        path.is_file() and 0 <= before.st_size <= limit,
        "File exceeds its identity bound",
    )
    hasher = hashlib.sha256()
    total = 0
    with path.open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            total += len(chunk)
            require(total <= limit, "File grew beyond its bound")
            hasher.update(chunk)
    after = path.stat()
    require(
        (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        == (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        and total == before.st_size,
        "File changed during native conservation read",
    )
    return {"sha256": hasher.hexdigest(), "size_bytes": total}


def write_new(path, value):
    raw = (canonical(value) + "\n").encode()
    require(len(raw) <= 2 * 1024 * 1024, "Preview receipt exceeds its bound")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    require(not path.exists(), "Preview receipt already exists")
    temporary.rename(path)


def process_start_filetime():
    require(os.name == "nt", "Owned native bridge requires Windows")
    from ctypes import wintypes

    times = [wintypes.FILETIME() for _ in range(4)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [
        ctypes.POINTER(wintypes.FILETIME)
    ] * 4
    require(
        kernel.GetProcessTimes(
            kernel.GetCurrentProcess(), *(ctypes.byref(value) for value in times)
        ),
        "Native process start time is unavailable",
    )
    return str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)


def dirty_state(api):
    return {
        name: sorted(
            package.get_path_name()
            for package in getattr(api.EditorLoadingAndSavingUtils, name)()
        )
        for name in ("get_dirty_map_packages", "get_dirty_content_packages")
    }



def recovery_dirty_conserved(result):
    before, after = result.get("dirty_before"), result.get("dirty_after")
    if before == after:
        return True
    if result.get("action") != "checkpoint" or type(before) is not dict or type(after) is not dict:
        return False
    keys = {"get_dirty_map_packages", "get_dirty_content_packages"}
    revision = result.get("script_revision_after", "")
    if set(before) != keys or set(after) != keys or not re.fullmatch(r"[0-9a-f]{40}", revision):
        return False
    root = "/Game/Generated/YACS/LiveCheckpoints/R" + revision[:12] + "/"
    allowed = {"get_dirty_map_packages": {root + "L_RoadSurface"},
               "get_dirty_content_packages": {root + name for name in ("M_Road", "MI_Road", "M_Shoulder", "MI_Shoulder")}}
    for key in keys:
        if type(before[key]) is not list or type(after[key]) is not list:
            return False
        if not set(before[key]) <= set(after[key]) or not set(after[key]) - set(before[key]) <= allowed[key]:
            return False
    return True


def vector(value):
    return [float(getattr(value, name)) for name in ("r", "g", "b", "a")]


def close_values(first, second):
    return abs(first["paint_roughness"] - second["paint_roughness"]) <= 1e-6 and all(
        abs(a - b) <= 1e-6
        for a, b in zip(first["paint_color"], second["paint_color"], strict=True)
    )


def validate_preview_toolset_identity(identity):
    """Bind the observed generated shape to one exact native class, not a family."""
    require(
        type(identity) is dict
        and set(identity) == {"class_name", "class_path", "outer_name", "toolset_name"}
        and all(type(value) is str for value in identity.values()),
        "Preview toolset identity must contain exactly four native string fields",
    )
    class_name, outer_name = identity["class_name"], identity["outer_name"]
    # This is our bounded admission policy for the generated shape observed in
    # run38131946787, not a universal Unreal/Python class naming convention.
    require(
        re.fullmatch(r"YacsRoadMaterialPreview_0x[0-9A-F]{8}", class_name) is not None,
        "Unexpected native preview class name; observed="
        + bounded_text(class_name, 128),
    )
    require(
        len(outer_name) <= 256
        and re.fullmatch(r"/(?:[A-Za-z0-9_]+/)*PythonTypes", outer_name) is not None,
        "Unexpected native preview outer package; observed="
        + bounded_text(outer_name, 300),
    )
    # FFunctionLibraryToolset::GetToolsetClassName uses the actual outer's last
    # slash-delimited segment. The admitted PythonTypes outer is its ordinary
    # package branch, never the separate *_PY package/module transformation.
    toolset_name = outer_name.rsplit("/", 1)[1] + "." + class_name
    require(
        identity["class_path"] == outer_name + "." + class_name
        and identity["toolset_name"] == toolset_name,
        "Native preview class path or qualified toolset name differs",
    )
    return toolset_name


def read_preview_toolset_identity(api, native_class):
    require(
        isinstance(native_class, api.Class),
        "Owned preview static_class did not return a native Class",
    )
    outer = native_class.get_outer()
    require(isinstance(outer, api.Object), "Owned preview class has no native outer")
    class_name, outer_name = native_class.get_name(), outer.get_name()
    require(
        type(class_name) is str and type(outer_name) is str,
        "Owned preview class and outer names must be native strings",
    )
    identity = {
        "class_name": class_name,
        "class_path": native_class.get_path_name(),
        "outer_name": outer_name,
        "toolset_name": outer_name.rsplit("/", 1)[-1] + "." + class_name,
    }
    validate_preview_toolset_identity(identity)
    return identity


def reflected_tool(schema, identity):
    toolset_name = validate_preview_toolset_identity(identity)
    require(
        type(schema) is dict
        and schema.get("name") == toolset_name
        and type(schema.get("tools")) is list
        and len(schema["tools"]) == 1,
        "The native preview registry must expose exactly the owned toolset and one tool",
    )
    tool = schema["tools"][0]
    require(
        tool.get("name") in (toolset_name + ".preview", toolset_name + ".Preview"),
        "Unexpected native preview tool name",
    )
    inputs = tool.get("inputSchema", {})
    properties = inputs.get("properties", {})
    require(
        inputs.get("type") == "object" and len(properties) == 1,
        "Preview must expose one typed string parameter",
    )
    parameter = next(iter(properties))
    require(
        parameter in ("request_json", "RequestJson")
        and properties[parameter].get("type") == "string"
        and inputs.get("required") == [parameter],
        "Unexpected native preview parameter schema",
    )
    return {key: tool[key] for key in ("name", "description", "inputSchema")}, parameter


def bounded_text(value, bound):
    text = str(value)[:bound]
    while len(canonical(text).encode("utf-8")) > bound:
        text = text[: len(text) // 2]
    return text


class NativeCensusError(ValueError):
    """Keep the original failure and its actual production candidate together."""

    def __init__(self, context, native_error):
        self.native_error = native_error
        self.context = {
            key: bounded_text(context[key], 64)
            for key in ("iterator", "stage")
            if key in context
        }
        if "index" in context:
            self.context["index"] = context["index"]
        for name in ("candidate", "coverage_candidate"):
            if name not in context:
                continue
            candidate = context[name]
            self.context[name] = {
                key: bounded_text(candidate[key], bound)
                for key, bound in (
                    ("python_type", 64),
                    ("path", 256),
                    ("object_class", 192),
                )
                if key in candidate
            }
        for key in ("parent_class", "cdo_path"):
            if key in context:
                self.context[key] = bounded_text(context[key], 192)
        super().__init__(
            "Native class census failed; observed="
            + canonical(
                {
                    "context": self.context,
                    "native_error": preflight_error(native_error),
                }
            )
        )


def legacy_census(api, *, evidence=None):
    # ClassIterator enumerates class types; ObjectIterator enumerates instances
    # of UClass, including any actual metaclass default objects. Fully crosscheck
    # both inventories. Only exact CDO identity can explain an object-only entry.
    class_path, limit = "/Script/CoreUObject.Class", NATIVE_CENSUS_LIMIT
    context = {"iterator": "fixed_classes", "stage": "load"}

    def identity(candidate):
        context["candidate"] = {"python_type": type(candidate).__name__}
        require(
            not isinstance(candidate, type),
            "Native class iterator returned a Python type instead of a native object",
        )
        path = candidate.get_path_name()
        context["candidate"]["path"] = path
        require(type(path) is str and path, "Native census class has no exact path")
        metaclass = candidate.get_class()
        context["candidate"]["object_class"] = metaclass.get_path_name()
        return path, metaclass

    try:
        classes = {}
        for path in (class_path, *sorted(ABSTRACT_LEGACY_CLASSES)):
            context = {
                "iterator": "fixed_classes",
                "stage": "load",
                "candidate": {"path": path},
            }
            native_class = api.load_class(None, path)
            actual = None if native_class is None else native_class.get_path_name()
            require(
                actual == path,
                "Required native census class is unavailable or differs; observed="
                + canonical({"expected": path, "actual": actual}),
            )
            classes[path] = native_class

        native_classes, names = {}, []
        context = {"iterator": "ClassIterator(Object)", "stage": "initialize"}
        candidates = iter(api.ClassIterator(api.Object))
        for index in range(limit):
            context = {
                "iterator": "ClassIterator(Object)",
                "index": index,
                "stage": "iterate",
            }
            try:
                candidate = next(candidates)
            except StopIteration:
                break
            context["stage"] = "identity"
            path, _metaclass = identity(candidate)
            context["stage"] = "unique_path"
            require(path not in native_classes, "Duplicate native ClassIterator path")
            native_classes[path] = candidate
            context.update({"stage": "inheritance", "parent_class": LEGACY_BASE_CLASS})
            is_legacy = api.MathLibrary.class_is_child_of(
                candidate, classes[LEGACY_BASE_CLASS]
            )
            require(
                type(is_legacy) is bool, "Native class comparison did not return bool"
            )
            if is_legacy:
                context["stage"] = "legacy_admission"
                require(
                    path in ABSTRACT_LEGACY_CLASSES,
                    "A concrete legacy library blocks preview-only startup",
                )
                names.append(path)
        else:
            context["stage"] = "completion"
            raise ValueError(
                "ClassIterator reached its bound without proving completion"
            )
        context = {"iterator": "ClassIterator(Object)", "stage": "required_bases"}
        require(
            set(names) == ABSTRACT_LEGACY_CLASSES,
            "Native legacy MCP census must contain exactly the two pinned abstract bases",
        )
        for path in sorted(ABSTRACT_LEGACY_CLASSES):
            context["candidate"] = {"path": path}
            require(
                native_classes[path] == classes[path],
                "Pinned legacy base differs from its actual native class",
            )

        objects, matched, meta_cdos, excluded = {}, set(), {}, []
        context = {"iterator": "ObjectIterator(Class)", "stage": "initialize"}
        candidates = iter(api.ObjectIterator(classes[class_path]))
        for index in range(limit):
            context = {
                "iterator": "ObjectIterator(Class)",
                "index": index,
                "stage": "iterate",
            }
            try:
                candidate = next(candidates)
            except StopIteration:
                break
            context["stage"] = "identity"
            path, metaclass = identity(candidate)
            context["stage"] = "unique_path"
            require(path not in objects, "Duplicate native ObjectIterator path")
            objects[path] = candidate
            if path in native_classes:
                context["stage"] = "coverage_identity"
                require(
                    native_classes[path] == candidate,
                    "The iterators disagree on native object identity at the same path",
                )
                matched.add(path)
                continue
            # Query only the actual metaclass of an object absent from the class
            # inventory. Never obtain a represented library's default instance.
            object_identity = context["candidate"]
            meta_path = object_identity["object_class"]
            context["coverage_candidate"] = object_identity
            identity(metaclass)
            context.update(
                {"stage": "metaclass_inheritance", "parent_class": class_path}
            )
            require(
                api.MathLibrary.class_is_child_of(metaclass, classes[class_path])
                is True,
                "Object-only candidate does not have an actual UClass metaclass",
            )
            context["candidate"] = object_identity
            del context["coverage_candidate"]
            context["stage"] = "metaclass_cdo"
            if meta_path in meta_cdos:
                cached_meta, cdo = meta_cdos[meta_path]
                require(
                    cached_meta == metaclass, "Metaclass identity changed at its path"
                )
            else:
                cdo = api.get_default_object(metaclass)
                meta_cdos[meta_path] = (metaclass, cdo)
            require(
                cdo is not None and not isinstance(cdo, type),
                "Actual metaclass CDO is unavailable as a native object",
            )
            context["cdo_path"] = cdo.get_path_name()
            require(
                cdo.get_class() == metaclass,
                "Returned default object belongs to another metaclass",
            )
            require(
                cdo == candidate,
                "ObjectIterator contains a non-CDO class omitted by ClassIterator",
            )
            excluded.append(
                {
                    "candidate_path": path,
                    "metaclass_path": meta_path,
                    "cdo_path": context["cdo_path"],
                }
            )
        else:
            context["stage"] = "completion"
            raise ValueError(
                "ObjectIterator reached its bound without proving completion"
            )
        missing = sorted(set(native_classes) - matched)
        context = {"iterator": "ClassIterator->ObjectIterator", "stage": "coverage"}
        if missing:
            identity(native_classes[missing[0]])
            raise ValueError(
                "ClassIterator contains a native class absent from ObjectIterator"
            )
        if evidence is not None:
            evidence.update(
                {
                    "class_count": len(native_classes),
                    "object_count": len(objects),
                    "class_iteration_complete": True,
                    "object_iteration_complete": True,
                    "native_coverage_verified": True,
                    "meta_cdo_count": len(excluded),
                    "first_meta_cdos": excluded[:4],
                    "meta_cdo_details_truncated": len(excluded) > 4,
                }
            )
        return sorted(names)
    except Exception as error:
        raise NativeCensusError(context, error) from error


def require_abstract_base(source, class_name):
    clean = re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)
    declaration = re.search(
        r"UCLASS\s*\(([^{};]{0,2048}?)\)\s*class\s+(?:\w+_API\s+)?"
        + re.escape(class_name)
        + r"\s*:\s*public\b",
        clean,
    )
    require(declaration is not None, "Pinned legacy base declaration is absent")
    specifiers = re.sub(r'"(?:\\.|[^"\\])*"', '""', declaration[1])
    require(
        re.search(r"(?:^|,)\s*Abstract\s*(?:,|$)", specifiers),
        "Legacy allowlisted base is not declared Abstract",
    )


def material_api_evidence(api, engine):
    relative = "Source/Runtime/Engine/Private/KismetMaterialLibrary.cpp"
    path = safe_path(engine, relative)
    identity = file_identity(path, 2 * 1024 * 1024)
    text = path.read_text(encoding="utf-8-sig")
    clean = re.sub(r"//[^\n]*|/\*.*?\*/", "", text, flags=re.DOTALL)
    match = re.search(
        r"UKismetMaterialLibrary::CreateDynamicMaterialInstance\s*\([^;{}]*\)\s*\{",
        clean,
    )
    require(match is not None, "Native MID allocator definition is absent")
    depth, body = 1, ""
    for character in clean[match.end() : match.end() + 16384]:
        depth += (character == "{") - (character == "}")
        if depth == 0:
            break
        body += character
    require(
        depth == 0
        and "EMIDCreationFlags::Transient" in body
        and "UMaterialInstanceDynamic::Create" in body
        and re.search(r"SetFlags\s*\(\s*RF_Transient\s*\)", body),
        "Installed MID allocator does not honor its explicit transient flag",
    )
    methods = {}
    for owner, names in (
        (
            "MaterialInstanceDynamic",
            (
                "get_scalar_parameter_value",
                "set_scalar_parameter_value",
                "get_vector_parameter_value",
                "set_vector_parameter_value",
            ),
        ),
        ("MaterialLibrary", ("create_dynamic_material_instance",)),
        (
            "AutomationLibrary",
            ("finish_loading_before_screenshot", "take_high_res_screenshot"),
        ),
    ):
        for name in names:
            method = getattr(getattr(api, owner, None), name, None)
            doc = str(getattr(method, "__doc__", "") or "")
            require(
                callable(method) and 0 < len(doc) <= 32768,
                "Required native material/capture API is absent: " + owner + "." + name,
            )
            methods[owner + "." + name] = {
                "signature": doc.splitlines()[0],
                "doc_sha256": hashlib.sha256(doc.encode()).hexdigest(),
            }
    return {
        "allocator_source": {"path": relative, **identity},
        "rf_transient_allocator_verified": True,
        "reflected_methods": methods,
    }


def preflight_error(error):
    if isinstance(error, NativeCensusError):
        # The native cause and actual production candidate are separate fields.
        # Truncating exception text must not erase which original call failed.
        return {
            **preflight_error(error.native_error),
            "census_context": error.context,
        }
    message = str(error)
    result = {
        "type": type(error).__name__[:64],
        "message": message[:768],
        "message_truncated": len(message) > 768,
    }
    # Count JSON escaping as well as UTF-8, including non-BMP exception text.
    while len(canonical(result).encode("utf-8")) > 1024:
        result["message"] = result["message"][: len(result["message"]) // 2]
        result["message_truncated"] = True
    return result


def diagnostic_class_identity(value):
    if isinstance(value, type):
        return {
            "representation": "python_type",
            "name": value.__name__[:128],
            "module": value.__module__[:128],
            "path": value.static_class().get_path_name()[:256],
        }
    return {
        "representation": "native_class_object",
        "python_type": type(value).__name__[:128],
        "path": value.get_path_name()[:256],
        "object_class": value.get_class().get_path_name()[:256],
    }


def compact_legacy_diagnostics(details):
    """Keep the disputed identities and outcomes when examples exceed the cap."""

    text_prefix = bounded_text

    def identity(value):
        return {
            key: text_prefix(value[key], 256 if key == "path" else 128)
            for key in (
                "representation",
                "python_type",
                "path",
                "object_class",
                "name",
                "module",
            )
            if key in value
        }

    def error(value):
        return {
            "type": text_prefix(value.get("type", ""), 64),
            "message": text_prefix(value.get("message", ""), 256),
            "message_truncated": True,
        }

    result = {"details_truncated": True, "diagnostic_only": True, "qualified": False}
    if "error" in details:
        result["error"] = error(details["error"])
    if "class_is_child_of_signature" in details:
        signature = details["class_is_child_of_signature"]
        result["class_is_child_of_signature"] = (
            None if signature is None else text_prefix(signature, 256)
        )
    if "class_is_child_of_signature_error" in details:
        result["class_is_child_of_signature_error"] = error(
            details["class_is_child_of_signature_error"]
        )
    if "metaclass_cdo" in details:
        cdo = details["metaclass_cdo"]
        result["metaclass_cdo"] = (
            {"error": error(cdo["error"])} if "error" in cdo else identity(cdo)
        )
    result["control_pairs"] = []
    for row in details.get("control_pairs", [])[:4]:
        compact = {
            key: row[key] for key in ("name", "status", "stage", "value") if key in row
        }
        if "error" in row:
            compact["error"] = error(row["error"])
        result["control_pairs"].append(compact)
    for name in ("candidate_scan", "class_iterator_comparison"):
        scan = details.get(name, {})
        compact = {
            key: scan[key]
            for key in (
                "candidate_limit",
                "checked_count",
                "true_count",
                "false_count",
                "error_count",
                "duplicate_path_count",
                "truncated",
                "iteration_complete",
                "native_coverage_verified",
            )
            if type(scan.get(key)) in (bool, int)
        }
        if scan.get("status") in ("READ", "ERROR"):
            compact["status"] = scan["status"]
        if "iteration_error" in scan:
            compact["iteration_error"] = error(scan["iteration_error"])
        if name == "class_iterator_comparison":
            memberships = scan.get("base_memberships", {})
            compact["base_memberships"] = {
                path: memberships[path]
                for path in sorted(ABSTRACT_LEGACY_CLASSES)
                if type(memberships.get(path)) is bool
            }
        compact["first_failures"] = []
        for row in scan.get("first_failures", [])[:1]:
            first = {
                key: row[key]
                for key in ("index", "stage", "is_metaclass_cdo")
                if key in row
            }
            if "python_type" in row:
                first["python_type"] = text_prefix(row["python_type"], 128)
            if "identity" in row:
                first["identity"] = identity(row["identity"])
            if "error" in row:
                first["error"] = error(row["error"])
            compact["first_failures"].append(first)
        result[name] = compact
    return result


def class_iterator_diagnostics(api):
    """Compare the public type iterator without treating it as native coverage."""
    scan = {
        "candidate_limit": 32768,
        "checked_count": 0,
        "true_count": 0,
        "false_count": 0,
        "error_count": 0,
        "duplicate_path_count": 0,
        "base_memberships": {path: False for path in sorted(ABSTRACT_LEGACY_CLASSES)},
        "first_yields": [],
        "first_failures": [],
        "truncated": True,
        "iteration_complete": False,
        "native_coverage_verified": False,
    }
    seen = set()
    try:
        base = api.load_class(None, LEGACY_BASE_CLASS)
        require(
            base is not None and base.get_path_name() == LEGACY_BASE_CLASS,
            "Diagnostic legacy base is unavailable or differs",
        )
        candidates = iter(api.ClassIterator(api.Object))
        for index in range(scan["candidate_limit"]):
            try:
                candidate = next(candidates)
            except StopIteration:
                scan.update({"truncated": False, "iteration_complete": True})
                break
            scan["checked_count"] += 1
            row = {
                "index": index,
                "stage": "identity",
                "python_type": type(candidate).__name__[:128],
            }
            try:
                row["identity"] = diagnostic_class_identity(candidate)
                # static_class is used only for a type actually yielded by the
                # iterator. Never substitute a nearest exported Python ancestor.
                native = (
                    candidate.static_class()
                    if isinstance(candidate, type)
                    else candidate
                )
                path = native.get_path_name()
                if path in seen:
                    scan["duplicate_path_count"] += 1
                seen.add(path)
                if path in scan["base_memberships"]:
                    scan["base_memberships"][path] = True
                row["stage"] = "call"
                value = api.MathLibrary.class_is_child_of(candidate, base)
                require(
                    type(value) is bool, "Native class comparison did not return bool"
                )
                scan["true_count" if value else "false_count"] += 1
            except Exception as error:  # noqa: BLE001 - report each native failure; never admit from diagnostics.
                scan["error_count"] += 1
                if len(scan["first_failures"]) < 4:
                    scan["first_failures"].append(
                        {**row, "error": preflight_error(error)}
                    )
            if index < 4:
                scan["first_yields"].append(
                    {
                        "index": index,
                        "python_type": row["python_type"],
                        "identity": row.get("identity"),
                    }
                )
    except Exception as error:  # noqa: BLE001 - incomplete diagnostic iteration is an explicit error.
        scan["iteration_error"] = preflight_error(error)
    scan["status"] = (
        "ERROR" if scan["error_count"] or "iteration_error" in scan else "READ"
    )
    return scan


def legacy_census_diagnostics(api):
    """Bounded readback after refusal; never supplies an admitted census."""
    object_path = "/Script/CoreUObject.Object"
    class_path = "/Script/CoreUObject.Class"
    editor_path = (
        "/Script/ModelContextProtocolEditor.ModelContextProtocolEditorToolLibrary"
    )

    def native(path):
        value = api.load_class(None, path)
        require(
            value is not None and value.get_path_name() == path,
            "Diagnostic native class is unavailable or differs: " + path,
        )
        return value

    result = {"diagnostic_only": True, "qualified": False, "control_pairs": []}
    try:
        doc = str(api.MathLibrary.class_is_child_of.__doc__ or "")
        result["class_is_child_of_signature"] = (
            doc.splitlines()[0][:256] if doc else None
        )
    except Exception as error:  # noqa: BLE001 - signature failure must not hide independent native readbacks.
        result["class_is_child_of_signature_error"] = preflight_error(error)
    for name, arguments in (
        ("python_object_to_object", lambda: (api.Object, api.Object)),
        ("native_object_to_object", lambda: (native(object_path), native(object_path))),
        ("legacy_to_object", lambda: (native(LEGACY_BASE_CLASS), native(object_path))),
        ("editor_to_legacy", lambda: (native(editor_path), native(LEGACY_BASE_CLASS))),
    ):
        row = {"name": name, "stage": "identity"}
        try:
            test, parent = arguments()
            row["test"] = diagnostic_class_identity(test)
            row["parent"] = diagnostic_class_identity(parent)
            row["stage"] = "call"
            value = api.MathLibrary.class_is_child_of(test, parent)
            require(type(value) is bool, "Native class comparison did not return bool")
            row.update({"status": "READ", "value": value})
        except Exception as error:  # noqa: BLE001 - retain each control failure independently.
            row.update({"status": "ERROR", "error": preflight_error(error)})
        result["control_pairs"].append(row)

    scan = {
        "candidate_limit": 256,
        "checked_count": 0,
        "true_count": 0,
        "false_count": 0,
        "error_count": 0,
        "truncated": True,
        "iteration_complete": False,
        "first_failures": [],
    }
    result["candidate_scan"] = scan
    try:
        metaclass, base = native(class_path), native(LEGACY_BASE_CLASS)
        metaclass_cdo = None
        try:
            metaclass_cdo = api.get_default_object(metaclass)
            result["metaclass_cdo"] = diagnostic_class_identity(metaclass_cdo)
        except Exception as error:  # noqa: BLE001 - optional CDO diagnostics cannot authorize or hide a census.
            result["metaclass_cdo"] = {"error": preflight_error(error)}
        candidates = iter(api.ObjectIterator(metaclass))
        for index in range(scan["candidate_limit"]):
            try:
                candidate = next(candidates)
            except StopIteration:
                scan["truncated"] = False
                scan["iteration_complete"] = True
                break
            scan["checked_count"] += 1
            row = {
                "index": index,
                "stage": "identity",
                "python_type": type(candidate).__name__[:128],
            }
            try:
                # Preserve the candidate's identity before the ClassProperty
                # conversion can raise. No candidate is omitted from a census.
                row["identity"] = diagnostic_class_identity(candidate)
                row["is_metaclass_cdo"] = (
                    candidate == metaclass_cdo if metaclass_cdo is not None else None
                )
                row["stage"] = "call"
                value = api.MathLibrary.class_is_child_of(candidate, base)
                require(
                    type(value) is bool, "Native class comparison did not return bool"
                )
                scan["true_count" if value else "false_count"] += 1
            except Exception as error:  # noqa: BLE001 - report each native failure; never admit from diagnostics.
                scan["error_count"] += 1
                if len(scan["first_failures"]) < 4:
                    scan["first_failures"].append(
                        {**row, "error": preflight_error(error)}
                    )
        # Reaching the limit remains truncated even if the next element would
        # end the iterator. This diagnostic never claims a complete census.
    except Exception as error:  # noqa: BLE001 - incomplete diagnostic iteration is an explicit error.
        scan["iteration_error"] = preflight_error(error)
    scan["status"] = (
        "ERROR" if scan["error_count"] or "iteration_error" in scan else "READ"
    )
    result["class_iterator_comparison"] = class_iterator_diagnostics(api)
    return result


def registration_preflight(api, engine, *, census_evidence=None):
    """Run the three existing read-only gates independently before registration."""

    def python_settings():
        settings = api.get_default_object(
            api.load_class(
                None, "/Script/PythonScriptPlugin.PythonScriptPluginSettings"
            )
        )
        require_python_remote_disabled(settings)
        return settings

    values, checks = {}, {}
    for name, inspect in (
        ("legacy_census", lambda: legacy_census(api, evidence=census_evidence)),
        ("python_remote_execution", python_settings),
        ("material_api_evidence", lambda: material_api_evidence(api, engine)),
    ):
        try:
            values[name] = inspect()
            checks[name] = {"status": "PASSED"}
            if name == "python_remote_execution":
                checks[name]["bRemoteExecution"] = False
        except Exception as error:  # noqa: BLE001 - every native exception blocks admission but preserves the other gates.
            checks[name] = {"status": "BLOCKED", "error": preflight_error(error)}
    if all(check["status"] == "PASSED" for check in checks.values()):
        return (
            values["legacy_census"],
            values["python_remote_execution"],
            values["material_api_evidence"],
        )
    observed = {
        "schema_version": 1,
        "status": "BLOCKED",
        "diagnostic_only": True,
        "qualified": False,
        "checks": checks,
    }
    # Diagnostics run only after all three admission checks have reported. An
    # error in this readback cannot hide the original refusals or admit startup.
    if checks["legacy_census"]["status"] == "BLOCKED":
        try:
            observed["legacy_class_diagnostics"] = legacy_census_diagnostics(api)
        except Exception as error:  # noqa: BLE001 - diagnostic failure cannot replace the original hard refusal.
            observed["legacy_class_diagnostics"] = {"error": preflight_error(error)}
    encoded = canonical(observed)
    if len(encoded.encode("utf-8")) > PREFLIGHT_LIMIT:
        # The three bounded per-check results take precedence over extra detail.
        observed["legacy_class_diagnostics"] = compact_legacy_diagnostics(
            observed.get("legacy_class_diagnostics", {})
        )
        encoded = canonical(observed)
    raise ValueError("Official registration preflight BLOCKED; observed=" + encoded)


class MaterialPreview:
    def __init__(self, api, root, preparation, session_id, launcher_sha):
        self.api, self.root, self.preparation = api, root, preparation
        self.editor = api.get_editor_subsystem(api.UnrealEditorSubsystem)
        self.world = self.editor.get_editor_world()
        self.identity = {
            "session_id": session_id,
            "editor_pid": os.getpid(),
            "editor_start_filetime_utc": process_start_filetime(),
            "project_root": str(root),
            "map_package": MAP_PACKAGE,
            "runtime_source_sha": RUNTIME_SHA,
            "launcher_sha": launcher_sha,
            "launcher_root": str(Path(__file__).resolve().parents[2]),
        }
        self.sequence, self.used, self.pending = 0, set(), None
        self.script_revision = launcher_sha
        self.recovery_blocked = False
        self.mid, self.targets, self.tick_handle = None, [], None
        self.in_tick = False
        self.native_guard = lambda: None
        self.assert_context()
        self.saved_digest = self.verify_saved_inputs()
        manifest_path = safe_path(
            root, "ReviewEvidence/road-asphalt-saved-manifest.json"
        )
        require(
            file_identity(manifest_path, 4 * 1024 * 1024)["sha256"] == MANIFEST_SHA256,
            "Retained paint manifest changed",
        )
        manifest = strict_json(manifest_path.read_bytes(), 4 * 1024 * 1024)
        self.resolve_targets(manifest["edge_markings"])
        self.expected_values = self.read_values(self.original)
        require(
            close_values(
                self.expected_values,
                {"paint_roughness": 0.90, "paint_color": [0.64, 0.63, 0.59, 1.0]},
            ),
            "Retained paint defaults differ",
        )
        self.initial_values = dict(self.expected_values)
        self.surface = surface_preview.SurfacePreview(api, self.world, manifest)
        self.shoulder_repair = shoulder_repair.ShoulderRepair(api, self.world, manifest)
        self.original_bindings = self.observe()

    def assert_context(self):
        require(
            self.editor.get_editor_world() == self.world
            and self.world is not None
            and self.world.get_path_name().split(".", 1)[0] == MAP_PACKAGE,
            "Loaded preview world changed",
        )
        require(
            Path(self.api.Paths.project_dir()).resolve() == self.root
            and os.getpid() == self.identity["editor_pid"],
            "Owned preview process/project changed",
        )
        self.native_guard()

    def verify_saved_inputs(self):
        rows = self.preparation["snapshot_files"]
        require(len(rows) == 278, "Retained preview snapshot file count differs")
        observed, source_observed = [], []
        source_root = Path(self.preparation["runtime_source_root"])
        require(
            str(source_root)
            == r"D:\yacs\runner\_work\YetAnotherCyclingSim\YetAnotherCyclingSim\rm-38116299783-1",
            "Retained source root differs",
        )
        launcher_root = Path(__file__).resolve().parents[2]
        for row in rows:
            identity = file_identity(safe_path(self.root, row["path"]))
            require(
                identity == {key: row[key] for key in ("sha256", "size_bytes")},
                "Saved preview input changed: " + row["path"],
            )
            observed.append({"path": row["path"], **identity})
            source = Path(row["source_path"])
            base = source_root if source.is_relative_to(source_root) else launcher_root
            require(
                source.is_relative_to(base),
                "Conserved source lies outside the authenticated source/launcher roots",
            )
            source = safe_path(base, source.relative_to(base).as_posix())
            source_identity = file_identity(source)
            require(
                source_identity == identity,
                "Original checkpoint input changed: " + str(source),
            )
            source_observed.append({"path": str(source), **source_identity})
        self.last_source_digest = digest(source_observed)
        return digest(observed)

    def resolve_targets(self, evidence):
        rows = evidence["actors"]
        require(
            len(rows) == 370
            and evidence["material"]["assets"]
            == {"instance": PAINT_MATERIAL, "master": PAINT_MASTER},
            "Paint target contract differs",
        )
        actors = self.api.get_editor_subsystem(
            self.api.EditorActorSubsystem
        ).get_all_level_actors()
        by_label = {}
        for actor in actors:
            label = actor.get_actor_label()
            if label.startswith("YACS_ROAD_EDGE_MARKING_"):
                require(label not in by_label, "Duplicate native paint label")
                by_label[label] = actor
        require(
            set(by_label) == {row["label"] for row in rows},
            "Native paint network census differs",
        )
        self.original = None
        prefix = self.world.get_path_name()
        for row in rows:
            actor = by_label[row["label"]]
            require(
                isinstance(actor, self.api.DynamicMeshActor),
                "Paint actor class differs",
            )
            component = actor.get_dynamic_mesh_component()
            require(
                isinstance(component, self.api.DynamicMeshComponent)
                and actor.get_editor_property("root_component") == component
                and actor.get_editor_property("hidden") is False
                and actor.get_path_name().replace(prefix, "<scene>.<world>")
                == row["actor"]["path"]
                and component.get_path_name().replace(prefix, "<scene>.<world>")
                == row["component"]
                and component.get_dynamic_mesh()
                .get_path_name()
                .replace(prefix, "<scene>.<world>")
                == row["mesh"]
                and component.get_num_materials() == 1,
                "Paint actor/component/slot identity differs",
            )
            material = component.get_material(0)
            require(
                isinstance(material, self.api.MaterialInstanceConstant)
                and material.get_path_name() == PAINT_MATERIAL
                and material.get_editor_property("parent").get_path_name()
                == PAINT_MASTER
                and (self.original is None or material == self.original),
                "Paint original binding differs",
            )
            self.original = material
            self.targets.append((actor, component, material))

    def read_values(self, material):
        if isinstance(material, self.api.MaterialInstanceDynamic):
            roughness = material.get_scalar_parameter_value("PaintRoughness")
            color = material.get_vector_parameter_value("PaintColor")
        else:
            library = self.api.MaterialEditingLibrary
            roughness = library.get_material_instance_scalar_parameter_value(
                material, "PaintRoughness"
            )
            color = library.get_material_instance_vector_parameter_value(
                material, "PaintColor"
            )
        values = {"paint_roughness": float(roughness), "paint_color": vector(color)}
        require(
            all(
                math.isfinite(value)
                for value in [values["paint_roughness"], *values["paint_color"]]
            ),
            "Native paint getter returned non-finite values",
        )
        return values

    def observe(self):
        self.assert_context()
        rows, bound = [], None
        expected = self.original if self.mid is None else self.mid
        for actor, component, original in self.targets:
            material = component.get_material(0)
            require(
                actor.get_dynamic_mesh_component() == component
                and component.get_num_materials() == 1
                and material == expected
                and original == self.original,
                "Paint binding changed outside this owned preview",
            )
            bound = material
            rows.append(
                {
                    "actor": actor.get_path_name(),
                    "component": component.get_path_name(),
                    "slot": 0,
                    "material": material.get_path_name(),
                    "original_material": original.get_path_name(),
                }
            )
        require(bound is not None, "No actually bound paint material")
        values = self.read_values(bound)
        require(
            close_values(values, self.expected_values),
            "Native paint state changed outside the preview",
        )
        parent = bound.get_editor_property("parent")
        require(
            parent
            == (
                self.original
                if self.mid is not None
                else self.original.get_editor_property("parent")
            ),
            "Paint material parent changed",
        )
        return {
            **values,
            "binding_count": len(rows),
            "binding_sha256": digest(rows),
            "bindings": rows,
            "bound_material": bound.get_path_name(),
            "parent_material": parent.get_path_name(),
            "transient_mid": self.mid is not None,
            **({"surface": self.surface.observe()} if hasattr(self, "surface") else {}),
            **({"shoulder_repair": self.shoulder_repair.observe()} if hasattr(self, "shoulder_repair") else {}),
        }

    def restore(self):
        self.observe()  # Refuse to overwrite any concurrent owner's material change.
        if self.mid is not None:
            try:
                for _, component, original in self.targets:
                    component.set_material(0, original)
                self.mid = None
                self.expected_values = dict(self.initial_values)
            except Exception as error:
                failures = self.recover_owned_bindings()
                if failures:
                    raise ValueError(
                        str(error) + "; bounded restore cleanup: " + "; ".join(failures)
                    ) from error
                raise
        if hasattr(self, "shoulder_repair"):
            self.shoulder_repair.restore()
        if hasattr(self, "surface"):
            self.surface.restore()
        restored = self.observe()
        require(
            restored == self.original_bindings,
            "Original paint bindings/values did not read back",
        )
        return restored

    def recover_owned_bindings(self):
        """Finish a partial owned write without replacing any foreign binding."""
        failures = []
        for _, component, original in self.targets:
            try:
                bound = component.get_material(0)
                if self.mid is not None and bound == self.mid:
                    component.set_material(0, original)
                    require(
                        component.get_material(0) == original,
                        "Own partial binding did not restore",
                    )
                elif bound != original:
                    failures.append(
                        "Concurrent owner binding preserved: "
                        + component.get_path_name()
                    )
            except Exception as rollback_error:
                LOGGER.exception("Owned paint binding cleanup failed")
                failures.append(str(rollback_error))
        if not failures:
            self.mid = None
            self.expected_values = dict(self.initial_values)
            self.observe()
        return failures

    def set_values(self, request):
        try:
            if self.mid is None:
                material = self.api.MaterialLibrary.create_dynamic_material_instance(
                    self.world,
                    self.original,
                    creation_flags=self.api.MIDCreationFlags.TRANSIENT,
                )
                require(
                    isinstance(material, self.api.MaterialInstanceDynamic)
                    and material.get_editor_property("parent") == self.original,
                    "Native transient MID allocation failed",
                )
                self.mid = material
                for _, component, _ in self.targets:
                    component.set_material(0, self.mid)
            self.mid.set_scalar_parameter_value(
                "PaintRoughness", float(request["paint_roughness"])
            )
            self.mid.set_vector_parameter_value(
                "PaintColor", self.api.LinearColor(*request["paint_color"])
            )
            self.expected_values = {
                "paint_roughness": float(request["paint_roughness"]),
                "paint_color": [float(value) for value in request["paint_color"]],
            }
            return self.observe()
        except Exception as error:
            # Our setters are not atomic. Do not make complete-MID observation a
            # precondition for undoing our own partially assigned slots. Never
            # replace a binding that is neither its original nor our exact MID.
            failures = self.recover_owned_bindings()
            if failures:
                raise ValueError(
                    str(error) + "; bounded rollback: " + "; ".join(failures)
                ) from error
            raise

    def camera_state(self):
        location, rotation = self.editor.get_level_viewport_camera_info()
        return {
            "location_cm": [float(getattr(location, name)) for name in ("x", "y", "z")],
            "rotation_deg": [
                float(getattr(rotation, name)) for name in ("pitch", "yaw", "roll")
            ],
        }

    def handle_json(self, raw):
        require(not self.recovery_blocked, "Previous mutation recovery is unproved; session remains blocked")
        request = validate_request(
            raw, self.identity["session_id"], self.sequence, self.used
        )
        require(self.pending is None, "Another owned preview capture is still pending")
        self.assert_context()
        before = self.observe()
        if request["action"] in ("set", "surface"):
            require(
                self.api.AutomationLibrary.get_editor_active_viewport_view_mode()
                == self.api.ViewModeIndex.VMI_LIT,
                "Material preview requires the active viewport to be Lit",
            )
        dirty = dirty_state(self.api)
        saved = self.verify_saved_inputs()
        require(
            saved == self.saved_digest, "Saved preview conservation fingerprint changed"
        )
        output = safe_path(self.root, REQUEST_ROOT + "/" + request["request_id"])
        require(not output.exists(), "Preview request output already exists")
        self.used.add(request["request_id"])
        output.mkdir(parents=True)
        result = {
            "schema_version": 1,
            **self.identity,
            "request_id": request["request_id"],
            "action": request["action"],
            "capture_requested": request["action"] in ("set", "surface") and request.get("capture", True),
            "before": before,
            "script_revision_before": self.script_revision,
            "script_revision_after": self.script_revision,
            "dirty_before": dirty,
            "saved_inputs_before_sha256": saved,
            "source_world_saved": False,
            "source_inputs_before_sha256": self.last_source_digest,
            "performance_pass": False,
            "owner_visual_status": "PENDING_FINAL_M3",
            "receipt_relative_path": str(
                (output / "receipt.json").relative_to(self.root)
            ).replace("\\", "/"),
        }
        previous_camera = None
        # Consume each accepted mutation once, including a failed attempt.
        if request["action"] != "inspect":
            self.sequence += 1
        result["sequence"] = self.sequence
        try:
            if request["action"] == "set":
                result["after"] = self.set_values(request)
            elif request["action"] == "surface":
                self.surface.apply(request["preset"])
                result["after"] = self.observe()
            elif request["action"] == "reload":
                result["script_reload"] = script_reload.apply(self)
                self.script_revision = result["script_reload"]["commit"]
                result["script_revision_after"] = self.script_revision
                result["after"] = self.observe()
                require(result["after"] == before, "Script reload changed world state")
            elif request["action"] == "checkpoint":
                result["checkpoint"] = self.surface.checkpoint(self.root, self.script_revision, self.shoulder_repair)
                result["after"] = self.observe()
                require(result["after"] == before, "Checkpoint changed active world state")
            elif request["action"] == "repair":
                self.shoulder_repair.apply()
                result["after"] = self.observe()
            elif request["action"] == "restore":
                result["after"] = self.restore()
            elif request["action"] == "camera":
                previous_camera = self.editor.get_level_viewport_camera_info()
                result.update(
                    camera_presets.apply(
                        self.api, self.editor, request["preset"], previous_camera
                    )
                )
                result["after"] = self.observe()
                require(
                    result["after"] == before, "Camera move changed material bindings"
                )
            else:
                result["after"] = before
            require(
                dirty_state(self.api) == dirty, "Preview changed dirty package state"
            )
            if result["capture_requested"]:
                result.update(
                    {
                        "status": "ACCEPTED",
                        "capture_pending": True,
                        "captures": [],
                        "camera": self.camera_state(),
                    }
                )
                self.pending = {
                    "result": result,
                    "root": output,
                    "index": 0,
                    "started": time.monotonic(),
                    "task": None,
                }
                self.submit_capture()
                self.tick_handle = self.api.register_slate_post_tick_callback(self.tick)
            else:
                result.update(
                    {
                        "status": "COMPLETED",
                        "capture_pending": False,
                        "captures": [],
                        "saved_inputs_after_sha256": self.verify_saved_inputs(),
                        "source_inputs_after_sha256": self.last_source_digest,
                        "dirty_after": dirty_state(self.api),
                    }
                )
                write_new(output / "receipt.json", result)
            return canonical(result)
        except Exception as error:
            result.update(
                {
                    "status": "BLOCKED",
                    "error": str(error),
                    "sequence": self.sequence,
                    "capture_pending": False,
                }
            )
            if request["action"] == "camera":
                try:
                    result["camera_restore_attempted"] = previous_camera is not None
                    if previous_camera is not None:
                        self.editor.set_level_viewport_camera_info(*previous_camera)
                        require(
                            camera_presets.matches(
                                self.camera_state(),
                                camera_presets.state(*previous_camera),
                            ),
                            "Camera rollback readback differs",
                        )
                        result["camera_restored_after_failure"] = True
                except Exception as rollback_error:
                    LOGGER.exception("Owned viewport camera rollback failed")
                    result["camera_restore_error"] = str(rollback_error)
            self.fail_capture(result, output)
            if result["status"] == "RECOVERED":
                return canonical(result)
            raise

    def submit_capture(self):
        pending = self.pending
        require(pending is not None, "No owned capture is pending")
        self.observe()
        require(
            self.camera_state() == pending["result"]["camera"],
            "Owner viewport moved during preview capture",
        )
        self.api.AutomationLibrary.finish_loading_before_screenshot()
        index = pending["index"]
        path = pending["root"] / (
            f"priming-{index}.png" if index < PRIMING_COUNT else "preview.png"
        )
        require(not path.exists(), "Owned preview PNG already exists")
        pending["path"] = path
        pending["task"] = self.api.AutomationLibrary.take_high_res_screenshot(
            res_x=1280,
            res_y=720,
            filename=str(path),
            mask_enabled=False,
            capture_hdr=False,
            comparison_tolerance=self.api.ComparisonTolerance.LOW,
            comparison_notes="YACS transient paint parameter preview; no final visual acceptance",
            delay=0.0,
            force_game_view=False,
        )
        require(
            pending["task"] is not None and pending["task"].is_valid_task(),
            "Native preview screenshot submission failed",
        )

    def fail_capture(self, result, output):
        if self.tick_handle is not None:
            self.api.unregister_slate_post_tick_callback(self.tick_handle)
            self.tick_handle = None
        self.pending = None
        try:
            result["restored_after_failure"] = self.observe() if result["action"] == "checkpoint" else self.restore()
            result["after"] = self.observe()
            result["saved_inputs_after_sha256"] = self.verify_saved_inputs()
            result["source_inputs_after_sha256"] = self.last_source_digest
            result["dirty_after"] = dirty_state(self.api)
            recovery_target = result["before"] if result["action"] == "checkpoint" else self.original_bindings
            require(result["after"] == recovery_target, "Recovery readback differs from conserved world")
            require(result["saved_inputs_after_sha256"] == result["saved_inputs_before_sha256"]
                    and result["source_inputs_after_sha256"] == result["source_inputs_before_sha256"]
                    and recovery_dirty_conserved(result), "Recovery changed saved/source/dirty state")
            require("camera_restore_error" not in result, "Camera recovery was not proved")
            require(result["action"] != "inspect", "Failed inspection cannot advance mutation history")
            result.update(status="RECOVERED", capture_pending=False, captures=[], recovery_verified=True)
        except Exception as restore_error:
            LOGGER.exception("Owned preview restoration was refused or failed")
            result["restore_error"] = str(restore_error)
            self.recovery_blocked = True
        if not (output / "receipt.json").exists():
            write_new(output / "receipt.json", result)

    def tick(self, _delta):
        pending = self.pending
        if pending is None or self.in_tick:
            return
        self.in_tick = True
        result, output = pending["result"], pending["root"]
        try:
            require(
                time.monotonic() - pending["started"] < CAPTURE_SECONDS,
                "Bounded preview capture deadline exceeded",
            )
            self.assert_context()
            if not pending["task"].is_task_done():
                return
            self.observe()
            require(
                self.camera_state() == result["camera"],
                "Owner viewport moved during preview capture",
            )
            require(
                dirty_state(self.api) == result["dirty_before"],
                "Dirty package state changed during preview",
            )
            path = pending["path"]
            identity = file_identity(path, PNG_LIMIT)
            with path.open("rb") as stream:
                header = stream.read(24)
            require(
                header[:8] == b"\x89PNG\r\n\x1a\n"
                and header[12:16] == b"IHDR"
                and struct.unpack(">II", header[16:24]) == (1280, 720)
                and identity["size_bytes"] > 4096,
                "Native preview did not complete a bounded 1280x720 PNG",
            )
            result["captures"].append(
                {
                    "path": str(path.relative_to(self.root)).replace("\\", "/"),
                    **identity,
                    "priming": pending["index"] < PRIMING_COUNT,
                }
            )
            pending["index"] += 1
            if pending["index"] <= PRIMING_COUNT:
                self.submit_capture()
                return
            result.update(
                {
                    "status": "COMPLETED",
                    "capture_pending": False,
                    "after": self.observe(),
                    "saved_inputs_after_sha256": self.verify_saved_inputs(),
                    "source_inputs_after_sha256": self.last_source_digest,
                    "dirty_after": dirty_state(self.api),
                    "capture_elapsed_seconds": time.monotonic() - pending["started"],
                }
            )
            require(
                result["saved_inputs_after_sha256"] == self.saved_digest,
                "Saved inputs changed during preview capture",
            )
            write_new(output / "receipt.json", result)
            self.api.unregister_slate_post_tick_callback(self.tick_handle)
            self.tick_handle, self.pending = None, None
        except Exception as error:
            LOGGER.exception("Owned preview capture failed")
            result.update(
                {"status": "BLOCKED", "error": str(error), "capture_pending": False}
            )
            self.fail_capture(result, output)
        finally:
            self.in_tick = False


def diagnostic_property(value, limit=64):
    if value is None or type(value) is bool:
        return value
    if isinstance(value, str):
        return value[:limit]
    return {"type": type(value).__name__}


def require_official_settings(settings, registry_settings):
    # These native classes are loaded via UClass paths and can use a generic
    # DeveloperSettings Python wrapper. Use literal UPROPERTY names from their
    # pinned headers without depending on generated snake_case aliases.
    auto_start = settings.get_editor_property("bAutoStartServer")
    tool_search = settings.get_editor_property("bEnableToolSearch")
    url_path = settings.get_editor_property("ServerUrlPath")
    require(
        auto_start is False and tool_search is False and url_path == "/mcp",
        "Official MCP must start explicitly with eager bounded tool inventory; observed="
        + canonical(
            {
                "bAutoStartServer": diagnostic_property(auto_start),
                "bEnableToolSearch": diagnostic_property(tool_search),
                "ServerUrlPath": diagnostic_property(url_path),
            }
        ),
    )
    allowed = list(registry_settings.get_editor_property("AllowedNames"))
    blocked = list(registry_settings.get_editor_property("BlockedNames"))
    require(
        allowed == list(ALLOWED_NAMES) and not blocked,
        "Official registry name filters differ from the preview-only allowlist; observed="
        + canonical(
            {
                name: {
                    "count": len(values),
                    "first_names": [diagnostic_property(v, 256) for v in values[:4]],
                    "first_name_lengths": [
                        len(v) if isinstance(v, str) else None for v in values[:4]
                    ],
                    "first_name_truncated": [
                        isinstance(v, str) and len(v) > 256 for v in values[:4]
                    ],
                    "names_truncated": len(values) > 4,
                }
                for name, values in (
                    ("AllowedNames", allowed),
                    ("BlockedNames", blocked),
                )
            }
        ),
    )


def require_python_remote_disabled(settings):
    # #384's native owner reads this exact FBoolProperty. A private CDO need
    # not have a generated Python alias. Missing or unreadable native access
    # remains a hard failure before StartServer; never infer the value from ini.
    remote_execution = settings.get_editor_property("bRemoteExecution")
    require(
        remote_execution is False,
        "Native Python remote execution must be disabled; observed="
        + canonical({"bRemoteExecution": diagnostic_property(remote_execution)}),
    )


def require_registry_catalog(registry, own_schema, identity):
    # GetAllToolsetJsonSchemas queries the live, filtered registry; the per-class
    # schema above is a testing API and cannot establish the complete inventory.
    # The pinned FToolsetRegistry declaration specifies an array of schemas.
    reflected_tool(own_schema, identity)
    catalog = strict_json(
        registry.get_all_toolset_json_schemas(), 64 * 1024, expected_type=list
    )
    observed = []
    for toolset in catalog[:4]:
        if type(toolset) is not dict:
            observed.append({"type": type(toolset).__name__})
            continue
        tools = toolset.get("tools")
        observed.append(
            {
                "name": diagnostic_property(toolset.get("name")),
                "tool_count": len(tools) if type(tools) is list else None,
                "first_tool_names": [
                    diagnostic_property(
                        tool.get("name") if type(tool) is dict else tool
                    )
                    for tool in (tools[:2] if type(tools) is list else [])
                ],
            }
        )
    require(
        len(catalog) == 1 and catalog[0] == own_schema,
        "Live official registry differs from the single owned preview toolset; observed="
        + canonical({"toolset_count": len(catalog), "first_toolsets": observed}),
    )
    return {"toolset_count": 1, "tool_count": 1, "schema_sha256": digest(catalog)}


def install(api, root, preparation, session_id, launcher_sha):
    """Called once by the owned bootstrap before the official listener is started."""
    global BRIDGE
    require(BRIDGE is None, "The preview bridge is already installed")
    require(
        api.SystemLibrary.get_engine_version() == ENGINE_VERSION,
        "Preview engine version differs",
    )
    engine = Path(
        api.Paths.convert_relative_path_to_full(api.Paths.engine_dir())
    ).resolve()
    for relative, expected in ENGINE_PINS.items():
        require(
            file_identity(safe_path(engine, relative), 2 * 1024 * 1024)["sha256"]
            == expected,
            "Installed official MCP declaration differs: " + relative,
        )
    for module, name in (
        ("ModelContextProtocolEngine", "ModelContextProtocolToolLibrary"),
        ("ModelContextProtocolEditor", "ModelContextProtocolEditorToolLibrary"),
    ):
        path = safe_path(
            engine,
            "Plugins/Experimental/ModelContextProtocol/Source/"
            + module
            + "/Public/"
            + name
            + ".h",
        )
        require_abstract_base(path.read_text(encoding="utf-8-sig"), "U" + name)
    settings = api.get_default_object(
        api.load_class(
            None, "/Script/ModelContextProtocolEngine.ModelContextProtocolSettings"
        )
    )
    registry_settings = api.get_default_object(
        api.load_class(None, "/Script/ToolsetRegistry.ToolsetRegistrySettings")
    )
    require_official_settings(settings, registry_settings)
    census_evidence = {}
    libraries, python_settings, native_material = registration_preflight(
        api, engine, census_evidence=census_evidence
    )
    catalog_before = strict_json(
        api.ToolsetRegistry.get_all_toolset_json_schemas(),
        64 * 1024,
        expected_type=list,
    )
    require(
        catalog_before == [],
        "Official registry must be empty before defining the owned preview class; observed="
        + canonical(
            {
                "toolset_count": len(catalog_before),
                "first_names": [
                    diagnostic_property(row.get("name") if type(row) is dict else row)
                    for row in catalog_before[:4]
                ],
            }
        ),
    )

    def guard():
        require_official_settings(settings, registry_settings)
        require(legacy_census(api) == libraries, "Legacy MCP class census changed")
        require_python_remote_disabled(python_settings)
        require(
            YacsRoadMaterialPreview.static_class() == native_toolset_class
            and read_preview_toolset_identity(api, native_toolset_class)
            == toolset_identity,
            "Owned native preview class identity changed",
        )
        require_registry_catalog(api.ToolsetRegistry, schema, toolset_identity)

    from toolset_registry import tool_call

    manager = MaterialPreview(api, root, preparation, session_id, launcher_sha)
    manager.native_guard = guard

    @api.uclass()
    class YacsRoadMaterialPreview(api.ToolsetDefinition):
        @tool_call
        @staticmethod
        def preview(request_json: str) -> str:
            """Preview or restore bounded paint parameters in the owned retained scene."""
            return manager.handle_json(request_json)

    native_toolset_class = YacsRoadMaterialPreview.static_class()
    toolset_identity = read_preview_toolset_identity(api, native_toolset_class)
    api.ToolsetRegistry.register_toolset_class(YacsRoadMaterialPreview)
    require(
        api.ToolsetRegistry.is_toolset_class_registered(YacsRoadMaterialPreview),
        "Official preview toolset is unavailable after the registration call, including name-filter rejection; observed="
        + canonical(toolset_identity),
    )
    schema = strict_json(
        api.ToolsetRegistry.get_toolset_json_schema(YacsRoadMaterialPreview), 64 * 1024
    )
    tool, parameter = reflected_tool(schema, toolset_identity)
    guard()
    api.SystemLibrary.execute_console_command(
        manager.world, "ModelContextProtocol.RefreshTools"
    )
    catalog = require_registry_catalog(api.ToolsetRegistry, schema, toolset_identity)
    # Fixed repository-owned command, never a remotely supplied command string.
    api.SystemLibrary.execute_console_command(
        manager.world, "ModelContextProtocol.StartServer 18784"
    )
    BRIDGE = manager  # Retain Python objects for the owner's persistent session.
    ready = {
        "schema_version": 1,
        "status": "MATERIAL_BRIDGE_READY",
        **manager.identity,
        "sequence": 0,
        "endpoint": "http://127.0.0.1:18784/mcp",
        "tool_schema": tool,
        "toolset_identity": dict(toolset_identity),
        "registry_catalog": catalog,
        "wire_parameter": parameter,
        "initial_state": manager.original_bindings,
        "source_world_saved": False,
        "saved_inputs_sha256": manager.saved_digest,
        "source_inputs_sha256": manager.last_source_digest,
        "reload_source_sha256": file_identity(Path(script_reload.__file__), 2 * 1024 * 1024)["sha256"],
        "repair_source_sha256": file_identity(Path(shoulder_repair.__file__), 2 * 1024 * 1024)["sha256"],
        "surface_source_sha256": file_identity(Path(surface_preview.__file__), 2 * 1024 * 1024)["sha256"],
        "camera_source_sha256": file_identity(
            Path(camera_presets.__file__), 2 * 1024 * 1024
        )["sha256"],
        "bridge_source_sha256": file_identity(Path(__file__), 2 * 1024 * 1024)[
            "sha256"
        ],
        "legacy_abstract_class_census": libraries,
        "native_class_census": census_evidence,
        "concrete_legacy_library_count": 0,
        "native_material_api": native_material,
        "engine_source_pins": ENGINE_PINS,
        "official_transport_verified": False,
        "performance_pass": False,
        "owner_visual_status": "PENDING_FINAL_M3",
    }
    write_new(safe_path(root, READY_RELATIVE), ready)
    return ready

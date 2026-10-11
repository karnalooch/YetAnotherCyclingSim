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

RUNTIME_SHA = "b9fddea3f6023239da98bec7a5107ed1124cf52e"
MAP_PACKAGE = "/Game/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview"
MAP_SHA256 = "cbbf374309508fdb2c6f86c6324af4a3824a0c5ed32a4bfc29200ad3b29da183"
PAINT_MATERIAL = "/Game/Generated/YACS/RoadAsphaltConsumer/EdgeMarkings/MI_RoadEdgeMarkings.MI_RoadEdgeMarkings"
PAINT_MASTER = "/Game/Generated/YACS/RoadAsphaltConsumer/EdgeMarkings/M_RoadEdgeMarkings.M_RoadEdgeMarkings"
MANIFEST_SHA256 = "974c86813d2ee95d4f3cc244fd3590f7f9711506973c10544f6ede954557344a"
ENGINE_VERSION = "5.8.2-56702186+++UE5+Release-5.8"
PORT = 18784
REQUEST_LIMIT = 4096
PNG_LIMIT = 8 * 1024 * 1024
CAPTURE_SECONDS = 150.0
PRIMING_COUNT = 3
READY_RELATIVE = "Saved/LevelEditorStream/material-bridge-ready.json"
REQUEST_ROOT = "Saved/LevelEditorStream/material-preview"
ALLOWED_NAMES = (
    "/^YacsRoadMaterialPreview$/",
    "/^YacsRoadMaterialPreview[.][Pp]review$/",
)
ABSTRACT_LEGACY_CLASSES = {
    "/Script/ModelContextProtocolEngine.ModelContextProtocolToolLibrary",
    "/Script/ModelContextProtocolEditor.ModelContextProtocolEditorToolLibrary",
}
BRIDGE = None
LOGGER = logging.getLogger(__name__)

# Actual installed UE 5.8.2 source, retained by #384 declaration/control-flow
# runs 37990333833/37993672276 and #364 run38044121552. No Epic source is copied.
ENGINE_PINS = {
    "Plugins/Experimental/ToolsetRegistry/ToolsetRegistry.uplugin": "2dfc01159b54daea67c62966a48b78254d1d848d84e8df48c708c7a69d3f2062",
    "Plugins/Experimental/ModelContextProtocol/ModelContextProtocol.uplugin": "74420534edcd6baafcb48e0af919d53b84891bdade7b97869b0ef485c3ea1518",
    "Plugins/Experimental/ToolsetRegistry/Content/Python/toolset_registry/__init__.py": "df6a65bc5740271dcd989a1df3208b40282323015ec1aa586895fffb1e97abbb",
    "Plugins/Experimental/ToolsetRegistry/Source/ToolsetRegistry/Public/ToolsetRegistry/UToolsetRegistry.h": "03e3abeec87a10ff1b099cdbdfba9d65349409af49e7d2a1688bb78c77f59d6b",
    "Plugins/Experimental/ModelContextProtocol/Source/ModelContextProtocol/Private/ModelContextProtocolModule.cpp": "86ee49f40a61e754040b72b8f618fa464542881ac04b0723fc3f68f5438880ee",
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


def strict_json(raw, limit):
    require(isinstance(raw, (bytes, str)), "JSON must be UTF-8 text")
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")
    require(len(raw.encode("utf-8")) <= limit, "JSON exceeds its bound")
    value = json.loads(
        raw,
        object_pairs_hook=_object_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON")),
    )
    require(type(value) is dict, "JSON must be one object")
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
    require(action in ("set", "restore", "inspect"), "Unknown preview action")
    expected = common | (
        {"paint_roughness", "paint_color"} if action == "set" else set()
    )
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


def vector(value):
    return [float(getattr(value, name)) for name in ("r", "g", "b", "a")]


def close_values(first, second):
    return abs(first["paint_roughness"] - second["paint_roughness"]) <= 1e-6 and all(
        abs(a - b) <= 1e-6
        for a, b in zip(first["paint_color"], second["paint_color"], strict=True)
    )


def reflected_tool(schema):
    require(
        type(schema) is dict
        and type(schema.get("tools")) is list
        and len(schema["tools"]) == 1,
        "The native preview registry must expose exactly one tool",
    )
    tool = schema["tools"][0]
    require(
        tool.get("name")
        in ("YacsRoadMaterialPreview.preview", "YacsRoadMaterialPreview.Preview"),
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


def legacy_census(api):
    # The isolated project admits no concrete legacy library. These two base
    # classes are Abstract in the pinned installed headers; no guessed Python
    # setter or unreflected DeregisterTools call is needed.
    names = sorted(
        api.get_default_object(cls).get_class().get_path_name()
        for cls in api.ClassIterator(api.ModelContextProtocolToolLibrary)
    )
    require(
        len(names) == len(set(names)) and set(names) <= ABSTRACT_LEGACY_CLASSES,
        "A concrete legacy MCP library is loaded; preview-only startup refused",
    )
    return names


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
                "Required native material/capture API is absent",
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
        request = validate_request(
            raw, self.identity["session_id"], self.sequence, self.used
        )
        require(self.pending is None, "Another owned preview capture is still pending")
        self.assert_context()
        before = self.observe()
        if request["action"] == "set":
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
            "before": before,
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
        try:
            if request["action"] == "set":
                result["after"] = self.set_values(request)
            elif request["action"] == "restore":
                result["after"] = self.restore()
            else:
                result["after"] = before
            if request["action"] != "inspect":
                self.sequence += 1
            result["sequence"] = self.sequence
            require(
                dirty_state(self.api) == dirty, "Preview changed dirty package state"
            )
            if request["action"] == "set":
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
            self.fail_capture(result, output)
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
            result["restored_after_failure"] = self.restore()
        except Exception as restore_error:
            LOGGER.exception("Owned preview restoration was refused or failed")
            result["restore_error"] = str(restore_error)
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
    require(
        settings.get_editor_property("auto_start_server") is False
        and settings.get_editor_property("enable_tool_search") is False
        and settings.get_editor_property("server_url_path") == "/mcp",
        "Official MCP must start explicitly with eager bounded tool inventory",
    )
    registry_settings = api.get_default_object(
        api.load_class(None, "/Script/ToolsetRegistry.ToolsetRegistrySettings")
    )
    require(
        list(registry_settings.get_editor_property("allowed_names"))
        == list(ALLOWED_NAMES)
        and not list(registry_settings.get_editor_property("blocked_names")),
        "Official registry name filters differ from the preview-only allowlist",
    )
    libraries = legacy_census(api)
    python_settings = api.get_default_object(
        api.load_class(None, "/Script/PythonScriptPlugin.PythonScriptPluginSettings")
    )
    require(
        python_settings.get_editor_property("remote_execution") is False,
        "Native Python remote execution is enabled",
    )
    native_material = material_api_evidence(api, engine)

    def guard():
        require(
            settings.get_editor_property("auto_start_server") is False
            and settings.get_editor_property("enable_tool_search") is False
            and settings.get_editor_property("server_url_path") == "/mcp",
            "Official MCP startup/search settings changed",
        )
        require(
            list(registry_settings.get_editor_property("allowed_names"))
            == list(ALLOWED_NAMES)
            and not list(registry_settings.get_editor_property("blocked_names")),
            "Official MCP registry filters changed",
        )
        require(legacy_census(api) == libraries, "Legacy MCP class census changed")
        require(
            python_settings.get_editor_property("remote_execution") is False,
            "Native Python remote execution was enabled",
        )

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

    api.ToolsetRegistry.register_toolset_class(YacsRoadMaterialPreview)
    require(
        api.ToolsetRegistry.is_toolset_class_registered(YacsRoadMaterialPreview),
        "Official registry did not register the preview toolset",
    )
    schema = strict_json(
        api.ToolsetRegistry.get_toolset_json_schema(YacsRoadMaterialPreview), 64 * 1024
    )
    tool, parameter = reflected_tool(schema)
    guard()
    api.SystemLibrary.execute_console_command(
        manager.world, "ModelContextProtocol.RefreshTools"
    )
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
        "wire_parameter": parameter,
        "initial_state": manager.original_bindings,
        "source_world_saved": False,
        "saved_inputs_sha256": manager.saved_digest,
        "source_inputs_sha256": manager.last_source_digest,
        "bridge_source_sha256": file_identity(Path(__file__), 2 * 1024 * 1024)[
            "sha256"
        ],
        "legacy_abstract_class_census": libraries,
        "concrete_legacy_library_count": 0,
        "native_material_api": native_material,
        "engine_source_pins": ENGINE_PINS,
        "official_transport_verified": False,
        "performance_pass": False,
        "owner_visual_status": "PENDING_FINAL_M3",
    }
    write_new(safe_path(root, READY_RELATIVE), ready)
    return ready

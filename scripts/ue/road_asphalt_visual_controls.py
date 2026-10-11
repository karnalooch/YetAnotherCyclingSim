"""Eight temporary road controls for the two retained views with distant bands.

The existing host owns IDLE arbitration, a fresh isolated Editor, authenticated
saved-consumer context, camera/mip readiness, asynchronous screenshots and final
whole-world audits. This helper only controls one road material slot and the
view mode. It never loads/saves a map, saves assets or starts a capture loop.

The host must set YACS_ROAD_VISUAL_CONTROLS_OWNED to its authenticated run token.
All viewports of that owned Level Editor are established as Lit and returned to
Lit. Unknown owner viewport states are neither queried nor claimed restored.
The active-viewmode getter does not expose the selected buffer name: exact API
calls and real debug images remain necessary evidence for BaseColor/WorldNormal.

UE 5.8 primary API (installed implementation/configuration are checked below):
https://dev.epicgames.com/documentation/unreal-engine/BlueprintAPI/Automation/SetEditorViewportVisualizeBuffer
https://dev.epicgames.com/documentation/unreal-engine/API/Developer/FunctionalTesting/UAutomationBlueprintFunctionLibr-
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re

from scripts.ci import official_mcp_bob_session as session
from scripts.ue import read_road_material_baseline as baseline
from scripts.ue import road_asphalt_saved_consumer as saved
from scripts.ue import road_material_views as views

ROOT = Path(__file__).resolve().parents[2]
ENGINE_VERSION = saved.shoulder_material.ENGINE_VERSION
OWNED_ENV = "YACS_ROAD_VISUAL_CONTROLS_OWNED"
FRAME_IDS = ("window-0071-forward-00002", "window-0082-forward-00002")
CONTROLS = ("current-lit", "current-basecolor", "current-worldnormal", "uniform-lit")
BUFFERS = {"current-basecolor": "BaseColor", "current-worldnormal": "WorldNormal"}
RESOLUTION = (1280, 720)
SOURCE_LIMIT = 4 * 1024 * 1024
AUTOMATION_CPP = "Source/Developer/FunctionalTesting/Private/AutomationBlueprintFunctionLibrary.cpp"
AUTOMATION_HEADER = "Source/Developer/FunctionalTesting/Public/AutomationBlueprintFunctionLibrary.h"
ALLOCATOR_CPP = "Source/YetAnotherCyclingSimEditor/Private/Diagnostics/YacsComponent230Detail.cpp"
UNIFORM = {"base_color_linear": [0.075, 0.075, 0.075], "roughness": 0.933,
           "specular": 0.20, "metallic": 0.0, "ambient_occlusion": 1.0,
           "emissive": 0.0, "normal_tangent_space": [0.0, 0.0, 1.0]}


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def control_plan(root=None):
    """Select only two already authenticated cameras; do not invent new poses."""
    network = views.current_view_plan(ROOT if root is None else root)
    by_id = {row["frame_id"]: row for row in network["frames"]}
    require(set(FRAME_IDS) <= set(by_id), "Required diagnostic cameras are absent")
    jobs = [{"job_id": frame_id + "--" + control, "control": control,
             "camera": deepcopy(by_id[frame_id])}
            for frame_id in FRAME_IDS for control in CONTROLS]
    return {"schema_version": 1, "network_plan_sha256": digest(network),
            "survey_sha256": network["survey_sha256"], "resolution": list(RESOLUTION),
            "priming_captures_per_condition": 3, "frame_count": 8, "jobs": jobs,
            "owner_visual_pass": False, "performance_pass": False}


def _read_source(root, relative):
    path = session._safe_path(root, relative)
    identity = session._identity(path, SOURCE_LIMIT)
    raw = path.read_bytes()
    require(len(raw) == identity["size_bytes"]
            and hashlib.sha256(raw).hexdigest() == identity["sha256"],
            "Diagnostic API source changed during read: " + relative)
    return raw.decode("utf-8-sig"), identity


def _function_body(source, name):
    """Bound one installed function definition; comments cannot satisfy checks."""
    clean = re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)
    matches = list(re.finditer(r"\b" + re.escape(name) + r"\s*\([^;{}]*\)\s*\{", clean))
    require(len(matches) == 1, "Installed diagnostic function is missing or ambiguous: " + name)
    start = matches[0].end()
    depth = 1
    for end in range(start, min(len(clean), start + 16384)):
        depth += (clean[end] == "{") - (clean[end] == "}")
        if depth == 0:
            return clean[start:end]
    raise ValueError("Installed diagnostic function exceeds its source bound: " + name)


def installed_api_evidence(api):
    """Read installed 5.8.2 sources and reflected methods before any mutation."""
    engine = Path(api.Paths.convert_relative_path_to_full(api.Paths.engine_dir())).resolve()
    source, cpp_id = _read_source(engine, AUTOMATION_CPP)
    header, header_id = _read_source(engine, AUTOMATION_HEADER)
    method = "UAutomationBlueprintFunctionLibrary::SetEditorViewportVisualizeBuffer"
    body = _function_body(source, method)
    forwarding = re.findall(r"\b(\w*[Bb]uffer\w*)\s*\(\s*BufferName\s*\)", body)
    require("VMI_VisualizeBuffer" in body and "GetViewports" in body and forwarding,
            "Installed buffer setter does not expose the expected viewport/argument path")
    require(all(name in header for name in (
        "SetEditorViewportVisualizeBuffer", "SetEditorViewportViewMode", "GetEditorActiveViewportViewMode")),
        "Installed diagnostic AutomationLibrary declarations differ")
    config, config_id = _read_source(engine, "Config/BaseEngine.ini")
    section = re.search(r"(?ms)^\[Engine\.BufferVisualizationMaterials\]\s*\n(.*?)(?=^\[|\Z)", config)
    require(section is not None, "Installed buffer visualization material section is absent")
    configured = {}
    for name in BUFFERS.values():
        entries = re.findall(r"(?m)^\s*" + name + r"\s*=\s*([^\r\n]+)", section[1])
        require(len(entries) == 1 and "/Engine/BufferVisualization/" + name in entries[0],
                "Installed visualization buffer is missing or remapped: " + name)
        configured[name] = {"entry_sha256": hashlib.sha256(entries[0].encode()).hexdigest()}
    allocator, allocator_id = _read_source(ROOT, ALLOCATOR_CPP)
    allocation = _function_body(allocator,
        "UYacsLandscapeMeshDiagnosticLibrary::CreateComponent230DetailMaterial")
    require(all(symbol in allocation for symbol in ("NewObject<UMaterial>", "GetTransientPackage()", "RF_Transient")),
            "Existing diagnostic material allocator is not transient")
    reflected = {}
    for owner, names in (
        ("AutomationLibrary", ("set_editor_viewport_visualize_buffer", "set_editor_viewport_view_mode",
                               "get_editor_active_viewport_view_mode")),
        ("MaterialEditingLibrary", ("create_material_expression", "connect_material_property", "recompile_material")),
        ("YacsLandscapeMeshDiagnosticLibrary", ("create_component230_detail_material",)),
    ):
        for name in names:
            function = getattr(getattr(api, owner, None), name, None)
            doc = str(getattr(function, "__doc__", "") or "")
            require(callable(function) and 0 < len(doc) <= 32768,
                    "Native diagnostic API has no callable signature: " + owner + "." + name)
            reflected[owner + "." + name] = {"signature": doc.splitlines()[0],
                                             "doc_sha256": hashlib.sha256(doc.encode()).hexdigest()}
    require(all(hasattr(api.ViewModeIndex, name) for name in ("VMI_LIT", "VMI_VISUALIZE_BUFFER")),
            "Native diagnostic viewmode enum is unavailable")
    return {"engine_version": ENGINE_VERSION, "installed_sources": {
                AUTOMATION_CPP: cpp_id, AUTOMATION_HEADER: header_id,
                "Config/BaseEngine.ini": config_id},
            "buffer_setter_body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "buffer_argument_forwarding_calls": sorted(set(forwarding)),
            "configured_buffers": configured, "transient_allocator": {ALLOCATOR_CPP: allocator_id},
            "reflected_methods": reflected, "engine_source_redistributed": False,
            "buffer_name_getter_available": False}


def _owned_context(api, context, plan):
    token = context.get("run_token", "")
    require(re.fullmatch(r"[1-9][0-9]{0,19}-[1-9][0-9]{0,5}", token)
            and os.environ.get(OWNED_ENV) == token
            and os.environ.get("YACS_ROAD_SAVED_RUN_TOKEN") == token,
            "Visual controls require the marked owned diagnostic process")
    require(re.fullmatch(r"[0-9a-f]{40}", context.get("exact_sha", ""))
            and context["exact_sha"] == os.environ.get("YACS_ROAD_MATERIAL_EXPECTED_HEAD"),
            "Diagnostic consumer exact SHA differs from the authenticated host context")
    session._assert_isolated_root()
    project = Path(api.Paths.convert_relative_path_to_full(api.Paths.project_dir())).resolve()
    require(project == ROOT.resolve() == session.ROOT.resolve() == saved.ROOT.resolve(),
            "Visual controls belong to another project")
    require(api.SystemLibrary.get_engine_version() == ENGINE_VERSION,
            "Visual controls require the pinned UE 5.8.2 build")
    world = api.get_editor_subsystem(api.UnrealEditorSubsystem).get_editor_world()
    require(world is not None and world.get_path_name().split(".")[0] == saved.MAP
            and context["manifest"]["map_package"] == saved.MAP,
            "Visual controls require the already loaded saved asphalt consumer")
    require(digest(context["view_plan"]) == plan["network_plan_sha256"],
            "Diagnostic cameras differ from the authenticated host camera plan")
    return {"pid": os.getpid(), "run_token": token, "project": str(project),
            "map_package": saved.MAP, "consumer_exact_sha": context["exact_sha"],
            "owned_process_marker_verified": True, "host_idle_arbitration_required": True}


def _verify_files(context):
    # These are the existing byte checks, not a second receipt format. The host
    # additionally owns the complete native scene and source replay audits.
    saved.verify_retained_files(context["retained"], context["manifest"]["assets"])
    session._verify_rows(ROOT, context["rows"])
    session._verify_rows(ROOT, context["source_dependencies"])


def preflight(api, context, plan=None):
    """A read-only check the existing runner can perform before its 68 Lit views."""
    return {"ownership": _owned_context(api, context, control_plan() if plan is None else plan),
            "native_api": installed_api_evidence(api)}


def _uniform_material(api):
    material = api.YacsLandscapeMeshDiagnosticLibrary.create_component230_detail_material()
    require(material is not None and isinstance(material, api.Material)
            and material.get_path_name().startswith("/Engine/Transient."),
            "Uniform control did not allocate a transient material")
    for name, value in {"material_domain": api.MaterialDomain.MD_SURFACE,
                        "shading_model": api.MaterialShadingModel.MSM_DEFAULT_LIT,
                        "blend_mode": api.BlendMode.BLEND_OPAQUE,
                        "tangent_space_normal": True, "two_sided": False}.items():
        material.set_editor_property(name, value)
        require(material.get_editor_property(name) == value, "Uniform material property readback differs: " + name)
    library = api.MaterialEditingLibrary
    for name, value, outputs in (
        ("base_color_linear", UNIFORM["base_color_linear"], ("MP_BASE_COLOR",)),
        ("normal_tangent_space", UNIFORM["normal_tangent_space"], ("MP_NORMAL",)),
        ("roughness", UNIFORM["roughness"], ("MP_ROUGHNESS",)),
        ("specular", UNIFORM["specular"], ("MP_SPECULAR",)),
        ("metallic", UNIFORM["metallic"], ("MP_METALLIC", "MP_EMISSIVE_COLOR")),
        ("ambient_occlusion", UNIFORM["ambient_occlusion"], ("MP_AMBIENT_OCCLUSION",)),
    ):
        vector = isinstance(value, list)
        expression = library.create_material_expression(material,
            api.MaterialExpressionConstant3Vector if vector else api.MaterialExpressionConstant)
        require(expression is not None, "Uniform control expression allocation failed: " + name)
        expression.set_editor_property("constant" if vector else "r",
                                       api.LinearColor(*value, 1.0) if vector else value)
        observed = expression.get_editor_property("constant" if vector else "r")
        channels = [observed.r, observed.g, observed.b] if vector else [observed]
        expected = value if vector else [value]
        require(all(math.isfinite(float(a)) and abs(float(a) - b) <= 1e-6
                    for a, b in zip(channels, expected, strict=True)),
                "Uniform expression value readback differs: " + name)
        for output in outputs:
            require(library.connect_material_property(expression, "", getattr(api.MaterialProperty, output)),
                    "Uniform material connection failed: " + output)
    require(not library.recompile_material(material), "Uniform material compilation reported errors")
    return material


class VisualControls:
    """State-only companion to the existing bounded native screenshot runner.

    Call begin(), apply(job_id) once per plan job, observe() before/after each
    asynchronous capture, and restore() in the host's final cleanup. Internal
    failures also attempt restoration. No completed-image count is inferred
    from setter calls; the host must authenticate all eight real PNGs.
    """

    def __init__(self, api, context):
        self.api = api
        self.context = {name: deepcopy(context[name]) for name in (
            "exact_sha", "run_token", "view_plan", "manifest", "retained", "rows", "source_dependencies")}
        self.plan = control_plan()
        self.component = self.original = self.uniform = None
        self.current = None
        self.started = self.restored = False
        self.report = {"schema_version": 1, "status": "NOT_STARTED", "plan_sha256": digest(self.plan),
                       "calls": [], "applied_jobs": [], "cleanup_errors": [],
                       "uniform_material": deepcopy(UNIFORM), "uniform_node_count": 6,
                       "geometry_vertex_normals_preserved": True,
                       "view_state_contract": "owned_editor_establish_Lit_and_restore_Lit",
                       "buffer_name_getter_available": False, "source_assets_saved": False,
                       "map_saved": False, "capture_count_verified": False,
                       "whole_native_scene_audit_owned_by_host": True,
                       "owner_visual_pass": False, "performance_pass": False}

    def _lit(self):
        self.report["calls"].append({"function": "AutomationLibrary.set_editor_viewport_view_mode",
                                     "argument": "VMI_LIT"})
        self.api.AutomationLibrary.set_editor_viewport_view_mode(self.api.ViewModeIndex.VMI_LIT)
        require(self.api.AutomationLibrary.get_editor_active_viewport_view_mode() == self.api.ViewModeIndex.VMI_LIT,
                "Active viewport did not read back Lit")

    def begin(self):
        require(not self.started and not self.restored, "Diagnostic controls cannot be restarted")
        self.report.update(preflight(self.api, self.context, self.plan))
        _verify_files(self.context)
        actors = list(self.api.get_editor_subsystem(self.api.EditorActorSubsystem).get_all_level_actors())
        self.component = baseline.road_support_actors(actors)[0].get_dynamic_mesh_component()
        require(self.component is not None and self.component.get_num_materials() == 1,
                "Diagnostic road component has an unexpected slot inventory")
        self.original = self.component.get_material(0)
        require(self.original is not None
                and self.original.get_path_name() == self.context["manifest"]["material_instance"],
                "Diagnostic road slot differs from its authenticated saved material")
        self.report["road_component"] = self.component.get_path_name()
        self.report["original_material"] = self.original.get_path_name()
        self.started = True
        try:
            self._lit()
            self.uniform = _uniform_material(self.api)
            self.report["transient_material"] = self.uniform.get_path_name()
            self.report["status"] = "READY"
            return deepcopy(self.report)
        except Exception as exc:
            self._fail(exc)

    def _fail(self, error):
        self.report["status"] = "FAILED"
        self.report["error"] = str(error)
        try:
            self.restore()
        except Exception as cleanup:
            raise RuntimeError(str(error) + "; diagnostic restoration failed: " + str(cleanup)) from error
        raise error

    def apply(self, job_id):
        require(self.started and not self.restored, "Diagnostic controls are not active")
        try:
            index = len(self.report["applied_jobs"])
            require(index < len(self.plan["jobs"]) and self.plan["jobs"][index]["job_id"] == job_id,
                    "Diagnostic jobs must follow the fixed eight-image plan")
            if self.current is not None:
                self._observe()
            job = self.plan["jobs"][index]
            material = self.uniform if job["control"] == "uniform-lit" else self.original
            self.report["calls"].append({"function": "road_component.set_material",
                                         "slot": 0, "material": material.get_path_name()})
            self.component.set_material(0, material)
            self.current = job
            buffer = BUFFERS.get(job["control"])
            if buffer is None:
                self._lit()
            else:
                self.report["calls"].append({"function": "AutomationLibrary.set_editor_viewport_visualize_buffer",
                                             "argument": buffer})
                self.api.AutomationLibrary.set_editor_viewport_visualize_buffer(buffer)
            observed = self._observe()
            self.report["applied_jobs"].append({"job_id": job_id, **observed})
            return deepcopy(observed)
        except Exception as exc:
            self._fail(exc)

    def _observe(self):
        require(self.current is not None, "No diagnostic condition has been applied")
        control = self.current["control"]
        material = self.uniform if control == "uniform-lit" else self.original
        actual = self.component.get_material(0)
        require(self.component.get_num_materials() == 1 and actual is not None
                and actual.get_path_name() == material.get_path_name(),
                "Diagnostic road material readback differs")
        buffer = BUFFERS.get(control)
        mode_name = "VMI_VISUALIZE_BUFFER" if buffer else "VMI_LIT"
        require(self.api.AutomationLibrary.get_editor_active_viewport_view_mode()
                == getattr(self.api.ViewModeIndex, mode_name), "Diagnostic active viewmode readback differs")
        return {"control": control, "active_viewmode_readback": mode_name,
                "road_material_readback": actual.get_path_name(), "requested_buffer": buffer,
                "buffer_name_readback_verified": False}

    def observe(self):
        require(self.started and not self.restored, "Diagnostic controls are not active")
        try:
            return self._observe()
        except Exception as exc:
            self._fail(exc)

    def restore(self):
        if not self.started or self.restored:
            return deepcopy(self.report)
        errors = []
        # Attempt both restorations independently, even after a partial setter
        # failure. Keep a failed session failed and expose every cleanup error.
        try:
            self.report["calls"].append({"function": "road_component.set_material", "phase": "restore",
                                         "slot": 0, "material": self.original.get_path_name()})
            self.component.set_material(0, self.original)
            actual = self.component.get_material(0)
            require(self.component.get_num_materials() == 1 and actual is not None
                    and actual.get_path_name() == self.original.get_path_name(),
                    "Original road material restoration readback differs")
            self.report["original_material_restored"] = True
        except Exception as exc:
            errors.append("road material: " + str(exc))
        try:
            self._lit()
            self.report["owned_viewports_returned_to_lit"] = True
        except Exception as exc:
            errors.append("Lit mode: " + str(exc))
        try:
            _verify_files(self.context)
            self.report["saved_and_staged_package_bytes_unchanged"] = True
        except Exception as exc:
            errors.append("immutable bytes: " + str(exc))
        self.report["cleanup_errors"] = errors
        self.restored = not errors
        if errors:
            self.report["status"] = "FAILED"
            raise RuntimeError("; ".join(errors))
        if self.report["status"] != "FAILED":
            self.report["status"] = "RESTORED"
        return deepcopy(self.report)


if __name__ == "__main__":
    print(json.dumps(control_plan(), sort_keys=True, separators=(",", ":"), allow_nan=False))

"""Eight temporary road controls for the two retained views with distant bands.

The existing host owns IDLE arbitration, a fresh isolated Editor, authenticated
saved-consumer context, camera/mip readiness, asynchronous screenshots and final
whole-world audits. This helper only controls one road material slot and the
view mode. It never loads/saves a map, saves assets or starts a capture loop.
An explicitly owned optional pair appends original/full-mask observations of
the existing white paint. It swaps only its 370 existing material slots.

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
COVERAGE_OWNED_ENV = "YACS_ROAD_PAINT_COVERAGE_OWNED"
COVERAGE_FRAME_ID = "window-0083-forward-00002"
COVERAGE_CONTROLS = ("paint-original-lit", "paint-fullmask-lit")
FULL_MASK_SCALARS = {"EdgeWearMinCm": -0.05, "EdgeWearSpanCm": 0.0, "MaskFeatherCm": 0.05}
PAINT_COUNT = 370
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


def control_plan(root=None, *, paint_coverage=False):
    """Select only two already authenticated cameras; do not invent new poses."""
    require(type(paint_coverage) is bool, "Paint coverage opt-in must be an explicit boolean")
    network = views.current_view_plan(ROOT if root is None else root)
    by_id = {row["frame_id"]: row for row in network["frames"]}
    require(set(FRAME_IDS) <= set(by_id), "Required diagnostic cameras are absent")
    jobs = [{"job_id": frame_id + "--" + control, "control": control,
             "camera": deepcopy(by_id[frame_id])}
            for frame_id in FRAME_IDS for control in CONTROLS]
    legacy = {"schema_version": 1, "network_plan_sha256": digest(network),
            "survey_sha256": network["survey_sha256"], "resolution": list(RESOLUTION),
            "priming_captures_per_condition": 3, "frame_count": 8, "jobs": jobs,
            "owner_visual_pass": False, "performance_pass": False}
    if not paint_coverage:
        return legacy
    require(COVERAGE_FRAME_ID in by_id, "Paint coverage camera is absent from the authenticated plan")
    return {**legacy, "schema_version": 2, "frame_count": 10,
            "jobs": jobs + [{"job_id": COVERAGE_FRAME_ID + "--" + control, "control": control,
                             "camera": deepcopy(by_id[COVERAGE_FRAME_ID])} for control in COVERAGE_CONTROLS],
            "legacy_control_plan_sha256": digest(legacy), "legacy_frame_count": 8,
            "paint_coverage_enabled": True, "paint_coverage_frame_count": 2,
            "paint_binding_count": PAINT_COUNT, "full_mask_scalar_parameters": dict(FULL_MASK_SCALARS)}


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
    # Installed 5.8.2 source read 38105475097 delegates buffer selection to
    # FEditorViewportClient::ChangeBufferVisualizationMode. The viewmode enum
    # is not a literal in this wrapper. Each capture separately reads the
    # actual native mode; requested buffer names remain explicitly unverified.
    require("GetViewports" in body and set(forwarding) == {"ChangeBufferVisualizationMode"},
            "Installed buffer setter does not expose the expected viewport/argument path")
    mode_body = _function_body(source, "UAutomationBlueprintFunctionLibrary::SetEditorViewportViewMode")
    getter_body = _function_body(source, "UAutomationBlueprintFunctionLibrary::GetEditorActiveViewportViewMode")
    require("GetViewports" in mode_body and re.search(r"\bSetViewMode\s*\(\s*Index\s*\)", mode_body)
            and "GetFirstActiveLevelViewport" in getter_body
            and re.search(r"\bGetViewMode\s*\(\s*\)", getter_body),
            "Installed viewmode setter/getter does not expose the native viewport path")
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
            "viewmode_setter_body_sha256": hashlib.sha256(mode_body.encode()).hexdigest(),
            "active_viewmode_getter_body_sha256": hashlib.sha256(getter_body.encode()).hexdigest(),
            "actual_viewmode_readback_required_per_capture": True,
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
    coverage = os.environ.get(COVERAGE_OWNED_ENV)
    require(coverage is None or (coverage == token
            and os.environ.get("YACS_ROAD_CRACK_CONTROLS_OWNED") is None
            and context["manifest"].get("edge_markings_enabled") is True),
            "Paint coverage requires the separately marked owned white-paint diagnostic")
    require(plan == control_plan(paint_coverage=coverage is not None),
            "Diagnostic plan differs from the explicit eight/ten-frame opt-in")
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
    plan = control_plan(paint_coverage=os.environ.get(COVERAGE_OWNED_ENV) is not None) if plan is None else plan
    result = {"ownership": _owned_context(api, context, plan), "native_api": installed_api_evidence(api)}
    if plan.get("paint_coverage_enabled"):
        targets, original = _paint_targets(api, context)
        _paint_scalars(api, original)
        result["native_api"]["paint_mid"] = _paint_mid_api_evidence(api)
        result["paint_binding_count"] = len(targets)
    return result


def _paint_mid_api_evidence(api):
    """Reuse the already exercised native MID implementation, without a new shader."""
    from scripts.ue import road_crack_visual_controls as mid_source

    engine = Path(api.Paths.convert_relative_path_to_full(api.Paths.engine_dir())).resolve()
    text, identity = _read_source(engine, mid_source.KISMET_CPP)
    body = _function_body(text, "UKismetMaterialLibrary::CreateDynamicMaterialInstance")
    require(all(name in body for name in ("UMaterialInstanceDynamic::Create", "CreationFlags", "EMIDCreationFlags::Transient"))
            and re.search(r"\bSetFlags\s*\(\s*RF_Transient\s*\)", body),
            "Paint MID allocator does not honor its explicit transient flag")
    header, name, header_id = mid_source._header(engine, "Materials", "MaterialInstanceDynamic")
    require(all(symbol in header for symbol in ("K2_GetScalarParameterValue", "SetScalarParameterValue")),
            "Installed paint MID getter/setter declarations differ")
    text, getter_id = _read_source(engine, mid_source.MID_CPP)
    getter = _function_body(text, "UMaterialInstanceDynamic::K2_GetScalarParameterValue")
    require("GetScalarParameterValue" in getter and "return" in getter,
            "Installed paint MID getter does not read its effective scalar")
    methods = {}
    for owner, names in (
        ("MaterialLibrary", ("create_dynamic_material_instance",)),
        ("MaterialInstanceDynamic", ("get_scalar_parameter_value", "set_scalar_parameter_value")),
        ("MaterialEditingLibrary", ("get_material_instance_scalar_parameter_value",)),
        ("DynamicMeshComponent", ("set_material", "get_material", "get_num_materials")),
        ("EditorLoadingAndSavingUtils", ("get_dirty_content_packages",)),
    ):
        for method_name in names:
            method = getattr(getattr(api, owner, None), method_name, None)
            doc = str(getattr(method, "__doc__", "") or "")
            require(callable(method) and 0 < len(doc) <= 32768,
                    "Native paint control API has no callable signature: " + owner + "." + method_name)
            methods[owner + "." + method_name] = {
                "signature": doc.splitlines()[0], "doc_sha256": hashlib.sha256(doc.encode()).hexdigest()}
    require(hasattr(api.MIDCreationFlags, "TRANSIENT"), "Native transient MID flag is unavailable")
    return {"installed_sources": {mid_source.KISMET_CPP: identity, name: header_id, mid_source.MID_CPP: getter_id},
            "allocator_body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "scalar_getter_body_sha256": hashlib.sha256(getter.encode()).hexdigest(),
            "reflected_methods": methods, "creation_flags": "MIDCreationFlags.TRANSIENT",
            "rf_transient_set_by_installed_allocator": True, "native_object_flags_readback_verified": False}


def _paint_scalars(api, instance, *, dynamic=False):
    from scripts.ue import road_edge_marking_material as paint

    expected = {**paint.SCALARS, **FULL_MASK_SCALARS} if dynamic else paint.SCALARS
    result = {}
    for name, value in expected.items():
        actual = (instance.get_scalar_parameter_value(name) if dynamic else
                  api.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(
                      instance, name, api.MaterialParameterAssociation.GLOBAL_PARAMETER))
        require(type(actual) in (int, float) and math.isfinite(actual) and abs(actual - value) <= 1e-6,
                "Paint control effective scalar differs: " + name)
        result[name] = float(actual)
    return result


def _paint_targets(api, context):
    from scripts.ue import road_edge_marking_consumer as paint

    receipt = context["manifest"].get("edge_markings")
    saved.edge_marking_inventory(receipt)
    rows = receipt["actors"]
    require(len(rows) == PAINT_COUNT, "Paint control requires the complete 370-slot saved network")
    actors = paint._actors(api)
    by_label = paint._paint_actors(actors, [row["label"] for row in rows])
    result, original = [], None
    for row in rows:
        actor = by_label[row["label"]]
        require(isinstance(actor, api.DynamicMeshActor), "Paint target is not a native DynamicMeshActor")
        component = actor.get_dynamic_mesh_component()
        require(isinstance(component, api.DynamicMeshComponent)
                and actor.get_editor_property("root_component") == component
                and actor.get_editor_property("hidden") is False
                and saved.normalized(paint.existing.actor_snapshot(actor), saved.MAP) == row["actor"]
                and saved.normalized(component.get_path_name(), saved.MAP) == row["component"]
                and saved.normalized(component.get_dynamic_mesh().get_path_name(), saved.MAP) == row["mesh"],
                "Paint control native actor/component/mesh differs from its saved receipt")
        paint._render_flags(api, component)
        material = component.get_material(0)
        require(component.get_num_materials() == 1 and isinstance(material, api.MaterialInstanceConstant)
                and material.get_path_name() == row["material"] == receipt["material"]["assets"]["instance"],
                "Paint control original material binding differs")
        require(original is None or material == original, "Paint network no longer shares its one saved MIC")
        original = material
        result.append({"label": row["label"], "component": component, "actor": actor})
    return result, original


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
        self.paint_coverage = os.environ.get(COVERAGE_OWNED_ENV) is not None
        self.plan = control_plan(paint_coverage=self.paint_coverage)
        self.component = self.original = self.uniform = None
        self.paint_targets = []
        self.paint_binding_templates = {}
        self.paint_original = self.paint_mid = None
        self.paint_assignment_started = False
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
        if self.paint_coverage:
            self.report.update(paint_coverage_enabled=True, paint_binding_count=PAINT_COUNT,
                               full_mask_scalar_parameters=dict(FULL_MASK_SCALARS),
                               saved_paint_parameters_changed=False, paint_geometry_changed=False,
                               paint_full_native_buffers_audit_owned_by_host=True,
                               paint_pixel_aliasing_cause_verified=False)

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
        if self.paint_coverage:
            self.paint_targets, self.paint_original = _paint_targets(self.api, self.context)
            self.report["paint_original_material"] = self.paint_original.get_path_name()
            self.report["paint_original_scalar_parameters"] = _paint_scalars(self.api, self.paint_original)
            self._paint_template("original_mic", self.paint_original)
        self.started = True
        try:
            self._lit()
            self.uniform = _uniform_material(self.api)
            self.report["transient_material"] = self.uniform.get_path_name()
            if self.paint_coverage:
                self._create_full_mask_material()
            self.report["status"] = "READY"
            result = deepcopy(self.report)
            if self.paint_coverage:
                # Full expected bindings occur once in the retained begin.
                # Each capture still reads all 370 actual slots, compares them
                # to these templates, and retains its own digest and scalars.
                result["paint_binding_templates"] = deepcopy(self.paint_binding_templates)
            return result
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
                    "Diagnostic jobs must follow the fixed eight-image plan and any explicitly appended paint pair")
            if self.current is not None:
                self._observe()
            job = self.plan["jobs"][index]
            material = self.uniform if job["control"] == "uniform-lit" else self.original
            self.report["calls"].append({"function": "road_component.set_material",
                                         "slot": 0, "material": material.get_path_name()})
            self.component.set_material(0, material)
            self.current = job
            if job["control"] == "paint-fullmask-lit":
                self._apply_full_mask()
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
        observed = {"control": control, "active_viewmode_readback": mode_name,
                "road_material_readback": actual.get_path_name(), "requested_buffer": buffer,
                "buffer_name_readback_verified": False}
        if control in COVERAGE_CONTROLS:
            observed["paint_coverage"] = self._paint_observation(full_mask=control == "paint-fullmask-lit")
        return observed

    def _paint_template(self, kind, material):
        bindings = [{"label": target["label"], "component": target["component"].get_path_name(),
                     "material_readback": material.get_path_name()} for target in self.paint_targets]
        self.paint_binding_templates[kind] = {"binding_count": len(bindings), "bindings": bindings,
            "bindings_sha256": digest(bindings), "role": "expected_slot_bindings"}

    def _create_full_mask_material(self):
        require(self.paint_coverage and self.paint_mid is None and len(self.paint_targets) == PAINT_COUNT,
                "Paint full-mask probe cannot be allocated twice")
        world = self.api.get_editor_subsystem(self.api.UnrealEditorSubsystem).get_editor_world()
        self.report["calls"].append({"function": "MaterialLibrary.create_dynamic_material_instance",
            "parent": self.paint_original.get_path_name(), "creation_flags": "MIDCreationFlags.TRANSIENT"})
        self.paint_mid = self.api.MaterialLibrary.create_dynamic_material_instance(
            world, self.paint_original, creation_flags=self.api.MIDCreationFlags.TRANSIENT)
        mid = self.paint_mid
        require(isinstance(mid, self.api.MaterialInstanceDynamic)
                and mid.get_editor_property("parent") == self.paint_original
                and mid.get_path_name() != self.paint_original.get_path_name(),
                "Paint probe did not allocate the owned transient MID with its saved parent")
        for name, value in FULL_MASK_SCALARS.items():
            self.report["calls"].append({"function": "MaterialInstanceDynamic.set_scalar_parameter_value",
                "material": mid.get_path_name(), "parameter": name, "value": value})
            mid.set_scalar_parameter_value(name, value)
        _paint_scalars(self.api, mid, dynamic=True)
        _paint_scalars(self.api, self.paint_original)
        self.report["paint_transient_mid"] = {"path": mid.get_path_name(),
            "parent": self.paint_original.get_path_name(), "creation_flags": "TRANSIENT"}
        self._paint_template("transient_mid", mid)

    def _apply_full_mask(self):
        require(self.paint_mid is not None and not self.paint_assignment_started,
                "Paint full-mask probe is missing or has already been applied")
        mid = self.paint_mid
        _paint_scalars(self.api, mid, dynamic=True)
        _paint_scalars(self.api, self.paint_original)
        # Register ownership before the first setter, including partial failures.
        self.paint_assignment_started = True
        for target in self.paint_targets:
            component = target["component"]
            self.report["calls"].append({"function": "paint_component.set_material",
                "component": component.get_path_name(), "slot": 0, "material": mid.get_path_name()})
            component.set_material(0, mid)

    def _paint_observation(self, *, full_mask):
        require(self.paint_coverage and len(self.paint_targets) == PAINT_COUNT,
                "Paint coverage has no complete native target inventory")
        expected = self.paint_mid if full_mask else self.paint_original
        require(expected is not None, "Paint coverage material is missing")
        original_scalars = _paint_scalars(self.api, self.paint_original)
        if full_mask:
            require(expected.get_editor_property("parent") == self.paint_original,
                    "Paint MID no longer inherits the original saved MIC")
        scalars = _paint_scalars(self.api, expected, dynamic=full_mask)
        bindings = []
        for target in self.paint_targets:
            component, actor = target["component"], target["actor"]
            actual = component.get_material(0)
            require(actor.get_dynamic_mesh_component() == component
                    and actor.get_editor_property("hidden") is False
                    and component.get_editor_property("visible") is True
                    and component.get_num_materials() == 1 and actual == expected,
                    "Paint coverage native slot or visibility readback differs: " + target["label"])
            bindings.append({"label": target["label"], "component": component.get_path_name(),
                             "material_readback": actual.get_path_name()})
        dirty = list(self.api.EditorLoadingAndSavingUtils.get_dirty_content_packages())
        require(not dirty, "Paint coverage inherited or changed a dirty content package")
        kind = "transient_mid" if full_mask else "original_mic"
        template = self.paint_binding_templates[kind]
        binding_hash = digest(bindings)
        require(bindings == template["bindings"] and binding_hash == template["bindings_sha256"],
                "Paint coverage native bindings differ from the retained expected template")
        return {"binding_count": len(bindings), "bindings_sha256": binding_hash,
                "binding_template": kind, "bindings_match_template": True, "material_kind": kind,
                "scalar_parameters": scalars, "original_mic_scalar_parameters": original_scalars,
                "dirty_content_count": 0, "geometry_buffers_modified": False}

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
        if self.paint_coverage:
            restored = True
            if self.paint_assignment_started:
                for target in self.paint_targets:
                    component = target["component"]
                    try:
                        self.report["calls"].append({"function": "paint_component.set_material", "phase": "restore",
                            "component": component.get_path_name(), "slot": 0, "material": self.paint_original.get_path_name()})
                        component.set_material(0, self.paint_original)
                        require(component.get_num_materials() == 1 and component.get_material(0) == self.paint_original,
                                "Original paint MIC did not read back")
                    except Exception as exc:
                        restored = False
                        errors.append(target["label"] + " paint material: " + str(exc))
            try:
                observation = self._paint_observation(full_mask=False)
                self.report.update(paint_restored_observation=observation,
                                   paint_original_mic_parameters_unchanged=True,
                                   dirty_content_count=observation["dirty_content_count"])
            except Exception as exc:
                restored = False
                errors.append("paint restoration readback: " + str(exc))
            self.report["paint_bindings_restored"] = restored
            self.report["paint_transient_mid_detached"] = restored
            if restored:
                self.paint_mid = None
            self.report["paint_transient_mid_ref_released"] = self.paint_mid is None
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

"""Sixteen temporary observations of two saved crack canaries; no capture loop.

The existing RoadLitCapture owns cameras, priming, readiness, actual PNGs and
whole-scene conservation. Only these two crack components may change material
slot/visibility. Original MICs are never edited. Two explicitly transient MIDs
inherit them and carry NeutralProbe=1. All content packages must stay clean;
dirty flags are never cleared and no map, asset or source is saved.

UE 5.8 primary APIs, complemented by exact installed source/reflection below:
https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MaterialLibrary
https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MIDCreationFlags
https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MaterialInstanceDynamic.html
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
from scripts.ue import road_asphalt_saved_consumer as saved
from scripts.ue import road_asphalt_visual_controls as viewport
from scripts.ue import road_crack_consumer as consumer
from scripts.ue import road_crack_material as material
from scripts.ue import road_crack_sources as sources
from scripts.ue import road_material_views as views

ROOT = Path(__file__).resolve().parents[2]
ENGINE_VERSION = material.ENGINE_VERSION
FAMILY = "road-crack"
OWNED_ENV = "YACS_ROAD_CRACK_CONTROLS_OWNED"
FRAME_IDS = ("window-0112-forward-00002", "window-0082-forward-00002")
CONTROLS = ("base-basecolor", "neutral-basecolor", "base-roughness", "neutral-roughness",
            "base-worldnormal", "neutral-worldnormal", "cracks-lit", "cracks-worldnormal")
BUFFERS = {name: {"basecolor": "BaseColor", "roughness": "Roughness", "worldnormal": "WorldNormal"}[name.split("-", 1)[1]]
           for name in CONTROLS if name != "cracks-lit"}
RESOLUTION = (1280, 720)
KISMET_CPP = "Source/Runtime/Engine/Private/KismetMaterialLibrary.cpp"
MID_CPP = "Source/Runtime/Engine/Private/Materials/MaterialInstanceDynamic.cpp"


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(value):
    return sources.digest(value)


def control_plan(root=None):
    network = views.current_view_plan(ROOT if root is None else root)
    by_id = {row["frame_id"]: row for row in network["frames"]}
    require(set(FRAME_IDS) <= set(by_id), "Crack diagnostic cameras are absent from the authenticated plan")
    return {"schema_version": 1, "network_plan_sha256": digest(network), "survey_sha256": network["survey_sha256"],
            "resolution": list(RESOLUTION), "priming_captures_per_condition": 3, "frame_count": 16,
            "jobs": [{"job_id": frame_id + "--" + name, "control": name, "camera": deepcopy(by_id[frame_id])}
                     for frame_id in FRAME_IDS for name in CONTROLS],
            "owner_visual_pass": False, "performance_pass": False}


def _header(engine, folder, name):
    candidates = ["Source/Runtime/Engine/" + base + "/" + folder + "/" + name + ".h" for base in ("Public", "Classes")]
    found = [name for name in candidates if session._safe_path(engine, name).is_file()]
    require(len(found) >= 1, "Installed transient crack header is missing: " + name)
    source, identity = viewport._read_source(engine, found[0])
    return source, found[0], identity


def installed_api_evidence(api):
    # Reuse the established, separately versioned viewport implementation
    # check. It also validates BaseColor/WorldNormal and the active-mode getter.
    result = viewport.installed_api_evidence(api)
    engine = Path(api.Paths.convert_relative_path_to_full(api.Paths.engine_dir())).resolve()
    config, config_id = viewport._read_source(engine, "Config/BaseEngine.ini")
    section = re.search(r"(?ms)^\[Engine\.BufferVisualizationMaterials\]\s*\n(.*?)(?=^\[|\Z)", config)
    entries = [] if section is None else re.findall(r"(?m)^\s*Roughness\s*=\s*([^\r\n]+)", section[1])
    require(len(entries) == 1 and "/Engine/BufferVisualization/Roughness" in entries[0],
            "Installed Roughness visualization buffer is missing or remapped")
    kismet, kismet_id = viewport._read_source(engine, KISMET_CPP)
    allocator = viewport._function_body(kismet, "UKismetMaterialLibrary::CreateDynamicMaterialInstance")
    require(all(symbol in allocator for symbol in ("UMaterialInstanceDynamic::Create", "CreationFlags", "EMIDCreationFlags::Transient"))
            and re.search(r"\bSetFlags\s*\(\s*RF_Transient\s*\)", allocator),
            "Installed MID allocator does not honor the explicit transient flag")
    kh, kh_name, kh_id = _header(engine, "Kismet", "KismetMaterialLibrary")
    mh, mh_name, mh_id = _header(engine, "Materials", "MaterialInstanceDynamic")
    require(all(symbol in kh for symbol in ("EMIDCreationFlags", "Transient", "CreateDynamicMaterialInstance"))
            and all(symbol in mh for symbol in ("K2_GetScalarParameterValue", "SetScalarParameterValue")),
            "Installed MID scalar/transient declarations differ")
    mid_cpp, mid_id = viewport._read_source(engine, MID_CPP)
    getter = viewport._function_body(mid_cpp, "UMaterialInstanceDynamic::K2_GetScalarParameterValue")
    require("GetScalarParameterValue" in getter and "return" in getter,
            "Installed MID getter does not read the current scalar value")
    reflected = {}
    for owner, names in (
        ("MaterialLibrary", ("create_dynamic_material_instance",)),
        ("MaterialInstanceDynamic", ("get_scalar_parameter_value", "set_scalar_parameter_value")),
        ("MaterialEditingLibrary", ("get_material_instance_scalar_parameter_value",)),
        ("DynamicMeshComponent", ("set_material", "get_material", "get_num_materials", "set_visibility")),
        ("EditorLoadingAndSavingUtils", ("get_dirty_content_packages",)),
    ):
        for name in names:
            method = getattr(getattr(api, owner, None), name, None)
            doc = str(getattr(method, "__doc__", "") or "")
            require(callable(method) and 0 < len(doc) <= 32768,
                    "Installed crack control API is missing: " + owner + "." + name)
            reflected[owner + "." + name] = {"signature": doc.splitlines()[0], "doc_sha256": hashlib.sha256(doc.encode()).hexdigest()}
    require(hasattr(api.MIDCreationFlags, "TRANSIENT"), "Installed MID transient creation flag is unavailable")
    return {**result, "crack_sources": {KISMET_CPP: kismet_id, kh_name: kh_id, MID_CPP: mid_id, mh_name: mh_id},
            "roughness_buffer": {"config": config_id, "entry_sha256": hashlib.sha256(entries[0].encode()).hexdigest()},
            "mid_allocator_body_sha256": hashlib.sha256(allocator.encode()).hexdigest(),
            "mid_scalar_getter_body_sha256": hashlib.sha256(getter.encode()).hexdigest(),
            "mid_creation_flags_argument": "MIDCreationFlags.TRANSIENT", "rf_transient_set_by_installed_allocator": True,
            "native_object_flags_readback_verified": False, "crack_reflected_methods": reflected,
            "normal_space_verified": False}


def _owned_context(api, context, plan):
    token = context.get("run_token", "")
    require(isinstance(token, str) and re.fullmatch(r"[1-9][0-9]{0,19}-[1-9][0-9]{0,5}", token)
            and os.environ.get(OWNED_ENV) == token and os.environ.get("YACS_ROAD_SAVED_RUN_TOKEN") == token
            and os.environ.get(viewport.OWNED_ENV) is None, "Crack controls require the single marked owned diagnostic process")
    require(re.fullmatch(r"[0-9a-f]{40}", context.get("exact_sha", ""))
            and os.environ.get("YACS_ROAD_MATERIAL_EXPECTED_HEAD") == context["exact_sha"],
            "Crack controls exact SHA differs from the authenticated host")
    session._assert_isolated_root()
    project = Path(api.Paths.convert_relative_path_to_full(api.Paths.project_dir())).resolve()
    require(project == ROOT.resolve() == saved.ROOT.resolve() == session.ROOT.resolve()
            and api.SystemLibrary.get_engine_version() == ENGINE_VERSION, "Crack controls require the pinned isolated UE project")
    world = api.get_editor_subsystem(api.UnrealEditorSubsystem).get_editor_world()
    require(world is not None and world.get_path_name().split(".")[0] == saved.MAP
            and context["manifest"].get("map_package") == saved.MAP
            and context["manifest"].get("crack_canary_enabled") is True,
            "Crack controls need the already loaded saved canary world")
    require(plan == control_plan() and digest(context["view_plan"]) == plan["network_plan_sha256"],
            "Crack controls cameras or sequence differ from the authenticated plan")
    return {"pid": os.getpid(), "run_token": token, "project": str(project), "map_package": saved.MAP,
            "consumer_exact_sha": context["exact_sha"], "owned_process_marker_verified": True,
            "host_idle_arbitration_required": True}


def _zero_dirty_content(api):
    dirty = list(api.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    require(not dirty, "Crack controls changed or inherited dirty content packages; no flag clearing is allowed")
    return 0


def _mic_probe(api, instance):
    value = api.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(
        instance, "NeutralProbe", api.MaterialParameterAssociation.GLOBAL_PARAMETER)
    require(type(value) in (float, int) and math.isfinite(value) and abs(value) <= 1e-6,
            "Saved crack MIC NeutralProbe must remain zero")
    return float(value)


def _targets(api, context):
    receipt = context["manifest"].get("crack_canary", {})
    require(receipt.get("status") == "LOCAL_CRACKS_CREATED_NORMAL_REVIEW_PENDING"
            and receipt.get("normal_space_verified") is False and receipt.get("world_normal_canary_required") is True,
            "Crack controls require the pending two-canary receipt")
    source = receipt.get("imports", {}).get("sources", {})
    require(source.get("pins") == sources.VERIFIED_PINS and source.get("pins_sha256") == digest(sources.VERIFIED_PINS)
            and source.get("selected_motifs") == list(sources.CANARY_MOTIFS), "Crack controls source pins/motifs differ")
    paths = material.asset_paths(source)
    material_receipt = receipt.get("material", {})
    require(material_receipt.get("assets") == paths and material_receipt.get("neutral_probe") == material.PROBE_CONTRACT
            and material_receipt.get("normal_space_verified") is False,
            "Crack controls need the authenticated material/probe contract")
    rows = receipt.get("actors")
    require(isinstance(rows, list) and len(rows) == 2
            and [row.get("motif_id") for row in rows] == list(sources.CANARY_MOTIFS), "Crack controls actor order differs")
    actors = list(api.get_editor_subsystem(api.EditorActorSubsystem).get_all_level_actors())
    by_label = consumer._crack_actors(actors, [row["label"] for row in rows])
    result = {}
    for index, row in enumerate(rows):
        motif = row["motif_id"]
        expected_label = consumer.ACTOR_PREFIX + ("ordinary_0112" if index == 0 else "nudo_0082")
        require(row["label"] == expected_label, "Crack controls contain a foreign event label")
        actor = by_label[row["label"]]
        require(isinstance(actor, api.DynamicMeshActor) and actor.get_editor_property("hidden") is False,
                "Crack control actor class/hidden state differs")
        component = actor.get_dynamic_mesh_component()
        require(isinstance(component, api.DynamicMeshComponent)
                and actor.get_editor_property("root_component") == component
                and saved.normalized(consumer.edge.existing.actor_snapshot(actor), saved.MAP) == row["actor"]
                and saved.normalized(component.get_path_name(), saved.MAP) == row["component"]
                and saved.normalized(component.get_dynamic_mesh().get_path_name(), saved.MAP) == row["mesh"],
                "Crack control native actor/component/mesh identity differs")
        consumer.edge._render_flags(api, component)
        original = component.get_material(0)
        require(component.get_num_materials() == 1 and isinstance(original, api.MaterialInstanceConstant)
                and original.get_path_name() == paths[motif]["instance"] == row["material"],
                "Crack control original material differs")
        contract = material.geometry_contract(source["motifs"][motif], uv_rotation_degrees=0.0 if index == 0 else 90.0)
        require(receipt.get("geometry_contracts", {}).get(motif) == contract
                and material_receipt.get("geometry_contracts", {}).get(motif) == contract,
                "Crack controls require the exact ordinary0/Nudo90 UV frames")
        _mic_probe(api, original)
        result[motif] = {"actor": actor, "component": component, "original": original,
                         "original_visibility": True, "uv_rotation_degrees": contract["uv_rotation_degrees"]}
    return result


def preflight(api, context, plan=None):
    plan = control_plan() if plan is None else plan
    ownership = _owned_context(api, context, plan)
    viewport._verify_files(context)
    _zero_dirty_content(api)
    _targets(api, context)
    return {"ownership": ownership, "native_api": installed_api_evidence(api)}


class VisualControls:
    """A state provider only; the existing runner authenticates the 16 PNGs."""
    def __init__(self, api, context):
        self.api = api
        self.context = {name: deepcopy(context[name]) for name in (
            "exact_sha", "run_token", "view_plan", "manifest", "retained", "rows", "source_dependencies")}
        self.plan = control_plan()
        self.targets, self.transients = {}, {}
        self.current = None
        self.started = self.restored = False
        self.report = {"schema_version": 1, "family": FAMILY, "status": "NOT_STARTED", "plan_sha256": digest(self.plan),
                       "calls": [], "applied_jobs": [], "cleanup_errors": [], "source_assets_saved": False, "map_saved": False,
                       "saved_material_parameters_changed": False, "geometry_buffers_modified": False,
                       "view_state_contract": "owned_editor_establish_Lit_and_restore_Lit", "buffer_name_getter_available": False,
                       "capture_count_verified": False, "whole_native_scene_audit_owned_by_host": True,
                       "world_normal_canary_required": True, "normal_space_verified": False,
                       "owner_visual_pass": False, "performance_pass": False}

    def _lit(self):
        self.report["calls"].append({"function": "AutomationLibrary.set_editor_viewport_view_mode", "argument": "VMI_LIT"})
        self.api.AutomationLibrary.set_editor_viewport_view_mode(self.api.ViewModeIndex.VMI_LIT)
        require(self.api.AutomationLibrary.get_editor_active_viewport_view_mode() == self.api.ViewModeIndex.VMI_LIT,
                "Crack control active viewport did not read back Lit")

    def begin(self):
        require(not self.started and not self.restored, "Crack controls cannot be restarted")
        self.report.update(preflight(self.api, self.context, self.plan))
        self.targets = _targets(self.api, self.context)
        self.report["original_materials"] = {m: target["original"].get_path_name() for m, target in self.targets.items()}
        self.report["original_visibility"] = {m: target["original_visibility"] for m, target in self.targets.items()}
        self.report["transient_mids"] = {}
        self.started = True
        try:
            self._lit()
            world = self.api.get_editor_subsystem(self.api.UnrealEditorSubsystem).get_editor_world()
            for motif, target in self.targets.items():
                self.report["calls"].append({"function": "MaterialLibrary.create_dynamic_material_instance",
                    "motif_id": motif, "parent": target["original"].get_path_name(), "creation_flags": "MIDCreationFlags.TRANSIENT"})
                mid = self.api.MaterialLibrary.create_dynamic_material_instance(world, target["original"],
                    creation_flags=self.api.MIDCreationFlags.TRANSIENT)
                require(mid is not None and isinstance(mid, self.api.MaterialInstanceDynamic)
                        and mid.get_editor_property("parent") == target["original"]
                        and mid.get_path_name() != target["original"].get_path_name(), "Transient crack MID identity/parent differs")
                self.transients[motif] = mid
                require(abs(float(mid.get_scalar_parameter_value("NeutralProbe"))) <= 1e-6,
                        "New crack MID did not inherit the neutral probe default")
                self.report["calls"].append({"function": "MaterialInstanceDynamic.set_scalar_parameter_value",
                                             "material": mid.get_path_name(), "parameter": "NeutralProbe", "value": 1.0})
                mid.set_scalar_parameter_value("NeutralProbe", 1.0)
                require(abs(float(mid.get_scalar_parameter_value("NeutralProbe")) - 1.0) <= 1e-6,
                        "Transient crack MID probe readback differs")
                _mic_probe(self.api, target["original"])
                self.report["transient_mids"][motif] = {"path": mid.get_path_name(), "parent": target["original"].get_path_name(),
                                                        "probe_value": 1.0, "creation_flags": "TRANSIENT"}
                _zero_dirty_content(self.api)
            require(len({mid.get_path_name() for mid in self.transients.values()}) == 2,
                    "Crack canaries did not receive distinct transient MIDs")
            self.report["dirty_content_count"] = _zero_dirty_content(self.api)
            self.report["status"] = "READY"
            return deepcopy(self.report)
        except Exception as error:
            self._fail(error)

    def _fail(self, error):
        self.report["status"], self.report["error"] = "FAILED", str(error)
        try:
            self.restore()
        except Exception as cleanup:
            raise RuntimeError(str(error) + "; crack restoration failed: " + str(cleanup)) from error
        raise error

    def apply(self, job_id):
        require(self.started and not self.restored, "Crack controls are not active")
        try:
            index = len(self.report["applied_jobs"])
            require(index < len(self.plan["jobs"]) and self.plan["jobs"][index]["job_id"] == job_id,
                    "Crack controls must follow the fixed sixteen-image sequence")
            if self.current is not None:
                self._observe()
            job = self.plan["jobs"][index]
            neutral, visible = job["control"].startswith("neutral-"), not job["control"].startswith("base-")
            for motif, target in self.targets.items():
                value = self.transients[motif] if neutral else target["original"]
                self.report["calls"].append({"function": "crack_component.set_material", "component": target["component"].get_path_name(),
                                             "slot": 0, "material": value.get_path_name()})
                target["component"].set_material(0, value)
                self.report["calls"].append({"function": "crack_component.set_visibility", "component": target["component"].get_path_name(),
                                             "visible": visible, "propagate_to_children": False})
                target["component"].set_visibility(visible, False)
            self.current = job
            buffer = BUFFERS.get(job["control"])
            if buffer is None:
                self._lit()
            else:
                self.report["calls"].append({"function": "AutomationLibrary.set_editor_viewport_visualize_buffer", "argument": buffer})
                self.api.AutomationLibrary.set_editor_viewport_visualize_buffer(buffer)
            observed = self._observe()
            self.report["applied_jobs"].append({"job_id": job_id, **observed})
            return deepcopy(observed)
        except Exception as error:
            self._fail(error)

    def _observe(self):
        require(self.current is not None, "No crack condition has been applied")
        control = self.current["control"]
        neutral, visible = control.startswith("neutral-"), not control.startswith("base-")
        rows = []
        for motif, target in self.targets.items():
            component, mid = target["component"], self.transients[motif]
            actual = component.get_material(0)
            expected = mid if neutral else target["original"]
            require(component.get_num_materials() == 1 and actual == expected
                    and component.get_editor_property("visible") is visible
                    and target["actor"].get_editor_property("hidden") is False
                    and mid.get_editor_property("parent") == target["original"],
                    "Crack component visibility, material or MID parent readback differs")
            mid_probe = mid.get_scalar_parameter_value("NeutralProbe")
            require(type(mid_probe) in (int, float) and math.isfinite(mid_probe) and abs(mid_probe - 1.0) <= 1e-6,
                    "Transient crack MID lost its probe parameter")
            original_probe = _mic_probe(self.api, target["original"])
            rows.append({"motif_id": motif, "label": target["actor"].get_actor_label(), "actor": target["actor"].get_path_name(),
                         "component": component.get_path_name(), "material_readback": actual.get_path_name(),
                         "material_kind": "transient_mid" if neutral else "original_mic", "visible_readback": visible,
                         "neutral_probe_readback": float(mid_probe) if neutral else original_probe,
                         "original_mic_probe_readback": original_probe,
                         "transient_mid_parent_readback": mid.get_editor_property("parent").get_path_name(),
                         "uv_rotation_degrees": target["uv_rotation_degrees"]})
        buffer = BUFFERS.get(control)
        mode = "VMI_VISUALIZE_BUFFER" if buffer else "VMI_LIT"
        require(self.api.AutomationLibrary.get_editor_active_viewport_view_mode() == getattr(self.api.ViewModeIndex, mode),
                "Crack control active viewmode readback differs")
        return {"control": control, "active_viewmode_readback": mode, "requested_buffer": buffer,
                "buffer_name_readback_verified": False, "crack_actors": rows,
                "dirty_content_count": _zero_dirty_content(self.api), "normal_space_verified": False}

    def observe(self):
        require(self.started and not self.restored, "Crack controls are not active")
        try:
            return self._observe()
        except Exception as error:
            self._fail(error)

    def restore(self):
        if not self.started or self.restored:
            return deepcopy(self.report)
        errors, material_ok, visibility_ok, probe_ok = [], True, True, True
        for motif, target in self.targets.items():
            component = target["component"]
            try:
                self.report["calls"].append({"function": "crack_component.set_material", "phase": "restore",
                    "component": component.get_path_name(), "slot": 0, "material": target["original"].get_path_name()})
                component.set_material(0, target["original"])
                require(component.get_num_materials() == 1 and component.get_material(0) == target["original"],
                        "original crack MIC was not restored")
            except Exception as error:
                material_ok = False
                errors.append(motif + " material: " + str(error))
            try:
                self.report["calls"].append({"function": "crack_component.set_visibility", "phase": "restore",
                    "component": component.get_path_name(), "visible": target["original_visibility"], "propagate_to_children": False})
                component.set_visibility(target["original_visibility"], False)
                require(component.get_editor_property("visible") is target["original_visibility"], "original crack visibility was not restored")
            except Exception as error:
                visibility_ok = False
                errors.append(motif + " visibility: " + str(error))
            try:
                _mic_probe(self.api, target["original"])
            except Exception as error:
                probe_ok = False
                errors.append(motif + " original MIC: " + str(error))
        self.report.update(original_material_restored=material_ok, original_visibility_restored=visibility_ok,
                           original_mic_probe_values_zero=probe_ok, transient_mids_detached=material_ok)
        if material_ok:
            self.transients.clear()
            self.report["transient_mid_refs_released"] = True
        try:
            self._lit()
            self.report["owned_viewports_returned_to_lit"] = True
        except Exception as error:
            errors.append("Lit mode: " + str(error))
        try:
            self.report["dirty_content_count"] = _zero_dirty_content(self.api)
            viewport._verify_files(self.context)
            self.report["saved_and_staged_package_bytes_unchanged"] = True
        except Exception as error:
            errors.append("immutable bytes/dirty content: " + str(error))
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

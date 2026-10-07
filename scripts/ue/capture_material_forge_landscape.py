"""Owner-facing 4K visual proof of the fixed Material Forge Landscape consumer.

The proof applies the exact fixed-master Material Instance session-only to the
accepted Sa Calobra Landscape, captures four lit views, then restores the
original Landscape material and every component override. The accepted map is
never saved.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import time
import traceback
import uuid
from pathlib import Path

import unreal


ROOT = Path(__file__).resolve().parents[2]
MAP = "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004"
MAP_FILE = ROOT / "Content/Worlds/SaCalobra/L_SaCalobraAccepted_20261004.umap"
PREVIEW = ROOT / "scripts/ue/preview_material_forge_chunked_landscape.py"
OUTPUT = Path(os.environ["YACS_MF_VISUAL_ROOT"])
EXPECTED_SHA = os.environ["YACS_MATERIAL_FORGE_EXECUTION_SHA"]
MIN_FREE_PHYSICAL_GB = 10
MIN_FREE_COMMIT_GB = 16
CAPTURE_RESOLUTION = [3840, 2160]
CAPTURE_DELAY_SECONDS = 4.0
LIB = unreal.MaterialEditingLibrary

_preview = None
_foundation = None
_world = None
_landscape = None
_components = []
_original_global = None
_original_overrides = {}
_before_snapshot = None
_before_map_hash = None
_instance = None
_camera = None
_transient_lights = []
_task = None
_handle = None
_started = 0.0
_index = 0
_views = []
_captures = []
_checkpoints = []
_scheduling = False
_finished = False


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load visual-proof module: " + str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _memory():
    return _preview._memory()


def _assert_memory(stage: str, physical_gb: int = MIN_FREE_PHYSICAL_GB):
    memory = _memory()
    _checkpoints.append({"stage": stage, "memory": memory})
    if (
        memory["_raw"]["free_physical"] < physical_gb * 1024**3
        or memory["_raw"]["free_commit"] < MIN_FREE_COMMIT_GB * 1024**3
    ):
        raise RuntimeError(
            f"Insufficient memory at {stage}: "
            f"{memory['free_physical_gb']} GiB physical / "
            f"{memory['free_commit_gb']} GiB commit"
        )
    return memory


def _landscape_bounds():
    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")
    target = None
    for component in _components:
        origin, extent, _radius = unreal.SystemLibrary.get_component_bounds(component)
        min_x = min(min_x, origin.x - extent.x)
        max_x = max(max_x, origin.x + extent.x)
        min_y = min(min_y, origin.y - extent.y)
        max_y = max(max_y, origin.y + extent.y)
        min_z = min(min_z, origin.z - extent.z)
        max_z = max(max_z, origin.z + extent.z)
        if component.get_name() == "LandscapeComponent_230":
            target = (origin, extent)
    if target is None:
        raise RuntimeError("Canonical material review component 230 is missing")
    return (min_x, max_x, min_y, max_y, min_z, max_z), target


def _build_views():
    bounds, target = _landscape_bounds()
    min_x, max_x, min_y, max_y, min_z, max_z = bounds
    origin, extent = target
    span_x = max_x - min_x
    span_y = max_y - min_y
    center = unreal.Vector(
        (min_x + max_x) * 0.5,
        (min_y + max_y) * 0.5,
        (min_z + max_z) * 0.5,
    )
    surface_z = origin.z + extent.z * 0.35
    target_center = unreal.Vector(origin.x, origin.y, surface_z)
    return [
        {
            "name": "01-sa-calobra-overview",
            "location": unreal.Vector(
                min_x - span_x * 0.18,
                min_y + span_y * 0.22,
                max_z + max(span_x, span_y) * 0.34,
            ),
            "target": center,
            "fov": 58.0,
            "purpose": "whole-area material distribution",
            "kind": "acceptance",
            "viewmode": "lit",
        },
        {
            "name": "02-refined-material-oblique",
            "location": unreal.Vector(
                origin.x - 18000.0,
                origin.y - 15000.0,
                surface_z + 11000.0,
            ),
            "target": target_center,
            "fov": 60.0,
            "purpose": "rock-soil readability and macro repetition",
            "kind": "acceptance",
            "viewmode": "lit",
        },
        {
            "name": "03-refined-material-medium",
            "location": unreal.Vector(
                origin.x - 7200.0,
                origin.y + 4800.0,
                surface_z + 4300.0,
            ),
            "target": target_center,
            "fov": 55.0,
            "purpose": "component-scale projection and blend quality",
            "kind": "acceptance",
            "viewmode": "lit",
        },
        {
            "name": "04-refined-material-close",
            "location": unreal.Vector(
                origin.x - 2300.0,
                origin.y - 1700.0,
                surface_z + 1350.0,
            ),
            "target": unreal.Vector(
                origin.x + 550.0,
                origin.y + 450.0,
                surface_z,
            ),
            "fov": 50.0,
            "purpose": "surface scale, normal response and transition quality",
            "kind": "acceptance",
            "viewmode": "lit",
        },
        {
            "name": "05-cliff-unlit",
            "location": unreal.Vector(
                origin.x - 2300.0,
                origin.y - 1700.0,
                surface_z + 1350.0,
            ),
            "target": unreal.Vector(
                origin.x + 550.0,
                origin.y + 450.0,
                surface_z,
            ),
            "fov": 50.0,
            "purpose": "cliff diagnostic: albedo/projection without lighting response",
            "kind": "diagnostic",
            "viewmode": "unlit",
        },
        {
            "name": "06-cliff-lighting-only",
            "location": unreal.Vector(
                origin.x - 2300.0,
                origin.y - 1700.0,
                surface_z + 1350.0,
            ),
            "target": unreal.Vector(
                origin.x + 550.0,
                origin.y + 450.0,
                surface_z,
            ),
            "fov": 50.0,
            "purpose": "cliff diagnostic: lighting and geometry without BaseColor or normal maps",
            "kind": "diagnostic",
            "viewmode": "lightingonly",
        },
        {
            "name": "07-cliff-detail-lighting",
            "location": unreal.Vector(
                origin.x - 2300.0,
                origin.y - 1700.0,
                surface_z + 1350.0,
            ),
            "target": unreal.Vector(
                origin.x + 550.0,
                origin.y + 450.0,
                surface_z,
            ),
            "fov": 50.0,
            "purpose": "cliff diagnostic: neutral material with original normal maps",
            "kind": "diagnostic",
            "viewmode": "lit_detaillighting",
        },
    ]


def _ensure_lighting():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    directional = list(
        unreal.GameplayStatics.get_all_actors_of_class(_world, unreal.DirectionalLight)
    )
    skylights = list(
        unreal.GameplayStatics.get_all_actors_of_class(_world, unreal.SkyLight)
    )
    if not directional:
        sun = actors.spawn_actor_from_class(
            unreal.DirectionalLight,
            unreal.Vector(0.0, 0.0, 300000.0),
            unreal.Rotator(pitch=-36.0, yaw=-52.0, roll=0.0),
            transient=True,
        )
        sun.get_component_by_class(unreal.DirectionalLightComponent).set_intensity(6.0)
        _transient_lights.append(sun)
        directional.append(sun)
    if not skylights:
        sky = actors.spawn_actor_from_class(
            unreal.SkyLight,
            unreal.Vector(0.0, 0.0, 300000.0),
            unreal.Rotator(),
            transient=True,
        )
        sky.get_component_by_class(unreal.SkyLightComponent).set_intensity(0.8)
        _transient_lights.append(sky)
        skylights.append(sky)
    return {
        "directional_lights": len(directional),
        "skylights": len(skylights),
        "transient_fallback_lights": len(_transient_lights),
    }


def _force_material_textures_resident():
    names = (
        "WeightTex",
        "RockBaseColorTex",
        "RockNormalTex",
        "RockORMTex",
        "RockDetailTex",
        "SoilBaseColorTex",
        "SoilNormalTex",
        "SoilORMTex",
        "SoilDetailTex",
    )
    association = unreal.MaterialParameterAssociation.GLOBAL_PARAMETER
    textures = []
    for name in names:
        texture = LIB.get_material_instance_texture_parameter_value(
            _instance, name, association
        )
        if texture is None:
            raise RuntimeError("Visual proof texture parameter missing: " + name)
        texture.set_force_mip_levels_to_be_resident(180.0, 0)
        textures.append(texture)
    unreal.AutomationLibrary.finish_loading_before_screenshot()
    return [texture.get_path_name() for texture in textures]


def _restore():
    global _camera
    errors = []
    try:
        if _landscape is not None:
            _landscape.set_editor_property("landscape_material", _original_global)
        for component in _components:
            path = component.get_path_name()
            if path in _original_overrides:
                component.set_editor_property(
                    "override_material", _original_overrides[path]
                )
    except Exception as exc:
        errors.append("binding restore: " + str(exc))

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    try:
        if _camera is not None:
            actors.destroy_actor(_camera)
            _camera = None
        for light in list(_transient_lights):
            actors.destroy_actor(light)
        _transient_lights.clear()
    except Exception as exc:
        errors.append("transient actor cleanup: " + str(exc))

    if _world is not None and _landscape is not None and _before_snapshot is not None:
        try:
            after = _foundation["scene_snapshot"](_world, _landscape, MAP_FILE)
            if after != _before_snapshot:
                errors.append("frozen scene snapshot changed after visual-proof rollback")
        except Exception as exc:
            errors.append("snapshot verify: " + str(exc))

    try:
        if _before_map_hash is not None and _foundation["digest"](MAP_FILE) != _before_map_hash:
            errors.append("accepted map bytes changed during visual proof")
    except Exception as exc:
        errors.append("map hash verify: " + str(exc))

    for component in _components:
        try:
            expected = _original_overrides.get(component.get_path_name())
            if component.get_editor_property("override_material") != expected:
                errors.append("component override rollback mismatch: " + component.get_name())
                break
        except Exception as exc:
            errors.append("component rollback readback: " + str(exc))
            break
    if _landscape is not None:
        try:
            if _landscape.get_editor_property("landscape_material") != _original_global:
                errors.append("global Landscape material rollback mismatch")
        except Exception as exc:
            errors.append("global rollback readback: " + str(exc))

    return errors


def _write_receipt(status: str, error: str = ""):
    payload = {
        "schema_version": 1,
        "status": status,
        "exact_sha": EXPECTED_SHA,
        "map": MAP,
        "material": None if _instance is None else _instance.get_path_name(),
        "fixed_master": os.environ.get("YACS_MF_FIXED_MASTER_PATH"),
        "rock": "regional_limestone/refined_b",
        "soil": "mediterranean_soil/refined_b",
        "mask_contract": "4033x4033; B=rock; soil=1-rock",
        "resolution": CAPTURE_RESOLUTION,
        "captures": [
            item for item in _captures if item.get("kind") == "acceptance"
        ],
        "capture_count": len(
            [item for item in _captures if item.get("kind") == "acceptance"]
        ),
        "diagnostics": [
            item for item in _captures if item.get("kind") == "diagnostic"
        ],
        "diagnostic_count": len(
            [item for item in _captures if item.get("kind") == "diagnostic"]
        ),
        "whole_landscape_components": len(_components),
        "map_saved": False,
        "assets_saved": False,
        "geometry_changed": False,
        "world_semantics_changed": False,
        "rollback_complete": status == "MF_LANDSCAPE_VISUAL_PROOF_PASS",
        "human_visual_status": "PENDING_OWNER",
        "performance_acceptance": "PENDING",
        "memory_checkpoints": _checkpoints,
        "error": error or None,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "visual-proof.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return payload


def finish(error: str = ""):
    global _handle, _finished
    if _finished:
        return
    _finished = True
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
    restore_errors = _restore()
    if restore_errors:
        error = (error + "\n" if error else "") + "\n".join(restore_errors)
    status = "MF_LANDSCAPE_VISUAL_PROOF_FAIL" if error else "MF_LANDSCAPE_VISUAL_PROOF_PASS"
    payload = _write_receipt(status, error)
    if error:
        unreal.log_error("YACS_MF_VISUAL " + json.dumps(payload, default=str))
    else:
        unreal.log("YACS_MF_VISUAL " + json.dumps(payload, default=str))
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)


def schedule():
    global _task, _started, _scheduling
    _scheduling = True
    _task = None
    try:
        view = _views[_index]
        _camera.set_actor_location(view["location"], False, False)
        _camera.set_actor_rotation(
            unreal.MathLibrary.find_look_at_rotation(
                view["location"], view["target"]
            ),
            False,
        )
        _camera.get_component_by_class(unreal.CameraComponent).set_editor_property(
            "field_of_view", view["fov"]
        )
        mode = view.get("viewmode", "lit")
        view_modes = {
            "lit": unreal.ViewModeIndex.VMI_LIT,
            "unlit": unreal.ViewModeIndex.VMI_UNLIT,
            "lightingonly": unreal.ViewModeIndex.VMI_LIGHTING_ONLY,
            "lit_detaillighting": unreal.ViewModeIndex.VMI_LIT_DETAIL_LIGHTING,
        }
        if mode not in view_modes:
            raise RuntimeError("Unsupported diagnostic view mode: " + mode)
        unreal.SystemLibrary.execute_console_command(_world, "viewmode " + mode)
        unreal.AutomationLibrary.set_editor_viewport_view_mode(view_modes[mode])
        unreal.AutomationLibrary.finish_loading_before_screenshot()
        path = OUTPUT / (view["name"] + ".png")
        if path.exists():
            raise RuntimeError("Refusing to overwrite visual evidence: " + str(path))
        _task = unreal.AutomationLibrary.take_high_res_screenshot(
            res_x=CAPTURE_RESOLUTION[0],
            res_y=CAPTURE_RESOLUTION[1],
            filename=str(path),
            camera=_camera,
            mask_enabled=False,
            capture_hdr=False,
            comparison_tolerance=unreal.ComparisonTolerance.LOW,
            comparison_notes="YACS Material Forge production Landscape visual proof",
            delay=CAPTURE_DELAY_SECONDS,
            force_game_view=True,
        )
        if not _task or not _task.is_valid_task():
            raise RuntimeError("Invalid visual screenshot task")
        _started = time.monotonic()
    finally:
        _scheduling = False


def tick(_delta):
    global _index
    if _scheduling or _task is None or _finished:
        return
    try:
        if time.monotonic() - _started > 120:
            finish("Screenshot timeout: " + _views[_index]["name"])
            return
        if not _task.is_task_done():
            return
        view = _views[_index]
        path = OUTPUT / (view["name"] + ".png")
        if not path.is_file() or path.stat().st_size < 100000:
            return
        _captures.append(
            {
                "name": view["name"],
                "purpose": view["purpose"],
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "resolution": CAPTURE_RESOLUTION,
                "viewmode": view.get("viewmode", "lit"),
                "kind": view.get("kind", "acceptance"),
                "fov": view["fov"],
            }
        )
        _index += 1
        if _index >= len(_views):
            finish()
        else:
            schedule()
    except Exception:
        finish(traceback.format_exc())


def main():
    global _preview, _foundation, _world, _landscape, _components
    global _original_global, _original_overrides, _before_snapshot, _before_map_hash
    global _instance, _camera, _views, _handle

    if _git_head() != EXPECTED_SHA:
        raise RuntimeError("Visual proof exact SHA differs from checkout")
    if not OUTPUT.is_absolute():
        raise RuntimeError("Visual proof output must be absolute")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if any(OUTPUT.iterdir()):
        raise RuntimeError("Visual proof output directory must start empty")

    _world = unreal.EditorLoadingAndSavingUtils.load_map(MAP)
    if _world is None:
        raise RuntimeError("Cannot load accepted Sa Calobra map for visual proof")
    landscapes = unreal.GameplayStatics.get_all_actors_of_class(
        _world, unreal.Landscape
    )
    if len(landscapes) != 1:
        raise RuntimeError("Expected exactly one accepted Landscape")
    _landscape = landscapes[0]
    _components = _landscape.get_components_by_class(unreal.LandscapeComponent)
    if len(_components) != 1024:
        raise RuntimeError("Unexpected accepted Landscape topology")

    _preview = _load("yacs_mf_visual_preview", PREVIEW)
    _foundation = _load(
        "yacs_mf_visual_foundation",
        ROOT / "scripts/ue/sa_calobra_material_foundation.py",
    ).__dict__

    _assert_memory("visual_start")
    _before_map_hash = _foundation["digest"](MAP_FILE)
    _before_snapshot = _foundation["scene_snapshot"](_world, _landscape, MAP_FILE)
    _original_global = _landscape.get_editor_property("landscape_material")
    _original_overrides = {
        component.get_path_name(): component.get_editor_property("override_material")
        for component in _components
    }

    package = "/Game/Generated/YACS/MFVisualAcceptance/" + uuid.uuid4().hex
    weights = _preview._import_weight(package)
    _checkpoints.append({"stage": "weight_imported", "memory": _memory()})
    _instance, _drain = _preview._create_fixed_master_instance(
        package, weights, _checkpoints
    )
    _assert_memory("fixed_master_instance_ready")

    _landscape.set_editor_property("landscape_material", _instance)
    for component in _components:
        component.set_editor_property("override_material", None)

    compile_drain = json.loads(
        unreal.YacsTextureAuditLibrary.drain_asset_compilation_and_collect_garbage()
    )
    if (
        not compile_drain.get("ok")
        or int(compile_drain.get("remaining_after", -1)) != 0
        or int(compile_drain.get("shader_jobs_after", -1)) != 0
    ):
        raise RuntimeError("Whole-Landscape visual compile drain failed")
    _checkpoints.append(
        {
            "stage": "whole_landscape_applied",
            "memory": _memory(),
            "compile_drain": compile_drain,
        }
    )
    _assert_memory("whole_landscape_ready", physical_gb=6)

    mismatch = [
        component.get_name()
        for component in _components
        if component.get_editor_property("override_material") is not None
        or component.get_material(0) != _instance
    ]
    if mismatch:
        raise RuntimeError(
            "Whole-Landscape material readback mismatch: " + ",".join(mismatch[:8])
        )

    texture_paths = _force_material_textures_resident()
    _checkpoints.append(
        {
            "stage": "capture_textures_resident",
            "memory": _memory(),
            "textures": texture_paths,
        }
    )

    lighting = _ensure_lighting()
    _checkpoints.append({"stage": "lit_view_ready", "lighting": lighting, "memory": _memory()})
    _views = _build_views()

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    _camera = actors.spawn_actor_from_class(
        unreal.CameraActor,
        unreal.Vector(),
        unreal.Rotator(),
        transient=True,
    )
    _camera.set_actor_label("YACS Material Forge visual acceptance")

    for command in (
        "viewmode lit",
        "r.ScreenPercentage 100",
        "r.PostProcessAAQuality 6",
    ):
        unreal.SystemLibrary.execute_console_command(_world, command)

    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    schedule()
    _handle = unreal.register_slate_post_tick_callback(tick)


try:
    main()
except Exception:
    if _world is not None:
        finish(traceback.format_exc())
    raise

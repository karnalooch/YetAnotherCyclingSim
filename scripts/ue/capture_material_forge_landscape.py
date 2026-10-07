"""Owner-facing 4K visual proof of the fixed Material Forge Landscape consumer.

The proof applies the exact fixed-master Material Instance session-only to the
accepted Sa Calobra Landscape, captures four lit views, then restores the
original Landscape material and every component override. The accepted map is
never saved.
"""

from __future__ import annotations

import importlib.util
import json
import math
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
FAST_MIN_FREE_PHYSICAL_GB = 6
FAST_READY_FREE_PHYSICAL_GB = 4
MIN_FREE_COMMIT_GB = 16
FULL_CAPTURE_RESOLUTION = [3840, 2160]
FAST_CAPTURE_RESOLUTION = [1920, 1080]
FAST_VISUAL = os.environ.get("YACS_MF_FAST_VISUAL", "0") == "1"
CAPTURE_RESOLUTION = FAST_CAPTURE_RESOLUTION if FAST_VISUAL else FULL_CAPTURE_RESOLUTION
CAPTURE_DELAY_SECONDS = 1.0 if FAST_VISUAL else 4.0
COLOR_GAIN_MIN = 0.65
COLOR_GAIN_MAX = 1.35
LIB = unreal.MaterialEditingLibrary

_preview = None
_foundation = None
_world = None
_landscape = None
_components = []
_applied_components = []
_original_global = None
_original_overrides = {}
_before_snapshot = None
_before_map_hash = None
_instance = None
_camera = None
_transient_lights = []
_transient_environment = []
_recaptured_existing_skylights = []
_directional_shadow_state = []
_task = None
_handle = None
_started = 0.0
_index = 0
_views = []
_captures = []
_checkpoints = []
_color_gains = {
    "rock": [1.0, 1.0, 1.0, 1.0],
    "soil": [1.0, 1.0, 1.0, 1.0],
}
_scheduling = False
_finished = False
_proof_started = time.monotonic()


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


def _parse_color_gain(env_name: str):
    raw = os.environ.get(env_name, "1,1,1,1").strip()
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 4:
        raise RuntimeError(env_name + " must contain exactly four comma-separated values")
    try:
        values = [float(part) for part in parts]
    except ValueError as exc:
        raise RuntimeError(env_name + " contains a non-numeric value") from exc
    if not all(math.isfinite(value) for value in values):
        raise RuntimeError(env_name + " contains a non-finite value")
    if any(value < COLOR_GAIN_MIN or value > COLOR_GAIN_MAX for value in values[:3]):
        raise RuntimeError(
            f"{env_name} RGB values must stay within "
            f"{COLOR_GAIN_MIN:.2f}..{COLOR_GAIN_MAX:.2f}"
        )
    if abs(values[3] - 1.0) > 0.0001:
        raise RuntimeError(env_name + " alpha must remain exactly 1.0")
    return unreal.LinearColor(*values), values


def _requested_color_gains():
    parsed = {
        "RockColorGain": _parse_color_gain("YACS_MF_ROCK_COLOR_GAIN"),
        "SoilColorGain": _parse_color_gain("YACS_MF_SOIL_COLOR_GAIN"),
    }
    values = {name: value for name, (value, _normalized) in parsed.items()}
    def binding_mode(normalized):
        return (
            "inherited_master_default"
            if all(abs(float(value) - 1.0) <= 0.0001 for value in normalized)
            else "explicit_instance_override"
        )

    receipt = {
        "rock": parsed["RockColorGain"][1],
        "soil": parsed["SoilColorGain"][1],
        "binding": {
            "rock": binding_mode(parsed["RockColorGain"][1]),
            "soil": binding_mode(parsed["SoilColorGain"][1]),
        },
        "rgb_bounds": [COLOR_GAIN_MIN, COLOR_GAIN_MAX],
        "alpha": 1.0,
    }
    return values, receipt


def _verify_color_gain_readback(instance, expected_values):
    visible = {str(name) for name in LIB.get_vector_parameter_names(instance)}
    missing = sorted(set(expected_values) - visible)
    if missing:
        raise RuntimeError(
            "Fixed-master color gain parameter contract missing: " + ",".join(missing)
        )

    association = unreal.MaterialParameterAssociation.GLOBAL_PARAMETER
    for name, expected in expected_values.items():
        actual = LIB.get_material_instance_vector_parameter_value(
            instance,
            name,
            association,
        )
        channels = ("r", "g", "b", "a")
        if any(
            abs(float(getattr(actual, channel)) - float(getattr(expected, channel)))
            > 0.001
            for channel in channels
        ):
            raise RuntimeError("Fixed-master color gain readback failed: " + name)


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


def _canonical_component_bounds():
    target = next(
        (
            component
            for component in _components
            if component.get_name() == "LandscapeComponent_230"
        ),
        None,
    )
    if target is None:
        raise RuntimeError("Canonical material review component 230 is missing")
    origin, extent, radius = unreal.SystemLibrary.get_component_bounds(target)
    values = [
        float(origin.x),
        float(origin.y),
        float(origin.z),
        float(extent.x),
        float(extent.y),
        float(extent.z),
        float(radius),
    ]
    if not all(math.isfinite(value) for value in values):
        raise RuntimeError("Canonical component 230 bounds contain non-finite values")
    if extent.x <= 0.0 or extent.y <= 0.0 or extent.z < 0.0 or radius <= 0.0:
        raise RuntimeError("Canonical component 230 bounds are invalid")
    return {
        "name": target.get_name(),
        "origin_cm": [float(origin.x), float(origin.y), float(origin.z)],
        "extent_cm": [float(extent.x), float(extent.y), float(extent.z)],
        "radius_cm": float(radius),
        "min_cm": [
            float(origin.x - extent.x),
            float(origin.y - extent.y),
            float(origin.z - extent.z),
        ],
        "max_cm": [
            float(origin.x + extent.x),
            float(origin.y + extent.y),
            float(origin.z + extent.z),
        ],
        "world_grid_mapping": {
            "cell_size_cm": 50.0,
            "axis": "X east;Y south",
            "first_sample_center_cm": [0.0, 0.0],
        },
    }


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
    views = [
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
    if FAST_VISUAL:
        fast_views = []
        for source, name, purpose, dynamic_shadows in (
            (
                views[3],
                "fast-cliff-lit",
                "non-production fast cliff lighting/material iteration",
                True,
            ),
            (
                views[4],
                "fast-cliff-unlit",
                "fast cliff diagnostic: albedo/projection without lighting response",
                True,
            ),
            (
                views[5],
                "fast-cliff-lighting-only",
                "fast cliff diagnostic: geometry/self-shadowing without BaseColor or normal maps",
                True,
            ),
            (
                views[5],
                "fast-cliff-lighting-no-dynamic-shadows",
                "fast cliff diagnostic: Lighting Only with dynamic shadows disabled",
                False,
            ),
            (
                views[6],
                "fast-cliff-detail-lighting",
                "fast cliff diagnostic: geometry/self-shadowing with material normal response",
                True,
            ),
        ):
            fast = dict(source)
            fast["name"] = name
            fast["purpose"] = purpose
            fast["dynamic_shadows"] = dynamic_shadows
            fast_views.append(fast)

        slope_bias_probe = dict(views[5])
        slope_bias_probe["name"] = "fast-cliff-lighting-slope-bias-1"
        slope_bias_probe["purpose"] = (
            "fast cliff diagnostic: Lighting Only with dynamic shadows on and "
            "ShadowSlopeBias forced to 1.0"
        )
        slope_bias_probe["dynamic_shadows"] = True
        slope_bias_probe["shadow_slope_bias"] = 1.0
        fast_views.insert(3, slope_bias_probe)
        return fast_views
    return views


def _ensure_lighting():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    directional = list(
        unreal.GameplayStatics.get_all_actors_of_class(_world, unreal.DirectionalLight)
    )
    skylights = list(
        unreal.GameplayStatics.get_all_actors_of_class(_world, unreal.SkyLight)
    )
    atmospheres = list(
        unreal.GameplayStatics.get_all_actors_of_class(_world, unreal.SkyAtmosphere)
    )

    spawned_atmosphere = False
    if not atmospheres:
        atmosphere = actors.spawn_actor_from_class(
            unreal.SkyAtmosphere,
            unreal.Vector(),
            unreal.Rotator(),
            transient=True,
        )
        if atmosphere is None:
            raise RuntimeError("Transient SkyAtmosphere fallback creation failed")
        _transient_environment.append(atmosphere)
        atmospheres.append(atmosphere)
        spawned_atmosphere = True

    if not directional:
        sun = actors.spawn_actor_from_class(
            unreal.DirectionalLight,
            unreal.Vector(0.0, 0.0, 300000.0),
            unreal.Rotator(pitch=-36.0, yaw=-52.0, roll=0.0),
            transient=True,
        )
        if sun is None:
            raise RuntimeError("Transient DirectionalLight fallback creation failed")
        sun_component = sun.get_component_by_class(unreal.DirectionalLightComponent)
        sun_component.set_intensity(6.0)
        sun_component.set_atmosphere_sun_light(True)
        _transient_lights.append(sun)
        directional.append(sun)

    spawned_skylight = False
    if not skylights:
        sky = actors.spawn_actor_from_class(
            unreal.SkyLight,
            unreal.Vector(0.0, 0.0, 300000.0),
            unreal.Rotator(),
            transient=True,
        )
        if sky is None:
            raise RuntimeError("Transient SkyLight fallback creation failed")
        sky_component = sky.get_component_by_class(unreal.SkyLightComponent)
        sky_component.set_intensity(1.15)
        sky_component.set_editor_property("lower_hemisphere_is_black", False)
        _transient_lights.append(sky)
        skylights.append(sky)
        spawned_skylight = True

    recaptured = []
    for sky in skylights:
        sky_component = sky.get_component_by_class(unreal.SkyLightComponent)
        if sky_component is None:
            raise RuntimeError("SkyLight actor has no SkyLightComponent")
        sky_component.recapture_sky()
        recaptured.append(sky.get_path_name())
        if sky not in _transient_lights:
            _recaptured_existing_skylights.append(sky_component)

    _directional_shadow_state.clear()
    for light in directional:
        component = light.get_component_by_class(unreal.DirectionalLightComponent)
        if component is None:
            raise RuntimeError("DirectionalLight actor has no DirectionalLightComponent")
        _directional_shadow_state.append(
            {
                "actor": light.get_path_name(),
                "component": component,
                "shadow_bias": float(component.get_editor_property("shadow_bias")),
                "shadow_slope_bias": float(
                    component.get_editor_property("shadow_slope_bias")
                ),
            }
        )
    if not _directional_shadow_state:
        raise RuntimeError("No Directional Light shadow state available")

    unreal.AutomationLibrary.finish_loading_before_screenshot()
    return {
        "directional_lights": len(directional),
        "directional_shadow_bias_baseline": [
            {
                "actor": state["actor"],
                "shadow_bias": state["shadow_bias"],
                "shadow_slope_bias": state["shadow_slope_bias"],
            }
            for state in _directional_shadow_state
        ],
        "skylights": len(skylights),
        "sky_atmospheres": len(atmospheres),
        "spawned_sky_atmosphere": spawned_atmosphere,
        "spawned_skylight": spawned_skylight,
        "fallback_skylight_intensity": 1.15 if spawned_skylight else None,
        "fallback_lower_hemisphere_is_black": False if spawned_skylight else None,
        "skylight_recaptured": True,
        "skylight_recapture_targets": recaptured,
        "transient_fallback_lights": len(_transient_lights),
        "transient_environment_actors": len(_transient_environment),
    }


def _directional_shadow_bias_readback():
    result = []
    for state in _directional_shadow_state:
        component = state["component"]
        result.append(
            {
                "actor": state["actor"],
                "shadow_bias": float(component.get_editor_property("shadow_bias")),
                "shadow_slope_bias": float(
                    component.get_editor_property("shadow_slope_bias")
                ),
            }
        )
    return result


def _restore_directional_shadow_bias():
    for state in _directional_shadow_state:
        component = state["component"]
        component.set_shadow_bias(float(state["shadow_bias"]))
        component.set_shadow_slope_bias(float(state["shadow_slope_bias"]))
    readback = _directional_shadow_bias_readback()
    for expected, actual in zip(_directional_shadow_state, readback):
        if (
            abs(float(actual["shadow_bias"]) - float(expected["shadow_bias"])) > 0.001
            or abs(
                float(actual["shadow_slope_bias"])
                - float(expected["shadow_slope_bias"])
            )
            > 0.001
        ):
            raise RuntimeError(
                "Directional Light shadow bias rollback readback mismatch: "
                + str(expected["actor"])
            )
    return readback


def _apply_directional_shadow_slope_bias(value: float):
    if value < 0.0 or value > 1.0:
        raise RuntimeError("ShadowSlopeBias probe must stay within 0.0..1.0")
    for state in _directional_shadow_state:
        state["component"].set_shadow_slope_bias(value)
    readback = _directional_shadow_bias_readback()
    if any(abs(float(item["shadow_slope_bias"]) - value) > 0.001 for item in readback):
        raise RuntimeError("Directional Light ShadowSlopeBias probe readback mismatch")
    return readback


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
        if _world is not None:
            unreal.SystemLibrary.execute_console_command(
                _world, "showflag.DynamicShadows 1"
            )
    except Exception as exc:
        errors.append("dynamic-shadow show flag restore: " + str(exc))

    try:
        if _directional_shadow_state:
            _restore_directional_shadow_bias()
    except Exception as exc:
        errors.append("directional shadow bias restore: " + str(exc))

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
        for actor in list(_transient_environment):
            actors.destroy_actor(actor)
        _transient_environment.clear()
        for sky_component in list(_recaptured_existing_skylights):
            sky_component.recapture_sky()
        _recaptured_existing_skylights.clear()
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
        "execution_sha": EXPECTED_SHA,
        "artifact_source_sha": os.environ.get(
            "YACS_MATERIAL_FORGE_ARTIFACT_SHA", EXPECTED_SHA
        ),
        "visual_mode": "FAST" if FAST_VISUAL else "FULL",
        "evidence_authority": (
            "NON_PRODUCTION_FAST_VISUAL"
            if FAST_VISUAL
            else "PRODUCTION_VISUAL_PROOF"
        ),
        "full_production_proof_required": bool(FAST_VISUAL),
        "map": MAP,
        "material": None if _instance is None else _instance.get_path_name(),
        "fixed_master": os.environ.get("YACS_MF_FIXED_MASTER_PATH"),
        "rock": "regional_limestone/refined_c",
        "soil": "mediterranean_soil/refined_c",
        "color_gains": _color_gains,
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
        "canonical_component_bounds": _canonical_component_bounds(),
        "applied_component_count": len(_applied_components),
        "applied_scope": "CANONICAL_COMPONENT_230" if FAST_VISUAL else "WHOLE_LANDSCAPE",
        "map_saved": False,
        "assets_saved": False,
        "geometry_changed": False,
        "world_semantics_changed": False,
        "rollback_complete": status in {
            "MF_LANDSCAPE_VISUAL_PROOF_PASS",
            "MF_FAST_VISUAL_PASS",
        },
        "human_visual_status": (
            "FAST_REVIEW_ONLY" if FAST_VISUAL else "PENDING_OWNER"
        ),
        "elapsed_seconds": round(time.monotonic() - _proof_started, 3),
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
    if FAST_VISUAL:
        status = "MF_FAST_VISUAL_FAIL" if error else "MF_FAST_VISUAL_PASS"
    else:
        status = (
            "MF_LANDSCAPE_VISUAL_PROOF_FAIL"
            if error
            else "MF_LANDSCAPE_VISUAL_PROOF_PASS"
        )
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
        _restore_directional_shadow_bias()
        requested_slope_bias = view.get("shadow_slope_bias")
        if requested_slope_bias is not None:
            _apply_directional_shadow_slope_bias(float(requested_slope_bias))
        view["directional_shadow_bias"] = _directional_shadow_bias_readback()
        dynamic_shadows = bool(view.get("dynamic_shadows", True))
        unreal.SystemLibrary.execute_console_command(
            _world, "showflag.DynamicShadows 1"
        )
        if not dynamic_shadows:
            unreal.SystemLibrary.execute_console_command(
                _world, "showflag.DynamicShadows 0"
            )
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
            comparison_notes=(
                "YACS Material Forge FAST cliff visual review"
                if FAST_VISUAL
                else "YACS Material Forge production Landscape visual proof"
            ),
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
                "dynamic_shadows": bool(view.get("dynamic_shadows", True)),
                "directional_shadow_bias": view.get("directional_shadow_bias", []),
                "requested_shadow_slope_bias": view.get("shadow_slope_bias"),
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
    global _preview, _foundation, _world, _landscape, _components, _applied_components
    global _original_global, _original_overrides, _before_snapshot, _before_map_hash
    global _instance, _camera, _views, _handle, _color_gains

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
    requested_color_gains, _color_gains = _requested_color_gains()
    _instance, _drain = _preview._create_fixed_master_instance(
        package,
        weights,
        _checkpoints,
        color_gain_values=requested_color_gains,
    )
    _verify_color_gain_readback(_instance, requested_color_gains)
    _checkpoints.append(
        {
            "stage": "color_gains_bound_in_fixed_master_update",
            "color_gains": _color_gains,
            "memory": _memory(),
        }
    )
    _assert_memory(
        "fixed_master_instance_ready",
        physical_gb=(
            FAST_MIN_FREE_PHYSICAL_GB
            if FAST_VISUAL
            else MIN_FREE_PHYSICAL_GB
        ),
    )

    if FAST_VISUAL:
        target = next(
            (
                component
                for component in _components
                if component.get_name() == "LandscapeComponent_230"
            ),
            None,
        )
        if target is None:
            raise RuntimeError("FAST visual target LandscapeComponent_230 is missing")
        target.set_editor_property("override_material", _instance)
        _applied_components = [target]
    else:
        _landscape.set_editor_property("landscape_material", _instance)
        for component in _components:
            component.set_editor_property("override_material", None)
        _applied_components = list(_components)

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
    _assert_memory(
        "fast_component_ready" if FAST_VISUAL else "whole_landscape_ready",
        physical_gb=FAST_READY_FREE_PHYSICAL_GB if FAST_VISUAL else 6,
    )

    mismatch = [
        component.get_name()
        for component in _applied_components
        if (
            (FAST_VISUAL and component.get_editor_property("override_material") != _instance)
            or (not FAST_VISUAL and component.get_editor_property("override_material") is not None)
            or component.get_material(0) != _instance
        )
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

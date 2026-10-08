"""Capture the Component_230 transient cliff visual A/B proof.

Without YACS_CLIFF_PCGEX_MESH this is the Phase 2B custom connected-skin
benchmark. With that variable set it renders the Phase 2C PCGEx topology using
the same map, camera, lighting, material, scree and acceptance metrics.

Loads the accepted Sa Calobra map, captures baseline Lit / Lighting Only,
spawns deterministic visual-only DynamicMesh cliff plates and bounded scree,
captures the same views again, destroys all transient proof actors and verifies
the accepted map and scene snapshot are unchanged.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import traceback
import uuid

import unreal


ROOT = Path(__file__).resolve().parents[2]
# A fresh -ExecutePythonScript process exposes this script directory, not the
# repository package root. Whole-map setup imports helpers before legacy lanes.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MAP = "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004"
MAP_FILE = ROOT / "Content/Worlds/SaCalobra/L_SaCalobraAccepted_20261004.umap"
PLAN = Path(os.environ["YACS_CLIFF_VISUAL_PLAN"]).resolve()
OUTPUT = Path(os.environ["YACS_CLIFF_VISUAL_OUTPUT"]).resolve()
EXPECTED_SHA = os.environ["YACS_CLIFF_VISUAL_EXPECTED_SHA"].strip()
PCGEX_MESH = (
    Path(os.environ["YACS_CLIFF_PCGEX_MESH"]).resolve()
    if os.environ.get("YACS_CLIFF_PCGEX_MESH")
    else None
)
PAIRED_CUSTOM_OUTPUT = (
    Path(os.environ["YACS_CLIFF_PAIRED_CUSTOM_OUTPUT"]).resolve()
    if os.environ.get("YACS_CLIFF_PAIRED_CUSTOM_OUTPUT") else None
)
_paired_pcgex_output = OUTPUT
_paired_pcgex_mesh = None
_paired_custom_record = None
_paired_scene = None
_shared_baseline = {"enabled": False}
RESOLUTION = (1920, 1080)
# Warm-up is counted in rendered frames below, never variable wall-clock time.
CAPTURE_DELAY_SECONDS = 0.0
CAPTURE_WARMUP_FRAMES = 64
NEUTRAL_LANDSCAPE = os.environ.get("YACS_CLIFF_NEUTRAL_LANDSCAPE") == "1"
NEUTRAL_MATERIAL = "/Engine/BasicShapes/BasicShapeMaterial"
MATCH_LANDSCAPE_MATERIAL = os.environ.get("YACS_CLIFF_MATCH_LANDSCAPE_MATERIAL") == "1"
LANDSCAPE_MESH_DIAGNOSTIC = os.environ.get("YACS_LANDSCAPE_MESH_DIAGNOSTIC") == "1"
LOCAL_CLIFF_SMOOTHING = os.environ.get("YACS_LOCAL_CLIFF_SMOOTHING") == "1"
TERRAIN_EROSION_TRIAL = os.environ.get("YACS_TERRAIN_EROSION_TRIAL") == "1"
TERRAIN_MESH_TRIAL = os.environ.get("YACS_TERRAIN_MESH_TRIAL") == "1"
WHOLE_MAP_PREP = os.environ.get("YACS_WHOLE_MAP_PREP")
_whole_map_capture = None
_whole_map_environment = None
_terrain_trial = {"enabled": False}
_terrain_source = None
_landscape_visibility_state = None
_landscape_lod_state = None
_landscape_lod_receipt = {"enabled": False}
_landscape_mesh_diagnostic = {"enabled": False}
PIXEL_SIZE_M = 0.5
CLIFF_MATERIAL = (
    "/Game/Generated/YACS/TextureMaterialPrep/Libraries/"
    "3d53743e48394f31beb35e4030dc8a87/LimestonePalette/"
    "1b3d9c45b1e24d6085bfcc8859390c19/M_SC_Limestone_ExposedRock"
)
SCREE_MATERIAL = (
    "/Game/Generated/YACS/TextureMaterialPrep/Libraries/"
    "3d53743e48394f31beb35e4030dc8a87/LimestonePalette/"
    "1b3d9c45b1e24d6085bfcc8859390c19/M_SC_Limestone_Scree"
)
_trace_cache: dict[tuple[float, float], float] = {}

_task = None
_handle = None
_started = 0.0
_index = 0
_finished = False
_world = None
_landscape = None
_target_component = None
_camera = None
_views = []
_captures = []
_diagnostic_captures = []
_candidate_actors = []
_transient_lights = []
_transient_environment = []
_recaptured_skylights = []
_before_hash = None
_before_scene = None
_plan = None
_pcgex_mesh = None
_mesh_receipt = {}
_material_override_state = None
_material_override_receipt = {"enabled": False}
_temporal_sequence_receipt = {}
_shadow_cache_probe = {"enabled": False}
_shadow_cache_previous = None
_survey_capture = None
_detail_capture = None


def _begin_detail_native():
    """Keep the accepted native v8 attributes and reuse this scene's rollback."""
    global _detail_capture
    if (not TERRAIN_MESH_TRIAL or not TERRAIN_EROSION_TRIAL or not NEUTRAL_LANDSCAPE
            or PCGEX_MESH is not None or PAIRED_CUSTOM_OUTPUT is not None
            or os.environ.get('YACS_SA_CALOBRA_TPP_SURVEY') == '1'):
        raise RuntimeError('Native detail requires only the bounded accepted-v8 scene')
    _spawn_rock_shape_trial()
    meshes = [actor for actor in _candidate_actors if isinstance(actor, unreal.DynamicMeshActor)]
    if len(meshes) != 1:
        raise RuntimeError('Native detail requires one accepted v8 visual surface')
    component = meshes[0].get_dynamic_mesh_component()
    mesh = component.get_dynamic_mesh()
    before = mesh.get_triangle_count()
    tile_m = float(_plan['skin_contract']['uv_world_size_m'])
    if tile_m != 3.0:
        raise RuntimeError('Native detail limestone texture scale drift')
    unreal.GeometryScript_UVs.set_mesh_u_vs_from_box_projection(
        mesh, 0, unreal.Transform(scale=unreal.Vector(300, 300, 300)),
        unreal.GeometryScriptMeshSelection(), min_island_tri_count=2)
    if mesh.get_triangle_count() != before:
        raise RuntimeError('Native detail UV projection changed topology')
    material = _load_surface_material(CLIFF_MATERIAL, 'accepted v8 limestone')
    component.set_material(0, material)
    component.notify_mesh_modified()
    if component.get_material(0) != material:
        raise RuntimeError('Native detail accepted limestone did not apply')
    _terrain_trial['limestone_uv_projection'] = {
        'method': 'Epic GeometryScript box projection', 'uv_channel': 0,
        'world_size_m': 3.0, 'triangles_unchanged': True,
        'scope': 'TRANSIENT_PBR_DETAIL_COMPARISON'}
    from scripts.ue.sa_calobra_detail_capture import DetailCapture
    scene = {
        'map': MAP, 'map_sha256': _before_hash,
        'accepted_cliff_implementation_sha': '4f2cba560d54931dc8ba080370d96a7aad24f15b',
        'retained_source_capture_sha': 'b1ea05b33b9f3208e7aeb6884f1a67792d9c6121',
        'cliff_recipe': 'rounded-limestone-reshape-v8',
        'component': 'LandscapeComponent_230', 'material_path': CLIFF_MATERIAL,
        'combined_audit': _terrain_trial['combined_audit'],
        'lighting': _mesh_receipt['lighting'], 'other_scene_actors_retained': True,
        'scope': 'Existing whole scene at two fixed pilot cameras; only Component 230 is substituted',
    }
    _detail_capture = DetailCapture(
        unreal, _world, _landscape, _camera, component, OUTPUT / 'detail-native',
        Path(os.environ['YACS_DETAIL_NATIVE']), EXPECTED_SHA, scene, finish)
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    _detail_capture.start()


def _begin_whole_map_prep():
    """Keep the same source-bound v8 scene while preparing the full Landscape."""
    global _whole_map_capture
    if (not TERRAIN_MESH_TRIAL or not TERRAIN_EROSION_TRIAL or not NEUTRAL_LANDSCAPE
            or PCGEX_MESH is not None or PAIRED_CUSTOM_OUTPUT is not None
            or os.environ.get('YACS_DETAIL_NATIVE')
            or os.environ.get('YACS_SA_CALOBRA_TPP_SURVEY') == '1'):
        raise RuntimeError('Whole-map preparation requires only the accepted v8 scene')
    _spawn_rock_shape_trial()
    meshes = [actor for actor in _candidate_actors if isinstance(actor, unreal.DynamicMeshActor)]
    if len(meshes) != 1:
        raise RuntimeError('Whole-map preparation requires one accepted v8 surface')
    component = meshes[0].get_dynamic_mesh_component()
    mesh = component.get_dynamic_mesh()
    triangles = mesh.get_triangle_count()
    if float(_plan['skin_contract']['uv_world_size_m']) != 3.0:
        raise RuntimeError('Whole-map v8 limestone scale differs')
    unreal.GeometryScript_UVs.set_mesh_u_vs_from_box_projection(
        mesh, 0, unreal.Transform(scale=unreal.Vector(300, 300, 300)),
        unreal.GeometryScriptMeshSelection(), min_island_tri_count=2)
    if mesh.get_triangle_count() != triangles:
        raise RuntimeError('Whole-map v8 UV preparation changed topology')
    material = _load_surface_material(CLIFF_MATERIAL, 'accepted v8 limestone')
    component.set_material(0, material)
    component.notify_mesh_modified()
    if component.get_material(0) != material:
        raise RuntimeError('Whole-map v8 limestone binding failed')
    _terrain_trial['limestone_uv_projection'] = {
        'method': 'Epic GeometryScript box projection', 'uv_channel': 0,
        'world_size_m': 3.0, 'triangles_unchanged': True,
        'scope': 'UNCHANGED_ACCEPTED_V8_IN_WHOLE_MAP_PREPARATION'}
    from scripts.ue.capture_sa_calobra_whole_map_prep import WholeMapCapture
    scene = {
        'map': MAP, 'map_sha256': _before_hash, 'component_bounds': _component_bounds(),
        'accepted_cliff_implementation_sha': '4f2cba560d54931dc8ba080370d96a7aad24f15b',
        'retained_source_capture_sha': 'b1ea05b33b9f3208e7aeb6884f1a67792d9c6121',
        'cliff_recipe': 'rounded-limestone-reshape-v8', 'material_path': CLIFF_MATERIAL,
        'combined_audit': _terrain_trial['combined_audit'], 'lighting': _mesh_receipt['lighting'],
        'other_scene_actors_retained': True,
        'scope': 'Full working Landscape material preparation; accepted v8 and separate road materials retained',
    }
    _whole_map_capture = WholeMapCapture(
        unreal, _world, _landscape, _camera, component, OUTPUT / 'whole-map-prep',
        Path(WHOLE_MAP_PREP), Path(os.environ['YACS_WHOLE_MAP_NATIVE_SOURCE']),
        Path(os.environ['YACS_WHOLE_MAP_MASTER_RECEIPT']), EXPECTED_SHA, scene,
        _whole_map_environment, finish)
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    _whole_map_capture.start()


def _begin_tpp_survey():
    """Reuse exactly the existing accepted v8 scene after its control views."""
    global _handle, _survey_capture, _task
    if not TERRAIN_MESH_TRIAL or _terrain_trial.get('mesh_export', {}).get('shape_profile') != 'rounded-limestone-reshape-v8':
        raise RuntimeError('TPP survey requires the owner-accepted v8 rock shape')
    if _terrain_trial.get('combined_audit', {}).get('status') != 'PASS':
        raise RuntimeError('TPP survey requires the unchanged source-relative geometry audit')
    meshes = [a for a in _candidate_actors if isinstance(a, unreal.DynamicMeshActor)]
    if len(meshes) != 1 or meshes[0].get_dynamic_mesh_component().get_material(0) != unreal.load_asset(CLIFF_MATERIAL):
        raise RuntimeError('TPP survey requires the accepted limestone material on the one v8 mesh')
    sys.path.insert(0, str(ROOT))
    from scripts.ue.sa_calobra_tpp_survey_capture import SurveyCapture, ACCEPTED_LOOK_SHA

    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
    _task = None
    scene = {
        'map': MAP, 'map_sha256': _before_hash,
        'accepted_cliff_implementation_sha': ACCEPTED_LOOK_SHA,
        'cliff_recipe': 'rounded-limestone-reshape-v8',
        'component': 'LandscapeComponent_230',
        'scope': 'Current frozen Landscape with accepted Component 230; whole-Landscape cliff rollout is not present',
        'material_path': CLIFF_MATERIAL,
        'combined_audit': _terrain_trial['combined_audit'],
        'engine_version': unreal.SystemLibrary.get_engine_version(),
    }
    _survey_capture = SurveyCapture(
        unreal, _world, _landscape, _camera, OUTPUT / 'tpp-survey',
        Path(os.environ['YACS_SA_CALOBRA_TPP_FROZEN_ROOT']), EXPECTED_SHA,
        scene, finish, _transient_environment.append)
    _survey_capture.start()


def _set_shadow_cache_probe(enabled):
    global _shadow_cache_previous
    name = "r.Shadow.Virtual.Cache"
    if enabled and _shadow_cache_previous is None:
        previous = unreal.SystemLibrary.get_console_variable_string_value(name)
        if previous == "":
            raise RuntimeError("Engine does not expose VSM cache control")
        _shadow_cache_previous = int(previous)
        _shadow_cache_probe.update(enabled=True, previous=_shadow_cache_previous,
                                   diagnostic_only=True, restored=False)
    if _shadow_cache_previous is None:
        return
    value = 0 if enabled else _shadow_cache_previous
    unreal.SystemLibrary.execute_console_command(_world, f"{name} {value}")
    if unreal.SystemLibrary.get_console_variable_int_value(name) != value:
        raise RuntimeError("VSM cache diagnostic control readback failed")
    _shadow_cache_probe["restored"] = not enabled


def _fix_temporal_sequence():
    # Require support from the actual engine instead of silently accepting an
    # unknown console command. Histories, lighting and shadows stay enabled.
    name = "r.Test.FreezeTemporalSequences"
    previous = unreal.SystemLibrary.get_console_variable_string_value(name)
    if previous == "":
        raise RuntimeError("Engine does not expose temporal-sequence control")
    unreal.SystemLibrary.execute_console_command(_world, name + " ?")
    unreal.SystemLibrary.execute_console_command(_world, name + " 1")
    actual = unreal.SystemLibrary.get_console_variable_int_value(name)
    if actual != 1:
        raise RuntimeError("Temporal-sequence control did not take effect")
    _temporal_sequence_receipt.update(name=name, previous=previous, value=actual)


def _pin_landscape_lod():
    global _landscape_lod_state
    previous = int(_target_component.get_editor_property("forced_lod"))
    _landscape_lod_state = previous
    _landscape_lod_receipt.update(
        enabled=True, component=_target_component.get_name(),
        previous=previous, forced_lod=0, restored=False,
    )
    _target_component.set_editor_property("forced_lod", 0)
    if int(_target_component.get_editor_property("forced_lod")) != 0:
        raise RuntimeError("Landscape component LOD0 override failed")


def _restore_landscape_lod():
    global _landscape_lod_state
    if _landscape_lod_state is None:
        return
    _target_component.set_editor_property("forced_lod", _landscape_lod_state)
    if int(_target_component.get_editor_property("forced_lod")) != _landscape_lod_state:
        raise RuntimeError("Landscape component LOD rollback failed")
    _landscape_lod_receipt["restored"] = True
    _landscape_lod_state = None


def _apply_neutral_landscape_material():
    global _material_override_state, _material_override_receipt
    if not NEUTRAL_LANDSCAPE:
        return
    material = _load_surface_material(NEUTRAL_MATERIAL, "neutral Landscape")
    previous = _target_component.get_editor_property("override_material")
    # Retain rollback state before the setter, including a failed setter.
    _material_override_state = (_target_component, previous)
    _material_override_receipt = {
        "enabled": True,
        "component": _target_component.get_name(),
        "material": material.get_path_name(),
        "previous_override": previous.get_path_name() if previous else None,
        "restored": False,
        "scope": "owner-approved isolated A/B presentation only",
    }
    _target_component.set_editor_property("override_material", material)
    if _target_component.get_editor_property("override_material") != material:
        raise RuntimeError("Neutral Landscape material override did not apply")


def _restore_landscape_material():
    global _material_override_state
    if _material_override_state is None:
        return
    component, previous = _material_override_state
    component.set_editor_property("override_material", previous)
    if component.get_editor_property("override_material") != previous:
        raise RuntimeError("Original Landscape material override did not restore")
    _material_override_receipt["restored"] = True
    _material_override_state = None


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def _scene_snapshot():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    rows = []
    for actor in actors.get_all_level_actors():
        rows.append(
            (
                actor.get_path_name(),
                actor.get_class().get_name(),
                actor.get_actor_label(),
                re.sub(
                    r" \(0x[0-9a-fA-F]+\)",
                    "",
                    str(actor.get_actor_transform()),
                ),
            )
        )
    return sorted(rows)


def _component_bounds():
    origin, extent, radius = unreal.SystemLibrary.get_component_bounds(
        _target_component
    )
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
        raise RuntimeError("Component_230 bounds are non-finite")
    return {
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
    }


def _ensure_lighting():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    directional = list(
        unreal.GameplayStatics.get_all_actors_of_class(
            _world, unreal.DirectionalLight
        )
    )
    skylights = list(
        unreal.GameplayStatics.get_all_actors_of_class(
            _world, unreal.SkyLight
        )
    )
    atmospheres = list(
        unreal.GameplayStatics.get_all_actors_of_class(
            _world, unreal.SkyAtmosphere
        )
    )

    if not atmospheres:
        atmosphere = actors.spawn_actor_from_class(
            unreal.SkyAtmosphere,
            unreal.Vector(),
            unreal.Rotator(),
            transient=True,
        )
        if atmosphere is None:
            raise RuntimeError("Could not create transient SkyAtmosphere")
        _transient_environment.append(atmosphere)

    if not directional:
        sun = actors.spawn_actor_from_class(
            unreal.DirectionalLight,
            unreal.Vector(0.0, 0.0, 300000.0),
            unreal.Rotator(pitch=-36.0, yaw=-52.0, roll=0.0),
            transient=True,
        )
        if sun is None:
            raise RuntimeError("Could not create transient DirectionalLight")
        component = sun.get_component_by_class(
            unreal.DirectionalLightComponent
        )
        component.set_intensity(6.0)
        component.set_atmosphere_sun_light(True)
        _transient_lights.append(sun)
        directional.append(sun)

    if not skylights:
        sky = actors.spawn_actor_from_class(
            unreal.SkyLight,
            unreal.Vector(0.0, 0.0, 300000.0),
            unreal.Rotator(),
            transient=True,
        )
        if sky is None:
            raise RuntimeError("Could not create transient SkyLight")
        component = sky.get_component_by_class(unreal.SkyLightComponent)
        component.set_intensity(1.15)
        component.set_editor_property("lower_hemisphere_is_black", False)
        _transient_lights.append(sky)
        skylights.append(sky)

    shadow_state = []
    for light in directional:
        component = light.get_component_by_class(
            unreal.DirectionalLightComponent
        )
        shadow_state.append(
            {
                "actor": light.get_path_name(),
                "rotation": str(light.get_actor_rotation()),
                "forward_vector": str(light.get_actor_forward_vector()),
                "shadow_bias": float(
                    component.get_editor_property("shadow_bias")
                ),
                "shadow_slope_bias": float(
                    component.get_editor_property("shadow_slope_bias")
                ),
            }
        )
    for sky in skylights:
        component = sky.get_component_by_class(unreal.SkyLightComponent)
        component.recapture_sky()
        if sky not in _transient_lights:
            _recaptured_skylights.append(component)

    unreal.AutomationLibrary.finish_loading_before_screenshot()
    return {
        "directional_light_count": len(directional),
        "skylight_count": len(skylights),
        "shadow_state": shadow_state,
    }


def _load_surface_material(path: str, label: str):
    material = unreal.load_asset(path)
    if material is None:
        raise RuntimeError(f"{label} material is unavailable: {path}")
    if not isinstance(material, unreal.MaterialInterface):
        raise RuntimeError(
            f"{label} asset is not a MaterialInterface: {material.get_class().get_name()}"
        )
    return material

def _extract_trace_z(
    hit,
    *,
    x_cm: float,
    y_cm: float,
    bottom_z_cm: float,
    top_z_cm: float,
) -> float:
    try:
        values = hit.to_tuple()
    except Exception:
        values = ()
    for value in values:
        if not all(hasattr(value, axis) for axis in ("x", "y", "z")):
            continue
        x, y, z = float(value.x), float(value.y), float(value.z)
        if (
            abs(x - x_cm) <= 1.0
            and abs(y - y_cm) <= 1.0
            and bottom_z_cm - 1.0 <= z <= top_z_cm + 1.0
            and abs(z - top_z_cm) > 1.0
            and abs(z - bottom_z_cm) > 1.0
        ):
            return z
    try:
        exported = hit.export_text()
    except Exception:
        exported = ""
    for field_name in ("ImpactPoint", "Location"):
        match = re.search(
            rf"{field_name}=\(X=([-+0-9.eE]+),Y=([-+0-9.eE]+),Z=([-+0-9.eE]+)\)",
            exported,
        )
        if match is None:
            continue
        x, y, z = map(float, match.groups())
        if abs(x - x_cm) <= 1.0 and abs(y - y_cm) <= 1.0:
            return z
    raise RuntimeError(
        "Could not extract Landscape trace height: " + exported[:240]
    )


def _trace_landscape_z(x_m: float, y_m: float) -> float:
    key = (round(float(x_m), 4), round(float(y_m), 4))
    if key in _trace_cache:
        return _trace_cache[key]
    origin, extent, _radius = unreal.SystemLibrary.get_component_bounds(
        _target_component
    )
    top = float(origin.z + extent.z + 250000.0)
    bottom = float(origin.z - extent.z - 250000.0)
    x_cm, y_cm = x_m * 100.0, y_m * 100.0
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    ignored = [
        actor
        for actor in actor_subsystem.get_all_level_actors()
        if actor != _landscape
    ]
    hit = unreal.SystemLibrary.line_trace_single(
        _world,
        unreal.Vector(x_cm, y_cm, top),
        unreal.Vector(x_cm, y_cm, bottom),
        unreal.TraceTypeQuery.ECC_VISIBILITY,
        True,
        ignored,
        unreal.DrawDebugTrace.NONE,
        True,
    )
    if hit is None:
        raise RuntimeError(
            f"Landscape trace missed for x={x_m:.3f} y={y_m:.3f}"
        )
    value = _extract_trace_z(
        hit,
        x_cm=x_cm,
        y_cm=y_cm,
        bottom_z_cm=bottom,
        top_z_cm=top,
    )
    _trace_cache[key] = value
    return value


def _fit_plane_gradient(
    points: list[tuple[float, float, float]],
) -> tuple[float, float]:
    if len(points) < 3:
        return 0.0, 0.0
    mean_x = sum(row[0] for row in points) / len(points)
    mean_y = sum(row[1] for row in points) / len(points)
    mean_z = sum(row[2] for row in points) / len(points)
    sxx = syy = sxy = sxz = syz = 0.0
    for x, y, z in points:
        dx, dy, dz = x - mean_x, y - mean_y, z - mean_z
        sxx += dx * dx
        syy += dy * dy
        sxy += dx * dy
        sxz += dx * dz
        syz += dy * dz
    determinant = sxx * syy - sxy * sxy
    if abs(determinant) <= 1e-9:
        return 0.0, 0.0
    gx = (sxz * syy - syz * sxy) / determinant
    gy = (syz * sxx - sxz * sxy) / determinant
    return gx, gy


def _local_trace_gradient(
    key: tuple[int, int],
    traced: dict[tuple[int, int], float],
    adjacency: dict[tuple[int, int], set[tuple[int, int]]],
    fallback: tuple[float, float],
) -> tuple[float, float]:
    row, col = key
    neighbours = adjacency.get(key, set())

    left = max(
        (n for n in neighbours if n[0] == row and n[1] < col),
        key=lambda n: n[1],
        default=None,
    )
    right = min(
        (n for n in neighbours if n[0] == row and n[1] > col),
        key=lambda n: n[1],
        default=None,
    )
    up = max(
        (n for n in neighbours if n[1] == col and n[0] < row),
        key=lambda n: n[0],
        default=None,
    )
    down = min(
        (n for n in neighbours if n[1] == col and n[0] > row),
        key=lambda n: n[0],
        default=None,
    )

    gx = None
    if left is not None and right is not None:
        dx = (right[1] - left[1]) * PIXEL_SIZE_M
        if dx > 0:
            gx = (traced[right] - traced[left]) / dx
    elif right is not None:
        dx = (right[1] - col) * PIXEL_SIZE_M
        if dx > 0:
            gx = (traced[right] - traced[key]) / dx
    elif left is not None:
        dx = (col - left[1]) * PIXEL_SIZE_M
        if dx > 0:
            gx = (traced[key] - traced[left]) / dx

    gy = None
    if up is not None and down is not None:
        dy = (down[0] - up[0]) * PIXEL_SIZE_M
        if dy > 0:
            gy = (traced[down] - traced[up]) / dy
    elif down is not None:
        dy = (down[0] - row) * PIXEL_SIZE_M
        if dy > 0:
            gy = (traced[down] - traced[key]) / dy
    elif up is not None:
        dy = (row - up[0]) * PIXEL_SIZE_M
        if dy > 0:
            gy = (traced[key] - traced[up]) / dy

    return (
        fallback[0] if gx is None else gx,
        fallback[1] if gy is None else gy,
    )


def _append_skin_cluster(
    vertices: list[unreal.Vector],
    triangles: list[unreal.IntVector],
    uvs: list[unreal.Vector2D],
    cluster: dict[str, object],
    cells: list[dict[str, object]],
):
    """Append one connected, smoothed presentation skin.

    Every mesh vertex starts from an exact Landscape trace. Interior vertices
    receive two bounded Laplacian smoothing passes to suppress sub-grid
    stair-step wedges; boundary vertices keep the real trace and are tucked
    slightly below it so there is no floating white seam.
    """
    if not cells:
        return None

    cell_corners = []
    adjacency: dict[tuple[int, int], set[tuple[int, int]]] = {}
    touch_count: dict[tuple[int, int], int] = {}
    for row in cells:
        r0, r1 = int(row["row0"]), int(row["row1"])
        c0, c1 = int(row["col0"]), int(row["col1"])
        nw, ne, se, sw = (r0, c0), (r0, c1), (r1, c1), (r1, c0)
        corners = (nw, ne, se, sw)
        cell_corners.append(corners)
        for key in corners:
            touch_count[key] = touch_count.get(key, 0) + 1
            adjacency.setdefault(key, set())
        for left, right in ((nw, ne), (ne, se), (se, sw), (sw, nw)):
            adjacency[left].add(right)
            adjacency[right].add(left)

    traced: dict[tuple[int, int], float] = {}
    xyz_points = []
    for row, col in sorted(adjacency):
        x_m, y_m = col * PIXEL_SIZE_M, row * PIXEL_SIZE_M
        z_m = _trace_landscape_z(x_m, y_m) / 100.0
        traced[(row, col)] = z_m
        xyz_points.append((x_m, y_m, z_m))

    original = dict(traced)
    smoothed = dict(traced)
    passes = int(cluster["smoothing_passes"])
    blend = float(cluster["smoothing_blend"])
    clamp_m = float(cluster["smoothing_clamp_m"])
    for _ in range(passes):
        next_values = dict(smoothed)
        for key, value in smoothed.items():
            if touch_count.get(key, 0) < 4:
                continue
            neighbours = adjacency.get(key, set())
            if not neighbours:
                continue
            mean = sum(smoothed[n] for n in neighbours) / len(neighbours)
            candidate = value * (1.0 - blend) + mean * blend
            base = original[key]
            next_values[key] = max(
                base - clamp_m,
                min(base + clamp_m, candidate),
            )
        smoothed = next_values

    gradient_x, gradient_y = _fit_plane_gradient(xyz_points)
    horizontal = math.hypot(gradient_x, gradient_y)
    if horizontal > 1e-6:
        downhill_x, downhill_y = -gradient_x / horizontal, -gradient_y / horizontal
    else:
        downhill_x, downhill_y = 0.0, 1.0
    tangent_x, tangent_y = -downhill_y, downhill_x

    normal_offset = float(cluster["normal_offset_m"])
    uv_scale = float(_plan["skin_contract"]["uv_world_size_m"])

    base = len(vertices)
    local_index: dict[tuple[int, int], int] = {}
    trace_min = float("inf")
    trace_max = float("-inf")
    lift = float(cluster["interior_lift_m"])
    underlap = float(cluster["boundary_underlap_m"])
    for key in sorted(adjacency):
        row, col = key
        x_m, y_m = col * PIXEL_SIZE_M, row * PIXEL_SIZE_M
        raw_z = original[key]
        trace_min = min(trace_min, raw_z * 100.0)
        trace_max = max(trace_max, raw_z * 100.0)
        touches = touch_count.get(key, 0)
        offset_factor = max(0.0, min(1.0, (touches - 1.0) / 3.0))
        smooth_target = max(raw_z, smoothed[key]) + lift
        z_m = (
            raw_z * (1.0 - offset_factor)
            + smooth_target * offset_factor
            - underlap * (1.0 - offset_factor)
        )
        local_gx, local_gy = _local_trace_gradient(
            key,
            original,
            adjacency,
            (gradient_x, gradient_y),
        )
        local_normal_length = math.sqrt(
            local_gx * local_gx + local_gy * local_gy + 1.0
        )
        # A vertical displacement gives the same local normal clearance while
        # preserving the authoritative XY footprint. Bound it on steep faces.
        normal_clearance_z = min(clamp_m, normal_offset * local_normal_length)
        x_render, y_render = x_m, y_m
        z_render = z_m + normal_clearance_z * offset_factor

        local_index[key] = len(vertices)
        vertices.append(
            unreal.Vector(
                x_render * 100.0,
                y_render * 100.0,
                z_render * 100.0,
            )
        )

        # Rock texture uses a 3 m physical scale. U follows the local cliff
        # tangent, V follows elevation so steep faces do not vertically smear.
        u = (x_m * tangent_x + y_m * tangent_y) / uv_scale
        if horizontal > 0.65:
            v = z_m / uv_scale
        else:
            v = (x_m * downhill_x + y_m * downhill_y) / uv_scale
        uvs.append(unreal.Vector2D(u, v))

    for nw, ne, se, sw in cell_corners:
        ia, ib = local_index[nw], local_index[ne]
        ic, id_ = local_index[se], local_index[sw]
        # World X/Y winding chosen for upward/outward-facing normals.
        triangles.append(unreal.IntVector(ia, ib, ic))
        triangles.append(unreal.IntVector(ia, ic, id_))

    return {
        "cluster_id": cluster["cluster_id"],
        "vertices": len(local_index),
        "triangles": len(cell_corners) * 2,
        "trace_z_range_cm": [trace_min, trace_max],
        "plane_gradient": [gradient_x, gradient_y],
        "normal_offset_m": normal_offset,
        "base_vertex": base,
    }

def _append_pcgex_cliff_mesh(
    mesh_receipt: dict[str, object],
) -> tuple[
    list[unreal.Vector],
    list[unreal.IntVector],
    list[unreal.Vector2D],
    dict[str, object],
]:
    """Drape PCGEx topology onto the real accepted Landscape.

    PCGEx owns polygon union/path refinement/constrained-Delaunay topology.
    This renderer only projects the resulting XY vertices onto Landscape and
    applies the same bounded presentation-layer Z/normal policy used by the
    custom benchmark. The accepted Landscape remains untouched.
    """
    raw_xy: list[tuple[float, float]] = []
    triangles_raw: list[tuple[int, int, int]] = []
    mesh_ranges: list[tuple[int, int]] = []

    for mesh in mesh_receipt["meshes"]:
        base = len(raw_xy)
        vertices_cm = mesh["vertices_cm"]
        local_count = len(vertices_cm)
        for row in vertices_cm:
            if len(row) != 3:
                raise RuntimeError("PCGEx mesh vertex must contain XYZ")
            x_cm, y_cm, z_cm = [float(value) for value in row]
            if not all(math.isfinite(value) for value in (x_cm, y_cm, z_cm)):
                raise RuntimeError("PCGEx mesh contains non-finite vertex")
            if abs(z_cm) > 1.0:
                raise RuntimeError(
                    "PCGEx topology must remain flat before Landscape projection"
                )
            raw_xy.append((x_cm / 100.0, y_cm / 100.0))

        mesh_ranges.append((base, len(raw_xy)))

        for row in mesh["triangles"]:
            if len(row) != 3:
                raise RuntimeError("PCGEx mesh triangle must contain three indices")
            a, b, c_ = [int(value) for value in row]
            if min(a, b, c_) < 0 or max(a, b, c_) >= local_count:
                raise RuntimeError("PCGEx mesh triangle index is out of bounds")
            if len({a, b, c_}) != 3:
                raise RuntimeError("PCGEx mesh contains degenerate index triangle")
            triangles_raw.append((base + a, base + b, base + c_))

    if len(raw_xy) != int(mesh_receipt["vertex_count"]):
        raise RuntimeError("PCGEx mesh vertex receipt drift")
    if len(triangles_raw) != int(mesh_receipt["triangle_count"]):
        raise RuntimeError("PCGEx mesh triangle receipt drift")
    if not raw_xy or not triangles_raw:
        raise RuntimeError("PCGEx topology is empty")

    adjacency: dict[int, set[int]] = {index: set() for index in range(len(raw_xy))}
    edge_counts: dict[tuple[int, int], int] = {}
    for a, b, c_ in triangles_raw:
        for left, right in ((a, b), (b, c_), (c_, a)):
            adjacency[left].add(right)
            adjacency[right].add(left)
            edge = (min(left, right), max(left, right))
            edge_counts[edge] = edge_counts.get(edge, 0) + 1

    boundary = {
        vertex
        for edge, count in edge_counts.items()
        if count == 1
        for vertex in edge
    }

    original = [
        _trace_landscape_z(x_m, y_m) / 100.0
        for x_m, y_m in raw_xy
    ]
    trace_min = min(original) * 100.0
    trace_max = max(original) * 100.0
    smoothed = list(original)
    # Match the custom benchmark's fixed projection per connected island.
    # Rotating the UV frame per vertex multiplies local normal noise by the
    # absolute world coordinates, creating large UV jumps across short edges.
    uv_frames = []
    for first, last in mesh_ranges:
        gx, gy = _fit_plane_gradient(
            [(raw_xy[i][0], raw_xy[i][1], original[i]) for i in range(first, last)]
        )
        horizontal = math.hypot(gx, gy)
        downhill = (
            (-gx / horizontal, -gy / horizontal)
            if horizontal > 1.0e-6
            else (0.0, 1.0)
        )
        uv_frames.extend([(horizontal, *downhill)] * (last - first))

    plates = list(_plan["plates"])
    smoothing_passes = max(
        int(row["smoothing_passes"]) for row in plates
    )
    smoothing_blend = sum(
        float(row["smoothing_blend"]) for row in plates
    ) / len(plates)
    smoothing_clamp = max(
        float(row["smoothing_clamp_m"]) for row in plates
    )
    lift = sum(float(row["interior_lift_m"]) for row in plates) / len(plates)
    underlap = sum(
        float(row["boundary_underlap_m"]) for row in plates
    ) / len(plates)
    normal_offset = sum(
        float(row["normal_offset_m"]) for row in plates
    ) / len(plates)

    for _ in range(smoothing_passes):
        next_values = list(smoothed)
        for index, value in enumerate(smoothed):
            if index in boundary:
                continue
            neighbours = adjacency[index]
            if not neighbours:
                continue
            mean = sum(smoothed[n] for n in neighbours) / len(neighbours)
            candidate = value * (1.0 - smoothing_blend) + mean * smoothing_blend
            base = original[index]
            next_values[index] = max(
                base - smoothing_clamp,
                min(base + smoothing_clamp, candidate),
            )
        smoothed = next_values

    def local_gradient(index: int) -> tuple[float, float]:
        x0, y0 = raw_xy[index]
        z0 = original[index]
        sxx = syy = sxy = sxz = syz = 0.0
        for neighbour in adjacency[index]:
            x1, y1 = raw_xy[neighbour]
            dx, dy = x1 - x0, y1 - y0
            dz = original[neighbour] - z0
            sxx += dx * dx
            syy += dy * dy
            sxy += dx * dy
            sxz += dx * dz
            syz += dy * dz
        determinant = sxx * syy - sxy * sxy
        if abs(determinant) <= 1.0e-9:
            return 0.0, 0.0
        return (
            (sxz * syy - syz * sxy) / determinant,
            (syz * sxx - sxz * sxy) / determinant,
        )

    uv_scale = float(_plan["skin_contract"]["uv_world_size_m"])
    vertices: list[unreal.Vector] = []
    uvs: list[unreal.Vector2D] = []
    for index, (x_m, y_m) in enumerate(raw_xy):
        is_boundary = index in boundary
        factor = 0.0 if is_boundary else 1.0
        z_m = (
            original[index] - underlap
            if is_boundary
            else max(original[index], smoothed[index]) + lift
        )
        gx, gy = local_gradient(index)
        normal_length = math.sqrt(gx * gx + gy * gy + 1.0)
        normal_clearance_z = min(smoothing_clamp, normal_offset * normal_length)
        x_render, y_render = x_m, y_m
        z_render = z_m + normal_clearance_z * factor
        vertices.append(
            unreal.Vector(
                x_render * 100.0,
                y_render * 100.0,
                z_render * 100.0,
            )
        )

        horizontal, downhill_x, downhill_y = uv_frames[index]
        tangent_x, tangent_y = -downhill_y, downhill_x
        u = (x_m * tangent_x + y_m * tangent_y) / uv_scale
        if horizontal > 0.65:
            v = z_m / uv_scale
        else:
            v = (x_m * downhill_x + y_m * downhill_y) / uv_scale
        uvs.append(unreal.Vector2D(u, v))

    triangles = [
        unreal.IntVector(a, b, c_) for a, b, c_ in triangles_raw
    ]
    return vertices, triangles, uvs, {
        "generator": "PCGEx",
        "pcgex_commit": mesh_receipt["pcgex_commit"],
        "pipeline": mesh_receipt["pipeline"],
        "source_skin_cell_count": int(mesh_receipt["source_skin_cell_count"]),
        "mesh_count": int(mesh_receipt["mesh_count"]),
        "target_edge_cm": float(mesh_receipt["target_edge_cm"]),
        "max_edge_cm_before": float(mesh_receipt["max_edge_cm_before"]),
        "max_edge_cm_after": float(mesh_receipt["max_edge_cm_after"]),
        "max_tessellation": int(mesh_receipt["max_tessellation"]),
        "pcgex_vertex_count": int(mesh_receipt["vertex_count"]),
        "pcgex_triangle_count": int(mesh_receipt["triangle_count"]),
        "front_vertices": len(vertices),
        "front_triangles": len(triangles),
        "boundary_vertices": len(boundary),
        "interior_vertices": len(vertices) - len(boundary),
        "trace_z_range_cm": [trace_min, trace_max],
        "smoothing_passes": smoothing_passes,
        "smoothing_blend": smoothing_blend,
        "smoothing_clamp_m": smoothing_clamp,
        "boundary_underlap_m": underlap,
        "normal_offset_m": normal_offset,
        "uv_projection": "fixed plane-gradient frame per physical island",
        "max_xy_shift_cm": max(
            math.hypot(vertex.x - xy[0] * 100.0, vertex.y - xy[1] * 100.0)
            for vertex, xy in zip(vertices, raw_xy, strict=True)
        ),
        "interior_smoothing_policy": "nonnegative displacement from traced surface",
    }


def _audit_surface_contact(vertices, triangles):
    """Measure signed vertical clearance; sampling is not continuous proof."""
    xyz = [[float(v.x), float(v.y), float(v.z)] for v in vertices]
    faces = [(int(t.x), int(t.y), int(t.z)) for t in triangles]
    edge_counts = {}
    for a, b, c in faces:
        for edge in ((a, b), (b, c), (c, a)):
            key = tuple(sorted(edge))
            edge_counts[key] = edge_counts.get(key, 0) + 1
    boundary = {v for edge, count in edge_counts.items() if count == 1 for v in edge}
    weights = ((1 / 3, 1 / 3, 1 / 3), (0.5, 0.5, 0), (0, 0.5, 0.5), (0.5, 0, 0.5))
    groups = {
        name: {
            "samples": 0,
            "below_minus_1cm": 0,
            "min_clearance_cm": None,
            "max_clearance_cm": None,
        }
        for name in ("interior", "boundary_incident")
    }
    clearances = []
    for face in faces:
        group = groups[
            "boundary_incident" if any(v in boundary for v in face) else "interior"
        ]
        gaps = []
        for weight in weights:
            point = [
                sum(weight[k] * xyz[face[k]][axis] for k in range(3))
                for axis in range(3)
            ]
            gap = point[2] - _trace_landscape_z(point[0] / 100.0, point[1] / 100.0)
            if not math.isfinite(gap):
                raise RuntimeError("Nonfinite cliff/Landscape contact sample")
            gaps.append(gap)
            group["samples"] += 1
            group["below_minus_1cm"] += int(gap < -1.0)
            low, high = group["min_clearance_cm"], group["max_clearance_cm"]
            group["min_clearance_cm"] = gap if low is None else min(low, gap)
            group["max_clearance_cm"] = gap if high is None else max(high, gap)
        clearances.append(gaps)
    report = {
        "schema_version": 1,
        "exact_sha": EXPECTED_SHA,
        "status": "DIAGNOSTIC_ONLY",
        "units": "cm",
        "sample_order": ["centroid", "edge_ab", "edge_bc", "edge_ca"],
        "positive_clearance": "mesh above Landscape",
        "groups": groups,
        "vertices_xyz_cm": xyz,
        "triangles": faces,
        "boundary_vertices": sorted(boundary),
        "sample_clearances_cm": clearances,
    }
    path = OUTPUT / "component230-cliff-contact-samples.json"
    path.write_text(
        json.dumps(report, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return {
        "status": "DIAGNOSTIC_ONLY",
        "groups": groups,
        "samples_file": path.name,
        "sha256": _digest(path),
    }


def _append_scree_rock(
    vertices: list[unreal.Vector],
    triangles: list[unreal.IntVector],
    uvs: list[unreal.Vector2D],
    row: dict[str, object],
    surface_z_cm: float,
):
    x_m, y_m = [float(value) for value in row["center_xy_m"]]
    radius = float(row["radius_m"])
    height = float(row["height_m"])
    yaw = math.radians(float(row["yaw_deg"]))
    base = len(vertices)
    ring = []
    for index in range(4):
        angle = yaw + index * math.pi * 0.5
        scale = 0.82 + index * 0.045
        ring.append(
            (
                x_m + math.cos(angle) * radius * scale,
                y_m + math.sin(angle) * radius * (1.05 - index * 0.035),
                surface_z_cm / 100.0 + 0.03,
            )
        )
    top = (x_m + radius * 0.08, y_m - radius * 0.06, surface_z_cm / 100.0 + height)
    bottom = (x_m, y_m, surface_z_cm / 100.0 - 0.08)
    points = ring + [top, bottom]
    vertices.extend(
        unreal.Vector(px * 100.0, py * 100.0, pz * 100.0)
        for px, py, pz in points
    )
    for px, py, _pz in points:
        uvs.append(unreal.Vector2D(px / 3.0, py / 3.0))
    for index in range(4):
        nxt = (index + 1) % 4
        triangles.append(unreal.IntVector(base + index, base + nxt, base + 4))
        triangles.append(unreal.IntVector(base + nxt, base + index, base + 5))


def _spawn_mesh(
    label: str,
    vertices: list[unreal.Vector],
    triangles: list[unreal.IntVector],
    uvs: list[unreal.Vector2D],
    material,
):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = actors.spawn_actor_from_class(
        unreal.DynamicMeshActor,
        unreal.Vector(),
        unreal.Rotator(),
        transient=True,
    )
    if actor is None:
        raise RuntimeError("Failed to spawn " + label)
    actor.set_actor_label(label)
    component = actor.get_dynamic_mesh_component()
    dynamic_mesh = component.get_dynamic_mesh()
    buffers = unreal.GeometryScriptSimpleMeshBuffers()
    buffers.set_editor_property("vertices", vertices)
    buffers.set_editor_property("triangles", triangles)
    if len(uvs) != len(vertices):
        raise RuntimeError(
            f"{label} UV count mismatch: {len(uvs)} != {len(vertices)}"
        )
    buffers.set_editor_property("uv0", uvs)
    dynamic_mesh.reset()
    dynamic_mesh.append_buffers_to_mesh(
        buffers,
        material_id=0,
        defer_change_notifications=True,
    )
    unreal.GeometryScript_Normals.set_per_vertex_normals(dynamic_mesh)
    component.set_tangents_type(
        unreal.DynamicMeshComponentTangentsMode.AUTO_CALCULATED
    )
    component.notify_mesh_modified()
    component.set_material(0, material)
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    collision = component.get_collision_enabled()
    if collision != unreal.CollisionEnabled.NO_COLLISION:
        raise RuntimeError(label + " collision did not disable")
    if hasattr(component, "set_cast_shadow"):
        component.set_cast_shadow(True)

    counts = {
        "vertices": int(dynamic_mesh.get_vertex_count()),
        "triangles": int(dynamic_mesh.get_triangle_count()),
    }
    if counts["vertices"] != len(vertices) or counts["triangles"] != len(triangles):
        raise RuntimeError(label + " DynamicMesh count mismatch")
    _candidate_actors.append(actor)
    return counts



def _spawn_landscape_mesh_diagnostic():
    global _landscape_visibility_state, _mesh_receipt
    if not NEUTRAL_LANDSCAPE or not _material_override_receipt["enabled"]:
        raise RuntimeError("Landscape mesh diagnostic requires common neutral material")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = actors.spawn_actor_from_class(
        unreal.DynamicMeshActor, unreal.Vector(), unreal.Rotator(), transient=True
    )
    if actor is None:
        raise RuntimeError("Cannot spawn Landscape mesh diagnostic")
    _candidate_actors.append(actor)
    actor.set_actor_label("YACS_Component230_NativeLandscapeMesh")
    component = actor.get_dynamic_mesh_component()
    mesh = component.get_dynamic_mesh()
    export = json.loads(
        unreal.YacsLandscapeMeshDiagnosticLibrary.copy_component230(
            _target_component, mesh,
            json.dumps(_plan) if LOCAL_CLIFF_SMOOTHING else "",
        )
    )
    if export.get("status") != "NATIVE_LANDSCAPE_COMPONENT_MESH":
        raise RuntimeError("Native Landscape export: " + json.dumps(export))
    if LOCAL_CLIFF_SMOOTHING:
        if (
            export.get("local_smoothing") is not True
            or export.get("source_skin_cells") != 1017
            or export.get("folded_xy_triangles") != 0
            or export.get("locked_vertex_displacement_cm") != 0
            or export.get("locked_normal_max_delta", float("inf")) != 0
            or export.get("displacement_limit_cm") != 100.0
            or export.get("max_displacement_cm", float("inf")) > 100.000001
        ):
            raise RuntimeError("Local cliff smoothing receipt failed")
        evidence = {
            "vertex_columns": ["id", "source_x", "source_y", "source_z", "x", "y", "z", "movable"],
            "vertices_cm": export.pop("audit_vertices_cm"),
            "triangles": export.pop("audit_triangles"),
            "refinement": export.get("refinement", "native"),
        }
        evidence_path = OUTPUT / "local-cliff-smoothing-mesh.json"
        evidence_path.write_text(
            json.dumps(evidence, sort_keys=True, separators=(",", ":")), encoding="utf-8"
        )
        export["mesh_evidence_sha256"] = _digest(evidence_path)
        component.set_tangents_type(
            unreal.DynamicMeshComponentTangentsMode.AUTO_CALCULATED
        )
    material = _target_component.get_editor_property("override_material")
    component.set_material(0, material)
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    component.set_cast_shadow(True)
    component.notify_mesh_modified()
    if mesh.get_triangle_count() != export["triangles"]:
        raise RuntimeError("Native Landscape mesh triangle count drifted")
    if component.get_material(0) != material:
        raise RuntimeError("Native Landscape mesh material identity mismatch")
    _landscape_visibility_state = (
        _target_component.get_editor_property("visible"),
        _target_component.get_editor_property("cast_hidden_shadow"),
    )
    _landscape_mesh_diagnostic.update(
        enabled=True, export=export, original_visibility=_landscape_visibility_state[0],
        restored=False, pcgex_overlay=False, scree_spawned=False,
        local_smoothing=LOCAL_CLIFF_SMOOTHING,
        scope="NON_PRODUCTION_NATIVE_LANDSCAPE_MESH_DIAGNOSTIC",
    )
    _target_component.set_editor_property("cast_hidden_shadow", False)
    _target_component.set_visibility(False, False)
    if _target_component.get_editor_property("visible"):
        raise RuntimeError("Original Landscape component did not hide")
    _mesh_receipt = {
        "lighting": _mesh_receipt.get("lighting"),
        "generator": "native-landscape-export",
        "cliff": {"vertices": export["vertices"], "triangles": export["triangles"]},
        "collision_enabled": False,
        "cast_dynamic_shadows": True,
        "material": {"cliff": material.get_path_name(), "diagnostic_only": True},
    }


def _restore_landscape_visibility():
    global _landscape_visibility_state
    if _landscape_visibility_state is None:
        return
    visible, hidden_shadow = _landscape_visibility_state
    _target_component.set_visibility(visible, False)
    _target_component.set_editor_property("cast_hidden_shadow", hidden_shadow)
    if (
        _target_component.get_editor_property("visible") != visible
        or _target_component.get_editor_property("cast_hidden_shadow") != hidden_shadow
    ):
        raise RuntimeError("Landscape visibility/shadow rollback failed")
    _landscape_mesh_diagnostic["restored"] = True
    _landscape_visibility_state = None


def _spawn_rock_shape_trial():
    global _terrain_source, _landscape_visibility_state, _mesh_receipt
    sys.path.insert(0, str(ROOT))
    from scripts.assets.analyze_local_cliff_smoothing import audit, source_only_surface_evidence
    library = unreal.YacsLandscapeMeshDiagnosticLibrary
    _terrain_source = json.loads(library.read_component230_heightfield(_target_component))
    for name in ('source', 'candidate', 'readback'):
        (OUTPUT / ('terrain-' + name + '.json')).write_text(json.dumps(_terrain_source), encoding='utf-8')
    erosion = dict(enabled=False, method='disabled-owner-edge-only', iterations=0,
        smoothing_passes=0, derived_heightfield_modified=False, fixed_samples_changed=0,
        height_sum_delta_units=0, max_abs_change_cm=0)
    (OUTPUT / 'terrain-erosion.json').write_text(json.dumps(erosion), encoding='utf-8')
    reference_path = Path(os.environ['YACS_TERRAIN_ORIGINAL_MESH'])
    reference_receipt = json.loads((reference_path.parent / 'component230-cliff-visual-receipt.json').read_text(encoding='utf-8-sig'))
    detail_root = os.environ.get('YACS_DETAIL_NATIVE') or os.environ.get('YACS_WHOLE_MAP_NATIVE_SOURCE')
    reference_sha = EXPECTED_SHA
    if detail_root:
        # Reuse the explicitly retained original-source control. Its historical
        # capture SHA stays historical; current native v8 is independently
        # reconstructed and matched to the fixed source mesh before any mask.
        expected_reference = Path(detail_root).resolve() / 'source-reference/local-cliff-smoothing-mesh.json'
        reference_sha = 'b1ea05b33b9f3208e7aeb6884f1a67792d9c6121'
        if (reference_path.resolve() != expected_reference
                or _digest(reference_path) != '9ed6c9179d2df04117fcc8992224061f942d42a03a714a4a75177c43728b1cd5'
                or _digest(reference_path.parent / 'component230-cliff-visual-receipt.json') != 'c9494905cbb51f5622e3a414c862eb86d21a261063d6b5adc357ee74ac2a2742'):
            raise RuntimeError('Native detail retained original-source provenance failed')
    if (reference_receipt['exact_sha'] != reference_sha
            or reference_receipt['status'] != 'COMPONENT230_CLIFF_VISUAL_PASS'
            or reference_receipt['landscape_mesh_diagnostic']['export']['mesh_evidence_sha256'] != _digest(reference_path)):
        raise RuntimeError('Edge-only original reference provenance failed')
    reference = json.loads(reference_path.read_text(encoding='utf-8-sig'))
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = actors.spawn_actor_from_class(unreal.DynamicMeshActor, unreal.Vector(), unreal.Rotator(), transient=True)
    if actor is None:
        raise RuntimeError('Cannot spawn edge-only preview mesh')
    _candidate_actors.append(actor)
    actor.set_actor_label('YACS Component230 bounded limestone rock reshaping (unsaved)')
    component = actor.get_dynamic_mesh_component()
    export = json.loads(library.copy_component230(_target_component, component.get_dynamic_mesh(),
        json.dumps(dict(_plan, limestone_rounded_flow=True, limestone_local_reshape=True))))
    (OUTPUT / 'edge-native-export.json').write_text(json.dumps(export), encoding='utf-8')
    if (export.get('status') != 'NATIVE_LANDSCAPE_COMPONENT_MESH'
            or export.get('shape_profile') != 'rounded-limestone-reshape-v8'
            or export.get('displacement_limit_cm') != 50 or export.get('locked_normal_max_delta') != 0
            or export.get('source_only_reshape') is not True
            or export.get('terrain_erosion') is not False):
        raise RuntimeError('Bounded rock reshape export failed: ' + json.dumps(export))
    combined = dict(vertices_cm=export.pop('audit_vertices_cm'), triangles=export.pop('audit_triangles'),
        refinement=export['refinement'])
    combined = source_only_surface_evidence(reference, combined)
    # Retain rejected geometry for diagnosis before the independent audit runs.
    for name, data in (('mesh-stage', combined), ('combined-mesh', combined)):
        (OUTPUT / (name + '.json')).write_text(json.dumps(data), encoding='utf-8')
    result = audit(_plan, combined, limit_cm=50.0, rounding_domain=True)
    (OUTPUT / 'combined-audit.json').write_text(json.dumps(result), encoding='utf-8')
    component.set_material(0, _target_component.get_editor_property('override_material'))
    component.set_tangents_type(unreal.DynamicMeshComponentTangentsMode.AUTO_CALCULATED)
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    component.set_cast_shadow(True)
    component.notify_mesh_modified()
    _landscape_visibility_state = (_target_component.get_editor_property('visible'),
        _target_component.get_editor_property('cast_hidden_shadow'))
    _target_component.set_editor_property('cast_hidden_shadow', False)
    _target_component.set_visibility(False, False)
    _terrain_trial.update(enabled=True, erosion=erosion, native_landscape=False, edge_only_mesh=False,
        reshaped_rock_mesh=True, reference_source=combined['source_reference'],
        terrain_import_performed=False, imported_heightfield_matches=None, restored=False, source_heightfield_unchanged=False,
        derived_heightfield_modified=False, post_erosion_mesh=True, mesh_export=export,
        combined_audit=result, original_reference_sha256=_digest(reference_path))
    _mesh_receipt = dict(lighting=_mesh_receipt.get('lighting'), generator='native-source-rock-reshape',
        cliff=dict(vertices=export['vertices'], triangles=export['triangles']),
        collision_enabled=False, cast_dynamic_shadows=True,
        material=dict(cliff=_material_override_receipt['material'], diagnostic_only=True))


def _spawn_terrain_erosion_trial():
    global _terrain_source, _landscape_visibility_state, _mesh_receipt
    if not NEUTRAL_LANDSCAPE or not _material_override_receipt["enabled"]:
        raise RuntimeError("Terrain erosion trial requires the common neutral material")
    sys.path.insert(0, str(ROOT))
    from scripts.geometry.local_thermal_erosion import erode

    if TERRAIN_MESH_TRIAL:
        _spawn_rock_shape_trial()
        return
    library = unreal.YacsLandscapeMeshDiagnosticLibrary
    _terrain_source = json.loads(library.read_component230_heightfield(_target_component))
    erosion_plan = dict(_plan, skin_cells=_plan['rounding_cells']) if TERRAIN_MESH_TRIAL else _plan
    candidate, erosion = erode(_terrain_source, erosion_plan, iterations=64 if TERRAIN_MESH_TRIAL else 96,
                               talus_slope=0.8,
                               limit_cm=150.0, smoothing_passes=16 if TERRAIN_MESH_TRIAL else 12)
    if (not erosion["derived_heightfield_modified"] or erosion["fixed_samples_changed"]
            or erosion["height_sum_delta_units"] or erosion["max_abs_change_cm"] > 150):
        raise RuntimeError("Terrain erosion bounds or sediment conservation failed")
    for name, data in (("source", _terrain_source), ("candidate", candidate), ("erosion", erosion)):
        (OUTPUT / ("terrain-" + name + ".json")).write_text(json.dumps(data), encoding="utf-8")
    actor = library.create_component230_terrain_trial(
        _target_component, json.dumps(candidate), json.dumps(dict(_plan, terrain_rounding_domain=TERRAIN_MESH_TRIAL))
    )
    if actor is None:
        raise RuntimeError("Native derived Landscape import or height readback failed")
    _candidate_actors.append(actor)
    components = actor.get_components_by_class(unreal.LandscapeComponent)
    if len(components) != 1:
        raise RuntimeError("Terrain trial must have exactly one component")
    actual = json.loads(library.read_component230_heightfield(components[0]))
    if actual != candidate:
        raise RuntimeError("Imported native Landscape differs from derived DTM")
    (OUTPUT / "terrain-readback.json").write_text(json.dumps(actual), encoding="utf-8")
    _terrain_trial.update(enabled=True, erosion=erosion, native_landscape=True,
                          imported_heightfield_matches=True, restored=False,
                          source_heightfield_unchanged=False, derived_heightfield_modified=True)
    _landscape_visibility_state = (
        _target_component.get_editor_property("visible"),
        _target_component.get_editor_property("cast_hidden_shadow"),
    )
    _target_component.set_editor_property("cast_hidden_shadow", False)
    _target_component.set_visibility(False, False)
    _mesh_receipt = {
        "lighting": _mesh_receipt.get("lighting"), "generator": "native-landscape-thermal-erosion",
        "cliff": {"vertices": 127 * 127, "triangles": 126 * 126 * 2},
        "collision_enabled": False, "cast_dynamic_shadows": True,
        "material": {"cliff": _material_override_receipt["material"], "diagnostic_only": True},
    }
    if TERRAIN_MESH_TRIAL:
        from scripts.assets.analyze_local_cliff_smoothing import audit, original_surface_evidence

        reference_path = Path(os.environ["YACS_TERRAIN_ORIGINAL_MESH"])
        reference_receipt = json.loads((reference_path.parent / "component230-cliff-visual-receipt.json").read_text(encoding="utf-8-sig"))
        if (reference_receipt["exact_sha"] != EXPECTED_SHA
                or reference_receipt["status"] != "COMPONENT230_CLIFF_VISUAL_PASS"
                or reference_receipt["landscape_mesh_diagnostic"]["export"]["mesh_evidence_sha256"] != _digest(reference_path)):
            raise RuntimeError("Original mesh reference provenance failed")
        reference = json.loads(reference_path.read_text(encoding="utf-8-sig"))
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        mesh_actor = actors.spawn_actor_from_class(unreal.DynamicMeshActor, unreal.Vector(), unreal.Rotator(), transient=True)
        if mesh_actor is None:
            raise RuntimeError("Cannot spawn post-erosion mesh")
        _candidate_actors.append(mesh_actor)
        mesh_actor.set_actor_label("YACS Component230 eroded terrain mesh (unsaved)")
        mesh_component = mesh_actor.get_dynamic_mesh_component()
        export = json.loads(library.copy_component230(
            components[0], mesh_component.get_dynamic_mesh(), json.dumps(dict(_plan, post_erosion_mesh=True, limestone_rounded_flow=True))))
        if (export.get("status") != "NATIVE_LANDSCAPE_COMPONENT_MESH"
                or export.get("displacement_limit_cm") != 50
                or export.get("locked_normal_max_delta") != 0):
            raise RuntimeError("Post-erosion mesh export failed: " + json.dumps(export))
        derived = {"vertices_cm": export.pop("audit_vertices_cm"),
                   "triangles": export.pop("audit_triangles"), "refinement": export["refinement"]}
        combined = original_surface_evidence(reference, derived)
        combined_audit = audit(_plan, combined, limit_cm=200.0, rounding_domain=True)
        for name, data in (("mesh-stage", derived), ("combined-mesh", combined), ("combined-audit", combined_audit)):
            (OUTPUT / (name + ".json")).write_text(json.dumps(data), encoding="utf-8")
        mesh_component.set_material(0, _target_component.get_editor_property("override_material"))
        mesh_component.set_tangents_type(unreal.DynamicMeshComponentTangentsMode.AUTO_CALCULATED)
        mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        mesh_component.set_cast_shadow(True)
        mesh_component.notify_mesh_modified()
        components[0].set_editor_property("cast_hidden_shadow", False)
        components[0].set_visibility(False, False)
        _terrain_trial.update(post_erosion_mesh=True, mesh_export=export, combined_audit=combined_audit,
                              original_reference_sha256=_digest(reference_path))
        _mesh_receipt["generator"] = "native-eroded-landscape-mesh"
        _mesh_receipt["cliff"] = {"vertices": export["vertices"], "triangles": export["triangles"]}


def _spawn_candidate():
    global _mesh_receipt
    if _candidate_actors:
        return

    if TERRAIN_EROSION_TRIAL:
        _spawn_terrain_erosion_trial()
        return

    if LANDSCAPE_MESH_DIAGNOSTIC:
        _spawn_landscape_mesh_diagnostic()
        return

    limestone = _load_surface_material(CLIFF_MATERIAL, "limestone")
    if MATCH_LANDSCAPE_MATERIAL:
        if not NEUTRAL_LANDSCAPE or not _material_override_receipt["enabled"]:
            raise RuntimeError("Same-material diagnostic requires neutral Landscape")
        limestone = _target_component.get_editor_property("override_material")
        if (
            limestone is None
            or limestone.get_path_name() != _material_override_receipt["material"]
        ):
            raise RuntimeError("Same-material diagnostic Landscape identity mismatch")
    scree_material = _load_surface_material(SCREE_MATERIAL, "scree")

    cells_by_cluster: dict[str, list[dict[str, object]]] = {}
    for row in _plan["skin_cells"]:
        cells_by_cluster.setdefault(str(row["cluster_id"]), []).append(row)

    cluster_receipts = []
    pcgex_receipt = None
    trace_min = float("inf")
    trace_max = float("-inf")

    if _pcgex_mesh is not None:
        (
            cliff_vertices,
            cliff_triangles,
            cliff_uvs,
            pcgex_receipt,
        ) = _append_pcgex_cliff_mesh(_pcgex_mesh)
        trace_min = min(
            trace_min,
            float(pcgex_receipt["trace_z_range_cm"][0]),
        )
        trace_max = max(
            trace_max,
            float(pcgex_receipt["trace_z_range_cm"][1]),
        )
    else:
        cliff_vertices: list[unreal.Vector] = []
        cliff_triangles: list[unreal.IntVector] = []
        cliff_uvs: list[unreal.Vector2D] = []
        for cluster in _plan["plates"]:
            cluster_id = str(cluster["cluster_id"])
            receipt = _append_skin_cluster(
                cliff_vertices,
                cliff_triangles,
                cliff_uvs,
                cluster,
                cells_by_cluster.get(cluster_id, []),
            )
            if receipt is None:
                continue
            cluster_receipts.append(receipt)
            trace_min = min(
                trace_min,
                float(receipt["trace_z_range_cm"][0]),
            )
            trace_max = max(
                trace_max,
                float(receipt["trace_z_range_cm"][1]),
            )

    contact = _audit_surface_contact(cliff_vertices, cliff_triangles)

    # Cliff skins are presentation surfaces viewed from highly oblique angles.
    # Duplicate the connected front surface with reversed winding so an
    # orientation change cannot become a pitch-black backface hole. Vertices
    # are duplicated intentionally so per-vertex normals do not cancel.
    front_vertex_count = len(cliff_vertices)
    front_vertices = list(cliff_vertices)
    front_uvs = list(cliff_uvs)
    front_triangles = list(cliff_triangles)
    cliff_vertices.extend(front_vertices)
    cliff_uvs.extend(front_uvs)
    for triangle in front_triangles:
        cliff_triangles.append(
            unreal.IntVector(
                front_vertex_count + int(triangle.z),
                front_vertex_count + int(triangle.y),
                front_vertex_count + int(triangle.x),
            )
        )

    scree_vertices: list[unreal.Vector] = []
    scree_triangles: list[unreal.IntVector] = []
    scree_uvs: list[unreal.Vector2D] = []
    for row in _plan["scree_rocks"]:
        z = _trace_landscape_z(*[float(v) for v in row["center_xy_m"]])
        trace_min = min(trace_min, z)
        trace_max = max(trace_max, z)
        _append_scree_rock(
            scree_vertices,
            scree_triangles,
            scree_uvs,
            row,
            z,
        )

    cliff_counts = _spawn_mesh(
        (
            "YACS_Component230_PCGExCliffSkin"
            if _pcgex_mesh is not None
            else "YACS_Component230_ConnectedCliffSkin"
        ),
        cliff_vertices,
        cliff_triangles,
        cliff_uvs,
        limestone,
    )
    scree_counts = _spawn_mesh(
        "YACS_Component230_Scree",
        scree_vertices,
        scree_triangles,
        scree_uvs,
        scree_material,
    )
    lighting = _mesh_receipt.get("lighting")
    _mesh_receipt = {
        "lighting": lighting,
        "generator": (
            "pcgex-clipper2"
            if _pcgex_mesh is not None
            else "yacs-connected-skin"
        ),
        "cliff": cliff_counts,
        "scree": scree_counts,
        "skin_cluster_count": int(_plan["counts"]["skin_cluster_count"]),
        "skin_cell_count": len(_plan["skin_cells"]),
        "plate_count": int(_plan["counts"]["skin_cluster_count"]),
        "scree_rock_count": len(_plan["scree_rocks"]),
        "clusters": cluster_receipts,
        "pcgex_topology": pcgex_receipt,
        "surface_contact": contact,
        "trace_z_range_cm": [trace_min, trace_max],
        "collision_enabled": False,
        "cast_dynamic_shadows": True,
        "double_sided_cliff_geometry": True,
        "material": {
            "cliff": limestone.get_path_name(),
            "matches_landscape": MATCH_LANDSCAPE_MATERIAL,
            "diagnostic_only": MATCH_LANDSCAPE_MATERIAL,
            "scree": SCREE_MATERIAL,
            "uv_world_size_m": _plan["skin_contract"]["uv_world_size_m"],
        },
    }
    unreal.AutomationLibrary.finish_loading_before_screenshot()

def _destroy_transient():
    errors = []
    try:
        _set_shadow_cache_probe(False)
    except Exception as exc:
        errors.append("VSM cache rollback: " + str(exc))
    try:
        _restore_landscape_lod()
    except Exception as exc:
        errors.append("Landscape LOD rollback: " + str(exc))
    try:
        _restore_landscape_visibility()
    except Exception as exc:
        errors.append("Landscape visibility rollback: " + str(exc))
    try:
        _restore_landscape_material()
    except Exception as exc:
        errors.append("Landscape presentation material rollback: " + str(exc))
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in list(_candidate_actors):
        try:
            actors.destroy_actor(actor)
        except Exception as exc:
            errors.append("candidate actor cleanup: " + str(exc))
    _candidate_actors.clear()
    if _camera is not None:
        try:
            actors.destroy_actor(_camera)
        except Exception as exc:
            errors.append("camera cleanup: " + str(exc))
    for actor in list(_transient_lights):
        try:
            actors.destroy_actor(actor)
        except Exception as exc:
            errors.append("light cleanup: " + str(exc))
    _transient_lights.clear()
    for actor in list(_transient_environment):
        try:
            actors.destroy_actor(actor)
        except Exception as exc:
            errors.append("environment cleanup: " + str(exc))
    _transient_environment.clear()
    for component in list(_recaptured_skylights):
        try:
            component.recapture_sky()
        except Exception as exc:
            errors.append("skylight recapture: " + str(exc))
    _recaptured_skylights.clear()
    return errors


def _write_receipt(status: str, error: str | None, *, output=None, mesh=None, captures=None):
    output = OUTPUT if output is None else output
    payload = {
        "schema_version": 1,
        "status": status,
        "exact_sha": EXPECTED_SHA,
        "map": MAP,
        "map_saved": False,
        "assets_saved": False,
        "canonical_landscape_mutation": False,
        "selector_policy_mutation": False,
        "landscape_presentation_material": _material_override_receipt,
        "landscape_mesh_diagnostic": _landscape_mesh_diagnostic,
        "terrain_erosion_trial": _terrain_trial,
        "component": _component_bounds() if _target_component else None,
        "plan_fingerprint": None if _plan is None else _plan.get("fingerprint"),
        "plan_counts": None if _plan is None else _plan.get("counts"),
        "hard_policy": None if _plan is None else _plan.get("hard_policy"),
        "mesh": _mesh_receipt if mesh is None else mesh,
        "captures": _captures if captures is None else captures,
        "diagnostic_captures": _diagnostic_captures,
        "dynamic_shadows": True,
        "shadow_bias_changed": False,
        "capture_protocol": {
            "shared_baseline": _shared_baseline,
            "shadow_cache_diagnostic": _shadow_cache_probe,
            "temporal_sequence": _temporal_sequence_receipt,
            "delay_seconds": CAPTURE_DELAY_SECONDS,
            "high_res_warmup_frames": CAPTURE_WARMUP_FRAMES,
            "prime_each_viewmode_transition": True,
            "priming_captures_per_view": 3,
            "force_lod": -1 if WHOLE_MAP_PREP else 0,
            "component_lod_override": _landscape_lod_receipt,
            "fully_load_used_textures": not bool(WHOLE_MAP_PREP),
        },
        "visual_acceptance": "PENDING_OWNER",
        "error": error,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "component230-cliff-visual-receipt.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return payload


def finish(error: str | None = None):
    global _finished
    if _finished:
        return
    _finished = True
    try:
        _finish_body(error)
    finally:
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)


def _finish_body(error: str | None = None):
    global _handle
    if _handle is not None:
        try:
            unreal.unregister_slate_post_tick_callback(_handle)
        except Exception as exc:
            error = (error + "\n" if error else "") + "capture callback cleanup: " + str(exc)
        finally:
            _handle = None
    try:
        unreal.SystemLibrary.execute_console_command(
            _world, "showflag.DynamicShadows 1"
        )
        unreal.SystemLibrary.execute_console_command(_world, "viewmode lit")
    except Exception:
        pass
    if _terrain_source is not None:
        try:
            before_cleanup = unreal.YacsLandscapeMeshDiagnosticLibrary.read_component230_heightfield(_target_component)
            (OUTPUT / "terrain-source-before-cleanup.json").write_text(before_cleanup, encoding="utf-8")
        except Exception as exc:
            error = (error + "\n" if error else "") + "pre-cleanup source diagnostic: " + str(exc)
    cleanup_errors = []
    try:
        cleanup_errors.extend(_destroy_transient())
    except Exception as exc:
        cleanup_errors.append("transient scene cleanup: " + str(exc))
    finally:
        if _whole_map_environment is not None:
            try:
                cleanup_errors.extend(_whole_map_environment.restore())
            except Exception as exc:
                cleanup_errors.append("whole-map capture environment rollback: " + str(exc))
    if cleanup_errors:
        error = (error + "\n" if error else "") + "\n".join(cleanup_errors)

    if _before_hash is not None and _digest(MAP_FILE) != _before_hash:
        error = (error + "\n" if error else "") + "accepted map hash changed"
    try:
        if _before_scene is not None and _scene_snapshot() != _before_scene:
            error = (error + "\n" if error else "") + "scene snapshot changed"
        if _terrain_source is not None:
            actual = json.loads(unreal.YacsLandscapeMeshDiagnosticLibrary.read_component230_heightfield(_target_component))
            (OUTPUT / "terrain-source-after-cleanup.json").write_text(json.dumps(actual), encoding="utf-8")
            if actual != _terrain_source:
                differences = [(i, a, b) for i, (a, b) in enumerate(zip(
                    _terrain_source.get("heights", []), actual.get("heights", []))) if a != b]
                metadata = {k: [v, actual.get(k)] for k, v in _terrain_source.items()
                            if k != "heights" and v != actual.get(k)}
                raise RuntimeError("Source Landscape heightfield changed during terrain trial: " + json.dumps(
                    {"changed_samples": len(differences), "first_changes": differences[:8],
                     "metadata": metadata, "read_error": actual.get("error")}))
            _terrain_trial.update(source_heightfield_unchanged=True,
                                  restored=not cleanup_errors and _landscape_visibility_state is None)
    except Exception as exc:
        error = (error + "\n" if error else "") + "snapshot verify: " + str(exc)

    status = "COMPONENT230_CLIFF_VISUAL_FAIL" if error else "COMPONENT230_CLIFF_VISUAL_PASS"
    try:
        payload = _write_receipt(status, error)
    except Exception as exc:
        error = (error + "\n" if error else "") + "capture receipt write: " + str(exc)
        payload = {"status": "COMPONENT230_CLIFF_VISUAL_FAIL", "error": error}
    if _survey_capture is not None:
        _survey_capture.mark_cleanup(error)
    if _detail_capture is not None:
        _detail_capture.mark_cleanup(error)
    if _whole_map_capture is not None:
        _whole_map_capture.mark_cleanup(error)
    if _paired_custom_record is not None:
        _write_receipt(status, error, output=PAIRED_CUSTOM_OUTPUT,
                       mesh=_paired_custom_record["mesh"],
                       captures=_paired_custom_record["captures"])
    if error:
        unreal.log_error("YACS_COMPONENT230_CLIFF " + json.dumps(payload, default=str))
    else:
        unreal.log("YACS_COMPONENT230_CLIFF " + json.dumps(payload, default=str))


def _begin_paired_candidate():
    global OUTPUT, _pcgex_mesh, _paired_custom_record, _captures, _mesh_receipt
    _paired_custom_record = {
        "mesh": copy.deepcopy(_mesh_receipt), "captures": copy.deepcopy(_captures)
    }
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in _candidate_actors:
        if not actors.destroy_actor(actor):
            raise RuntimeError("Could not remove custom A before PCGEx B")
    _candidate_actors.clear()
    if _scene_snapshot() != _paired_scene:
        raise RuntimeError("Paired A/B scene changed after removing custom A")
    OUTPUT = _paired_pcgex_output
    _captures = []
    for capture in _paired_custom_record["captures"]:
        if capture["candidate"]:
            continue
        source = Path(capture["path"])
        target = OUTPUT / source.name
        # Package the one actual reference frame for both consumers. This is
        # explicitly a shared acquisition, never an independent repeat proof.
        shutil.copyfile(source, target)
        if _digest(target) != capture["sha256"]:
            raise RuntimeError("Shared baseline packaging changed image bytes")
        packaged = dict(capture, path=str(target))
        _captures.append(packaged)
    _shared_baseline["custom_removed_before_pcgex"] = True
    _pcgex_mesh = _paired_pcgex_mesh
    _mesh_receipt = {"lighting": _mesh_receipt["lighting"]}


def schedule():
    global _task, _started
    view = _views[_index]
    if view.get("paired_pcgex") and _pcgex_mesh is None:
        _begin_paired_candidate()
    if int(_target_component.get_editor_property("forced_lod")) != 0:
        raise RuntimeError("Landscape component LOD drifted during capture")
    _set_shadow_cache_probe(bool(view.get("uncached_shadows")))
    if view["candidate"] and not _candidate_actors:
        _spawn_candidate()
    if view.get("review_camera"):
        camera = view["review_camera"]
        ex, ey = camera["eye_xy_m"]
        tx, ty = camera["target_xy_m"]
        eye = unreal.Vector(ex * 100.0, ey * 100.0,
            _trace_landscape_z(ex, ey) + camera["eye_height_above_accepted_landscape_cm"])
        target = unreal.Vector(tx * 100.0, ty * 100.0, _trace_landscape_z(tx, ty) + 100.0)
        _camera.set_actor_location(eye, False, False)
        _camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(eye, target), False)
        _camera.get_component_by_class(unreal.CameraComponent).set_editor_property(
            "field_of_view", camera["fov_deg"])
        if not view.get("limestone_material"):
            meshes = [a for a in _candidate_actors if isinstance(a, unreal.DynamicMeshActor)]
            if len(meshes) != 1:
                raise RuntimeError("Review requires exactly one combined mesh")
            meshes[0].get_dynamic_mesh_component().set_material(
                0, _target_component.get_editor_property("override_material"))

    unreal.SystemLibrary.execute_console_command(
        _world, "showflag.DynamicShadows 1"
    )
    unreal.SystemLibrary.execute_console_command(
        _world, "viewmode " + view["viewmode"]
    )
    modes = {
        "lit": unreal.ViewModeIndex.VMI_LIT,
        "lightingonly": unreal.ViewModeIndex.VMI_LIGHTING_ONLY,
    }
    unreal.AutomationLibrary.set_editor_viewport_view_mode(
        modes[view["viewmode"]]
    )
    unreal.AutomationLibrary.finish_loading_before_screenshot()
    if view.get("limestone_material"):
        meshes = [actor for actor in _candidate_actors
                  if isinstance(actor, unreal.DynamicMeshActor)]
        if not TERRAIN_MESH_TRIAL or len(meshes) != 1:
            raise RuntimeError("Limestone material diagnostic requires one combined mesh")
        component = meshes[0].get_dynamic_mesh_component()
        if not _terrain_trial.get("limestone_uv_projection"):
            # ExportToRawMesh defaults to proxy-bounds UVs, which stretch one
            # tile over this 63 m proxy. Reproject only the transient PBR preview
            # after neutral admission, using the existing 3 m skin contract.
            mesh = component.get_dynamic_mesh()
            triangles_before = mesh.get_triangle_count()
            tile_m = float(_plan["skin_contract"]["uv_world_size_m"])
            if tile_m != 3.0:
                raise RuntimeError("Limestone physical texture scale drifted")
            unreal.GeometryScript_UVs.set_mesh_u_vs_from_box_projection(
                mesh, 0, unreal.Transform(scale=unreal.Vector(tile_m * 100.0,
                    tile_m * 100.0, tile_m * 100.0)),
                unreal.GeometryScriptMeshSelection(), min_island_tri_count=2)
            if mesh.get_triangle_count() != triangles_before:
                raise RuntimeError("UV-only projection changed triangle count")
            _terrain_trial["limestone_uv_projection"] = {
                "method": "Epic GeometryScript box projection", "uv_channel": 0,
                "world_size_m": tile_m, "triangles_unchanged": True,
                "scope": "TRANSIENT_PBR_DIAGNOSTIC_AFTER_NEUTRAL_CAPTURE"}
        material = _load_surface_material(CLIFF_MATERIAL, "limestone")
        component.set_material(0, material)
        component.notify_mesh_modified()
        unreal.AutomationLibrary.finish_loading_before_screenshot()
    if view.get("flat_normals"):
        if not LOCAL_CLIFF_SMOOTHING or len(_candidate_actors) != 1:
            raise RuntimeError("Flat-normal diagnostic requires the local single surface")
        component = _candidate_actors[0].get_dynamic_mesh_component()
        mesh = component.get_dynamic_mesh()
        triangles_before = mesh.get_triangle_count()
        unreal.GeometryScript_Normals.set_per_face_normals(mesh)
        component.notify_mesh_modified()
        if mesh.get_triangle_count() != triangles_before:
            raise RuntimeError("Normal-only diagnostic changed triangle count")
    path = OUTPUT / (view["name"] + ".png")
    path.unlink(missing_ok=True)
    _task = unreal.AutomationLibrary.take_high_res_screenshot(
        res_x=RESOLUTION[0],
        res_y=RESOLUTION[1],
        filename=str(path),
        camera=_camera,
        mask_enabled=False,
        capture_hdr=False,
        comparison_tolerance=unreal.ComparisonTolerance.LOW,
        comparison_notes=(
            "YACS Component_230 cliff Phase 2C PCGEx A/B"
            if _pcgex_mesh is not None
            else "YACS Component_230 cliff Phase 2B visual spike"
        ),
        delay=CAPTURE_DELAY_SECONDS,
        force_game_view=True,
    )
    if not _task or not _task.is_valid_task():
        raise RuntimeError("Invalid screenshot task")
    _started = time.monotonic()


def tick(_delta):
    global _index
    if _finished or _task is None:
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
        if view.get("warmup_only", False):
            _index += 1
            schedule()
            return
        capture_list = _diagnostic_captures if view.get("diagnostic_only") else _captures
        capture_list.append(
            {
                "name": view["name"],
                "candidate": view["candidate"],
                "viewmode": view["viewmode"],
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "sha256": _digest(path),
                "resolution": list(RESOLUTION),
                "material_profile": "limestone-pbr" if view.get("limestone_material") else "neutral-fixture",
                "material_path": CLIFF_MATERIAL if view.get("limestone_material") else None,
                "review_camera": view.get("review_camera"),
                "camera_location_cm": [float(getattr(_camera.get_actor_location(), a)) for a in ("x", "y", "z")],
                "camera_rotation_deg": [float(getattr(_camera.get_actor_rotation(), a)) for a in ("pitch", "yaw", "roll")],
                "camera_fov_deg": float(_camera.get_component_by_class(unreal.CameraComponent).get_editor_property("field_of_view")),
            }
        )
        _index += 1
        if _index >= len(_views):
            if os.environ.get('YACS_SA_CALOBRA_TPP_SURVEY') == '1':
                _begin_tpp_survey()
            else:
                finish()
        else:
            schedule()
    except Exception:
        finish(traceback.format_exc())


def main():
    global _world, _landscape, _target_component, _camera, _views
    global _handle, _before_hash, _before_scene, _plan, _pcgex_mesh
    global OUTPUT, _paired_pcgex_mesh, _paired_scene
    global _whole_map_environment

    if _git_head() != EXPECTED_SHA:
        raise RuntimeError("Cliff visual exact SHA mismatch")
    if not PLAN.is_file():
        raise RuntimeError("Component_230 cliff plan is missing")
    _plan = json.loads(PLAN.read_text(encoding="utf-8"))
    if _plan.get("status") != "COMPONENT230_CLIFF_VISUAL_PLAN":
        raise RuntimeError("Invalid Component_230 cliff visual plan")
    if _plan["hard_policy"] != {
        "pavement": True,
        "shoulder_envelope": True,
        "mapped_water_buffer_m": 0.5,
        "bob": False,
        "buildings": False,
        "infrastructure": False,
        "other_unknown_lidar": False,
    }:
        raise RuntimeError("Phase 2B narrow hard-policy drift")
    if int(_plan["counts"]["component_cliff_cells"]) != 2611:
        raise RuntimeError("Phase 2B cliff count drift")

    if PCGEX_MESH is not None:
        if not PCGEX_MESH.is_file():
            raise RuntimeError("Phase 2C PCGEx mesh receipt is missing")
        _pcgex_mesh = json.loads(PCGEX_MESH.read_text(encoding="utf-8"))
        if _pcgex_mesh.get("status") != "YACS_SA_CALOBRA_PCGEX_CLIFF_MESH_PASS":
            raise RuntimeError("Invalid Phase 2C PCGEx mesh receipt")
        if _pcgex_mesh.get("pcgex_commit") != (
            "39a8f1bdc65b2c4613a1e87b71d93b4576db0a66"
        ):
            raise RuntimeError("Phase 2C PCGEx dependency drift")
        if bool(_pcgex_mesh.get("canonical_landscape_mutation")):
            raise RuntimeError("PCGEx mesh receipt claims Landscape mutation")
        if bool(_pcgex_mesh.get("assets_saved")) or bool(
            _pcgex_mesh.get("graph_saved")
        ):
            raise RuntimeError("PCGEx topology proof must be transient")
        if int(_pcgex_mesh["source_skin_cell_count"]) != len(
            _plan["skin_cells"]
        ):
            raise RuntimeError("PCGEx source cell count does not match Phase 2B plan")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    if any(OUTPUT.iterdir()):
        raise RuntimeError("Visual output directory must start empty")

    if PAIRED_CUSTOM_OUTPUT is not None:
        if (PCGEX_MESH is None or LANDSCAPE_MESH_DIAGNOSTIC
                or LOCAL_CLIFF_SMOOTHING or MATCH_LANDSCAPE_MATERIAL
                or PAIRED_CUSTOM_OUTPUT == OUTPUT):
            raise RuntimeError("Paired capture requires distinct custom/PCGEx outputs only")
        PAIRED_CUSTOM_OUTPUT.mkdir(parents=True, exist_ok=True)
        if any(PAIRED_CUSTOM_OUTPUT.iterdir()):
            raise RuntimeError("Paired custom output must start empty")
        _paired_pcgex_mesh = _pcgex_mesh
        _pcgex_mesh = None
        OUTPUT = PAIRED_CUSTOM_OUTPUT
        _shared_baseline.update(
            enabled=True, acquisition_id=str(uuid.uuid4()),
            protocol="single-scene-baseline-custom-pcgex-v1",
            source_output=str(OUTPUT), custom_removed_before_pcgex=False,
            independent_pixel_determinism_claimed=False,
        )

    _world = unreal.EditorLoadingAndSavingUtils.load_map(MAP)
    if _world is None:
        raise RuntimeError("Cannot load accepted Sa Calobra map")
    landscapes = unreal.GameplayStatics.get_all_actors_of_class(
        _world, unreal.Landscape
    )
    if len(landscapes) != 1:
        raise RuntimeError("Expected exactly one accepted Landscape")
    _landscape = landscapes[0]
    components = _landscape.get_components_by_class(
        unreal.LandscapeComponent
    )
    if len(components) != 1024:
        raise RuntimeError("Unexpected accepted Landscape topology")
    _target_component = next(
        (
            component
            for component in components
            if component.get_name() == "LandscapeComponent_230"
        ),
        None,
    )
    if _target_component is None:
        raise RuntimeError("LandscapeComponent_230 is missing")

    _before_hash = _digest(MAP_FILE)
    # Finish the accepted edit-layer composite/readbacks before defining the
    # reference. Importing another Landscape can otherwise flush pending CUT
    # readbacks on the original halfway through the comparison.
    _landscape.force_layers_full_update()
    _before_scene = _scene_snapshot()
    if WHOLE_MAP_PREP:
        from scripts.ue.sa_calobra_whole_map_prep import CaptureEnvironment
        _whole_map_environment = CaptureEnvironment(unreal, _world, _landscape)
    _fix_temporal_sequence()
    if _whole_map_environment is not None:
        _whole_map_environment.enable_adaptive()
    else:
        _pin_landscape_lod()
    _apply_neutral_landscape_material()
    lighting = _ensure_lighting()
    bounds = _component_bounds()
    origin = unreal.Vector(*bounds["origin_cm"])
    extent = unreal.Vector(*bounds["extent_cm"])
    surface_z = origin.z + extent.z * 0.35

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    _camera = actors.spawn_actor_from_class(
        unreal.CameraActor,
        unreal.Vector(
            origin.x - 2300.0,
            origin.y - 1700.0,
            surface_z + 1350.0,
        ),
        unreal.Rotator(),
        transient=True,
    )
    if _camera is None:
        raise RuntimeError("Could not create proof camera")
    target = unreal.Vector(
        origin.x + 550.0,
        origin.y + 450.0,
        surface_z,
    )
    _camera.set_actor_rotation(
        unreal.MathLibrary.find_look_at_rotation(
            _camera.get_actor_location(), target
        ),
        False,
    )
    camera_component = _camera.get_component_by_class(unreal.CameraComponent)
    camera_component.set_editor_property("field_of_view", 50.0)
    _camera.set_actor_label("YACS Component230 Cliff Proof Camera")
    unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem
    ).set_level_viewport_camera_info(
        _camera.get_actor_location(), _camera.get_actor_rotation()
    )

    unreal.SystemLibrary.execute_console_command(_world, "r.ScreenPercentage 100")
    if not WHOLE_MAP_PREP:
        unreal.SystemLibrary.execute_console_command(_world, "r.PostProcessAAQuality 6")
    unreal.SystemLibrary.execute_console_command(_world, "showflag.DynamicShadows 1")
    if not WHOLE_MAP_PREP:
        unreal.SystemLibrary.execute_console_command(_world, "r.ForceLOD 0")
    unreal.SystemLibrary.execute_console_command(
        _world, "r.Streaming.FullyLoadUsedTextures 0" if WHOLE_MAP_PREP else "r.Streaming.FullyLoadUsedTextures 1"
    )
    unreal.SystemLibrary.execute_console_command(
        _world, f"r.HighResScreenshotDelay {CAPTURE_WARMUP_FRAMES}"
    )

    _mesh_receipt["lighting"] = lighting
    if os.environ.get('YACS_WHOLE_MAP_PREP'):
        # Whole-area review owns its camera plan, all1024 material bindings and
        # adaptive LOD. It must enter before either legacy matrix or detail lane.
        _begin_whole_map_prep()
        return
    if os.environ.get('YACS_DETAIL_NATIVE'):
        # Enter before the legacy matrix tries to read its review-camera file.
        # This lane uses only the two hash-bound pilot poses.
        _begin_detail_native()
        return

    # The first offscreen screenshot can precede Landscape streaming readiness
    # even after finish_loading_before_screenshot. Render a complete camera view
    # before admitting baseline pixels; retain it as diagnostic evidence only.
    _views = [
        {
            "name": "00-streaming-prime",
            "candidate": False,
            "viewmode": "lit",
            "warmup_only": True,
        },
        {"name": "01-baseline-lit", "candidate": False, "viewmode": "lit"},
        {
            "name": "02-baseline-lighting-only",
            "candidate": False,
            "viewmode": "lightingonly",
        },
        {"name": "03-candidate-lit", "candidate": True, "viewmode": "lit"},
        {
            "name": "04-candidate-lighting-only",
            "candidate": True,
            "viewmode": "lightingonly",
        },
    ]
    if PAIRED_CUSTOM_OUTPUT is not None:
        _paired_scene = _scene_snapshot()
        _views.extend([
            {"name": "03-candidate-lit", "candidate": True,
             "viewmode": "lit", "paired_pcgex": True},
            {"name": "04-candidate-lighting-only", "candidate": True,
             "viewmode": "lightingonly", "paired_pcgex": True},
        ])
    if LOCAL_CLIFF_SMOOTHING:
        _views.extend([
            {"name": "diagnostic-uncached-shadow-lit", "candidate": True,
             "viewmode": "lit", "diagnostic_only": True, "uncached_shadows": True},
            {"name": "diagnostic-uncached-shadow-lighting-only", "candidate": True,
             "viewmode": "lightingonly", "diagnostic_only": True, "uncached_shadows": True},

            {
                "name": "05-flat-normal-lit",
                "candidate": True,
                "viewmode": "lit",
                "diagnostic_only": True,
                "flat_normals": True,
            },
            {
                "name": "06-flat-normal-lighting-only",
                "candidate": True,
                "viewmode": "lightingonly",
                "diagnostic_only": True,
            },
        ])
    if TERRAIN_MESH_TRIAL:
        _views.append({"name": "diagnostic-limestone-pbr-lit", "candidate": True,
                       "viewmode": "lit", "diagnostic_only": True, "limestone_material": True})
        camera_path = PLAN.parent / "component230-review-cameras.json"
        cameras = json.loads(camera_path.read_text(encoding="utf-8"))
        if cameras["plan_fingerprint"] != _plan["fingerprint"] or cameras["pavement_bit"] != 1:
            raise RuntimeError("Review camera source provenance mismatch")
        _terrain_trial["review_camera_recipe_sha256"] = _digest(camera_path)
        for camera in cameras["cameras"]:
            for material in ("neutral", "limestone"):
                _views.append({"name": "diagnostic-review-" + camera["name"] + "-" + material,
                    "candidate": True, "viewmode": "lit", "diagnostic_only": True,
                    "limestone_material": material == "limestone", "review_camera": camera})
    # A Lit-only prime cannot warm histories after a view-mode transition.
    # Exercise the exact scene/view once before every admitted screenshot.
    primed_views = []
    for view in _views:
        if not view.get("warmup_only"):
            for prime_index in range(3):
                prefix = "prime-" if prime_index == 2 else f"prime-{prime_index + 1}-"
                prime = dict(view, name=prefix + view["name"], warmup_only=True)
                primed_views.append(prime)
        primed_views.append(view)
    _views = primed_views
    if os.environ.get('YACS_EDGE_GEOMETRY_PREFLIGHT') == '1':
        # Reject an invalid native recipe before spending time on reference
        # renders. This transient probe does not replace any later audit.
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        probe = actors.spawn_actor_from_class(unreal.DynamicMeshActor,
            unreal.Vector(), unreal.Rotator(), transient=True)
        if probe is None:
            raise RuntimeError('Cannot create transient edge preflight mesh')
        try:
            export = json.loads(unreal.YacsLandscapeMeshDiagnosticLibrary.copy_component230(
                _target_component, probe.get_dynamic_mesh_component().get_dynamic_mesh(),
                json.dumps(dict(_plan, limestone_rounded_flow=True, limestone_local_reshape=True))))
            (OUTPUT / 'edge-native-probe.json').write_text(json.dumps(export), encoding='utf-8')
        finally:
            if not actors.destroy_actor(probe):
                raise RuntimeError('Edge preflight actor cleanup failed')
        if export.get('status') != 'NATIVE_LANDSCAPE_COMPONENT_MESH':
            raise RuntimeError('Native edge geometry preflight failed: ' + json.dumps(export))
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    schedule()
    _handle = unreal.register_slate_post_tick_callback(tick)


try:
    main()
except Exception:
    if _world is not None:
        finish(traceback.format_exc())
    raise

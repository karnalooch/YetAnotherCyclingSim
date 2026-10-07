"""Capture the Phase 2B Component_230 transient cliff visual spike.

Loads the accepted Sa Calobra map, captures baseline Lit / Lighting Only,
spawns deterministic visual-only DynamicMesh cliff plates and bounded scree,
captures the same views again, destroys all transient proof actors and verifies
the accepted map and scene snapshot are unchanged.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import traceback

import unreal


ROOT = Path(__file__).resolve().parents[2]
MAP = "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004"
MAP_FILE = ROOT / "Content/Worlds/SaCalobra/L_SaCalobraAccepted_20261004.umap"
PLAN = Path(os.environ["YACS_CLIFF_VISUAL_PLAN"]).resolve()
OUTPUT = Path(os.environ["YACS_CLIFF_VISUAL_OUTPUT"]).resolve()
EXPECTED_SHA = os.environ["YACS_CLIFF_VISUAL_EXPECTED_SHA"].strip()
RESOLUTION = (1920, 1080)
CAPTURE_DELAY_SECONDS = 1.0

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
_candidate_actors = []
_transient_lights = []
_transient_environment = []
_recaptured_skylights = []
_before_hash = None
_before_scene = None
_plan = None
_mesh_receipt = {}


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


def _make_color_material(
    color: unreal.LinearColor,
) -> unreal.MaterialInstanceDynamic:
    parent = unreal.load_asset(
        "/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"
    )
    if parent is None:
        raise RuntimeError("BasicShapeMaterial is unavailable")
    material = unreal.MaterialLibrary.create_dynamic_material_instance(
        _world, parent
    )
    material.set_vector_parameter_value("Color", color)
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
    return _extract_trace_z(
        hit,
        x_cm=x_cm,
        y_cm=y_cm,
        bottom_z_cm=bottom,
        top_z_cm=top,
    )


def _append_box_plate(
    vertices: list[unreal.Vector],
    triangles: list[unreal.IntVector],
    row: dict[str, object],
    surface_z_cm: float,
):
    x_m, y_m = [float(value) for value in row["center_xy_m"]]
    dx, dy = [float(value) for value in row["downhill_xy"]]
    tx, ty = [float(value) for value in row["tangent_xy"]]
    width = float(row["width_m"])
    height = float(row["height_m"])
    thickness = float(row["thickness_m"])
    underlap = float(row["underlap_m"])
    inset = float(row["top_inset_m"])
    outward = float(row["outward_offset_m"])

    cx = x_m + dx * outward
    cy = y_m + dy * outward
    bottom_z = surface_z_cm / 100.0 - underlap
    top_z = bottom_z + height

    front_bottom = (cx, cy)
    front_top = (cx - dx * inset, cy - dy * inset)
    back_bottom = (
        front_bottom[0] - dx * thickness,
        front_bottom[1] - dy * thickness,
    )
    back_top = (
        front_top[0] - dx * thickness,
        front_top[1] - dy * thickness,
    )
    half = width * 0.5
    top_half = half * 0.92

    points = [
        (front_bottom[0] - tx * half, front_bottom[1] - ty * half, bottom_z),
        (front_bottom[0] + tx * half, front_bottom[1] + ty * half, bottom_z),
        (front_top[0] - tx * top_half, front_top[1] - ty * top_half, top_z),
        (front_top[0] + tx * top_half, front_top[1] + ty * top_half, top_z),
        (back_bottom[0] - tx * half, back_bottom[1] - ty * half, bottom_z),
        (back_bottom[0] + tx * half, back_bottom[1] + ty * half, bottom_z),
        (back_top[0] - tx * top_half, back_top[1] - ty * top_half, top_z),
        (back_top[0] + tx * top_half, back_top[1] + ty * top_half, top_z),
    ]
    base = len(vertices)
    vertices.extend(
        unreal.Vector(px * 100.0, py * 100.0, pz * 100.0)
        for px, py, pz in points
    )
    faces = [
        (0, 1, 2), (1, 3, 2),
        (5, 4, 6), (7, 5, 6),
        (4, 0, 6), (0, 2, 6),
        (1, 5, 7), (1, 7, 3),
        (2, 3, 6), (3, 7, 6),
        (4, 5, 0), (5, 1, 0),
    ]
    triangles.extend(
        unreal.IntVector(base + a, base + b, base + c)
        for a, b, c in faces
    )


def _append_scree_rock(
    vertices: list[unreal.Vector],
    triangles: list[unreal.IntVector],
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
    for index in range(4):
        nxt = (index + 1) % 4
        triangles.append(unreal.IntVector(base + index, base + nxt, base + 4))
        triangles.append(unreal.IntVector(base + nxt, base + index, base + 5))


def _spawn_mesh(
    label: str,
    vertices: list[unreal.Vector],
    triangles: list[unreal.IntVector],
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
    dynamic_mesh.reset()
    dynamic_mesh.append_buffers_to_mesh(
        buffers,
        material_id=0,
        defer_change_notifications=True,
    )
    dynamic_mesh.recompute_normals(
        unreal.GeometryScriptCalculateNormalsOptions(),
        defer_change_notifications=True,
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


def _spawn_candidate():
    global _mesh_receipt
    if _candidate_actors:
        return

    limestone = _make_color_material(
        unreal.LinearColor(0.54, 0.55, 0.52, 1.0)
    )
    scree_material = _make_color_material(
        unreal.LinearColor(0.43, 0.43, 0.40, 1.0)
    )

    cliff_vertices: list[unreal.Vector] = []
    cliff_triangles: list[unreal.IntVector] = []
    trace_min = float("inf")
    trace_max = float("-inf")
    for row in _plan["plates"]:
        z = _trace_landscape_z(*[float(v) for v in row["center_xy_m"]])
        trace_min = min(trace_min, z)
        trace_max = max(trace_max, z)
        _append_box_plate(cliff_vertices, cliff_triangles, row, z)

    scree_vertices: list[unreal.Vector] = []
    scree_triangles: list[unreal.IntVector] = []
    for row in _plan["scree_rocks"]:
        z = _trace_landscape_z(*[float(v) for v in row["center_xy_m"]])
        trace_min = min(trace_min, z)
        trace_max = max(trace_max, z)
        _append_scree_rock(scree_vertices, scree_triangles, row, z)

    cliff_counts = _spawn_mesh(
        "YACS_Component230_CliffSheets",
        cliff_vertices,
        cliff_triangles,
        limestone,
    )
    scree_counts = _spawn_mesh(
        "YACS_Component230_Scree",
        scree_vertices,
        scree_triangles,
        scree_material,
    )
    lighting = _mesh_receipt.get("lighting")
    _mesh_receipt = {
        "lighting": lighting,
        "cliff": cliff_counts,
        "scree": scree_counts,
        "plate_count": len(_plan["plates"]),
        "scree_rock_count": len(_plan["scree_rocks"]),
        "trace_z_range_cm": [trace_min, trace_max],
        "collision_enabled": False,
        "cast_dynamic_shadows": True,
        "material": "transient pale-limestone proof proxy",
    }
    unreal.AutomationLibrary.finish_loading_before_screenshot()


def _destroy_transient():
    errors = []
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


def _write_receipt(status: str, error: str | None):
    payload = {
        "schema_version": 1,
        "status": status,
        "exact_sha": EXPECTED_SHA,
        "map": MAP,
        "map_saved": False,
        "assets_saved": False,
        "canonical_landscape_mutation": False,
        "selector_policy_mutation": False,
        "component": _component_bounds() if _target_component else None,
        "plan_fingerprint": None if _plan is None else _plan.get("fingerprint"),
        "plan_counts": None if _plan is None else _plan.get("counts"),
        "hard_policy": None if _plan is None else _plan.get("hard_policy"),
        "mesh": _mesh_receipt,
        "captures": _captures,
        "dynamic_shadows": True,
        "shadow_bias_changed": False,
        "visual_acceptance": "PENDING_OWNER",
        "error": error,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "component230-cliff-visual-receipt.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return payload


def finish(error: str | None = None):
    global _handle, _finished
    if _finished:
        return
    _finished = True
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
    try:
        unreal.SystemLibrary.execute_console_command(
            _world, "showflag.DynamicShadows 1"
        )
        unreal.SystemLibrary.execute_console_command(_world, "viewmode lit")
    except Exception:
        pass
    cleanup_errors = _destroy_transient()
    if cleanup_errors:
        error = (error + "\n" if error else "") + "\n".join(cleanup_errors)

    if _before_hash is not None and _digest(MAP_FILE) != _before_hash:
        error = (error + "\n" if error else "") + "accepted map hash changed"
    try:
        if _before_scene is not None and _scene_snapshot() != _before_scene:
            error = (error + "\n" if error else "") + "scene snapshot changed"
    except Exception as exc:
        error = (error + "\n" if error else "") + "snapshot verify: " + str(exc)

    status = "COMPONENT230_CLIFF_VISUAL_FAIL" if error else "COMPONENT230_CLIFF_VISUAL_PASS"
    payload = _write_receipt(status, error)
    if error:
        unreal.log_error("YACS_COMPONENT230_CLIFF " + json.dumps(payload, default=str))
    else:
        unreal.log("YACS_COMPONENT230_CLIFF " + json.dumps(payload, default=str))
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)


def schedule():
    global _task, _started
    view = _views[_index]
    if view["candidate"] and not _candidate_actors:
        _spawn_candidate()

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
        comparison_notes="YACS Component_230 cliff Phase 2B visual spike",
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
        _captures.append(
            {
                "name": view["name"],
                "candidate": view["candidate"],
                "viewmode": view["viewmode"],
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "sha256": _digest(path),
                "resolution": list(RESOLUTION),
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
    global _world, _landscape, _target_component, _camera, _views
    global _handle, _before_hash, _before_scene, _plan

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

    OUTPUT.mkdir(parents=True, exist_ok=True)
    if any(OUTPUT.iterdir()):
        raise RuntimeError("Visual output directory must start empty")

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
    _before_scene = _scene_snapshot()
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

    unreal.SystemLibrary.execute_console_command(_world, "r.ScreenPercentage 100")
    unreal.SystemLibrary.execute_console_command(_world, "r.PostProcessAAQuality 6")
    unreal.SystemLibrary.execute_console_command(_world, "showflag.DynamicShadows 1")

    _views = [
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
    _mesh_receipt["lighting"] = lighting
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    schedule()
    _handle = unreal.register_slate_post_tick_callback(tick)


try:
    main()
except Exception:
    if _world is not None:
        finish(traceback.format_exc())
    raise

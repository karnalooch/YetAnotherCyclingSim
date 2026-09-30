"""Render a cyclist-height proof of the persisted official SP638 road spline."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import time
import traceback

import unreal


SPIKE_MAP = "/Game/Prototype/Maps/L_PassoGiauTerrainSpike"
CAPTURE_RES_X = 3840
CAPTURE_RES_Y = 2160
PROOF_AA_QUALITY = 6
EYE_HEIGHT_CM = 160.0
CAMERA_BACK_CM = 2500.0
LOOK_AHEAD_CM = 4500.0
CURVATURE_SAMPLE_STEP_CM = 5000.0
CURVATURE_HALF_WINDOW_CM = 2500.0
END_MARGIN_CM = 10000.0

_task = None
_tick_handle = None
_started_at = 0.0
_output_path: Path | None = None
_proof_path: Path | None = None
_camera = None
_proof_data: dict[str, object] = {}


def _finish(success: bool, error: str = "") -> None:
    global _tick_handle
    if _tick_handle is not None:
        unreal.unregister_slate_post_tick_callback(_tick_handle)
        _tick_handle = None

    if success and _output_path is not None and _proof_path is not None:
        proof = {
            "schema_version": 1,
            "passo_giau_sp638_rider_capture": "PASS",
            "map": SPIKE_MAP,
            "screenshot": str(_output_path),
            "screenshot_bytes": _output_path.stat().st_size,
            "resolution": [CAPTURE_RES_X, CAPTURE_RES_Y],
            "camera_height_above_road_cm": EYE_HEIGHT_CM,
            "capture_strategy": "rider-height-max-curvature-road-proof",
            "proof_aa_method": "FXAA",
            "post_process_aa_quality": PROOF_AA_QUALITY,
            "visual_acceptance": "PENDING_HUMAN_REVIEW",
            "presentation_only": True,
            "authoritative_route_geometry": False,
            "authoritative_physics": False,
            **_proof_data,
        }
        _proof_path.parent.mkdir(parents=True, exist_ok=True)
        _proof_path.write_text(
            json.dumps(proof, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        unreal.log(
            f"[PassoGiauRoadCapture] PASS: {_output_path} "
            f"({_output_path.stat().st_size} bytes)"
        )
    elif error:
        unreal.log_error(f"[PassoGiauRoadCapture] FAILURE: {error}")

    unreal.EditorPythonScripting.set_keep_python_script_alive(False)


def _tick(_delta_time: float) -> None:
    if _task is None:
        _finish(False, "screenshot task was not initialized")
        return

    if _task.is_task_done():
        if (
            _output_path is not None
            and _output_path.is_file()
            and _output_path.stat().st_size >= 100_000
        ):
            _finish(True)
        else:
            _finish(False, "screenshot task completed without a valid PNG")
        return

    if time.monotonic() - _started_at > 90.0:
        _finish(False, "screenshot task timed out after 90 seconds")


def _dot(a: unreal.Vector, b: unreal.Vector) -> float:
    return float(a.x * b.x + a.y * b.y + a.z * b.z)


def _find_road_spline(
    world: unreal.World,
) -> tuple[unreal.Actor, unreal.SplineComponent, int]:
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    candidates: list[tuple[unreal.Actor, unreal.SplineComponent, int]] = []
    for actor in actor_subsystem.get_all_level_actors():
        spline_components = list(actor.get_components_by_class(unreal.SplineComponent))
        for spline in spline_components:
            point_count = int(spline.get_number_of_spline_points())
            if point_count >= 50:
                candidates.append((actor, spline, point_count))

    if len(candidates) != 1:
        labels = [
            f"{actor.get_actor_label()}:{count}"
            for actor, _spline, count in candidates
        ]
        raise RuntimeError(
            "expected exactly one persisted road spline with >=50 points, "
            f"found {len(candidates)}: {labels}"
        )
    return candidates[0]


def _choose_hairpin_distance(spline: unreal.SplineComponent) -> tuple[float, float]:
    length = float(spline.get_spline_length())
    if length <= 2.0 * END_MARGIN_CM:
        raise RuntimeError(f"road spline is unexpectedly short: {length:.1f} cm")

    best_distance = END_MARGIN_CM
    best_score = -1.0
    distance = END_MARGIN_CM
    while distance <= length - END_MARGIN_CM:
        before = spline.get_direction_at_distance_along_spline(
            max(0.0, distance - CURVATURE_HALF_WINDOW_CM),
            unreal.SplineCoordinateSpace.WORLD,
        )
        after = spline.get_direction_at_distance_along_spline(
            min(length, distance + CURVATURE_HALF_WINDOW_CM),
            unreal.SplineCoordinateSpace.WORLD,
        )
        score = 1.0 - max(-1.0, min(1.0, _dot(before, after)))
        if score > best_score:
            best_score = score
            best_distance = distance
        distance += CURVATURE_SAMPLE_STEP_CM

    return best_distance, best_score


def main() -> None:
    global _task, _tick_handle, _started_at, _output_path, _proof_path, _camera
    global _proof_data

    output_value = os.environ.get("YACS_PASSO_GIAU_ROAD_CAPTURE_PNG", "")
    proof_value = os.environ.get("YACS_PASSO_GIAU_ROAD_CAPTURE_PROOF", "")
    if not output_value or not proof_value:
        raise RuntimeError(
            "YACS_PASSO_GIAU_ROAD_CAPTURE_PNG and "
            "YACS_PASSO_GIAU_ROAD_CAPTURE_PROOF are required"
        )

    _output_path = Path(output_value)
    _proof_path = Path(proof_value)
    _output_path.parent.mkdir(parents=True, exist_ok=True)
    _output_path.unlink(missing_ok=True)
    _proof_path.unlink(missing_ok=True)

    world = unreal.EditorLoadingAndSavingUtils.load_map(SPIKE_MAP)
    if not world:
        raise RuntimeError(f"failed to load {SPIKE_MAP}")

    landscapes = list(
        unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    )
    if len(landscapes) != 1:
        raise RuntimeError(f"expected exactly one Landscape, found {len(landscapes)}")
    landscape_components = list(
        landscapes[0].get_components_by_class(unreal.LandscapeComponent)
    )
    if len(landscape_components) != 1024:
        raise RuntimeError(
            f"expected 1024 Landscape components, found {len(landscape_components)}"
        )
    for component in landscape_components:
        component.set_forced_lod(0)
        component.set_lod_bias(0)

    road_actor, spline, control_count = _find_road_spline(world)
    spline_meshes = list(
        road_actor.get_components_by_class(unreal.SplineMeshComponent)
    )
    if len(spline_meshes) != control_count - 1:
        raise RuntimeError(
            "persisted road spline-mesh count mismatch: "
            f"controls={control_count} meshes={len(spline_meshes)}"
        )

    spline_length_cm = float(spline.get_spline_length())
    focus_distance_cm, curvature_score = _choose_hairpin_distance(spline)
    camera_distance_cm = max(0.0, focus_distance_cm - CAMERA_BACK_CM)
    target_distance_cm = min(
        spline_length_cm,
        focus_distance_cm + LOOK_AHEAD_CM,
    )
    road_camera = spline.get_location_at_distance_along_spline(
        camera_distance_cm,
        unreal.SplineCoordinateSpace.WORLD,
    )
    road_target = spline.get_location_at_distance_along_spline(
        target_distance_cm,
        unreal.SplineCoordinateSpace.WORLD,
    )
    camera_location = unreal.Vector(
        road_camera.x,
        road_camera.y,
        road_camera.z + EYE_HEIGHT_CM,
    )
    target = unreal.Vector(
        road_target.x,
        road_target.y,
        road_target.z + 80.0,
    )
    camera_rotation = unreal.MathLibrary.find_look_at_rotation(
        camera_location,
        target,
    )

    unreal.SystemLibrary.execute_console_command(
        world,
        "r.RayTracing.Geometry.Landscape.LODBias -1",
    )
    unreal.SystemLibrary.execute_console_command(world, "viewmode lit")
    unreal.SystemLibrary.execute_console_command(world, "r.AntiAliasingMethod 1")
    unreal.SystemLibrary.execute_console_command(
        world,
        f"r.PostProcessAAQuality {PROOF_AA_QUALITY}",
    )
    unreal.SystemLibrary.execute_console_command(world, "r.ScreenPercentage 100")

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    sun = actor_subsystem.spawn_actor_from_class(
        unreal.DirectionalLight,
        camera_location + unreal.Vector(0.0, 0.0, 200000.0),
        unreal.Rotator(pitch=-28.0, yaw=-42.0, roll=0.0),
        transient=True,
    )
    sun.set_actor_label("PassoGiauRoad_ProofSun")
    sun_component = sun.get_component_by_class(unreal.DirectionalLightComponent)
    sun_component.set_intensity(6.0)
    sun_component.set_cast_shadows(True)

    sky = actor_subsystem.spawn_actor_from_class(
        unreal.SkyLight,
        camera_location + unreal.Vector(0.0, 0.0, 100000.0),
        unreal.Rotator(),
        transient=True,
    )
    sky.set_actor_label("PassoGiauRoad_ProofSky")
    sky.get_component_by_class(unreal.SkyLightComponent).set_intensity(1.0)

    atmosphere = actor_subsystem.spawn_actor_from_class(
        unreal.SkyAtmosphere,
        unreal.Vector(),
        unreal.Rotator(),
        transient=True,
    )
    atmosphere.set_actor_label("PassoGiauRoad_ProofAtmosphere")

    fog = actor_subsystem.spawn_actor_from_class(
        unreal.ExponentialHeightFog,
        camera_location,
        unreal.Rotator(),
        transient=True,
    )
    fog.set_actor_label("PassoGiauRoad_ProofFog")
    fog_component = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    fog_component.set_editor_property("fog_density", 0.00025)
    fog_component.set_editor_property("fog_height_falloff", 0.2)
    fog_component.set_editor_property("fog_max_opacity", 0.2)

    _camera = actor_subsystem.spawn_actor_from_class(
        unreal.CameraActor,
        camera_location,
        camera_rotation,
        transient=True,
    )
    _camera.set_actor_label("PassoGiauRoad_RiderProofCamera")
    camera_component = _camera.get_component_by_class(unreal.CameraComponent)
    if camera_component is None:
        raise RuntimeError("spawned CameraActor has no CameraComponent")
    camera_component.set_editor_property("field_of_view", 78.0)

    _proof_data = {
        "road_actor_label": road_actor.get_actor_label(),
        "road_control_points": control_count,
        "road_spline_mesh_segments": len(spline_meshes),
        "road_spline_length_m": round(spline_length_cm / 100.0, 3),
        "selected_hairpin_distance_m": round(focus_distance_cm / 100.0, 3),
        "curvature_score": round(curvature_score, 6),
        "camera_location_cm": [
            float(camera_location.x),
            float(camera_location.y),
            float(camera_location.z),
        ],
        "camera_rotation_deg": [
            float(camera_rotation.pitch),
            float(camera_rotation.yaw),
            float(camera_rotation.roll),
        ],
        "landscape_component_count": len(landscape_components),
        "forced_landscape_lod": 0,
        "proof_viewmode": "lit",
    }

    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    _task = unreal.AutomationLibrary.take_high_res_screenshot(
        res_x=CAPTURE_RES_X,
        res_y=CAPTURE_RES_Y,
        filename=str(_output_path),
        camera=_camera,
        mask_enabled=False,
        capture_hdr=False,
        comparison_tolerance=unreal.ComparisonTolerance.LOW,
        comparison_notes="Stage 3G R4.1 official SP638 cyclist-height road proof",
        delay=2.0,
        force_game_view=True,
    )
    if not _task or not _task.is_valid_task():
        raise RuntimeError("AutomationLibrary returned an invalid screenshot task")

    _started_at = time.monotonic()
    _tick_handle = unreal.register_slate_post_tick_callback(_tick)
    unreal.log(
        "[PassoGiauRoadCapture] screenshot scheduled: "
        f"spline_m={spline_length_cm / 100.0:.1f} "
        f"focus_m={focus_distance_cm / 100.0:.1f} "
        f"curvature={curvature_score:.4f} "
        f"controls={control_count} meshes={len(spline_meshes)}"
    )


try:
    main()
except Exception as exc:
    unreal.log_error(f"[PassoGiauRoadCapture] FAILURE: {exc}")
    unreal.log_error(traceback.format_exc())
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)
    raise

"""Render a bounded SP638 hairpin proof with one roadside alpine house.

Loads the persisted Passo Giau map, selects the highest-curvature road slice,
temporarily deforms the Landscape, draws a neutral road/shoulder proof, places
one deterministic transient alpine chalet beside the road, and captures a
cyclist-height 4K PNG. Nothing is saved back to the map.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import sys
import time
import traceback

import unreal


REPO_ROOT = Path(__file__).resolve().parents[2]
UE_HELPERS = REPO_ROOT / "scripts" / "ue"
if str(UE_HELPERS) not in sys.path:
    sys.path.insert(0, str(UE_HELPERS))

import yacs_scene_composer  # noqa: E402


SPIKE_MAP = "/Game/Prototype/Maps/L_PassoGiauTerrainSpike"
GROVE_PRESET_PATH = (
    REPO_ROOT / "worldgen" / "presets" / "alpine_roadside_grove_v1.json"
)
CAPTURE_RES_X = 3840
CAPTURE_RES_Y = 2160
PROOF_AA_QUALITY = 6

SLICE_HALF_LENGTH_CM = 35000.0
SLICE_POINT_STEP_CM = 1000.0
MESH_SEGMENT_CM = 500.0
ROAD_HALF_WIDTH_CM = 300.0
SHOULDER_HALF_WIDTH_CM = 500.0
LANDSCAPE_SPLINE_WIDTH_CM = 520.0
LANDSCAPE_SPLINE_FALLOFF_CM = 1600.0
LANDSCAPE_SPLINE_SUBDIVISIONS = 240
ROAD_SURFACE_LIFT_CM = 18.0
SHOULDER_SURFACE_LIFT_CM = 5.0

HOUSE_ROAD_OFFSET_CM = 1200.0
HOUSE_ALONG_ROAD_OFFSET_CM = 1200.0
HOUSE_BODY_LENGTH_CM = 800.0
HOUSE_BODY_WIDTH_CM = 600.0
HOUSE_BODY_HEIGHT_CM = 420.0
HOUSE_FOUNDATION_DEPTH_CM = 900.0
HOUSE_FOUNDATION_TOP_CM = 120.0
HOUSE_ROOF_PITCH_DEG = 32.0

EYE_HEIGHT_CM = 160.0
CAMERA_BACK_CM = 3500.0
LOOK_AHEAD_CM = 2500.0
CURVATURE_SAMPLE_STEP_CM = 2500.0
CURVATURE_HALF_WINDOW_CM = 2500.0
END_MARGIN_CM = 10000.0

_task = None
_tick_handle = None
_started_at = 0.0
_output_path: Path | None = None
_proof_path: Path | None = None
_camera = None
_pcg_volume = None
_pcg_component = None
_pcg_ready = False
_proof_data: dict[str, object] = {}


def _finish(success: bool, error: str = "") -> None:
    global _tick_handle
    if _tick_handle is not None:
        unreal.unregister_slate_post_tick_callback(_tick_handle)
        _tick_handle = None

    if success and _output_path is not None and _proof_path is not None:
        proof = {
            "schema_version": 1,
            "passo_giau_roadside_house_capture": "PASS",
            "yacs_world_authoring_library": "PASS",
            "map": SPIKE_MAP,
            "screenshot": str(_output_path),
            "screenshot_bytes": _output_path.stat().st_size,
            "resolution": [CAPTURE_RES_X, CAPTURE_RES_Y],
            "capture_strategy": "r4.1-world-authoring-library-house-grove-proof",
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
            f"[PassoGiauRoadsideHouse] PASS: {_output_path} "
            f"({_output_path.stat().st_size} bytes)"
        )
    elif error:
        unreal.log_error(f"[PassoGiauRoadsideHouse] FAILURE: {error}")

    unreal.EditorPythonScripting.set_keep_python_script_alive(False)


def _schedule_screenshot() -> None:
    global _task, _started_at
    if _camera is None or _output_path is None:
        _finish(False, "camera/output is unavailable for screenshot scheduling")
        return
    _task = unreal.AutomationLibrary.take_high_res_screenshot(
        res_x=CAPTURE_RES_X,
        res_y=CAPTURE_RES_Y,
        filename=str(_output_path),
        camera=_camera,
        mask_enabled=False,
        capture_hdr=False,
        comparison_tolerance=unreal.ComparisonTolerance.LOW,
        comparison_notes=(
            "YACS World Authoring Library: SP638 house + real PCG alpine grove proof"
        ),
        delay=3.0,
        force_game_view=True,
    )
    if not _task or not _task.is_valid_task():
        _finish(False, "AutomationLibrary returned an invalid screenshot task")
        return
    _started_at = time.monotonic()
    unreal.log("[PassoGiauRoadsideHouse] PCG generation complete; screenshot scheduled")


def _tick(_delta_time: float) -> None:
    global _pcg_ready

    if not _pcg_ready:
        if _pcg_component is None or _pcg_volume is None:
            _finish(False, "PCG patch backend was not initialized")
            return

        try:
            generating = bool(_pcg_component.is_generating())
        except Exception:
            generating = False
        try:
            generated = bool(_pcg_component.get_editor_property("generated"))
        except Exception:
            generated = not generating

        if generating or not generated:
            if time.monotonic() - _started_at > 90.0:
                _finish(False, "PCG patch generation timed out after 90 seconds")
            return

        actual_instances = yacs_scene_composer.count_pcg_instances(_pcg_volume)
        expected_instances = int(_proof_data["forest"]["tree_count"])
        _proof_data["forest"]["pcg_contract"]["generated"] = True
        _proof_data["forest"]["pcg_contract"][
            "instanced_mesh_instances"
        ] = actual_instances
        if actual_instances != expected_instances:
            _finish(
                False,
                "PCG patch instance count mismatch: "
                f"expected={expected_instances} actual={actual_instances}",
            )
            return

        _pcg_ready = True
        _schedule_screenshot()
        return

    if _task is None:
        _finish(False, "screenshot task was not initialized after PCG generation")
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


def _find_road_spline() -> tuple[unreal.Actor, unreal.SplineComponent, int]:
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    candidates: list[tuple[unreal.Actor, unreal.SplineComponent, int]] = []
    for actor in actor_subsystem.get_all_level_actors():
        for spline in actor.get_components_by_class(unreal.SplineComponent):
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


def _sample_slice(
    spline: unreal.SplineComponent,
    start_cm: float,
    end_cm: float,
    step_cm: float,
) -> list[unreal.Vector]:
    points: list[unreal.Vector] = []
    distance = start_cm
    while distance < end_cm:
        points.append(
            spline.get_location_at_distance_along_spline(
                distance,
                unreal.SplineCoordinateSpace.WORLD,
            )
        )
        distance += step_cm
    points.append(
        spline.get_location_at_distance_along_spline(
            end_cm,
            unreal.SplineCoordinateSpace.WORLD,
        )
    )
    return points


def _replace_with_slice(
    spline: unreal.SplineComponent,
    points: list[unreal.Vector],
) -> None:
    spline.clear_spline_points(False)
    for index, point in enumerate(points):
        spline.add_spline_point(point, unreal.SplineCoordinateSpace.WORLD, False)
        spline.set_spline_point_type(
            index,
            unreal.SplinePointType.CURVE_CLAMPED,
            False,
        )
    spline.set_closed_loop(False, False)
    spline.update_spline()


def _make_material(
    world: unreal.World,
    parent: unreal.MaterialInterface,
    color: unreal.LinearColor,
):
    material = unreal.MaterialLibrary.create_dynamic_material_instance(world, parent)
    material.set_vector_parameter_value("Color", color)
    return material


def _spawn_box_strip(
    actor_subsystem: unreal.EditorActorSubsystem,
    cube_mesh: unreal.StaticMesh,
    material,
    spline: unreal.SplineComponent,
    half_width_cm: float,
    lift_cm: float,
    thickness_cm: float,
    prefix: str,
) -> int:
    length = float(spline.get_spline_length())
    count = 0
    distance = 0.0
    while distance < length:
        end_distance = min(length, distance + MESH_SEGMENT_CM)
        start = spline.get_location_at_distance_along_spline(
            distance,
            unreal.SplineCoordinateSpace.WORLD,
        )
        end = spline.get_location_at_distance_along_spline(
            end_distance,
            unreal.SplineCoordinateSpace.WORLD,
        )
        dx = float(end.x - start.x)
        dy = float(end.y - start.y)
        dz = float(end.z - start.z)
        horizontal = max(1.0, math.hypot(dx, dy))
        segment_length = max(1.0, math.sqrt(dx * dx + dy * dy + dz * dz))
        midpoint = unreal.Vector(
            (start.x + end.x) * 0.5,
            (start.y + end.y) * 0.5,
            (start.z + end.z) * 0.5 + lift_cm - thickness_cm * 0.5,
        )
        rotation = unreal.Rotator(
            pitch=math.degrees(math.atan2(dz, horizontal)),
            yaw=math.degrees(math.atan2(dy, dx)),
            roll=0.0,
        )
        actor = actor_subsystem.spawn_actor_from_class(
            unreal.StaticMeshActor,
            midpoint,
            rotation,
            transient=True,
        )
        actor.set_actor_label(f"{prefix}_{count:04d}")
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        if component is None:
            raise RuntimeError(f"{prefix}: spawned StaticMeshActor has no component")
        component.set_static_mesh(cube_mesh)
        if material is not None:
            component.set_material(0, material)
        component.set_cast_shadow(True)
        actor.set_actor_scale3d(
            unreal.Vector(
                segment_length / 100.0 * 1.08,
                (half_width_cm * 2.0) / 100.0,
                thickness_cm / 100.0,
            )
        )
        count += 1
        distance = end_distance
    return count


def _spawn_box(
    actor_subsystem: unreal.EditorActorSubsystem,
    cube_mesh: unreal.StaticMesh,
    material,
    location: unreal.Vector,
    rotation: unreal.Rotator,
    size_cm: tuple[float, float, float],
    label: str,
) -> unreal.StaticMeshActor:
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.StaticMeshActor,
        location,
        rotation,
        transient=True,
    )
    actor.set_actor_label(label)
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    if component is None:
        raise RuntimeError(f"{label}: spawned StaticMeshActor has no component")
    component.set_static_mesh(cube_mesh)
    if material is not None:
        component.set_material(0, material)
    component.set_cast_shadow(True)
    actor.set_actor_scale3d(
        unreal.Vector(
            size_cm[0] / 100.0,
            size_cm[1] / 100.0,
            size_cm[2] / 100.0,
        )
    )
    return actor


def _spawn_alpine_house(
    actor_subsystem: unreal.EditorActorSubsystem,
    cube_mesh: unreal.StaticMesh,
    world: unreal.World,
    basic_material,
    spline: unreal.SplineComponent,
    focus_cm: float,
) -> dict[str, object]:
    length = float(spline.get_spline_length())
    placement_cm = min(
        max(1000.0, focus_cm + HOUSE_ALONG_ROAD_OFFSET_CM),
        max(1000.0, length - 1000.0),
    )
    road = spline.get_location_at_distance_along_spline(
        placement_cm,
        unreal.SplineCoordinateSpace.WORLD,
    )
    tangent = spline.get_direction_at_distance_along_spline(
        placement_cm,
        unreal.SplineCoordinateSpace.WORLD,
    )
    before = spline.get_direction_at_distance_along_spline(
        max(0.0, placement_cm - 1200.0),
        unreal.SplineCoordinateSpace.WORLD,
    )
    after = spline.get_direction_at_distance_along_spline(
        min(length, placement_cm + 1200.0),
        unreal.SplineCoordinateSpace.WORLD,
    )
    turn_cross_z = float(before.x * after.y - before.y * after.x)

    if turn_cross_z >= 0.0:
        normal_x = float(tangent.y)
        normal_y = float(-tangent.x)
        outside_side = "right"
    else:
        normal_x = float(-tangent.y)
        normal_y = float(tangent.x)
        outside_side = "left"

    normal_len = max(1.0e-6, math.hypot(normal_x, normal_y))
    normal_x /= normal_len
    normal_y /= normal_len

    yaw = math.degrees(math.atan2(float(tangent.y), float(tangent.x)))
    house_x = float(road.x) + normal_x * HOUSE_ROAD_OFFSET_CM
    house_y = float(road.y) + normal_y * HOUSE_ROAD_OFFSET_CM

    foundation_top_z = float(road.z) + HOUSE_FOUNDATION_TOP_CM
    foundation_center_z = foundation_top_z - HOUSE_FOUNDATION_DEPTH_CM * 0.5
    body_base_z = foundation_top_z
    body_center_z = body_base_z + HOUSE_BODY_HEIGHT_CM * 0.5
    roof_base_z = body_base_z + HOUSE_BODY_HEIGHT_CM

    stone_material = None
    wood_material = None
    roof_material = None
    trim_material = None
    window_material = None
    if basic_material is not None:
        stone_material = _make_material(
            world,
            basic_material,
            unreal.LinearColor(0.22, 0.23, 0.24, 1.0),
        )
        wood_material = _make_material(
            world,
            basic_material,
            unreal.LinearColor(0.22, 0.075, 0.025, 1.0),
        )
        roof_material = _make_material(
            world,
            basic_material,
            unreal.LinearColor(0.15, 0.025, 0.018, 1.0),
        )
        trim_material = _make_material(
            world,
            basic_material,
            unreal.LinearColor(0.055, 0.025, 0.012, 1.0),
        )
        window_material = _make_material(
            world,
            basic_material,
            unreal.LinearColor(0.95, 0.58, 0.16, 1.0),
        )

    base_rotation = unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0)
    parts: list[unreal.StaticMeshActor] = []

    parts.append(
        _spawn_box(
            actor_subsystem,
            cube_mesh,
            stone_material,
            unreal.Vector(house_x, house_y, foundation_center_z),
            base_rotation,
            (900.0, 700.0, HOUSE_FOUNDATION_DEPTH_CM),
            "YACS_HOUSE_Foundation",
        )
    )
    parts.append(
        _spawn_box(
            actor_subsystem,
            cube_mesh,
            wood_material,
            unreal.Vector(house_x, house_y, body_center_z),
            base_rotation,
            (HOUSE_BODY_LENGTH_CM, HOUSE_BODY_WIDTH_CM, HOUSE_BODY_HEIGHT_CM),
            "YACS_HOUSE_Body",
        )
    )

    roof_half_width_cm = 385.0
    roof_lift_cm = 105.0
    for index, sign in enumerate((-1.0, 1.0)):
        local_y = sign * 190.0
        world_dx = -normal_x * local_y
        world_dy = -normal_y * local_y
        parts.append(
            _spawn_box(
                actor_subsystem,
                cube_mesh,
                roof_material,
                unreal.Vector(
                    house_x + world_dx,
                    house_y + world_dy,
                    roof_base_z + roof_lift_cm,
                ),
                unreal.Rotator(
                    pitch=0.0,
                    yaw=yaw,
                    roll=sign * HOUSE_ROOF_PITCH_DEG,
                ),
                (920.0, roof_half_width_cm, 38.0),
                f"YACS_HOUSE_Roof_{index}",
            )
        )

    road_facing_x = house_x - normal_x * (HOUSE_BODY_WIDTH_CM * 0.5 + 14.0)
    road_facing_y = house_y - normal_y * (HOUSE_BODY_WIDTH_CM * 0.5 + 14.0)
    inward_x = -normal_x
    inward_y = -normal_y
    tangent_x = float(tangent.x)
    tangent_y = float(tangent.y)
    tangent_len = max(1.0e-6, math.hypot(tangent_x, tangent_y))
    tangent_x /= tangent_len
    tangent_y /= tangent_len

    parts.append(
        _spawn_box(
            actor_subsystem,
            cube_mesh,
            trim_material,
            unreal.Vector(
                road_facing_x,
                road_facing_y,
                body_base_z + 125.0,
            ),
            base_rotation,
            (150.0, 22.0, 250.0),
            "YACS_HOUSE_Door",
        )
    )

    for index, along in enumerate((-220.0, 220.0)):
        parts.append(
            _spawn_box(
                actor_subsystem,
                cube_mesh,
                window_material,
                unreal.Vector(
                    road_facing_x + tangent_x * along,
                    road_facing_y + tangent_y * along,
                    body_base_z + 255.0,
                ),
                base_rotation,
                (125.0, 18.0, 115.0),
                f"YACS_HOUSE_Window_{index}",
            )
        )

    chimney_x = house_x + tangent_x * 220.0 + inward_x * 95.0
    chimney_y = house_y + tangent_y * 220.0 + inward_y * 95.0
    parts.append(
        _spawn_box(
            actor_subsystem,
            cube_mesh,
            stone_material,
            unreal.Vector(chimney_x, chimney_y, roof_base_z + 235.0),
            base_rotation,
            (95.0, 95.0, 300.0),
            "YACS_HOUSE_Chimney",
        )
    )

    return {
        "location_cm": [house_x, house_y, body_base_z],
        "road_anchor_cm": [float(road.x), float(road.y), float(road.z)],
        "road_offset_m": HOUSE_ROAD_OFFSET_CM / 100.0,
        "placement_distance_m": placement_cm / 100.0,
        "outside_side": outside_side,
        "turn_cross_z": turn_cross_z,
        "yaw_deg": yaw,
        "part_count": len(parts),
        "transient": True,
        "saved_to_map": False,
        "body_size_m": [
            HOUSE_BODY_LENGTH_CM / 100.0,
            HOUSE_BODY_WIDTH_CM / 100.0,
            HOUSE_BODY_HEIGHT_CM / 100.0,
        ],
    }


def main() -> None:
    global _task, _tick_handle, _started_at, _output_path, _proof_path, _camera
    global _pcg_volume, _pcg_component, _pcg_ready, _proof_data

    output_value = os.environ.get("YACS_PASSO_GIAU_HOUSE_CAPTURE_PNG", "")
    proof_value = os.environ.get("YACS_PASSO_GIAU_HOUSE_CAPTURE_PROOF", "")
    selection_value = os.environ.get("YACS_WORLD_ASSET_SELECTION_PLAN", "")
    if not output_value or not proof_value or not selection_value:
        raise RuntimeError(
            "YACS_PASSO_GIAU_HOUSE_CAPTURE_PNG, "
            "YACS_PASSO_GIAU_HOUSE_CAPTURE_PROOF and "
            "YACS_WORLD_ASSET_SELECTION_PLAN are required"
        )

    grove_preset = yacs_scene_composer.load_json(GROVE_PRESET_PATH)
    selection_plan = yacs_scene_composer.load_json(Path(selection_value))

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
    landscape = landscapes[0]
    landscape_components = list(
        landscape.get_components_by_class(unreal.LandscapeComponent)
    )
    if len(landscape_components) != 1024:
        raise RuntimeError(
            f"expected 1024 Landscape components, found {len(landscape_components)}"
        )
    for component in landscape_components:
        component.set_forced_lod(0)
        component.set_lod_bias(0)

    road_actor, spline, original_control_count = _find_road_spline()
    for component in road_actor.get_components_by_class(unreal.SplineMeshComponent):
        component.set_visibility(False, True)

    full_length_cm = float(spline.get_spline_length())
    focus_distance_cm, curvature_score = _choose_hairpin_distance(spline)
    slice_start_cm = max(0.0, focus_distance_cm - SLICE_HALF_LENGTH_CM)
    slice_end_cm = min(full_length_cm, focus_distance_cm + SLICE_HALF_LENGTH_CM)
    slice_points = _sample_slice(
        spline,
        slice_start_cm,
        slice_end_cm,
        SLICE_POINT_STEP_CM,
    )
    _replace_with_slice(spline, slice_points)

    edit_layer_names: list[str] = []
    if hasattr(landscape, "get_edit_layers"):
        for edit_layer in landscape.get_edit_layers():
            if edit_layer is None:
                continue
            if hasattr(edit_layer, "get_name_bp"):
                name = str(edit_layer.get_name_bp())
                if name and name != "None":
                    edit_layer_names.append(name)
    # Landscapes created by the R4.1 commandlet use UE's default initial
    # edit layer unless an explicit named layer has been authored.
    edit_layer_name = edit_layer_names[0] if edit_layer_names else "Layer"
    unreal.log(
        "[PassoGiauRoadsideHouse] applying cut/fill to edit layer "
        f"{edit_layer_name!r}; discovered={edit_layer_names}"
    )
    landscape.editor_apply_spline(
        spline,
        start_width=LANDSCAPE_SPLINE_WIDTH_CM,
        end_width=LANDSCAPE_SPLINE_WIDTH_CM,
        start_side_falloff=LANDSCAPE_SPLINE_FALLOFF_CM,
        end_side_falloff=LANDSCAPE_SPLINE_FALLOFF_CM,
        start_roll=0.0,
        end_roll=0.0,
        num_subdivisions=LANDSCAPE_SPLINE_SUBDIVISIONS,
        raise_heights=True,
        lower_heights=True,
        paint_layer=None,
        edit_layer_name=edit_layer_name,
    )

    neutral_landscape_material = unreal.load_asset(
        "/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial"
    )
    if neutral_landscape_material is not None:
        landscape.set_editor_property(
            "landscape_material",
            neutral_landscape_material,
        )

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    cube_mesh = unreal.load_asset("/Engine/BasicShapes/Cube.Cube")
    if cube_mesh is None:
        raise RuntimeError("failed to load /Engine/BasicShapes/Cube.Cube")

    basic_material = unreal.load_asset(
        "/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"
    )
    road_material = None
    shoulder_material = None
    if basic_material is not None:
        road_material = _make_material(
            world,
            basic_material,
            unreal.LinearColor(0.025, 0.025, 0.028, 1.0),
        )
        shoulder_material = _make_material(
            world,
            basic_material,
            unreal.LinearColor(0.24, 0.22, 0.18, 1.0),
        )

    shoulder_segments = _spawn_box_strip(
        actor_subsystem,
        cube_mesh,
        shoulder_material,
        spline,
        SHOULDER_HALF_WIDTH_CM,
        SHOULDER_SURFACE_LIFT_CM,
        24.0,
        "HairpinShoulder",
    )
    road_segments = _spawn_box_strip(
        actor_subsystem,
        cube_mesh,
        road_material,
        spline,
        ROAD_HALF_WIDTH_CM,
        ROAD_SURFACE_LIFT_CM,
        10.0,
        "HairpinAsphalt",
    )

    local_length_cm = float(spline.get_spline_length())
    local_focus_cm = min(
        max(0.0, focus_distance_cm - slice_start_cm),
        local_length_cm,
    )
    house = _spawn_alpine_house(
        actor_subsystem,
        cube_mesh,
        world,
        basic_material,
        spline,
        local_focus_cm,
    )

    house_location = house["location_cm"]
    road_anchor = house["road_anchor_cm"]
    outward_x = float(house_location[0]) - float(road_anchor[0])
    outward_y = float(house_location[1]) - float(road_anchor[1])
    outward_length = max(1.0, math.hypot(outward_x, outward_y))
    outward_x /= outward_length
    outward_y /= outward_length

    house_yaw_rad = math.radians(float(house["yaw_deg"]))
    tangent_x = math.cos(house_yaw_rad)
    tangent_y = math.sin(house_yaw_rad)

    forest_center = unreal.Vector(
        float(house_location[0]) + outward_x * 1100.0 + tangent_x * 180.0,
        float(house_location[1]) + outward_y * 1100.0 + tangent_y * 180.0,
        float(road_anchor[2]),
    )
    forest, _pcg_volume, _pcg_component = (
        yacs_scene_composer.begin_pcg_forest_patch(
            preset=grove_preset,
            selection_plan=selection_plan,
            actor_subsystem=actor_subsystem,
            center_cm=forest_center,
            world_yaw_deg=float(house["yaw_deg"]),
            label_prefix="YACS_ALPINE_GROVE_PCG",
        )
    )

    camera_distance_cm = max(0.0, local_focus_cm - CAMERA_BACK_CM)
    target_distance_cm = min(
        local_length_cm,
        local_focus_cm + LOOK_AHEAD_CM,
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
        float(road_target.x) * 0.25
        + float(house_location[0]) * 0.35
        + float(forest_center.x) * 0.40,
        float(road_target.y) * 0.25
        + float(house_location[1]) * 0.35
        + float(forest_center.y) * 0.40,
        float(road_target.z) * 0.25
        + float(house_location[2]) * 0.35
        + float(forest_center.z) * 0.40
        + 260.0,
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

    sun = actor_subsystem.spawn_actor_from_class(
        unreal.DirectionalLight,
        camera_location + unreal.Vector(0.0, 0.0, 200000.0),
        unreal.Rotator(pitch=-32.0, yaw=-55.0, roll=0.0),
        transient=True,
    )
    sun.set_actor_label("HairpinCorridor_ProofSun")
    sun_component = sun.get_component_by_class(unreal.DirectionalLightComponent)
    sun_component.set_intensity(5.0)
    sun_component.set_cast_shadows(True)

    sky = actor_subsystem.spawn_actor_from_class(
        unreal.SkyLight,
        camera_location + unreal.Vector(0.0, 0.0, 100000.0),
        unreal.Rotator(),
        transient=True,
    )
    sky.set_actor_label("HairpinCorridor_ProofSky")
    sky.get_component_by_class(unreal.SkyLightComponent).set_intensity(1.0)

    atmosphere = actor_subsystem.spawn_actor_from_class(
        unreal.SkyAtmosphere,
        unreal.Vector(),
        unreal.Rotator(),
        transient=True,
    )
    atmosphere.set_actor_label("HairpinCorridor_ProofAtmosphere")

    fog = actor_subsystem.spawn_actor_from_class(
        unreal.ExponentialHeightFog,
        camera_location,
        unreal.Rotator(),
        transient=True,
    )
    fog.set_actor_label("HairpinCorridor_ProofFog")
    fog_component = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    fog_component.set_editor_property("fog_density", 0.00018)
    fog_component.set_editor_property("fog_height_falloff", 0.22)
    fog_component.set_editor_property("fog_max_opacity", 0.16)

    _camera = actor_subsystem.spawn_actor_from_class(
        unreal.CameraActor,
        camera_location,
        camera_rotation,
        transient=True,
    )
    _camera.set_actor_label("HairpinCorridor_RiderCamera")
    camera_component = _camera.get_component_by_class(unreal.CameraComponent)
    if camera_component is None:
        raise RuntimeError("spawned CameraActor has no CameraComponent")
    camera_component.set_editor_property("field_of_view", 82.0)

    _proof_data = {
        "source_full_road_length_m": round(full_length_cm / 100.0, 3),
        "source_control_points": original_control_count,
        "selected_hairpin_distance_m": round(focus_distance_cm / 100.0, 3),
        "curvature_score": round(curvature_score, 6),
        "slice_start_m": round(slice_start_cm / 100.0, 3),
        "slice_end_m": round(slice_end_cm / 100.0, 3),
        "slice_length_m": round(local_length_cm / 100.0, 3),
        "slice_control_points": len(slice_points),
        "landscape_cut_fill": {
            "api": "LandscapeProxy.editor_apply_spline",
            "edit_layer_name": edit_layer_name,
            "discovered_edit_layer_names": edit_layer_names,
            "width_cm": LANDSCAPE_SPLINE_WIDTH_CM,
            "side_falloff_cm": LANDSCAPE_SPLINE_FALLOFF_CM,
            "subdivisions": LANDSCAPE_SPLINE_SUBDIVISIONS,
            "raise_heights": True,
            "lower_heights": True,
            "saved_to_map": False,
        },
        "proof_mesh": {
            "road_width_cm": ROAD_HALF_WIDTH_CM * 2.0,
            "shoulder_width_cm": SHOULDER_HALF_WIDTH_CM * 2.0,
            "road_segments": road_segments,
            "shoulder_segments": shoulder_segments,
            "segment_length_cm": MESH_SEGMENT_CM,
        },
        "house": house,
        "forest": forest,
        "asset_selection_plan": str(Path(selection_value).resolve()),
        "landscape_component_count": len(landscape_components),
        "forced_landscape_lod": 0,
        "neutral_landscape_material": neutral_landscape_material is not None,
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
        "proof_viewmode": "lit",
    }

    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    _pcg_ready = False
    _started_at = time.monotonic()
    _tick_handle = unreal.register_slate_post_tick_callback(_tick)
    unreal.log(
        "[PassoGiauRoadsideHouse] screenshot scheduled: "
        f"slice_m={local_length_cm / 100.0:.1f} "
        f"focus_m={focus_distance_cm / 100.0:.1f} "
        f"curvature={curvature_score:.4f} "
        f"road_segments={road_segments} shoulder_segments={shoulder_segments} "
        f"house_offset_m={house['road_offset_m']:.1f} "
        f"forest_trees={forest['tree_count']}"
    )


try:
    main()
except Exception as exc:
    unreal.log_error(f"[PassoGiauRoadsideHouse] FAILURE: {exc}")
    unreal.log_error(traceback.format_exc())
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)
    raise

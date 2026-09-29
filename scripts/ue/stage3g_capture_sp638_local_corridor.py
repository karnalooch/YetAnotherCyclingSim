"""Render the R4.1B.3 rider-close SP638 local-ground corridor proof.

The proof keeps the corrected MASE Landscape as macro terrain, applies only a
broad transient Landscape cut/fill around the selected real SP638 hairpin, and
then overlays the cyclist-close road bench with continuous DynamicMesh surfaces.

The canonical road XY is never snapped to Landscape/DTM vertices. Nothing is
saved back to the map.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from pathlib import Path
import sys
import time
import traceback

import unreal


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.geometry.sp638_local_corridor import (  # noqa: E402
    CrossSectionPoint,
    Vec3,
    build_corridor_mesh,
    corridor_mesh_hash,
    make_constant_profiles,
    make_curvature_adaptive_profiles,
    minimum_sampled_radius_xy,
)
from scripts.geometry.local_terrain_skin import (  # noqa: E402
    apply_road_clearance_to_height_grid,
    build_terrain_skin_mesh,
    smooth_height_grid,
    terrain_skin_hash,
)


SPIKE_MAP = "/Game/Prototype/Maps/L_PassoGiauTerrainSpike"
CAPTURE_RES_X = 3840
CAPTURE_RES_Y = 2160
PROOF_AA_QUALITY = 6

SLICE_HALF_LENGTH_CM = 35000.0
KERNEL_SAMPLE_STEP_CM = 200.0
SOURCE_GEOMETRY_HALF_WINDOW_M = 6.0
SOURCE_GEOMETRY_HALF_WINDOW_STATIONS = 3
LANDSCAPE_SPLINE_POINT_STEP_CM = 1000.0
CURVATURE_SAMPLE_STEP_CM = 2500.0
CURVATURE_HALF_WINDOW_CM = 2500.0
END_MARGIN_CM = 10000.0

LANDSCAPE_SPLINE_WIDTH_CM = 520.0
LANDSCAPE_SPLINE_FALLOFF_CM = 1600.0
LANDSCAPE_SPLINE_SUBDIVISIONS = 240

# Rider-close terrain is a bounded presentation skin sampled from the already
# deformed Landscape. World-aligned sampling avoids hairpin offset singularities.
TERRAIN_SKIN_HALF_EXTENT_CM = 25000.0
TERRAIN_SKIN_GRID_STEP_CM = 400.0
TERRAIN_SKIN_TRACE_HALF_SPAN_CM = 250000.0
TERRAIN_SKIN_LIFT_M = 0.02
TERRAIN_SKIN_SMOOTHING_ITERATIONS = 3
TERRAIN_SKIN_SMOOTHING_BLEND = 0.45
TERRAIN_SKIN_CURVATURE_THRESHOLD_M = 0.04
TERRAIN_SKIN_MAX_STEP_ADJUSTMENT_M = 0.30
TERRAIN_SKIN_MAX_TOTAL_ADJUSTMENT_M = 0.90
TERRAIN_SKIN_PINNED_BORDER_CELLS = 2
TERRAIN_SKIN_BOUNDARY_BLEND_CELLS = 6
TERRAIN_SKIN_ROAD_PROTECTED_HALF_WIDTH_M = 4.0
TERRAIN_SKIN_ROAD_TRANSITION_WIDTH_M = 4.0
TERRAIN_SKIN_MINIMUM_SURFACE_OFFSET_M = -0.07
TERRAIN_SKIN_VERTICAL_CLEARANCE_M = 0.08
TERRAIN_SKIN_MAX_LOWERING_M = 3.0

INSIDE_CLEARANCE_FRACTION = 0.75
MINIMUM_SHOULDER_SPAN_M = 0.25
MINIMUM_EARTHWORK_SPAN_M = 0.10
TAPER_PER_STATION = 0.12
PROTECTED_ROLES = frozenset(
    {
        "left_road_edge",
        "right_road_edge",
    }
)
SHOULDER_ROLES = frozenset(
    {
        "left_shoulder",
        "right_shoulder",
    }
)

EARTHWORK_PROFILE = (
    CrossSectionPoint(-10.0, 2.5, "left_tie"),
    CrossSectionPoint(-7.0, 1.2, "left_earthwork"),
    CrossSectionPoint(-4.0, 0.15, "left_shoulder"),
    CrossSectionPoint(-3.0, 0.0, "left_road_edge"),
    CrossSectionPoint(3.0, 0.0, "right_road_edge"),
    CrossSectionPoint(4.0, -0.10, "right_shoulder"),
    CrossSectionPoint(7.0, -0.9, "right_earthwork"),
    CrossSectionPoint(10.0, -1.8, "right_tie"),
)

ROAD_PROFILE = (
    CrossSectionPoint(-3.0, 0.06, "left_road_surface"),
    CrossSectionPoint(3.0, 0.06, "right_road_surface"),
)
EYE_HEIGHT_CM = 160.0
CAMERA_BACK_CM = 3500.0
LOOK_AHEAD_CM = 6500.0

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
        screenshot_sha256 = hashlib.sha256(_output_path.read_bytes()).hexdigest()
        proof = {
            "schema_version": 1,
            "sp638_local_corridor_visual": "PASS",
            "map": SPIKE_MAP,
            "screenshot": str(_output_path),
            "screenshot_bytes": _output_path.stat().st_size,
            "screenshot_sha256": screenshot_sha256,
            "resolution": [CAPTURE_RES_X, CAPTURE_RES_Y],
            "visual_acceptance": "PENDING_HUMAN_REVIEW",
            "presentation_only": True,
            "authoritative_route_geometry": False,
            "authoritative_physics": False,
            "saved_to_map": False,
            "road_xy_snapped_to_terrain_grid": False,
            **_proof_data,
        }
        _proof_path.parent.mkdir(parents=True, exist_ok=True)
        _proof_path.write_text(
            json.dumps(proof, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        unreal.log(
            "[YacsSp638LocalCorridorVisual] PASS: "
            f"{_output_path} ({_output_path.stat().st_size} bytes)"
        )
    elif error:
        unreal.log_error(f"[YacsSp638LocalCorridorVisual] FAILURE: {error}")

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


def _sample_world(
    spline: unreal.SplineComponent,
    start_cm: float,
    end_cm: float,
    step_cm: float,
) -> list[unreal.Vector]:
    result: list[unreal.Vector] = []
    distance = start_cm
    while distance < end_cm:
        result.append(
            spline.get_location_at_distance_along_spline(
                distance,
                unreal.SplineCoordinateSpace.WORLD,
            )
        )
        distance += step_cm
    result.append(
        spline.get_location_at_distance_along_spline(
            end_cm,
            unreal.SplineCoordinateSpace.WORLD,
        )
    )
    return result


def _to_local_centerline_m(points: list[unreal.Vector]) -> tuple[Vec3, ...]:
    origin = points[0]
    return tuple(
        Vec3(
            (float(point.x) - float(origin.x)) / 100.0,
            (float(point.y) - float(origin.y)) / 100.0,
            (float(point.z) - float(origin.z)) / 100.0,
        )
        for point in points
    )


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


def _circumradius_xy(a: Vec3, b: Vec3, c: Vec3) -> float | None:
    ab = math.hypot(b.x - a.x, b.y - a.y)
    bc = math.hypot(c.x - b.x, c.y - b.y)
    ca = math.hypot(a.x - c.x, a.y - c.y)
    cross2 = abs(
        (b.x - a.x) * (c.y - a.y)
        - (b.y - a.y) * (c.x - a.x)
    )
    if min(ab, bc, ca) <= 1e-9 or cross2 <= 1e-9:
        return None
    return (ab * bc * ca) / (2.0 * cross2)


def _minimum_sampled_radius_m(centerline: tuple[Vec3, ...]) -> float | None:
    radii = [
        radius
        for index in range(1, len(centerline) - 1)
        if (
            radius := _circumradius_xy(
                centerline[index - 1],
                centerline[index],
                centerline[index + 1],
            )
        )
        is not None
    ]
    return min(radii) if radii else None


def _profile_diagnostics(
    profiles: tuple[tuple[CrossSectionPoint, ...], ...],
) -> dict[str, object]:
    authored_by_role = {point.role: point.lateral_m for point in EARTHWORK_PROFILE}
    clipped_station_count = 0
    for profile in profiles:
        if any(
            abs(point.lateral_m - authored_by_role[point.role]) > 1e-9
            for point in profile
        ):
            clipped_station_count += 1
        for point in profile:
            if point.role in PROTECTED_ROLES:
                authored = authored_by_role[point.role]
                if abs(point.lateral_m - authored) > 1e-9:
                    raise RuntimeError(
                        f"adaptive profile moved protected role {point.role}: "
                        f"{authored} -> {point.lateral_m}"
                    )

    shoulder_widths = []
    for profile in profiles:
        by_role = {point.role: point.lateral_m for point in profile}
        shoulder_widths.extend(
            (
                abs(by_role["left_shoulder"]) - abs(by_role["left_road_edge"]),
                abs(by_role["right_shoulder"]) - abs(by_role["right_road_edge"]),
            )
        )
    minimum_actual_shoulder_width_m = min(shoulder_widths)
    if minimum_actual_shoulder_width_m < MINIMUM_SHOULDER_SPAN_M - 1e-9:
        raise RuntimeError(
            "adaptive profile pinched shoulder below minimum: "
            f"{minimum_actual_shoulder_width_m:.6f} m"
        )

    return {
        "inside_clearance_fraction": INSIDE_CLEARANCE_FRACTION,
        "minimum_shoulder_span_m": MINIMUM_SHOULDER_SPAN_M,
        "minimum_earthwork_span_m": MINIMUM_EARTHWORK_SPAN_M,
        "taper_per_station": TAPER_PER_STATION,
        "clipped_station_count": clipped_station_count,
        "minimum_actual_outer_extent_m": [
            min(abs(profile[0].lateral_m) for profile in profiles),
            min(profile[-1].lateral_m for profile in profiles),
        ],
        "minimum_actual_shoulder_width_m": minimum_actual_shoulder_width_m,
        "protected_roles": sorted(PROTECTED_ROLES),
        "shoulder_roles": sorted(SHOULDER_ROLES),
    }


def _shoulder_surface_profiles(
    profiles: tuple[tuple[CrossSectionPoint, ...], ...],
    *,
    left: bool,
) -> tuple[tuple[CrossSectionPoint, ...], ...]:
    result: list[tuple[CrossSectionPoint, ...]] = []
    for profile in profiles:
        by_role = {point.role: point for point in profile}
        if left:
            shoulder = by_role["left_shoulder"]
            road_edge = by_role["left_road_edge"]
            result.append(
                (
                    CrossSectionPoint(
                        shoulder.lateral_m,
                        shoulder.vertical_m + 0.03,
                        "left_shoulder_outer_surface",
                    ),
                    CrossSectionPoint(
                        road_edge.lateral_m,
                        road_edge.vertical_m + 0.03,
                        "left_shoulder_inner_surface",
                    ),
                )
            )
        else:
            road_edge = by_role["right_road_edge"]
            shoulder = by_role["right_shoulder"]
            result.append(
                (
                    CrossSectionPoint(
                        road_edge.lateral_m,
                        road_edge.vertical_m + 0.03,
                        "right_shoulder_inner_surface",
                    ),
                    CrossSectionPoint(
                        shoulder.lateral_m,
                        shoulder.vertical_m + 0.03,
                        "right_shoulder_outer_surface",
                    ),
                )
            )
    return tuple(result)


def _vertical_trace_height_cm(
    hit,
    *,
    expected_x_cm: float,
    expected_y_cm: float,
    trace_bottom_z_cm: float,
    trace_top_z_cm: float,
) -> float:
    """Extract a vertical line-trace surface Z without relying on HitResult field names.

    UE Python's reflected HitResult surface changed in 5.8. StructBase.to_tuple()
    is stable and exposes the underlying values, so select the vector that lies
    on the known vertical ray. For a line trace, Location and ImpactPoint are
    coincident; either yields the sampled surface height.
    """

    try:
        values = hit.to_tuple()
    except Exception:
        values = ()

    candidates: list[float] = []
    for value in values:
        if not all(hasattr(value, axis) for axis in ("x", "y", "z")):
            continue
        x = float(value.x)
        y = float(value.y)
        z = float(value.z)
        if (
            abs(x - expected_x_cm) <= 1.0
            and abs(y - expected_y_cm) <= 1.0
            and trace_bottom_z_cm - 1.0 <= z <= trace_top_z_cm + 1.0
            and abs(z - trace_top_z_cm) > 1.0
            and abs(z - trace_bottom_z_cm) > 1.0
        ):
            candidates.append(z)

    if candidates:
        return candidates[0]

    # Defensive fallback for engine wrappers that expose only text export.
    try:
        exported = hit.export_text()
    except Exception:
        exported = ""
    for field_name in ("ImpactPoint", "Location"):
        match = re.search(
            rf"{field_name}=\\(X=([-+0-9.eE]+),Y=([-+0-9.eE]+),Z=([-+0-9.eE]+)\\)",
            exported,
        )
        if match is None:
            continue
        x = float(match.group(1))
        y = float(match.group(2))
        z = float(match.group(3))
        if abs(x - expected_x_cm) <= 1.0 and abs(y - expected_y_cm) <= 1.0:
            return z

    raise RuntimeError(
        "could not extract a surface point from UE HitResult on vertical ray; "
        f"tuple_len={len(values)} export={exported[:240]!r}"
    )


def _sample_local_terrain_skin(
    world: unreal.World,
    road_actor: unreal.Actor,
    center_world: unreal.Vector,
    road_centerline_world: list[unreal.Vector],
):
    """Sample the transient Landscape into a bounded world-aligned local skin."""

    span_count = int(round((2.0 * TERRAIN_SKIN_HALF_EXTENT_CM) / TERRAIN_SKIN_GRID_STEP_CM))
    if span_count < 4:
        raise RuntimeError("terrain skin grid is unexpectedly small")

    min_x_cm = float(center_world.x) - TERRAIN_SKIN_HALF_EXTENT_CM
    max_y_cm = float(center_world.y) + TERRAIN_SKIN_HALF_EXTENT_CM
    x_coordinates_cm = [
        min_x_cm + index * TERRAIN_SKIN_GRID_STEP_CM
        for index in range(span_count + 1)
    ]
    y_coordinates_cm = [
        max_y_cm - index * TERRAIN_SKIN_GRID_STEP_CM
        for index in range(span_count + 1)
    ]

    trace_top_z = float(center_world.z) + TERRAIN_SKIN_TRACE_HALF_SPAN_CM
    trace_bottom_z = float(center_world.z) - TERRAIN_SKIN_TRACE_HALF_SPAN_CM
    raw_heights_m: list[tuple[float, ...]] = []
    misses: list[tuple[int, int]] = []

    for row_index, y_cm in enumerate(y_coordinates_cm):
        row: list[float] = []
        for column_index, x_cm in enumerate(x_coordinates_cm):
            hit = unreal.SystemLibrary.line_trace_single(
                world,
                unreal.Vector(x_cm, y_cm, trace_top_z),
                unreal.Vector(x_cm, y_cm, trace_bottom_z),
                unreal.TraceTypeQuery.ECC_VISIBILITY,
                True,
                [road_actor],
                unreal.DrawDebugTrace.NONE,
                True,
            )
            if hit is None:
                misses.append((row_index, column_index))
                row.append(float("nan"))
                continue
            height_cm = _vertical_trace_height_cm(
                hit,
                expected_x_cm=x_cm,
                expected_y_cm=y_cm,
                trace_bottom_z_cm=trace_bottom_z,
                trace_top_z_cm=trace_top_z,
            )
            row.append(height_cm / 100.0)
        raw_heights_m.append(tuple(row))

    if misses:
        preview = ", ".join(f"{row}:{column}" for row, column in misses[:8])
        raise RuntimeError(
            "terrain skin Landscape sampling missed "
            f"{len(misses)} grid points; first={preview}"
        )

    smoothed_heights_m, metrics = smooth_height_grid(
        tuple(raw_heights_m),
        iterations=TERRAIN_SKIN_SMOOTHING_ITERATIONS,
        blend=TERRAIN_SKIN_SMOOTHING_BLEND,
        curvature_threshold_m=TERRAIN_SKIN_CURVATURE_THRESHOLD_M,
        max_step_adjustment_m=TERRAIN_SKIN_MAX_STEP_ADJUSTMENT_M,
        max_total_adjustment_m=TERRAIN_SKIN_MAX_TOTAL_ADJUSTMENT_M,
        pinned_border_cells=TERRAIN_SKIN_PINNED_BORDER_CELLS,
        boundary_blend_cells=TERRAIN_SKIN_BOUNDARY_BLEND_CELLS,
    )

    x_coordinates_m = tuple(value / 100.0 for value in x_coordinates_cm)
    y_coordinates_m = tuple(value / 100.0 for value in y_coordinates_cm)
    road_centerline_world_m = tuple(
        Vec3(
            float(point.x) / 100.0,
            float(point.y) / 100.0,
            float(point.z) / 100.0,
        )
        for point in road_centerline_world
    )
    cleared_heights_m, road_clearance = apply_road_clearance_to_height_grid(
        x_coordinates_m,
        y_coordinates_m,
        smoothed_heights_m,
        road_centerline_world_m,
        protected_half_width_m=TERRAIN_SKIN_ROAD_PROTECTED_HALF_WIDTH_M,
        transition_width_m=TERRAIN_SKIN_ROAD_TRANSITION_WIDTH_M,
        minimum_surface_offset_m=TERRAIN_SKIN_MINIMUM_SURFACE_OFFSET_M,
        vertical_clearance_m=TERRAIN_SKIN_VERTICAL_CLEARANCE_M,
        max_lowering_m=TERRAIN_SKIN_MAX_LOWERING_M,
    )

    origin_x_m = x_coordinates_m[0]
    origin_y_m = y_coordinates_m[0]
    origin_z_m = min(min(row) for row in cleared_heights_m)

    mesh = build_terrain_skin_mesh(
        x_coordinates_m,
        y_coordinates_m,
        cleared_heights_m,
        origin_x_m=origin_x_m,
        origin_y_m=origin_y_m,
        origin_z_m=origin_z_m,
        lift_m=TERRAIN_SKIN_LIFT_M,
    )
    origin_world = unreal.Vector(
        origin_x_m * 100.0,
        origin_y_m * 100.0,
        origin_z_m * 100.0,
    )
    diagnostics = {
        "world_aligned": True,
        "half_extent_m": TERRAIN_SKIN_HALF_EXTENT_CM / 100.0,
        "grid_step_m": TERRAIN_SKIN_GRID_STEP_CM / 100.0,
        "row_count": mesh.row_count,
        "column_count": mesh.column_count,
        "sample_count": mesh.row_count * mesh.column_count,
        "smoothing_iterations": TERRAIN_SKIN_SMOOTHING_ITERATIONS,
        "smoothing_blend": TERRAIN_SKIN_SMOOTHING_BLEND,
        "curvature_threshold_m": TERRAIN_SKIN_CURVATURE_THRESHOLD_M,
        "max_step_adjustment_m": TERRAIN_SKIN_MAX_STEP_ADJUSTMENT_M,
        "max_total_adjustment_m": TERRAIN_SKIN_MAX_TOTAL_ADJUSTMENT_M,
        "pinned_border_cells": TERRAIN_SKIN_PINNED_BORDER_CELLS,
        "boundary_blend_cells": TERRAIN_SKIN_BOUNDARY_BLEND_CELLS,
        "road_clearance": {
            "protected_half_width_m": TERRAIN_SKIN_ROAD_PROTECTED_HALF_WIDTH_M,
            "transition_width_m": TERRAIN_SKIN_ROAD_TRANSITION_WIDTH_M,
            "minimum_surface_offset_m": TERRAIN_SKIN_MINIMUM_SURFACE_OFFSET_M,
            "required_vertical_clearance_m": TERRAIN_SKIN_VERTICAL_CLEARANCE_M,
            "max_lowering_limit_m": TERRAIN_SKIN_MAX_LOWERING_M,
            "adjusted_sample_count": road_clearance.adjusted_sample_count,
            "protected_sample_count": road_clearance.protected_sample_count,
            "max_lowering_m": road_clearance.max_lowering_m,
            "minimum_vertical_clearance_m": (
                road_clearance.minimum_vertical_clearance_m
            ),
        },
        "max_abs_adjustment_m": metrics.max_abs_adjustment_m,
        "rms_adjustment_m": metrics.rms_adjustment_m,
        "max_abs_laplacian_before_m": metrics.max_abs_laplacian_before_m,
        "max_abs_laplacian_after_m": metrics.max_abs_laplacian_after_m,
        "mesh_sha256": terrain_skin_hash(mesh),
        "source": "transient Landscape collision after broad spline cut/fill",
        "canonical_road_xy_modified": False,
    }
    return mesh, origin_world, diagnostics


def _make_material(
    world: unreal.World,
    parent: unreal.MaterialInterface,
    color: unreal.LinearColor,
):
    material = unreal.MaterialLibrary.create_dynamic_material_instance(world, parent)
    material.set_vector_parameter_value("Color", color)
    return material


def _spawn_dynamic_mesh(
    actor_subsystem: unreal.EditorActorSubsystem,
    origin_world: unreal.Vector,
    mesh,
    label: str,
    material,
) -> dict[str, int]:
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.DynamicMeshActor,
        origin_world,
        unreal.Rotator(),
        transient=True,
    )
    if actor is None:
        raise RuntimeError(f"failed to spawn DynamicMeshActor for {label}")
    actor.set_actor_label(label)

    component = actor.get_dynamic_mesh_component()
    if component is None:
        raise RuntimeError(f"{label}: DynamicMeshActor has no DynamicMeshComponent")
    dynamic_mesh = component.get_dynamic_mesh()
    if dynamic_mesh is None:
        raise RuntimeError(f"{label}: DynamicMeshComponent has no DynamicMesh")

    buffers = unreal.GeometryScriptSimpleMeshBuffers()
    buffers.set_editor_property(
        "vertices",
        [
            unreal.Vector(vertex.x * 100.0, vertex.y * 100.0, vertex.z * 100.0)
            for vertex in mesh.vertices
        ],
    )
    buffers.set_editor_property(
        "triangles",
        [unreal.IntVector(*triangle) for triangle in mesh.triangles],
    )

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
    if material is not None:
        component.set_material(0, material)

    vertex_count = int(dynamic_mesh.get_vertex_count())
    triangle_count = int(dynamic_mesh.get_triangle_count())
    if vertex_count != len(mesh.vertices) or triangle_count != len(mesh.triangles):
        raise RuntimeError(
            f"{label}: DynamicMesh count mismatch "
            f"{vertex_count}/{triangle_count} != "
            f"{len(mesh.vertices)}/{len(mesh.triangles)}"
        )
    return {"vertices": vertex_count, "triangles": triangle_count}


def main() -> None:
    global _task, _tick_handle, _started_at, _output_path, _proof_path, _camera
    global _proof_data

    output_value = os.environ.get("YACS_SP638_LOCAL_CORRIDOR_VISUAL_PNG", "")
    proof_value = os.environ.get("YACS_SP638_LOCAL_CORRIDOR_VISUAL_PROOF", "")
    if not output_value or not proof_value:
        raise RuntimeError(
            "YACS_SP638_LOCAL_CORRIDOR_VISUAL_PNG and "
            "YACS_SP638_LOCAL_CORRIDOR_VISUAL_PROOF are required"
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
    focus_cm, curvature_score = _choose_hairpin_distance(spline)
    start_cm = max(0.0, focus_cm - SLICE_HALF_LENGTH_CM)
    end_cm = min(full_length_cm, focus_cm + SLICE_HALF_LENGTH_CM)

    camera_distance_cm = max(0.0, focus_cm - CAMERA_BACK_CM)
    target_distance_cm = min(full_length_cm, focus_cm + LOOK_AHEAD_CM)
    road_camera = spline.get_location_at_distance_along_spline(
        camera_distance_cm,
        unreal.SplineCoordinateSpace.WORLD,
    )
    road_target = spline.get_location_at_distance_along_spline(
        target_distance_cm,
        unreal.SplineCoordinateSpace.WORLD,
    )

    kernel_world = _sample_world(
        spline,
        start_cm,
        end_cm,
        KERNEL_SAMPLE_STEP_CM,
    )
    centerline = _to_local_centerline_m(kernel_world)
    raw_adjacent_minimum_radius_m = minimum_sampled_radius_xy(
        centerline,
        half_window_stations=1,
    )
    source_scale_minimum_radius_m = minimum_sampled_radius_xy(
        centerline,
        half_window_stations=SOURCE_GEOMETRY_HALF_WINDOW_STATIONS,
    )

    adaptive_profiles = make_curvature_adaptive_profiles(
        centerline,
        EARTHWORK_PROFILE,
        protected_roles=PROTECTED_ROLES,
        shoulder_roles=SHOULDER_ROLES,
        clearance_fraction=INSIDE_CLEARANCE_FRACTION,
        minimum_shoulder_span_m=MINIMUM_SHOULDER_SPAN_M,
        minimum_earthwork_span_m=MINIMUM_EARTHWORK_SPAN_M,
        taper_per_station=TAPER_PER_STATION,
        curvature_half_window_stations=SOURCE_GEOMETRY_HALF_WINDOW_STATIONS,
    )
    earthwork_mesh = build_corridor_mesh(
        centerline,
        adaptive_profiles,
        tangent_half_window_stations=SOURCE_GEOMETRY_HALF_WINDOW_STATIONS,
    )
    road_mesh = build_corridor_mesh(
        centerline,
        make_constant_profiles(len(centerline), ROAD_PROFILE),
        tangent_half_window_stations=SOURCE_GEOMETRY_HALF_WINDOW_STATIONS,
    )
    left_shoulder_mesh = build_corridor_mesh(
        centerline,
        _shoulder_surface_profiles(adaptive_profiles, left=True),
        tangent_half_window_stations=SOURCE_GEOMETRY_HALF_WINDOW_STATIONS,
    )
    right_shoulder_mesh = build_corridor_mesh(
        centerline,
        _shoulder_surface_profiles(adaptive_profiles, left=False),
        tangent_half_window_stations=SOURCE_GEOMETRY_HALF_WINDOW_STATIONS,
    )
    profile_diagnostics = _profile_diagnostics(adaptive_profiles)

    landscape_slice = _sample_world(
        spline,
        start_cm,
        end_cm,
        LANDSCAPE_SPLINE_POINT_STEP_CM,
    )
    _replace_with_slice(spline, landscape_slice)

    edit_layer_names: list[str] = []
    if hasattr(landscape, "get_edit_layers"):
        for edit_layer in landscape.get_edit_layers():
            if edit_layer is None:
                continue
            if hasattr(edit_layer, "get_name_bp"):
                name = str(edit_layer.get_name_bp())
                if name and name != "None":
                    edit_layer_names.append(name)
    edit_layer_name = edit_layer_names[0] if edit_layer_names else "Layer"
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

    terrain_skin_center_world = kernel_world[len(kernel_world) // 2]
    (
        terrain_skin_mesh,
        terrain_skin_origin_world,
        terrain_skin_diagnostics,
    ) = _sample_local_terrain_skin(
        world,
        road_actor,
        terrain_skin_center_world,
        kernel_world,
    )

    basic_material = unreal.load_asset(
        "/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"
    )
    if basic_material is None:
        raise RuntimeError("failed to load solid neutral proof material")

    neutral_landscape_material = _make_material(
        world,
        basic_material,
        unreal.LinearColor(0.36, 0.35, 0.31, 1.0),
    )
    landscape.set_editor_property(
        "landscape_material",
        neutral_landscape_material,
    )
    terrain_skin_material = _make_material(
        world,
        basic_material,
        unreal.LinearColor(0.34, 0.33, 0.29, 1.0),
    )
    earth_material = _make_material(
        world,
        basic_material,
        unreal.LinearColor(0.33, 0.31, 0.27, 1.0),
    )
    shoulder_material = _make_material(
        world,
        basic_material,
        unreal.LinearColor(0.22, 0.20, 0.16, 1.0),
    )
    road_material = _make_material(
        world,
        basic_material,
        unreal.LinearColor(0.025, 0.025, 0.028, 1.0),
    )

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    terrain_skin_counts = _spawn_dynamic_mesh(
        actor_subsystem,
        terrain_skin_origin_world,
        terrain_skin_mesh,
        "SP638_LocalTerrainSkin",
        terrain_skin_material,
    )

    # Keep the corrected MASE Landscape visible as macro terrain. The lifted,
    # smoothed DynamicMesh skin owns only the bounded rider-close patch and
    # overlays the Landscape locally; no persisted map change is saved.
    origin_world = kernel_world[0]
    earth_counts = _spawn_dynamic_mesh(
        actor_subsystem,
        origin_world,
        earthwork_mesh,
        "SP638_LocalCorridor_Earthwork",
        earth_material,
    )
    left_shoulder_counts = _spawn_dynamic_mesh(
        actor_subsystem,
        origin_world,
        left_shoulder_mesh,
        "SP638_LocalCorridor_LeftShoulder",
        shoulder_material,
    )
    right_shoulder_counts = _spawn_dynamic_mesh(
        actor_subsystem,
        origin_world,
        right_shoulder_mesh,
        "SP638_LocalCorridor_RightShoulder",
        shoulder_material,
    )
    road_counts = _spawn_dynamic_mesh(
        actor_subsystem,
        origin_world,
        road_mesh,
        "SP638_LocalCorridor_Asphalt",
        road_material,
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
    # Render the rider-close terrain and visible macro Landscape in ordinary
    # lit mode with solid neutral proof materials so slope/occlusion artifacts
    # are readable without the editor checker pattern masking the geometry.
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
    sun.set_actor_label("SP638_LocalCorridor_ProofSun")
    sun_component = sun.get_component_by_class(unreal.DirectionalLightComponent)
    sun_component.set_intensity(5.0)
    # Shadowless slope shading keeps heightfield self-shadow aliasing out of
    # the geometry acceptance decision.
    sun_component.set_cast_shadows(False)

    sky = actor_subsystem.spawn_actor_from_class(
        unreal.SkyLight,
        camera_location + unreal.Vector(0.0, 0.0, 100000.0),
        unreal.Rotator(),
        transient=True,
    )
    sky.set_actor_label("SP638_LocalCorridor_ProofSky")
    sky.get_component_by_class(unreal.SkyLightComponent).set_intensity(1.0)

    atmosphere = actor_subsystem.spawn_actor_from_class(
        unreal.SkyAtmosphere,
        unreal.Vector(),
        unreal.Rotator(),
        transient=True,
    )
    atmosphere.set_actor_label("SP638_LocalCorridor_ProofAtmosphere")

    fog = actor_subsystem.spawn_actor_from_class(
        unreal.ExponentialHeightFog,
        camera_location,
        unreal.Rotator(),
        transient=True,
    )
    fog.set_actor_label("SP638_LocalCorridor_ProofFog")
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
    _camera.set_actor_label("SP638_LocalCorridor_RiderCamera")
    camera_component = _camera.get_component_by_class(unreal.CameraComponent)
    if camera_component is None:
        raise RuntimeError("spawned CameraActor has no CameraComponent")
    camera_component.set_editor_property("field_of_view", 76.0)

    _proof_data = {
        "capture_strategy": "r4.1b.3-world-aligned-terrain-skin-plus-corridor",
        "source_full_road_length_m": round(full_length_cm / 100.0, 3),
        "source_control_points": original_control_count,
        "selected_hairpin_distance_m": round(focus_cm / 100.0, 3),
        "curvature_score": round(curvature_score, 6),
        "slice_start_m": round(start_cm / 100.0, 3),
        "slice_end_m": round(end_cm / 100.0, 3),
        "kernel_sample_step_m": KERNEL_SAMPLE_STEP_CM / 100.0,
        "station_count": earthwork_mesh.station_count,
        "source_geometry_analysis": {
            "half_window_m": SOURCE_GEOMETRY_HALF_WINDOW_M,
            "half_window_stations": SOURCE_GEOMETRY_HALF_WINDOW_STATIONS,
            "raw_adjacent_minimum_radius_m": (
                round(raw_adjacent_minimum_radius_m, 3)
                if raw_adjacent_minimum_radius_m is not None
                else None
            ),
            "source_scale_minimum_radius_m": (
                round(source_scale_minimum_radius_m, 3)
                if source_scale_minimum_radius_m is not None
                else None
            ),
            "canonical_centerline_xy_modified": False,
        },
        "minimum_sampled_centerline_radius_m": (
            round(source_scale_minimum_radius_m, 3)
            if source_scale_minimum_radius_m is not None
            else None
        ),
        "corridor_mesh_sha256": corridor_mesh_hash(earthwork_mesh),
        "adaptive_inside_offset": profile_diagnostics,
        "local_geometry": {
            "continuous_dynamic_mesh_surfaces": True,
            "box_strip_roadbed": False,
            "terrain_skin": terrain_skin_counts,
            "earthwork": earth_counts,
            "left_shoulder": left_shoulder_counts,
            "right_shoulder": right_shoulder_counts,
            "asphalt": road_counts,
        },
        "landscape_cut_fill": {
            "api": "LandscapeProxy.editor_apply_spline",
            "edit_layer_name": edit_layer_name,
            "width_cm": LANDSCAPE_SPLINE_WIDTH_CM,
            "side_falloff_cm": LANDSCAPE_SPLINE_FALLOFF_CM,
            "subdivisions": LANDSCAPE_SPLINE_SUBDIVISIONS,
            "raise_heights": True,
            "lower_heights": True,
            "saved_to_map": False,
        },
        "spatial_grid_guardrail": {
            "canonical_road_xy_preserved": True,
            "snapped_to_dtm_grid": False,
            "snapped_to_landscape_vertices": False,
            "canonical_macro_terrain_source": "MASE PST 1372858",
            "prepared_metric_working_grid_m": 1.0,
            "veneto_fallback_source_spacing_m": 5.0,
            "landscape_vertex_spacing_is_source_resolution": False,
        },
        "local_terrain_skin": {
            **terrain_skin_diagnostics,
            "landscape_hidden_after_sampling": False,
            "macro_landscape_visible": True,
            "occlusion_lift_m": TERRAIN_SKIN_LIFT_M,
        },
        "landscape_component_count": len(landscape_components),
        "forced_landscape_lod": 0,
        "proof_viewmode": "lit",
        "neutral_landscape_material": True,
        "neutral_landscape_material_source": (
            "/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"
        ),
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
        comparison_notes="R4.1B.3 SP638 neutral continuous local-ground corridor proof",
        delay=3.0,
        force_game_view=True,
    )
    if not _task or not _task.is_valid_task():
        raise RuntimeError("AutomationLibrary returned an invalid screenshot task")

    _started_at = time.monotonic()
    _tick_handle = unreal.register_slate_post_tick_callback(_tick)
    unreal.log(
        "[YacsSp638LocalCorridorVisual] screenshot scheduled: "
        f"stations={earthwork_mesh.station_count} "
        f"raw_adjacent_min_radius_m={raw_adjacent_minimum_radius_m} "
        f"source_scale_min_radius_m={source_scale_minimum_radius_m} "
        f"analysis_half_window_m={SOURCE_GEOMETRY_HALF_WINDOW_M} "
        f"clipped={profile_diagnostics['clipped_station_count']} "
        f"hash={corridor_mesh_hash(earthwork_mesh)}"
    )


try:
    main()
except Exception as exc:
    unreal.log_error(f"[YacsSp638LocalCorridorVisual] FAILURE: {exc}")
    unreal.log_error(traceback.format_exc())
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)
    raise

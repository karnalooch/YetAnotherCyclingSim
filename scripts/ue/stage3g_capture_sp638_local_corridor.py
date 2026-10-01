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
import struct
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
    build_terrain_skin_mesh,
    smooth_height_grid,
    terrain_skin_hash,
)


SPIKE_MAP = "/Game/Prototype/Maps/L_PassoGiauTerrainSpike"
CAPTURE_RES_X = 3840
CAPTURE_RES_Y = 2160
PROOF_AA_QUALITY = 6

SESSION_MANAGED_ENV = "YACS_R4_1_EDITOR_SESSION_MANAGED"
PCGEX_CORRIDOR_OUTPUT_ENV = "YACS_PCGEX_CORRIDOR_OUTPUT"
PCGEX_CENTER_DATASET_INDEX = 0
PCGEX_RENDER_SPLINE_STRIDE = 5

DIAGNOSTIC_VARIANT_ENV = "YACS_SP638_LOCAL_CORRIDOR_VARIANT"
NATIVE_DTM_PATCH_ENV = "YACS_NATIVE_DTM_PATCH_METADATA"

DIAGNOSTIC_VARIANTS = {
    "A": {
        "macro_landscape_visible": True,
        "local_terrain_visible": False,
        "corridor_visible": False,
        "apply_landscape_cut_fill": False,
    },
    "B": {
        "macro_landscape_visible": True,
        "local_terrain_visible": False,
        "corridor_visible": True,
        "apply_landscape_cut_fill": True,
    },
    "C": {
        "macro_landscape_visible": False,
        "local_terrain_visible": True,
        "corridor_visible": False,
        "apply_landscape_cut_fill": True,
    },
    "D": {
        "macro_landscape_visible": False,
        "local_terrain_visible": True,
        "corridor_visible": True,
        "apply_landscape_cut_fill": True,
    },
    "E": {
        "macro_landscape_visible": True,
        "local_terrain_visible": True,
        "corridor_visible": True,
        "apply_landscape_cut_fill": True,
    },
    # F/G isolate the additional transient spline edit from corridor meshes.
    # Persisted map layers remain unchanged; these are not new world owners.
    "F": {
        "macro_landscape_visible": True,
        "local_terrain_visible": False,
        "corridor_visible": False,
        "apply_landscape_cut_fill": True,
    },
    "G": {
        "macro_landscape_visible": True,
        "local_terrain_visible": False,
        "corridor_visible": True,
        "apply_landscape_cut_fill": False,
    },
    "C3": {
        "macro_landscape_visible": False,
        "local_terrain_visible": True,
        "corridor_visible": False,
        "apply_landscape_cut_fill": False,
    },
}


def _release_python_script() -> None:
    if os.environ.get(SESSION_MANAGED_ENV, "").strip() != "1":
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)


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

    _release_python_script()


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


def _load_pcgex_presentation_centerline() -> tuple[list[unreal.Vector], dict[str, object]] | None:
    output_value = os.environ.get(PCGEX_CORRIDOR_OUTPUT_ENV, "").strip()
    if not output_value:
        return None

    output_path = Path(output_value)
    if not output_path.is_file():
        raise RuntimeError(f"PCGEx corridor output is missing: {output_path}")

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    if payload.get("status") != "PASS":
        raise RuntimeError("PCGEx corridor output did not report PASS")

    datasets = payload.get("datasets") or []
    center_dataset = next(
        (
            dataset
            for dataset in datasets
            if int(dataset.get("source_collection_index", -1))
            == PCGEX_CENTER_DATASET_INDEX
        ),
        None,
    )
    if center_dataset is None:
        raise RuntimeError(
            f"PCGEx corridor output is missing center dataset {PCGEX_CENTER_DATASET_INDEX}"
        )

    raw_points = center_dataset.get("points") or []
    if len(raw_points) < 100:
        raise RuntimeError(
            f"PCGEx center dataset is unexpectedly sparse: {len(raw_points)} points"
        )

    world_points = [
        unreal.Vector(
            float(point["x_cm"]),
            float(point["y_cm"]),
            float(point["z_cm"]),
        )
        for point in raw_points
    ]
    output_sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()
    metadata = {
        "source": "pcgex_graph_output",
        "pcgex_presentation_only": True,
        "canonical_route_authority_preserved": True,
        "authoritative_physics": False,
        "source_collection_index": PCGEX_CENTER_DATASET_INDEX,
        "source_point_count": len(world_points),
        "render_spline_stride": PCGEX_RENDER_SPLINE_STRIDE,
        "execution_output_sha256": output_sha256,
        "pcgex_edge_paths_rendered": False,
    }
    return world_points, metadata


def _gate_c_proof_focus_contract() -> dict[str, object]:
    manifest_path = (
        REPO_ROOT / "worldgen" / "embark" / "passo_giau_terrain_pipeline.json"
    )
    if not manifest_path.is_file():
        raise RuntimeError(f"terrain pipeline manifest is missing: {manifest_path}")

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    proof = (payload.get("proof_locations") or {}).get("gate_c_hairpin")
    if not isinstance(proof, dict):
        raise RuntimeError(
            "terrain pipeline manifest is missing proof_locations.gate_c_hairpin"
        )

    focus_ue = proof.get("focus_ue_m")
    if not isinstance(focus_ue, list) or len(focus_ue) != 2:
        raise RuntimeError("Gate C proof focus_ue_m must contain exactly two values")

    focus_x_m = float(focus_ue[0])
    focus_y_m = float(focus_ue[1])
    max_drift_m = float(proof.get("max_render_focus_xy_drift_m", -1.0))
    if not all(math.isfinite(value) for value in (focus_x_m, focus_y_m, max_drift_m)):
        raise RuntimeError("Gate C proof focus contract contains non-finite values")
    if max_drift_m <= 0.0:
        raise RuntimeError("Gate C proof focus contract has a non-positive drift limit")

    return {
        "focus_ue_m": [focus_x_m, focus_y_m],
        "max_render_focus_xy_drift_m": max_drift_m,
        "selection_basis": str(proof.get("selection_basis", "")),
        "reference_pcgex_focus_distance_m": float(
            proof["reference_pcgex_focus_distance_m"]
        ),
        "reference_pcgex_execution_output_sha256": str(
            proof["reference_pcgex_execution_output_sha256"]
        ),
        "reference_workflow_run_id": int(proof["reference_workflow_run_id"]),
    }


def _validate_pcgex_proof_focus(
    center_world: unreal.Vector,
    pcgex_metadata: dict[str, object] | None,
) -> dict[str, object]:
    if pcgex_metadata is None:
        return {
            "enforced": False,
            "reason": "renderer is not using the PCGEx presentation centerline",
        }

    contract = _gate_c_proof_focus_contract()
    expected_x_m, expected_y_m = contract["focus_ue_m"]
    actual_x_m = float(center_world.x) / 100.0
    actual_y_m = float(center_world.y) / 100.0
    drift_m = math.hypot(actual_x_m - expected_x_m, actual_y_m - expected_y_m)
    max_drift_m = float(contract["max_render_focus_xy_drift_m"])
    if drift_m > max_drift_m:
        raise RuntimeError(
            "Gate C PCGEx proof focus drifted from the versioned proof-selected XY: "
            f"drift={drift_m:.3f} m limit={max_drift_m:.3f} m "
            f"expected=({expected_x_m:.3f},{expected_y_m:.3f}) "
            f"actual=({actual_x_m:.3f},{actual_y_m:.3f})"
        )

    return {
        **contract,
        "enforced": True,
        "actual_render_focus_ue_m": [
            round(actual_x_m, 6),
            round(actual_y_m, 6),
        ],
        "observed_xy_drift_m": round(drift_m, 6),
        "current_pcgex_execution_output_sha256": pcgex_metadata[
            "execution_output_sha256"
        ],
    }


def _replace_with_pcgex_centerline(
    spline: unreal.SplineComponent,
    points: list[unreal.Vector],
) -> int:
    sampled = points[::PCGEX_RENDER_SPLINE_STRIDE]
    if (len(points) - 1) % PCGEX_RENDER_SPLINE_STRIDE != 0:
        sampled.append(points[-1])

    spline.clear_spline_points(False)
    for index, point in enumerate(sampled):
        spline.add_spline_point(
            point,
            unreal.SplineCoordinateSpace.WORLD,
            False,
        )
        spline.set_spline_point_type(
            index,
            unreal.SplinePointType.LINEAR,
            False,
        )
    spline.set_closed_loop(False, False)
    spline.update_spline()
    return len(sampled)


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
    )

    x_coordinates_m = tuple(value / 100.0 for value in x_coordinates_cm)
    y_coordinates_m = tuple(value / 100.0 for value in y_coordinates_cm)
    origin_x_m = x_coordinates_m[0]
    origin_y_m = y_coordinates_m[0]
    origin_z_m = min(min(row) for row in smoothed_heights_m)

    mesh = build_terrain_skin_mesh(
        x_coordinates_m,
        y_coordinates_m,
        smoothed_heights_m,
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
        "max_abs_adjustment_m": metrics.max_abs_adjustment_m,
        "rms_adjustment_m": metrics.rms_adjustment_m,
        "max_abs_laplacian_before_m": metrics.max_abs_laplacian_before_m,
        "max_abs_laplacian_after_m": metrics.max_abs_laplacian_after_m,
        "mesh_sha256": terrain_skin_hash(mesh),
        "source": "transient Landscape collision after broad spline cut/fill",
        "canonical_road_xy_modified": False,
    }
    return mesh, origin_world, diagnostics


def _load_native_dtm_patch(center_world: unreal.Vector):
    metadata_value = os.environ.get(NATIVE_DTM_PATCH_ENV, "").strip()
    if not metadata_value:
        raise RuntimeError(
            f"{NATIVE_DTM_PATCH_ENV} is required for Gate C.3 native-DTM proof"
        )
    metadata_path = Path(metadata_value)
    if not metadata_path.is_file():
        raise RuntimeError(f"native DTM patch metadata is missing: {metadata_path}")

    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    source = payload.get("source") or {}
    grid = payload.get("grid") or {}
    binary = payload.get("binary") or {}
    policy = payload.get("yacs_policy") or {}
    if payload.get("schema_version") != 1 or payload.get("proof_gate") != "C.3":
        raise RuntimeError("native DTM patch schema/gate mismatch")
    if source.get("kind") != "prepared native metric DTM":
        raise RuntimeError("native DTM patch source kind drifted")
    if source.get("crs") != "EPSG:32632":
        raise RuntimeError(f"native DTM patch CRS drifted: {source.get('crs')}")
    if source.get("landscape_collision_sampled") is not False:
        raise RuntimeError("Gate C.3 patch unexpectedly samples Landscape collision")
    if policy.get("native_dtm_direct") is not True or policy.get("smoothing_applied") is not False:
        raise RuntimeError("Gate C.3 native-DTM policy drifted")
    if grid.get("x_order") != "ue_x_ascending" or grid.get("row_order") != "ue_y_descending":
        raise RuntimeError("Gate C.3 patch axis order drifted")

    rows = int(grid["rows"])
    columns = int(grid["columns"])
    step_x_m = float(grid["step_x_m"])
    step_y_m = float(grid["step_y_m"])
    if rows < 3 or columns < 3 or abs(step_x_m - 1.0) > 1e-6 or abs(step_y_m - 1.0) > 1e-6:
        raise RuntimeError(
            f"Gate C.3 patch grid drifted: rows={rows} columns={columns} "
            f"step=({step_x_m},{step_y_m})"
        )

    binary_path = metadata_path.parent / str(binary["file"])
    raw = binary_path.read_bytes()
    expected_bytes = rows * columns * 4
    if len(raw) != expected_bytes or int(binary.get("byte_count", -1)) != expected_bytes:
        raise RuntimeError(
            f"Gate C.3 patch byte count mismatch: actual={len(raw)} expected={expected_bytes}"
        )
    if hashlib.sha256(raw).hexdigest() != str(binary.get("sha256", "")):
        raise RuntimeError("Gate C.3 patch binary SHA256 mismatch")
    if binary.get("dtype") != "float32-le" or binary.get("layout") != "row-major":
        raise RuntimeError("Gate C.3 patch binary contract drifted")

    values = struct.unpack(f"<{rows * columns}f", raw)
    heights_m = tuple(
        tuple(values[row * columns : (row + 1) * columns])
        for row in range(rows)
    )
    first_x_m = float(grid["first_ue_x_m"])
    first_y_m = float(grid["first_ue_y_m"])
    x_coordinates_m = tuple(first_x_m + column * step_x_m for column in range(columns))
    y_coordinates_m = tuple(first_y_m - row * step_y_m for row in range(rows))

    focus_x_m = float(center_world.x) / 100.0
    focus_y_m = float(center_world.y) / 100.0
    min_x_m = min(x_coordinates_m)
    max_x_m = max(x_coordinates_m)
    min_y_m = min(y_coordinates_m)
    max_y_m = max(y_coordinates_m)
    focus_margin_m = min(
        focus_x_m - min_x_m,
        max_x_m - focus_x_m,
        focus_y_m - min_y_m,
        max_y_m - focus_y_m,
    )
    if focus_margin_m < 100.0:
        raise RuntimeError(
            "Gate C.3 prepared patch does not contain the actual rendered hairpin "
            f"with the required 100 m margin: margin={focus_margin_m:.3f} m "
            f"focus=({focus_x_m:.3f},{focus_y_m:.3f})"
        )

    origin_z_m = min(values)
    mesh = build_terrain_skin_mesh(
        x_coordinates_m,
        y_coordinates_m,
        heights_m,
        origin_x_m=first_x_m,
        origin_y_m=first_y_m,
        origin_z_m=origin_z_m,
        lift_m=0.0,
    )
    origin_world = unreal.Vector(first_x_m * 100.0, first_y_m * 100.0, origin_z_m * 100.0)
    diagnostics = {
        "world_aligned": True,
        "native_metric_dtm": True,
        "landscape_collision_sampled": False,
        "source": "prepared native metric DTM bounded patch",
        "source_crs": source["crs"],
        "source_sha256": source["sha256"],
        "binary_sha256": binary["sha256"],
        "grid_step_m": step_x_m,
        "half_extent_m": float(grid["extent_m"]) * 0.5,
        "row_count": rows,
        "column_count": columns,
        "sample_count": rows * columns,
        "smoothing_applied": False,
        "proof_focus_margin_m": focus_margin_m,
        "proof_focus_ue_m": [focus_x_m, focus_y_m],
        "occlusion_lift_m": 0.0,
        "mesh_sha256": terrain_skin_hash(mesh),
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
    return {"vertices": vertex_count, "triangles": triangle_count, "spawned": True}


def _disabled_mesh_counts() -> dict[str, int | bool]:
    return {"vertices": 0, "triangles": 0, "spawned": False}


def main() -> None:
    global _task, _tick_handle, _started_at, _output_path, _proof_path, _camera
    global _proof_data

    variant_name = os.environ.get(DIAGNOSTIC_VARIANT_ENV, "E").strip().upper() or "E"
    if variant_name not in DIAGNOSTIC_VARIANTS:
        raise RuntimeError(
            f"unsupported {DIAGNOSTIC_VARIANT_ENV}={variant_name!r}; "
            f"expected one of {sorted(DIAGNOSTIC_VARIANTS)}"
        )
    variant = DIAGNOSTIC_VARIANTS[variant_name]

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

    if variant_name == "A":
        from scripts.ue.audit_macro_landscape import capture_macro_height_evidence

        capture_macro_height_evidence(
            world, landscape, landscape_components, _proof_path.parent
        )

    road_actor, spline, original_control_count = _find_road_spline()
    for component in road_actor.get_components_by_class(unreal.SplineMeshComponent):
        component.set_visibility(False, True)

    pcgex_presentation = _load_pcgex_presentation_centerline()
    pcgex_metadata: dict[str, object] | None = None
    if pcgex_presentation is not None:
        pcgex_points, pcgex_metadata = pcgex_presentation
        render_control_count = _replace_with_pcgex_centerline(
            spline,
            pcgex_points,
        )
        pcgex_metadata["render_control_point_count"] = render_control_count
        unreal.log(
            "[YacsSp638LocalCorridorVisual] using PCGEx presentation centerline: "
            f"source_points={len(pcgex_points)} render_controls={render_control_count}"
        )

    full_length_cm = float(spline.get_spline_length())
    focus_cm, curvature_score = _choose_hairpin_distance(spline)
    start_cm = max(0.0, focus_cm - SLICE_HALF_LENGTH_CM)
    end_cm = min(full_length_cm, focus_cm + SLICE_HALF_LENGTH_CM)

    camera_distance_cm = max(0.0, focus_cm - CAMERA_BACK_CM)
    target_distance_cm = min(full_length_cm, focus_cm + LOOK_AHEAD_CM)
    # Sample the forward frame before replacing the full spline with its slice.
    road_forward = spline.get_direction_at_distance_along_spline(
        camera_distance_cm,
        unreal.SplineCoordinateSpace.WORLD,
    )
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
    terrain_skin_center_world = kernel_world[len(kernel_world) // 2]
    proof_focus_contract = _validate_pcgex_proof_focus(
        terrain_skin_center_world,
        pcgex_metadata,
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

    if not hasattr(landscape, "get_edit_layers_bp"):
        raise RuntimeError(
            "UE 5.8 Landscape.get_edit_layers_bp() is unavailable; "
            "cannot verify semantic edit-layer ownership"
        )

    edit_layer_names: list[str] = []
    for edit_layer in landscape.get_edit_layers_bp():
        if edit_layer is None or not hasattr(edit_layer, "get_name_bp"):
            raise RuntimeError(
                "Landscape edit-layer entry does not expose get_name_bp()"
            )
        name = str(edit_layer.get_name_bp())
        if name and name != "None":
            edit_layer_names.append(name)

    if "Base_DTM" not in edit_layer_names:
        raise RuntimeError(
            f"required Base_DTM edit layer is missing: {edit_layer_names}"
        )
    road_earthworks_layers = [
        name for name in edit_layer_names if name == "Road_Earthworks"
    ]
    if len(road_earthworks_layers) != 1:
        raise RuntimeError(
            "expected exactly one Road_Earthworks edit layer, "
            f"found {len(road_earthworks_layers)} in {edit_layer_names}"
        )
    edit_layer_name = road_earthworks_layers[0]

    if bool(variant["apply_landscape_cut_fill"]):
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

    terrain_skin_mesh = None
    terrain_skin_origin_world = None
    terrain_skin_diagnostics: dict[str, object] = {
        "enabled": False,
        "source": "not sampled for this diagnostic variant",
        "canonical_road_xy_modified": False,
    }
    if bool(variant["local_terrain_visible"]):
        (
            terrain_skin_mesh,
            terrain_skin_origin_world,
            terrain_skin_diagnostics,
        ) = (
            _load_native_dtm_patch(terrain_skin_center_world)
            if variant_name == "C3"
            else _sample_local_terrain_skin(
                world,
                road_actor,
                terrain_skin_center_world,
            )
        )
        terrain_skin_diagnostics["enabled"] = True

    neutral_landscape_material = unreal.load_asset(
        "/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial"
    )
    if neutral_landscape_material is None:
        raise RuntimeError("failed to load neutral Landscape proof material")
    landscape.set_editor_property(
        "landscape_material",
        neutral_landscape_material,
    )

    basic_material = unreal.load_asset(
        "/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"
    )
    terrain_skin_material = None
    earth_material = None
    shoulder_material = None
    road_material = None
    if basic_material is not None:
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

    terrain_skin_counts = _disabled_mesh_counts()
    if bool(variant["local_terrain_visible"]):
        if terrain_skin_mesh is None or terrain_skin_origin_world is None:
            raise RuntimeError("local terrain variant did not build a terrain skin")
        terrain_skin_counts = _spawn_dynamic_mesh(
            actor_subsystem,
            terrain_skin_origin_world,
            terrain_skin_mesh,
            "SP638_LocalTerrainSkin",
            terrain_skin_material,
        )

    origin_world = kernel_world[0]
    earth_counts = _disabled_mesh_counts()
    left_shoulder_counts = _disabled_mesh_counts()
    right_shoulder_counts = _disabled_mesh_counts()
    road_counts = _disabled_mesh_counts()
    if bool(variant["corridor_visible"]):
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

    macro_landscape_visible = bool(variant["macro_landscape_visible"])
    landscape.set_actor_hidden_in_game(not macro_landscape_visible)
    for component in landscape_components:
        component.set_visibility(macro_landscape_visible, True)

    from scripts.ue.road_capture_camera import rider_capture_frame

    camera_frame = rider_capture_frame(
        (float(road_camera.x), float(road_camera.y), float(road_camera.z)),
        (float(road_forward.x), float(road_forward.y), float(road_forward.z)),
        (float(road_target.x), float(road_target.y), float(road_target.z) + 80.0),
        EYE_HEIGHT_CM,
    )
    camera_frame["camera_station_m"] = camera_distance_cm / 100.0
    camera_frame["legacy_target_station_m"] = target_distance_cm / 100.0
    camera_location = unreal.Vector(*camera_frame["camera_location_cm"])
    target = unreal.Vector(*camera_frame["target_cm"])
    camera_rotation = unreal.MathLibrary.find_look_at_rotation(
        camera_location,
        target,
    )

    unreal.SystemLibrary.execute_console_command(
        world,
        "r.RayTracing.Geometry.Landscape.LODBias -1",
    )
    # Keep all A-E captures on the same lit proof path. Surface ownership is
    # changed only through explicit variant visibility, never through lighting.
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
        "capture_strategy": (
            "gate-c3-native-dtm-bounded-patch"
            if variant_name == "C3"
            else "gate-c1-surface-ownership-diagnostic"
        ),
        "diagnostic_variant": variant_name,
        "persisted_map_layers_preserved": True,
        "surface_visibility": {
            "macro_landscape": macro_landscape_visible,
            "local_terrain": bool(variant["local_terrain_visible"]),
            "corridor": bool(variant["corridor_visible"]),
        },
        "render_centerline": (
            pcgex_metadata
            if pcgex_metadata is not None
            else {
                "source": "persisted_sp638_spline",
                "pcgex_presentation_only": False,
                "canonical_route_authority_preserved": True,
                "authoritative_physics": False,
            }
        ),
        "source_full_road_length_m": round(full_length_cm / 100.0, 3),
        "source_control_points": original_control_count,
        "selected_hairpin_distance_m": round(focus_cm / 100.0, 3),
        "proof_focus_contract": proof_focus_contract,
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
            "applied": bool(variant["apply_landscape_cut_fill"]),
            "available_edit_layers": edit_layer_names,
            "selected_earthworks_layer": edit_layer_name,
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
            "landscape_hidden_after_sampling": not macro_landscape_visible,
            "macro_landscape_visible": macro_landscape_visible,
            "occlusion_lift_m": (
                float(terrain_skin_diagnostics.get("occlusion_lift_m", TERRAIN_SKIN_LIFT_M))
                if bool(variant["local_terrain_visible"])
                else 0.0
            ),
        },
        "landscape_component_count": len(landscape_components),
        "forced_landscape_lod": 0,
        "proof_viewmode": "lit",
        "neutral_landscape_material": True,
        "camera_frame": camera_frame,
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

    # Load for the actual rider view; elapsed time alone is not resource readiness.
    from scripts.ue.prepare_landscape_capture import prepare_capture

    _proof_data["capture_preparation"] = prepare_capture(
        unreal, landscape, camera_location, camera_rotation, _proof_path.parent,
        request_height_mips=macro_landscape_visible,
    )

    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    _task = unreal.AutomationLibrary.take_high_res_screenshot(
        res_x=CAPTURE_RES_X,
        res_y=CAPTURE_RES_Y,
        filename=str(_output_path),
        camera=_camera,
        mask_enabled=False,
        capture_hdr=False,
        comparison_tolerance=unreal.ComparisonTolerance.LOW,
        comparison_notes=(
            "Gate C.3 native metric DTM bounded patch"
            if variant_name == "C3"
            else f"Gate C.1 surface ownership diagnostic variant {variant_name}"
        ),
        delay=3.0,
        force_game_view=True,
    )
    if not _task or not _task.is_valid_task():
        raise RuntimeError("AutomationLibrary returned an invalid screenshot task")

    _started_at = time.monotonic()
    _tick_handle = unreal.register_slate_post_tick_callback(_tick)
    unreal.log(
        "[YacsSp638LocalCorridorVisual] screenshot scheduled: "
        f"variant={variant_name} "
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
    _release_python_script()
    raise

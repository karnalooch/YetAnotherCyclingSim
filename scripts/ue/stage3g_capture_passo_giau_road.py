"""Render a cyclist-height proof of the persisted official SP638 road spline."""

from __future__ import annotations

from array import array
import json
import math
import os
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
    make_branch_clearance_adaptive_profiles,
    make_curvature_adaptive_profiles,
)


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
LANDSCAPE_VERTICES = 4033
LANDSCAPE_MAX_INDEX = LANDSCAPE_VERTICES - 1
XY_SCALE_CM_PER_VERTEX = 198.412698
CUT_SKIN_HALF_LENGTH_CM = 10000.0
CUT_SKIN_STATION_STEP_CM = 250.0
CUT_SKIN_INNER_OFFSET_CM = 315.0
CUT_SKIN_MAX_OUTER_TIE_OFFSET_CM = 1100.0
CUT_SKIN_COLUMNS = 6
CUT_SKIN_LIFT_CM = 3.0
CUT_SKIN_CLEARANCE_FRACTION = 0.75
CUT_SKIN_MINIMUM_SHOULDER_SPAN_M = 0.25
CUT_SKIN_MINIMUM_EARTHWORK_SPAN_M = 0.10
CUT_SKIN_TAPER_PER_STATION = 0.12
CUT_SKIN_CURVATURE_HALF_WINDOW_STATIONS = 3
CUT_SKIN_BRANCH_CLEARANCE_FRACTION = 0.45
CUT_SKIN_BRANCH_MIN_STATION_SEPARATION = 8
CUT_SKIN_BRANCH_MAX_NEIGHBOR_DISTANCE_M = 30.0
ROAD_MESH_TANGENT_CHORD_FACTOR = 0.5
CUT_SKIN_PROFILE = (
    CrossSectionPoint(-11.0, 0.0, "left_tie"),
    CrossSectionPoint(-9.43, 0.0, "left_earthwork_outer"),
    CrossSectionPoint(-7.86, 0.0, "left_earthwork_mid"),
    CrossSectionPoint(-6.29, 0.0, "left_earthwork_inner"),
    CrossSectionPoint(-4.72, 0.0, "left_shoulder"),
    CrossSectionPoint(-3.15, 0.0, "left_road_edge"),
    CrossSectionPoint(3.15, 0.0, "right_road_edge"),
    CrossSectionPoint(4.72, 0.0, "right_shoulder"),
    CrossSectionPoint(6.29, 0.0, "right_earthwork_inner"),
    CrossSectionPoint(7.86, 0.0, "right_earthwork_mid"),
    CrossSectionPoint(9.43, 0.0, "right_earthwork_outer"),
    CrossSectionPoint(11.0, 0.0, "right_tie"),
)
CUT_SKIN_MIN_FOCUS_RELIEF_CM = 50.0
R16_RELATIVE_PATH = Path(
    "ExternalAssets/Terrain/PassoGiau/PreparedMasePstLidar1x1/"
    "passo_giau_mase_pst_ue_landscape_4033.r16"
)

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
            "capture_strategy": "rider-height-retaining-fill-road-tangent-clamp-proof",
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



def _clamp_road_mesh_tangents_for_ab(
    spline: unreal.SplineComponent,
    road_spline_meshes: list[unreal.SplineMeshComponent],
) -> dict[str, object]:
    expected_segments = int(spline.get_number_of_spline_points()) - 1
    if len(road_spline_meshes) != expected_segments:
        raise RuntimeError(
            "road tangent A/B segment count mismatch: "
            f"{len(road_spline_meshes)} != {expected_segments}"
        )

    clamped_segments = 0
    max_ratio_before = 0.0
    max_ratio_after = 0.0

    def vector_size(vector: unreal.Vector) -> float:
        return math.sqrt(
            float(vector.x * vector.x + vector.y * vector.y + vector.z * vector.z)
        )

    def clamp_tangent(
        tangent: unreal.Vector,
        maximum_length: float,
    ) -> tuple[unreal.Vector, bool]:
        length = vector_size(tangent)
        if length <= maximum_length or length <= 1e-6:
            return tangent, False
        scale = maximum_length / length
        return (
            unreal.Vector(
                float(tangent.x) * scale,
                float(tangent.y) * scale,
                float(tangent.z) * scale,
            ),
            True,
        )

    for index, segment in enumerate(road_spline_meshes):
        start_position = segment.get_start_position()
        end_position = segment.get_end_position()
        start_tangent = segment.get_start_tangent()
        end_tangent = segment.get_end_tangent()
        chord = unreal.Vector(
            float(end_position.x - start_position.x),
            float(end_position.y - start_position.y),
            float(end_position.z - start_position.z),
        )
        chord_length = vector_size(chord)
        if chord_length <= 1e-3:
            raise RuntimeError(f"road segment {index} has degenerate chord")

        before_ratio = max(
            vector_size(start_tangent),
            vector_size(end_tangent),
        ) / chord_length
        max_ratio_before = max(max_ratio_before, before_ratio)
        maximum_tangent = chord_length * ROAD_MESH_TANGENT_CHORD_FACTOR
        clamped_start, start_changed = clamp_tangent(
            start_tangent,
            maximum_tangent,
        )
        clamped_end, end_changed = clamp_tangent(
            end_tangent,
            maximum_tangent,
        )
        if start_changed or end_changed:
            clamped_segments += 1

        segment.set_start_and_end(
            start_position,
            clamped_start,
            end_position,
            clamped_end,
            True,
        )
        after_ratio = max(
            vector_size(clamped_start),
            vector_size(clamped_end),
        ) / chord_length
        max_ratio_after = max(max_ratio_after, after_ratio)

    return {
        "presentation_only": True,
        "saved_to_map": False,
        "tangent_chord_factor": ROAD_MESH_TANGENT_CHORD_FACTOR,
        "segments": len(road_spline_meshes),
        "clamped_segments": clamped_segments,
        "max_tangent_to_chord_before": round(max_ratio_before, 6),
        "max_tangent_to_chord_after": round(max_ratio_after, 6),
    }



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



def _load_r16_height_data() -> array:
    path = Path(__file__).resolve().parents[2] / R16_RELATIVE_PATH
    raw = path.read_bytes()
    expected_bytes = LANDSCAPE_VERTICES * LANDSCAPE_VERTICES * 2
    if len(raw) != expected_bytes:
        raise RuntimeError(
            f"prepared R16 byte count mismatch: {len(raw)} != {expected_bytes}"
        )
    values = array("H")
    values.frombytes(raw)
    if sys.byteorder != "little":
        values.byteswap()
    if len(values) != LANDSCAPE_VERTICES * LANDSCAPE_VERTICES:
        raise RuntimeError("prepared R16 sample count mismatch")
    return values


def _sample_r16_height_cm(
    values: array,
    *,
    world_x_cm: float,
    world_y_cm: float,
    scale_z: float,
    location_z_cm: float,
) -> float:
    grid_x = world_x_cm / XY_SCALE_CM_PER_VERTEX
    grid_y = world_y_cm / XY_SCALE_CM_PER_VERTEX
    if not 0.0 <= grid_x <= LANDSCAPE_MAX_INDEX:
        raise RuntimeError(f"R16 X sample is outside Landscape: {grid_x:.3f}")
    if not 0.0 <= grid_y <= LANDSCAPE_MAX_INDEX:
        raise RuntimeError(f"R16 Y sample is outside Landscape: {grid_y:.3f}")

    x0 = max(0, min(LANDSCAPE_MAX_INDEX, math.floor(grid_x)))
    y0 = max(0, min(LANDSCAPE_MAX_INDEX, math.floor(grid_y)))
    x1 = min(x0 + 1, LANDSCAPE_MAX_INDEX)
    y1 = min(y0 + 1, LANDSCAPE_MAX_INDEX)
    fx = grid_x - x0
    fy = grid_y - y0

    def sample(x: int, y: int) -> float:
        return float(values[y * LANDSCAPE_VERTICES + x])

    top = sample(x0, y0) * (1.0 - fx) + sample(x1, y0) * fx
    bottom = sample(x0, y1) * (1.0 - fx) + sample(x1, y1) * fx
    encoded = top * (1.0 - fy) + bottom * fy
    return location_z_cm + ((encoded - 32768.0) / 128.0) * scale_z


def _make_material(
    world: unreal.World,
    parent: unreal.MaterialInterface,
    color: unreal.LinearColor,
):
    material = unreal.MaterialLibrary.create_dynamic_material_instance(world, parent)
    material.set_vector_parameter_value("Color", color)
    return material


def _spawn_earthwork_skin(
    world: unreal.World,
    actor_subsystem: unreal.EditorActorSubsystem,
    spline: unreal.SplineComponent,
    *,
    focus_distance_cm: float,
    side: str,
    role: str,
    scale_z: float,
    location_z_cm: float,
    visible: bool,
) -> dict[str, object]:
    side_multiplier = -1.0 if side == "left" else 1.0
    if side not in {"left", "right"}:
        raise RuntimeError(f"invalid earthwork-skin side: {side!r}")
    if role not in {"cut", "fill"}:
        raise RuntimeError(f"invalid earthwork-skin role: {role!r}")

    height_data = _load_r16_height_data()
    spline_length_cm = float(spline.get_spline_length())
    start_cm = max(END_MARGIN_CM, focus_distance_cm - CUT_SKIN_HALF_LENGTH_CM)
    end_cm = min(
        spline_length_cm - END_MARGIN_CM,
        focus_distance_cm + CUT_SKIN_HALF_LENGTH_CM,
    )
    station_count = int(math.ceil((end_cm - start_cm) / CUT_SKIN_STATION_STEP_CM)) + 1
    if not 20 <= station_count <= 100:
        raise RuntimeError(f"earthwork-skin station count is invalid: {station_count}")

    station_roads: list[unreal.Vector] = []
    centerline_m: list[Vec3] = []
    for station_index in range(station_count):
        alpha = station_index / max(1, station_count - 1)
        distance_cm = start_cm + (end_cm - start_cm) * alpha
        road = spline.get_location_at_distance_along_spline(
            distance_cm,
            unreal.SplineCoordinateSpace.WORLD,
        )
        station_roads.append(road)
        centerline_m.append(
            Vec3(
                float(road.x) / 100.0,
                float(road.y) / 100.0,
                float(road.z) / 100.0,
            )
        )

    curvature_profiles = make_curvature_adaptive_profiles(
        tuple(centerline_m),
        CUT_SKIN_PROFILE,
        clearance_fraction=CUT_SKIN_CLEARANCE_FRACTION,
        minimum_shoulder_span_m=CUT_SKIN_MINIMUM_SHOULDER_SPAN_M,
        minimum_earthwork_span_m=CUT_SKIN_MINIMUM_EARTHWORK_SPAN_M,
        taper_per_station=CUT_SKIN_TAPER_PER_STATION,
        curvature_half_window_stations=CUT_SKIN_CURVATURE_HALF_WINDOW_STATIONS,
    )
    adaptive_profiles = make_branch_clearance_adaptive_profiles(
        tuple(centerline_m),
        curvature_profiles,
        clearance_fraction=CUT_SKIN_BRANCH_CLEARANCE_FRACTION,
        minimum_station_separation=CUT_SKIN_BRANCH_MIN_STATION_SEPARATION,
        maximum_neighbor_distance_m=CUT_SKIN_BRANCH_MAX_NEIGHBOR_DISTANCE_M,
        minimum_shoulder_span_m=CUT_SKIN_MINIMUM_SHOULDER_SPAN_M,
        minimum_earthwork_span_m=CUT_SKIN_MINIMUM_EARTHWORK_SPAN_M,
        taper_per_station=CUT_SKIN_TAPER_PER_STATION,
        tangent_half_window_stations=CUT_SKIN_CURVATURE_HALF_WINDOW_STATIONS,
    )

    world_vertices: list[unreal.Vector] = []
    focus_relief_cm = None
    focus_outer_offset_cm = None
    outer_offsets_cm: list[float] = []
    for station_index, (road, station_profile) in enumerate(
        zip(station_roads, adaptive_profiles)
    ):
        alpha = station_index / max(1, station_count - 1)
        distance_cm = start_cm + (end_cm - start_cm) * alpha
        right = spline.get_right_vector_at_distance_along_spline(
            distance_cm,
            unreal.SplineCoordinateSpace.WORLD,
        )
        right_size = math.sqrt(float(right.x * right.x + right.y * right.y))
        if right_size <= 1e-6:
            raise RuntimeError("earthwork-skin road right vector is degenerate")
        right_x = float(right.x) / right_size
        right_y = float(right.y) / right_size

        side_points = [
            point
            for point in station_profile
            if (point.lateral_m < 0.0 if side == "left" else point.lateral_m > 0.0)
        ]
        if side == "left":
            side_points.reverse()
        if len(side_points) != CUT_SKIN_COLUMNS:
            raise RuntimeError(
                f"adaptive earthwork profile has {len(side_points)} columns, "
                f"expected {CUT_SKIN_COLUMNS}"
            )
        offsets_cm = [abs(point.lateral_m) * 100.0 for point in side_points]
        if abs(offsets_cm[0] - CUT_SKIN_INNER_OFFSET_CM) > 0.01:
            raise RuntimeError(
                "curvature-adaptive profile moved the protected road edge: "
                f"{offsets_cm[0]:.3f} cm"
            )
        outer_offset_cm = offsets_cm[-1]
        if outer_offset_cm > CUT_SKIN_MAX_OUTER_TIE_OFFSET_CM + 0.01:
            raise RuntimeError(
                "curvature-adaptive profile expanded beyond the authored tie-in: "
                f"{outer_offset_cm:.3f} cm"
            )
        outer_offsets_cm.append(outer_offset_cm)

        outer_x = float(road.x) + right_x * side_multiplier * outer_offset_cm
        outer_y = float(road.y) + right_y * side_multiplier * outer_offset_cm
        outer_height_cm = _sample_r16_height_cm(
            height_data,
            world_x_cm=outer_x,
            world_y_cm=outer_y,
            scale_z=scale_z,
            location_z_cm=location_z_cm,
        ) + CUT_SKIN_LIFT_CM
        inner_height_cm = float(road.z) + CUT_SKIN_LIFT_CM

        if abs(distance_cm - focus_distance_cm) <= CUT_SKIN_STATION_STEP_CM * 0.51:
            focus_relief_cm = outer_height_cm - float(road.z)
            focus_outer_offset_cm = outer_offset_cm

        span_cm = outer_offset_cm - CUT_SKIN_INNER_OFFSET_CM
        if span_cm <= 0.0:
            raise RuntimeError("curvature-adaptive earthwork span collapsed")
        for offset_cm in offsets_cm:
            fraction = (offset_cm - CUT_SKIN_INNER_OFFSET_CM) / span_cm
            x = float(road.x) + right_x * side_multiplier * offset_cm
            y = float(road.y) + right_y * side_multiplier * offset_cm
            profile_fraction = fraction * fraction * (3.0 - 2.0 * fraction)
            z = (
                inner_height_cm * (1.0 - profile_fraction)
                + outer_height_cm * profile_fraction
            )
            world_vertices.append(unreal.Vector(x, y, z))

    if focus_outer_offset_cm is None:
        raise RuntimeError("earthwork-skin focus adaptive offset was not sampled")
    if focus_relief_cm is None or abs(focus_relief_cm) < CUT_SKIN_MIN_FOCUS_RELIEF_CM:
        raise RuntimeError(
            "earthwork-skin focus relief is too small: "
            f"{focus_relief_cm}"
        )
    if role == "cut" and focus_relief_cm <= 0.0:
        raise RuntimeError(f"cut skin is not uphill at focus: {focus_relief_cm}")
    if role == "fill" and focus_relief_cm >= 0.0:
        raise RuntimeError(f"fill skin is not downhill at focus: {focus_relief_cm}")

    origin = world_vertices[0]
    local_vertices = [
        unreal.Vector(
            float(vertex.x - origin.x),
            float(vertex.y - origin.y),
            float(vertex.z - origin.z),
        )
        for vertex in world_vertices
    ]
    triangles: list[unreal.IntVector] = []
    for station in range(station_count - 1):
        row = station * CUT_SKIN_COLUMNS
        next_row = (station + 1) * CUT_SKIN_COLUMNS
        for column in range(CUT_SKIN_COLUMNS - 1):
            a = row + column
            b = row + column + 1
            c = next_row + column
            d = next_row + column + 1

            def upward(i0: int, i1: int, i2: int) -> unreal.IntVector:
                p0 = world_vertices[i0]
                p1 = world_vertices[i1]
                p2 = world_vertices[i2]
                abx = float(p1.x - p0.x)
                aby = float(p1.y - p0.y)
                acx = float(p2.x - p0.x)
                acy = float(p2.y - p0.y)
                normal_z = abx * acy - aby * acx
                if normal_z >= 0.0:
                    return unreal.IntVector(i0, i1, i2)
                return unreal.IntVector(i0, i2, i1)

            triangles.append(upward(a, c, b))
            triangles.append(upward(b, c, d))

    actor = actor_subsystem.spawn_actor_from_class(
        unreal.DynamicMeshActor,
        origin,
        unreal.Rotator(),
        transient=True,
    )
    if actor is None:
        raise RuntimeError(f"failed to spawn SP638 {role}-skin DynamicMeshActor")
    actor.set_actor_label(f"SP638_R16_{role.title()}Skin")

    component = actor.get_dynamic_mesh_component()
    if component is None:
        raise RuntimeError(f"SP638 {role}-skin actor has no DynamicMeshComponent")
    dynamic_mesh = component.get_dynamic_mesh()
    if dynamic_mesh is None:
        raise RuntimeError(f"SP638 {role}-skin component has no DynamicMesh")

    buffers = unreal.GeometryScriptSimpleMeshBuffers()
    buffers.set_editor_property("vertices", local_vertices)
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

    basic_material = unreal.load_asset(
        "/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"
    )
    if basic_material is not None:
        material = _make_material(
            world,
            basic_material,
            unreal.LinearColor(0.42, 0.39, 0.32, 1.0),
        )
        component.set_material(0, material)
    component.set_cast_shadow(False)
    component.set_visibility(visible, True)

    vertex_count = int(dynamic_mesh.get_vertex_count())
    triangle_count = int(dynamic_mesh.get_triangle_count())
    if vertex_count != len(local_vertices) or triangle_count != len(triangles):
        raise RuntimeError(
            f"SP638 {role}-skin DynamicMesh count mismatch: "
            f"{vertex_count}/{triangle_count} != "
            f"{len(local_vertices)}/{len(triangles)}"
        )

    return {
        "strategy": "r16-curvature-branch-adaptive-route-local-dynamic-mesh",
        "role": role,
        "side": side,
        "transient": True,
        "saved_to_map": False,
        "half_length_m": CUT_SKIN_HALF_LENGTH_CM / 100.0,
        "station_step_m": CUT_SKIN_STATION_STEP_CM / 100.0,
        "station_count": station_count,
        "columns": CUT_SKIN_COLUMNS,
        "cross_profile": "curvature-branch-adaptive-smoothstep-road-edge-to-r16-tie-in",
        "cast_shadow": False,
        "visible": visible,
        "inner_offset_m": CUT_SKIN_INNER_OFFSET_CM / 100.0,
        "max_authored_outer_tie_offset_m": CUT_SKIN_MAX_OUTER_TIE_OFFSET_CM / 100.0,
        "minimum_outer_tie_offset_m": round(min(outer_offsets_cm) / 100.0, 3),
        "maximum_outer_tie_offset_m": round(max(outer_offsets_cm) / 100.0, 3),
        "focus_outer_tie_offset_m": round(float(focus_outer_offset_cm) / 100.0, 3),
        "curvature_adaptive_profiles": True,
        "branch_clearance_adaptive_profiles": True,
        "road_edge_preserved": True,
        "focus_outer_relief_m": round(float(focus_relief_cm) / 100.0, 3),
        "vertices": vertex_count,
        "triangles": triangle_count,
    }


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
    all_spline_meshes = list(
        road_actor.get_components_by_class(unreal.SplineMeshComponent)
    )
    road_spline_meshes = sorted(
        [
            component
            for component in all_spline_meshes
            if str(component.get_name()).startswith("SP638Segment_")
        ],
        key=lambda component: str(component.get_name()),
    )
    retaining_helper_meshes = [
        component
        for component in all_spline_meshes
        if str(component.get_name()).startswith("SP638RetainingSegment_")
    ]
    for component in retaining_helper_meshes:
        component.set_visibility(True, True)
    if len(road_spline_meshes) != control_count - 1:
        raise RuntimeError(
            "persisted road spline-mesh count mismatch: "
            f"controls={control_count} road_meshes={len(road_spline_meshes)}"
        )
    if not 20 <= len(retaining_helper_meshes) < 50:
        raise RuntimeError(
            "bounded retaining-helper mesh count is invalid: "
            f"{len(retaining_helper_meshes)}"
        )

    road_tangent_ab = _clamp_road_mesh_tangents_for_ab(
        spline,
        road_spline_meshes,
    )

    spline_length_cm = float(spline.get_spline_length())
    focus_distance_cm, curvature_score = _choose_hairpin_distance(spline)
    import_proof_path = _proof_path.parent / "landscape_import_proof.json"
    if not import_proof_path.is_file():
        raise RuntimeError(f"Landscape import proof is missing: {import_proof_path}")
    import_proof = json.loads(import_proof_path.read_text(encoding="utf-8"))
    helper_side = str(import_proof.get("retaining_helper_side", ""))
    helper_focus_m = float(import_proof.get("retaining_helper_focus_distance_m", -1.0))
    if abs(helper_focus_m * 100.0 - focus_distance_cm) > 10.0:
        raise RuntimeError("road capture and import proof selected different hairpins")
    scale_z = float(import_proof["scale_z"])
    location_z_cm = float(import_proof["location_z_cm"])
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
    low_side = "left" if helper_side == "right" else "right"
    cut_skin = _spawn_earthwork_skin(
        world,
        actor_subsystem,
        spline,
        focus_distance_cm=focus_distance_cm,
        side=helper_side,
        role="cut",
        scale_z=scale_z,
        location_z_cm=location_z_cm,
        visible=False,
    )
    fill_skin = _spawn_earthwork_skin(
        world,
        actor_subsystem,
        spline,
        focus_distance_cm=focus_distance_cm,
        side=low_side,
        role="fill",
        scale_z=scale_z,
        location_z_cm=location_z_cm,
        visible=True,
    )

    sun = actor_subsystem.spawn_actor_from_class(
        unreal.DirectionalLight,
        camera_location + unreal.Vector(0.0, 0.0, 200000.0),
        unreal.Rotator(pitch=-28.0, yaw=-42.0, roll=0.0),
        transient=True,
    )
    sun.set_actor_label("PassoGiauRoad_ProofSun")
    sun_component = sun.get_component_by_class(unreal.DirectionalLightComponent)
    sun_component.set_intensity(6.0)
    sun_component.set_cast_shadows(False)

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
        "road_spline_mesh_segments": len(road_spline_meshes),
        "road_mesh_tangent_ab": road_tangent_ab,
        "retaining_helper_segments": len(retaining_helper_meshes),
        "persisted_retaining_helper_visible_for_high_side_ab": True,
        "cut_skin": cut_skin,
        "fill_skin": fill_skin,
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
        "proof_sun_cast_shadows": False,
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
        f"controls={control_count} meshes={len(road_spline_meshes)}"
    )


try:
    main()
except Exception as exc:
    unreal.log_error(f"[PassoGiauRoadCapture] FAILURE: {exc}")
    unreal.log_error(traceback.format_exc())
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)
    raise

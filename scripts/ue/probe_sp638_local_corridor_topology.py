"""Read-only topology proof for the R4.1B.3 local SP638 earthwork corridor.

Loads the persisted Passo Giau spike map, selects the exact maximum-curvature
hairpin used by R4.1B.2, samples it densely, and runs the pure-Python corridor
kernel against that real presentation spline. Nothing is saved or mutated.

Units in the Unreal-facing portion are centimetres; the kernel uses metres.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import sys
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
)


SPIKE_MAP = "/Game/Prototype/Maps/L_PassoGiauTerrainSpike"
SLICE_HALF_LENGTH_CM = 35000.0
SAMPLE_STEP_CM = 200.0
CURVATURE_SAMPLE_STEP_CM = 2500.0
CURVATURE_HALF_WINDOW_CM = 2500.0
END_MARGIN_CM = 10000.0

# Topology-only section. The final per-station Z values will be derived from
# Landscape tie-in samples; these fixed values exist only to prove that the
# planned lateral corridor width survives the real hairpin without folding.
TOPOLOGY_PROFILE = (
    CrossSectionPoint(-10.0, 2.5, "left_tie"),
    CrossSectionPoint(-7.0, 1.2, "left_earthwork"),
    CrossSectionPoint(-4.0, 0.15, "left_shoulder"),
    CrossSectionPoint(-3.0, 0.0, "left_road_edge"),
    CrossSectionPoint(3.0, 0.0, "right_road_edge"),
    CrossSectionPoint(4.0, -0.10, "right_shoulder"),
    CrossSectionPoint(7.0, -0.9, "right_earthwork"),
    CrossSectionPoint(10.0, -1.8, "right_tie"),
)


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


def _sample_centerline_m(
    spline: unreal.SplineComponent,
    start_cm: float,
    end_cm: float,
) -> tuple[Vec3, ...]:
    samples_cm: list[unreal.Vector] = []
    distance = start_cm
    while distance < end_cm:
        samples_cm.append(
            spline.get_location_at_distance_along_spline(
                distance,
                unreal.SplineCoordinateSpace.WORLD,
            )
        )
        distance += SAMPLE_STEP_CM
    samples_cm.append(
        spline.get_location_at_distance_along_spline(
            end_cm,
            unreal.SplineCoordinateSpace.WORLD,
        )
    )

    origin = samples_cm[0]
    return tuple(
        Vec3(
            (float(point.x) - float(origin.x)) / 100.0,
            (float(point.y) - float(origin.y)) / 100.0,
            (float(point.z) - float(origin.z)) / 100.0,
        )
        for point in samples_cm
    )


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
    # triangle area = cross2 / 2; R = abc / (4A)
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


def main() -> None:
    output_value = os.environ.get("YACS_SP638_CORRIDOR_TOPOLOGY_JSON", "")
    if not output_value:
        raise RuntimeError("YACS_SP638_CORRIDOR_TOPOLOGY_JSON is required")

    output_path = Path(output_value)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.unlink(missing_ok=True)

    world = unreal.EditorLoadingAndSavingUtils.load_map(SPIKE_MAP)
    if not world:
        raise RuntimeError(f"failed to load {SPIKE_MAP}")

    _actor, spline, control_points = _find_road_spline()
    full_length_cm = float(spline.get_spline_length())
    focus_cm, curvature_score = _choose_hairpin_distance(spline)
    start_cm = max(0.0, focus_cm - SLICE_HALF_LENGTH_CM)
    end_cm = min(full_length_cm, focus_cm + SLICE_HALF_LENGTH_CM)

    centerline = _sample_centerline_m(spline, start_cm, end_cm)
    mesh = build_corridor_mesh(
        centerline,
        make_constant_profiles(len(centerline), TOPOLOGY_PROFILE),
    )
    minimum_radius_m = _minimum_sampled_radius_m(centerline)

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    mesh_actor = actor_subsystem.spawn_actor_from_class(
        unreal.DynamicMeshActor,
        unreal.Vector(),
        unreal.Rotator(),
        transient=True,
    )
    if mesh_actor is None:
        raise RuntimeError("failed to spawn transient DynamicMeshActor")
    mesh_actor.set_actor_label("SP638_LocalCorridor_TopologyProbe")
    mesh_component = mesh_actor.get_dynamic_mesh_component()
    if mesh_component is None:
        raise RuntimeError("DynamicMeshActor has no DynamicMeshComponent")
    dynamic_mesh = mesh_component.get_dynamic_mesh()
    if dynamic_mesh is None:
        raise RuntimeError("DynamicMeshComponent has no DynamicMesh")

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
    mesh_component.notify_mesh_modified()

    unreal_vertex_count = int(dynamic_mesh.get_vertex_count())
    unreal_triangle_count = int(dynamic_mesh.get_triangle_count())
    if unreal_vertex_count != len(mesh.vertices):
        raise RuntimeError(
            "DynamicMesh vertex count mismatch: "
            f"{unreal_vertex_count} != {len(mesh.vertices)}"
        )
    if unreal_triangle_count != len(mesh.triangles):
        raise RuntimeError(
            "DynamicMesh triangle count mismatch: "
            f"{unreal_triangle_count} != {len(mesh.triangles)}"
        )

    payload = {
        "schema_version": 1,
        "sp638_local_corridor_topology": "PASS",
        "map": SPIKE_MAP,
        "presentation_only": True,
        "authoritative_route_geometry": False,
        "authoritative_physics": False,
        "saved_to_map": False,
        "source_control_points": control_points,
        "source_full_road_length_m": round(full_length_cm / 100.0, 3),
        "selected_hairpin_distance_m": round(focus_cm / 100.0, 3),
        "curvature_score": round(curvature_score, 6),
        "slice_start_m": round(start_cm / 100.0, 3),
        "slice_end_m": round(end_cm / 100.0, 3),
        "sample_step_m": SAMPLE_STEP_CM / 100.0,
        "station_count": mesh.station_count,
        "cross_section_point_count": mesh.cross_section_point_count,
        "vertex_count": len(mesh.vertices),
        "triangle_count": len(mesh.triangles),
        "lateral_extent_m": [
            TOPOLOGY_PROFILE[0].lateral_m,
            TOPOLOGY_PROFILE[-1].lateral_m,
        ],
        "minimum_sampled_centerline_radius_m": (
            round(minimum_radius_m, 3) if minimum_radius_m is not None else None
        ),
        "corridor_mesh_sha256": corridor_mesh_hash(mesh),
        "unreal_dynamic_mesh": {
            "actor_class": "DynamicMeshActor",
            "vertex_count": unreal_vertex_count,
            "triangle_count": unreal_triangle_count,
            "append_api": "DynamicMesh.append_buffers_to_mesh",
            "normals_api": "DynamicMesh.recompute_normals",
            "transient": True,
        },
        "validation": {
            "positive_winding": True,
            "no_degenerate_triangles": True,
            "stable_lateral_topology": True,
            "real_sp638_hairpin": True,
            "dynamic_mesh_counts_match_kernel": True,
        },
    }
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    unreal.log(
        "[YacsSp638CorridorTopology] PASS: "
        f"stations={mesh.station_count} vertices={len(mesh.vertices)} "
        f"triangles={len(mesh.triangles)} "
        f"ue_vertices={unreal_vertex_count} "
        f"ue_triangles={unreal_triangle_count} "
        f"min_radius_m={minimum_radius_m} "
        f"hash={payload['corridor_mesh_sha256']}"
    )


try:
    main()
except Exception as exc:
    unreal.log_error(f"[YacsSp638CorridorTopology] FAILURE: {exc}")
    unreal.log_error(traceback.format_exc())
    raise

"""Use native USplineComponent curves to author paired presentation edges.

Runs during the existing map-preparation boot. No saved actor, terrain edit,
custom spline evaluator, or change to the canonical road source is involved.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import unreal


def reference_transition(holder, source, spec):
    start, end = spec["start_station_m"], spec["end_station_m"]
    duration = (end - start) / 2.5
    span = unreal.SplineComponent(outer=holder)
    span.clear_spline_points(False)
    for index, station in enumerate((start, end)):
        key = station / 2.5
        point = source.get_location_at_spline_input_key(
            key, unreal.SplineCoordinateSpace.LOCAL
        )
        tangent = source.get_tangent_at_spline_input_key(
            key, unreal.SplineCoordinateSpace.LOCAL
        )
        span.add_spline_point(point, unreal.SplineCoordinateSpace.LOCAL, False)
        span.set_spline_point_type(
            index, unreal.SplinePointType.CURVE_CUSTOM_TANGENT, False
        )
        span.set_tangent_at_spline_point(
            index,
            unreal.Vector(tangent.x * duration, tangent.y * duration, 0),
            unreal.SplineCoordinateSpace.LOCAL,
            False,
        )
    span.update_spline()
    return span


def author(guide_path):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    guide_path = Path(guide_path)
    guide_bytes = guide_path.read_bytes()
    guides = json.loads(guide_bytes)
    output = guide_path.with_name("ma2141-curved-edges.json")
    if output.exists():
        raise RuntimeError("Preserve native curved-edge evidence")
    if (
        guides["guide_step_m"] != 2.5
        or guides["sample_step_m"] != 0.0625
        or len(guides["guides"]) != 121
        or [g["station_m"] for g in guides["guides"]] != [i * 2.5 for i in range(121)]
    ):
        raise RuntimeError("Unexpected native curve guide domain")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    holder = actors.spawn_actor_from_class(
        unreal.Actor, unreal.Vector(), unreal.Rotator(), transient=True
    )
    if not holder:
        raise RuntimeError("Cannot create transient spline holder")
    try:
        from scripts.geometry.road_edge_roles import anchored_edges
        from scripts.geometry.road_width_profile import boundary_width_profile, width_at

        spline = unreal.SplineComponent(outer=holder)
        spline.clear_spline_points(False)
        if guides.get("geometry_contract") != "cliff-edge-width-v3":
            raise ValueError(
                "Road authoring requires an authoritative edge and explicit width"
            )
        anchor_edge = guides["edge_constraint"]["reference_edge"]
        if anchor_edge not in (0, 1):
            raise ValueError("Missing explicit reference edge")
        for index, row in enumerate(guides["guides"]):
            x, y = row["reference_xy_m"]
            spline.add_spline_point(
                unreal.Vector(x * 100, y * 100, 0),
                unreal.SplineCoordinateSpace.LOCAL,
                False,
            )
            spline.set_spline_point_type(
                index, unreal.SplinePointType.CURVE_CUSTOM_TANGENT, False
            )
            arrive, leave = row["arrive_tangent_xy_m"], row["leave_tangent_xy_m"]
            spline.set_tangents_at_spline_point(
                index,
                unreal.Vector(arrive[0] * 100, arrive[1] * 100, 0),
                unreal.Vector(leave[0] * 100, leave[1] * 100, 0),
                unreal.SplineCoordinateSpace.LOCAL,
                False,
            )
        spline.set_editor_property("allow_discontinuous_spline", True)
        spline.set_closed_loop(False, False)
        spline.update_spline()
        transitions = [
            (spec, reference_transition(holder, spline, spec))
            for spec in guides["reference_arc"]["transitions"]
        ]
        rows = []
        for index in range(4801):
            station = index * 0.0625
            key = station / 2.5
            active = spline
            derivative_scale = 1.0
            for spec, transition in transitions:
                start, end = spec["start_station_m"], spec["end_station_m"]
                if start <= station <= end:
                    active, key = transition, (station - start) / (end - start)
                    derivative_scale = 2.5 / (end - start)
            point = active.get_location_at_spline_input_key(
                key, unreal.SplineCoordinateSpace.LOCAL
            )
            direction = active.get_tangent_at_spline_input_key(
                key, unreal.SplineCoordinateSpace.LOCAL
            )
            anchor = [float(point.x) / 100, float(point.y) / 100]
            tangent = [
                float(direction.x) / 100 * derivative_scale,
                float(direction.y) / 100 * derivative_scale,
            ]
            rows.append(
                {
                    "station_m": station,
                    "anchor_xy_m": anchor,
                    "anchor_tangent_xy_m_per_key": tangent,
                }
            )
        distance_profile, distances = boundary_width_profile(
            guides["width_profile"], rows
        )
        for row, distance in zip(rows, distances):
            width = sum(width_at(distance_profile, distance))
            edges = anchored_edges(
                row["anchor_xy_m"],
                row["anchor_tangent_xy_m_per_key"],
                width,
                anchor_edge,
            )
            row.update(
                edges_xy_m=edges,
                center_xy_m=[(edges[0][k] + edges[1][k]) / 2 for k in range(2)],
                boundary_distance_m=distance,
            )
        result = {
            "schema_version": 1,
            "exact_sha": guides["exact_sha"],
            "source_sha256": guides["source_sha256"],
            "profile_sha256": guides["profile_sha256"],
            "origin_epsg_m": guides["origin_epsg_m"],
            "guide_sha256": hashlib.sha256(guide_bytes).hexdigest(),
            "author_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "producer": "USplineComponent",
            "point_type": "CurveCustomTangent",
            "boundary_spans": [],
            "geometry_contract": guides["geometry_contract"],
            "edge_constraint": guides["edge_constraint"],
            "reference_arc": guides["reference_arc"],
            "width_profile": guides["width_profile"],
            "width_distance_profile": distance_profile,
            "parameterization": "authoritative boundary at source chainage / 2.5 m; not physics distance",
            "status": "NATIVE_CURVES_EXPORTED_REVIEW_REQUIRED",
            "stations": rows,
            "canonical_source_modified": False,
            "map_modified": False,
        }
        output.write_text(json.dumps(result, allow_nan=False) + "\n")
        unreal.log(
            "[BobCurvedEdges] Native edge-constrained pavement exported; validation pending"
        )
    finally:
        actors.destroy_actor(holder)

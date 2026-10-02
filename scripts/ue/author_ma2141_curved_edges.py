"""Use native USplineComponent curves to author paired presentation edges.

Runs during the existing map-preparation boot. No saved actor, terrain edit,
custom spline evaluator, or change to the canonical road source is involved.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import unreal


def axis_transition(holder, source, start, end):
    span = unreal.SplineComponent(outer=holder)
    span.clear_spline_points(False)
    duration = (end - start) / 2.5
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
        from scripts.geometry.road_width_profile import offset_edges, width_at

        spline = unreal.SplineComponent(outer=holder)
        spline.clear_spline_points(False)
        if guides.get("geometry_contract") != "common-axis-width-v2":
            raise ValueError("Road authoring requires a common axis and explicit width")
        for index, row in enumerate(guides["guides"]):
            x, y = row["center_xy_m"]
            tx, ty = row["tangent_xy_m_per_key"]
            spline.add_spline_point(
                unreal.Vector(x * 100, y * 100, 0),
                unreal.SplineCoordinateSpace.LOCAL,
                False,
            )
            spline.set_spline_point_type(
                index, unreal.SplinePointType.CURVE_CUSTOM_TANGENT, False
            )
            spline.set_tangent_at_spline_point(
                index,
                unreal.Vector(tx * 100, ty * 100, 0),
                unreal.SplineCoordinateSpace.LOCAL,
                False,
            )
        spline.set_closed_loop(False, False)
        spline.update_spline()
        transitions = [
            (
                spec,
                axis_transition(
                    holder, spline, spec["start_station_m"], spec["end_station_m"]
                ),
            )
            for spec in guides["axis_transitions"]
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
            center = [float(point.x) / 100, float(point.y) / 100]
            tangent = [
                float(direction.x) / 100 * derivative_scale,
                float(direction.y) / 100 * derivative_scale,
            ]
            edges = offset_edges(
                center, tangent, width_at(guides["width_profile"], station)
            )
            rows.append(
                {
                    "station_m": station,
                    "edges_xy_m": edges,
                    "center_xy_m": center,
                    "tangent_xy_m_per_key": tangent,
                }
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
            "axis_arc": guides["axis_arc"],
            "axis_transitions": guides["axis_transitions"],
            "width_profile": guides["width_profile"],
            "parameterization": "common axis at source chainage / 2.5 m; not physics distance",
            "status": "NATIVE_CURVES_EXPORTED_REVIEW_REQUIRED",
            "stations": rows,
            "canonical_source_modified": False,
            "map_modified": False,
        }
        output.write_text(json.dumps(result, allow_nan=False) + "\n")
        unreal.log(
            "[BobCurvedEdges] Native common-axis pavement exported; validation pending"
        )
    finally:
        actors.destroy_actor(holder)

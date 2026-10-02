"""Use native USplineComponent curves to author paired presentation edges.

Runs during the existing map-preparation boot. No saved actor, terrain edit,
custom spline evaluator, or change to the canonical road source is involved.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import unreal


def boundary_span(holder, source, start_key, end_key):
    """One native cubic, with the source endpoint positions and derivatives."""
    span = unreal.SplineComponent(outer=holder)
    span.clear_spline_points(False)
    duration = end_key - start_key
    if duration <= 0:
        raise ValueError("Boundary span must advance source chainage")
    for index, key in enumerate((start_key, end_key)):
        point = source.get_location_at_spline_input_key(
            key, unreal.SplineCoordinateSpace.LOCAL
        )
        tangent = source.get_tangent_at_spline_input_key(
            key, unreal.SplineCoordinateSpace.LOCAL
        )
        # Source keys cover 2.5 m; the new single segment covers the whole span.
        tangent = unreal.Vector(tangent.x * duration, tangent.y * duration, 0.0)
        span.add_spline_point(point, unreal.SplineCoordinateSpace.LOCAL, False)
        span.set_spline_point_type(
            index, unreal.SplinePointType.CURVE_CUSTOM_TANGENT, False
        )
        span.set_tangent_at_spline_point(
            index, tangent, unreal.SplineCoordinateSpace.LOCAL, False
        )
    span.set_closed_loop(False, False)
    span.update_spline()
    position_error, tangent_error = 0.0, 0.0
    for index, key in enumerate((start_key, end_key)):
        original = source.get_location_at_spline_input_key(
            key, unreal.SplineCoordinateSpace.LOCAL
        )
        actual = span.get_location_at_spline_input_key(
            index, unreal.SplineCoordinateSpace.LOCAL
        )
        before = source.get_tangent_at_spline_input_key(
            key, unreal.SplineCoordinateSpace.LOCAL
        )
        after = span.get_tangent_at_spline_input_key(
            index, unreal.SplineCoordinateSpace.LOCAL
        )
        position_error = max(
            position_error,
            math.hypot(actual.x - original.x, actual.y - original.y) / 100,
        )
        tangent_error = max(
            tangent_error,
            math.hypot(after.x / duration - before.x, after.y / duration - before.y)
            / 100,
        )
    if max(position_error, tangent_error) > 1e-4:
        raise ValueError("Native boundary span breaks position/tangent continuity")
    return span, {
        "join_position_error_m": position_error,
        "join_tangent_error_m_per_key": tangent_error,
    }


def author(guide_path):
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
        curves = []
        for edge in range(2):
            spline = unreal.SplineComponent(outer=holder)
            spline.clear_spline_points(False)
            for index, row in enumerate(guides["guides"]):
                x, y = row["edges_xy_m"][edge]
                spline.add_spline_point(
                    unreal.Vector(x * 100.0, y * 100.0, 0.0),
                    unreal.SplineCoordinateSpace.LOCAL,
                    False,
                )
                spline.set_spline_point_type(index, unreal.SplinePointType.CURVE, False)
            spline.set_closed_loop(False, False)
            spline.update_spline()
            curves.append(spline)
        spans = []
        for spec in guides.get("boundary_spans", []):
            start, end = spec["start_station_m"], spec["end_station_m"]
            if spec["edge"] not in (0, 1) or not 0 <= start < end <= 300:
                raise ValueError("Invalid presentation boundary span")
            if any(
                old["edge"] == spec["edge"]
                and max(start, old["start_station_m"]) < min(end, old["end_station_m"])
                for old, _ in spans
            ):
                raise ValueError("Overlapping presentation boundary spans")
            replacement, joins = boundary_span(
                holder, curves[spec["edge"]], start / 2.5, end / 2.5
            )
            spans.append((dict(spec, **joins), replacement))
        rows = []
        for index in range(4801):
            station = index * 0.0625
            edges = []
            for edge, spline in enumerate(curves):
                key = station / 2.5
                for spec, replacement in spans:
                    start, end = spec["start_station_m"], spec["end_station_m"]
                    if edge == spec["edge"] and start <= station <= end:
                        spline, key = replacement, (station - start) / (end - start)
                point = spline.get_location_at_spline_input_key(
                    key, unreal.SplineCoordinateSpace.LOCAL
                )
                edges.append([float(point.x) / 100.0, float(point.y) / 100.0])
            rows.append({"station_m": station, "edges_xy_m": edges})
        result = {
            "schema_version": 1,
            "exact_sha": guides["exact_sha"],
            "source_sha256": guides["source_sha256"],
            "profile_sha256": guides["profile_sha256"],
            "origin_epsg_m": guides["origin_epsg_m"],
            "guide_sha256": hashlib.sha256(guide_bytes).hexdigest(),
            "author_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "producer": "USplineComponent",
            "point_type": "Curve",
            "boundary_spans": [
                dict(spec, point_type="CurveCustomTangent") for spec, _ in spans
            ],
            "parameterization": "shared source chainage / 2.5 m; not edge arc length",
            "status": "NATIVE_CURVES_EXPORTED_REVIEW_REQUIRED",
            "stations": rows,
            "canonical_source_modified": False,
            "map_modified": False,
        }
        output.write_text(json.dumps(result, allow_nan=False) + "\n")
        unreal.log("[BobCurvedEdges] Native paired curves exported; validation pending")
    finally:
        actors.destroy_actor(holder)

"""Use native USplineComponent curves to author paired presentation edges.

Runs during the existing map-preparation boot. No saved actor, terrain edit,
custom spline evaluator, or change to the canonical road source is involved.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import unreal


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
        rows = []
        for index in range(4801):
            station = index * 0.0625
            edges = []
            for spline in curves:
                point = spline.get_location_at_spline_input_key(
                    station / 2.5, unreal.SplineCoordinateSpace.LOCAL
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

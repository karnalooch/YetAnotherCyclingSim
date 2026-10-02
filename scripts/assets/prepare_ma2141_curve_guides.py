"""Prepare paired pavement guides for native Unreal spline authoring."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.assets.prepare_ma2141_diagnostic import SOURCE_SHA, sha256
from scripts.assets.prepare_ma2141_road_preview import (
    PROFILE,
    build_trial,
    read_profile,
)

# Explicit bounded presentation fit; raw CartoCiudad/physics remain separate.
AXIS_ARC = {
    "fit_start_m": 135.0,
    "fit_end_m": 155.0,
    "blend_start_m": 125.0,
    "blend_end_m": 165.0,
    "evidence": "Pinned PNOA pavement-midpoint inference; owner review required",
}


def axis_guides(guides):
    """Fit a circle to observed midpoints and join it smoothly to the approach.

    This creates native spline controls, not a replacement spline evaluator.
    Circle radius is measured from inputs, not prescribed by terrain contact.
    """
    import math

    import numpy as np

    from scripts.assets.prepare_ma2141_profile import local_linear_fit

    stations = np.array([r["station_m"] for r in guides])
    centers = np.array([np.mean(r["edges_xy_m"], axis=0) for r in guides])
    use = (stations >= AXIS_ARC["fit_start_m"]) & (stations <= AXIS_ARC["fit_end_m"])
    points = centers[use]
    anchor = points.mean(axis=0)
    local = points - anchor
    design = np.column_stack((2 * local, np.ones(len(local))))
    coefficients, _, rank, _ = np.linalg.lstsq(
        design, np.sum(local**2, axis=1), rcond=None
    )
    if rank != 3:
        raise ValueError("Degenerate hairpin circle observations")
    circle = anchor + coefficients[:2]
    radius = math.sqrt(coefficients[2] + np.dot(coefficients[:2], coefficients[:2]))
    centers = np.column_stack(
        [local_linear_fit(stations, centers[:, k], 7.5) for k in range(2)]
    )
    angles = np.unwrap(np.arctan2(centers[:, 1] - circle[1], centers[:, 0] - circle[0]))
    angular_rates = np.gradient(angles, stations, edge_order=2)
    for i, station in enumerate(stations):
        if AXIS_ARC["fit_start_m"] <= station <= AXIS_ARC["fit_end_m"]:
            angle = angles[i]
            centers[i] = circle + radius * np.array([math.cos(angle), math.sin(angle)])
    tangents = np.gradient(centers, stations, axis=0, edge_order=2) * 2.5
    # Exact circle derivatives in the interior; native cubic approximation is checked.
    for i, station in enumerate(stations):
        if AXIS_ARC["fit_start_m"] <= station <= AXIS_ARC["fit_end_m"]:
            angle = angles[i]
            tangents[i] = (
                radius
                * angular_rates[i]
                * 2.5
                * np.array([-math.sin(angle), math.cos(angle)])
            )
        guides[i]["center_xy_m"] = centers[i].tolist()
        guides[i]["tangent_xy_m_per_key"] = tangents[i].tolist()
    return dict(
        AXIS_ARC,
        center_xy_m=circle.tolist(),
        radius_m=radius,
        maximum_observation_radial_error_m=float(
            np.max(abs(np.linalg.norm(points - circle, axis=1) - radius))
        ),
    )


def prepare(prepared, output, exact_sha):
    if output.exists():
        raise FileExistsError("Preserve previous curve guide evidence")
    if len(exact_sha) != 40 or any(c not in "0123456789abcdef" for c in exact_sha):
        raise ValueError("Exact SHA required")
    manifest = json.loads((prepared / "terrain-import.json").read_text())
    profile, edges = read_profile()
    vertices, _, _ = build_trial(edges, lambda x, y: 0.0, manifest["origin_epsg_m"])
    # Two-and-a-half-metre control spacing removes GIS corners from the dense render
    # control polygon. The two curves share source-chainage input keys.
    guides = [
        {
            "station_m": i * 0.5,
            "edges_xy_m": [vertices[i * 25][:2], vertices[i * 25 + 24][:2]],
        }
        for i in range(0, 601, 5)
    ]
    arc = axis_guides(guides)
    width_profile = {
        "evidence": {
            "class": "Inference",
            "imagery_sha256": profile["imagery_sha256"],
            "method": "Existing observed widths; smooth interpolation; metric re-review pending",
            "geographic_width_admitted": False,
        },
        "samples": [
            {
                "station_m": float(station),
                "left_m": float((hi - lo) / 2),
                "right_m": float((hi - lo) / 2),
            }
            for station, lo, hi in edges
        ],
    }
    packet = {
        "schema_version": 1,
        "exact_sha": exact_sha,
        "source_sha256": SOURCE_SHA,
        "profile_sha256": sha256(PROFILE),
        "origin_epsg_m": manifest["origin_epsg_m"],
        "guide_step_m": 2.5,
        "sample_step_m": 0.0625,
        "guides": guides,
        "boundary_spans": [],
        "axis_arc": arc,
        "axis_transitions": [
            {"start_station_m": 125.0, "end_station_m": 135.0},
            {"start_station_m": 155.0, "end_station_m": 165.0},
        ],
        "width_profile": width_profile,
        "geometry_contract": "common-axis-width-v2",
    }
    output.write_text(json.dumps(packet, allow_nan=False) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-terrain", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exact-sha", required=True)
    args = parser.parse_args()
    prepare(args.prepared_terrain, args.output, args.exact_sha)

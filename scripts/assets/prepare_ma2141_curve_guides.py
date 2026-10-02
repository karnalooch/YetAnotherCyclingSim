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
from scripts.geometry.road_single_bend import CONTRACT, design

# Explicit reviewed-window semantics, not a network-wide terrain assumption.
# Stored edge 0 is travel-left in the authored direction in UE's X/Y frame.
EDGE_CONSTRAINT = {
    "reference_edge": 0,
    "evidence": "Owner cliff-side priority; pinned PNOA-inferred boundary, not LiDAR-extracted pavement",
    "terrain_spans": [
        {
            "start_station_m": 125.0,
            "end_station_m": 165.0,
            "roles": ["CLIFF", "MOUNTAIN"],
            "evidence": "Owner interpretation of the reviewed hairpin; preview inference",
        }
    ],
}


def reference_guides(guides, width_profile):
    """Fit only the reference edge; inner position never participates in fit.

    Circular cubic handles are explicit so uneven source keys cannot create
    curvature spikes. Remaining approaches reuse the existing local fit.
    """
    import math

    import numpy as np

    from scripts.assets.prepare_ma2141_profile import local_linear_fit

    stations = np.array([r["station_m"] for r in guides])
    points = np.array(
        [r["edges_xy_m"][EDGE_CONSTRAINT["reference_edge"]] for r in guides]
    )
    start, end = 135.0, 155.0
    use = (stations >= start) & (stations <= end)
    observed = points[use]
    origin = observed.mean(axis=0)
    local = observed - origin
    design = np.column_stack((2 * local, np.ones(len(local))))
    coefficients, _, rank, _ = np.linalg.lstsq(
        design, np.sum(local**2, axis=1), rcond=None
    )
    if rank != 3:
        raise ValueError("Degenerate reference-edge arc")
    center = origin + coefficients[:2]
    radius = math.sqrt(coefficients[2] + np.dot(coefficients[:2], coefficients[:2]))
    # Avoid the focal singularity of a normal offset; retain a 1.3 m design margin.
    maximum_width = max(r["left_m"] + r["right_m"] for r in width_profile["samples"])
    radius = max(radius, maximum_width + 1.3)
    for _ in range(8):
        vector = observed - center
        lengths = np.linalg.norm(vector, axis=1)
        center += np.linalg.lstsq(
            -vector / lengths[:, None], radius - lengths, rcond=None
        )[0]
    angles = np.unwrap(np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0]))
    controls = np.column_stack(
        [local_linear_fit(stations, points[:, k], 7.5) for k in (0, 1)]
    )
    controls[use] = center + radius * np.column_stack(
        (np.cos(angles[use]), np.sin(angles[use]))
    )
    tangents = np.gradient(controls, stations, axis=0, edge_order=2) * 2.5
    for i, row in enumerate(guides):
        arrive, leave = tangents[i].copy(), tangents[i].copy()
        if use[i]:
            direction = np.array([-math.sin(angles[i]), math.cos(angles[i])])
            rate = (angles[min(i + 1, len(angles) - 1)] - angles[max(i - 1, 0)]) / 2
            arrive = leave = direction * radius * rate
            if i > 0 and use[i - 1]:
                arrive = (
                    direction * 4 * radius * math.tan((angles[i] - angles[i - 1]) / 4)
                )
            if i + 1 < len(guides) and use[i + 1]:
                leave = (
                    direction * 4 * radius * math.tan((angles[i + 1] - angles[i]) / 4)
                )
        row.update(
            reference_xy_m=controls[i].tolist(),
            arrive_tangent_xy_m=arrive.tolist(),
            leave_tangent_xy_m=leave.tolist(),
        )
    return {
        "center_xy_m": center.tolist(),
        "radius_m": radius,
        "start_station_m": start,
        "end_station_m": end,
        "minimum_offset_margin_m": 1.3,
        "approach_fit_radius_m": 7.5,
        "maximum_observation_radial_error_m": float(
            np.max(abs(np.linalg.norm(observed - center, axis=1) - radius))
        ),
        "transition_method": "quintic-G2-from-native-endpoints",
        "transitions": [
            {"start_station_m": 127.5, "end_station_m": 135.0},
            {"start_station_m": 155.0, "end_station_m": 165.0},
        ],
    }


def prepare(prepared, output, exact_sha):
    if output.exists():
        raise FileExistsError("Preserve previous curve guide evidence")
    if len(exact_sha) != 40 or any(c not in "0123456789abcdef" for c in exact_sha):
        raise ValueError("Exact SHA required")
    manifest = json.loads((prepared / "terrain-import.json").read_text())
    profile, edges = read_profile()
    vertices, _, _ = build_trial(edges, lambda x, y: 0.0, manifest["origin_epsg_m"])
    # Two-and-a-half-metre control spacing removes GIS corners from the dense render
    # control polygon. The authoritative boundary retains source-chainage input keys.
    guides = [
        {
            "station_m": i * 0.5,
            "edges_xy_m": [vertices[i * 25][:2], vertices[i * 25 + 24][:2]],
        }
        for i in range(0, 601, 5)
    ]
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
    reference_arc = reference_guides(guides, width_profile)
    width_profile, single_bend = design(
        guides, [vertices[i * 25:(i + 1) * 25] for i in range(601)],
        width_profile, reference_arc, reference_edge=EDGE_CONSTRAINT["reference_edge"],
    )
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
        "edge_constraint": EDGE_CONSTRAINT,
        "single_bend": single_bend,
        "width_profile": width_profile,
        "geometry_contract": CONTRACT,
    }
    output.write_text(json.dumps(packet, allow_nan=False) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-terrain", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exact-sha", required=True)
    args = parser.parse_args()
    prepare(args.prepared_terrain, args.output, args.exact_sha)

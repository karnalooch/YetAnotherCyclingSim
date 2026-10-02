"""Measure a bounded road-profile candidate before authorizing any earthworks.

This is an offline inference experiment, not an asphalt survey, terrain writer,
or physics profile. Station-local fitting never averages nearby hairpin arms.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.assets.prepare_ma2141_diagnostic import SOURCE_SHA, sha256  # noqa: E402
from scripts.assets.prepare_ma2141_road_preview import (  # noqa: E402
    PROFILE,
    build_trial,
    read_profile,
    triangle_candidates,
)

STATION_STEP_M = 0.5
FIT_RADIUS_M = 5.0
# Review triggers for this experiment, NOT engineering acceptance thresholds.
REVIEW_DELTA_M = 0.5
REVIEW_GRADE = 0.25
REVIEW_CROSSFALL = 0.12


def local_linear_fit(stations, values, radius_m):
    """Weighted least squares in chainage, preserving constant grades at ends."""
    stations = np.asarray(stations, dtype=float)
    values = np.asarray(values, dtype=float)
    if (
        stations.ndim != 1
        or values.shape != stations.shape
        or len(stations) < 3
        or not np.isfinite(stations).all()
        or not np.isfinite(values).all()
        or (np.diff(stations) <= 0).any()
        or not np.isfinite(radius_m)
        or radius_m <= 0
    ):
        raise ValueError("Invalid finite ordered profile samples or radius")
    result = []
    for s in stations:
        offsets = stations - s
        use = np.abs(offsets) < radius_m
        if use.sum() < 3:
            raise ValueError("Profile fit needs three local samples")
        weights = (1 - (np.abs(offsets[use]) / radius_m) ** 3) ** 3
        design = np.column_stack((np.ones(use.sum()), offsets[use]))
        root_weights = np.sqrt(weights)
        coefficients, _, rank, _ = np.linalg.lstsq(
            design * root_weights[:, None], values[use] * root_weights, rcond=None
        )
        if rank != 2:
            raise ValueError("Degenerate profile fit")
        result.append(float(coefficients[0]))
    return np.array(result)


def fit_sections(stations, lateral_m, ground_m, radius_m=FIT_RADIUS_M):
    """Infer a single transverse plane, then regularize along station order.

    Use the central half of the inferred width to reduce roadside contamination;
    evaluate required cut/fill over ALL samples, including the omitted edges.
    Do not clamp extreme results or modify source widths to pass review.
    """
    lateral_m = np.asarray(lateral_m, dtype=float)
    ground_m = np.asarray(ground_m, dtype=float)
    if (
        lateral_m.ndim != 2
        or lateral_m.shape != ground_m.shape
        or lateral_m.shape != (len(stations), 25)
        or not np.isfinite(lateral_m).all()
        or not np.isfinite(ground_m).all()
        or (np.diff(lateral_m, axis=1) <= 0).any()
    ):
        raise ValueError("Invalid finite ordered transverse samples")
    raw = []
    for offsets, heights in zip(lateral_m, ground_m, strict=True):
        design = np.column_stack((np.ones(13), offsets[6:19]))
        coefficients, _, rank, _ = np.linalg.lstsq(design, heights[6:19], rcond=None)
        if rank != 2:
            raise ValueError("Degenerate transverse fit")
        raw.append(coefficients)
    raw = np.asarray(raw)
    center = local_linear_fit(stations, raw[:, 0], radius_m)
    crossfall = local_linear_fit(stations, raw[:, 1], radius_m)
    target = center[:, None] + crossfall[:, None] * lateral_m
    delta = target - ground_m
    grade = np.diff(center) / np.diff(stations)
    flagged = np.flatnonzero(
        (np.max(np.abs(delta), axis=1) > REVIEW_DELTA_M)
        | (np.abs(crossfall) > REVIEW_CROSSFALL)
    )
    grade_flags = np.flatnonzero(np.abs(grade) > REVIEW_GRADE)
    flagged = sorted(
        set(flagged.tolist() + grade_flags.tolist() + (grade_flags + 1).tolist())
    )
    return {
        "raw_center_m": raw[:, 0],
        "center_m": center,
        "raw_crossfall": raw[:, 1],
        "crossfall": crossfall,
        "target_ground_m": target,
        "delta_m": delta,
        "review_station_indices": flagged,
        "metrics": {
            "max_cut_m": float(max(0, -delta.min())),
            "max_fill_m": float(max(0, delta.max())),
            "rms_adjustment_m": float(np.sqrt(np.mean(delta**2))),
            "p95_abs_adjustment_m": float(np.percentile(np.abs(delta), 95)),
            "max_abs_grade": float(np.max(np.abs(grade))),
            "max_abs_crossfall": float(np.max(np.abs(crossfall))),
            "raw_center_second_difference_rms_m": float(
                np.sqrt(np.mean(np.diff(raw[:, 0], n=2) ** 2))
            ),
            "candidate_center_second_difference_rms_m": float(
                np.sqrt(np.mean(np.diff(center, n=2) ** 2))
            ),
            "review_station_count": len(flagged),
        },
    }


def prepare(prepared: Path, output: Path, exact_sha: str):
    if len(exact_sha) != 40 or any(c not in "0123456789abcdef" for c in exact_sha):
        raise ValueError("Exact lowercase SHA required")
    if output.exists():
        raise FileExistsError("Preserve existing profile evidence")
    manifest = json.loads((prepared / "terrain-import.json").read_text())
    r16 = prepared / "terrain.r16"
    if (
        manifest["region_id"] != "sa_calobra"
        or manifest["vertices"] != [4033, 4033]
        or manifest["source_crs"] != "EPSG:25831"
        or manifest["nodata_sample_count"] != 0
        or manifest["source_sha256"]
        != "6092a48a949b7b7e8ccf120cb46d59cfd7fdd3522085e8a55162fd52fe5a139a"
        or r16.stat().st_size != 4033 * 4033 * 2
        or sha256(r16) != manifest["heightmap_sha256"]
    ):
        raise ValueError("Unadmitted native terrain")
    heights = np.fromfile(r16, dtype="<u2").reshape(4033, 4033)
    profile, edges = read_profile()
    origin = manifest["origin_epsg_m"]
    # Existing kernel owns exactly the same inferred footprint and local frame.
    vertices, _, _ = build_trial(
        edges, lambda x, y: triangle_candidates(heights, manifest, x, y)[0], origin
    )
    sections = np.asarray(vertices[:15025]).reshape(601, 25, 3)
    ground = sections[:, :, 2] - 0.04  # Remove the existing nominal slab offset.
    stations = np.arange(601) * STATION_STEP_M
    lateral = np.array(
        [
            np.linspace(
                -np.interp(s, edges[:, 0], edges[:, 2]),
                -np.interp(s, edges[:, 0], edges[:, 1]),
                25,
            )
            for s in stations
        ]
    )
    fit = fit_sections(stations, lateral, ground)
    rows = []
    for i, s in enumerate(stations):
        rows.append(
            {
                "station_m": float(s),
                "xy_local_m": sections[i, :, :2].tolist(),
                "lateral_m": lateral[i].tolist(),
                "native_ground_m": ground[i].tolist(),
                "candidate_ground_m": fit["target_ground_m"][i].tolist(),
                "raw_center_m": float(fit["raw_center_m"][i]),
                "candidate_center_m": float(fit["center_m"][i]),
                "crossfall": float(fit["crossfall"][i]),
                "max_cut_m": float(max(0, -fit["delta_m"][i].min())),
                "max_fill_m": float(max(0, fit["delta_m"][i].max())),
            }
        )
    result = {
        "schema_version": 1,
        "exact_sha": exact_sha,
        "region_id": "sa_calobra",
        "status": "REVIEW_REQUIRED",
        "evidence_class": "Inference",
        "source_sha256": SOURCE_SHA,
        "profile_sha256": sha256(PROFILE),
        "heightmap_sha256": manifest["heightmap_sha256"],
        "origin_epsg_m": origin,
        "metric_crs": "EPSG:25831",
        "earthworks_authoring_permitted": False,
        "producer_sha256": sha256(Path(__file__)),
        "imagery_sha256": profile["imagery_sha256"],
        "parameters": {
            "station_step_m": STATION_STEP_M,
            "fit_radius_m": FIT_RADIUS_M,
            "review_delta_m": REVIEW_DELTA_M,
            "review_grade": REVIEW_GRADE,
            "review_crossfall": REVIEW_CROSSFALL,
        },
        "metrics": fit["metrics"],
        "review_stations_m": [
            float(stations[i]) for i in fit["review_station_indices"]
        ],
        "stations": rows,
        "source_xy_preserved": True,
        "terrain_modified": False,
        "road_earthworks_modified": False,
        "authoritative_physics": False,
        "geographic_width_admitted": False,
        "eligible_for_learning": False,
        "road_admitted": False,
        "limitations": [
            "A smoother numeric profile is not measured asphalt geometry.",
            "Single transverse plane cannot establish road crown or drainage.",
            "Review triggers are experimental, not accepted design limits.",
            "Cut/fill estimates are sample differences, not volumes or authoring commands.",
            "No shoulder falloff, retaining structure, branch overlap or continuous contact proof.",
            "Do not apply this candidate until footprint and flagged locations are reviewed.",
        ],
        "attribution": profile["attribution"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, separators=(",", ":"), allow_nan=False) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-terrain", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exact-sha", required=True)
    args = parser.parse_args()
    result = prepare(args.prepared_terrain, args.output, args.exact_sha)
    print(json.dumps({"status": result["status"], "metrics": result["metrics"]}))

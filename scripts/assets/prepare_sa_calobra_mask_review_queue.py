"""Locate unresolved stream gaps on frozen masks; never authorize a repair."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from rasterio.features import rasterize
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_sa_calobra_pcg_masks import verified_manifest
from verify_sa_calobra_lidar_masks import digest

REASONS = {
    1: "pavement",
    2: "conservative_shoulder",
    4: "conservative_bob",
    8: "mapped_building",
    16: "decorative_water_holdback",
    32: "infrastructure",
    64: "other_lidar_class",
    128: "unknown_samples",
}


def locate_gap(candidate, grid, reasons):
    if grid["crs"] != "EPSG:25831" or grid["transform"] != [
        0.5,
        0.0,
        483000.0,
        0.0,
        -0.5,
        4409516.5,
    ]:
        raise ValueError("Unsupported frozen coordinate contract")
    if reasons.shape != (grid["height"], grid["width"]):
        raise ValueError("Reason raster shape differs from grid")
    line = shape(candidate["geometry"])
    if (
        line.geom_type != "LineString"
        or line.is_empty
        or not line.is_valid
        or not all(math.isfinite(v) for xy in line.coords for v in xy)
        or not math.isfinite(candidate["gap_m"])
        or abs(line.length - candidate["gap_m"]) > 1e-6
        or candidate["status"] != "UNVERIFIED_GAP_CANDIDATE"
    ):
        raise ValueError("Invalid unresolved gap geometry/identity")
    covered = rasterize(
        [(candidate["geometry"], 1)],
        out_shape=reasons.shape,
        transform=Affine(*grid["transform"]),
        all_touched=True,
        dtype="uint8",
    ).astype(bool)
    values = reasons[covered]
    if values.size == 0:
        raise ValueError("Gap does not intersect frozen grid")
    world = [(100 * (x - 483000.25), 100 * (4409516.25 - y)) for x, y in line.coords]
    midpoint = line.interpolate(0.5, normalized=True)
    return {
        "object_id": candidate["object_id"],
        "nearest_object_id": candidate["nearest_object_id"],
        "source_end": candidate["end"],
        "gap_m": candidate["gap_m"],
        "geometry": candidate["geometry"],
        "world_xy_cm": world,
        "focus_world_xy_cm": [
            100 * (midpoint.x - 483000.25),
            100 * (4409516.25 - midpoint.y),
        ],
        "touched_cells": int(values.size),
        "overlap_cells": {
            name: int(np.count_nonzero(values & bit)) for bit, name in REASONS.items()
        },
        "status": "REVIEW_ONLY_KEEP_UNJOINED",
        "culvert": "UNVERIFIED",
        "wetness": "UNKNOWN",
        "repair_authorized": False,
    }


def prepare(transition_path, pcg_path, output):
    if output.exists():
        raise FileExistsError("Preserve previous review queue")
    transition, pcg = verified_manifest(transition_path), verified_manifest(pcg_path)
    if transition["grid"] != pcg["grid"] or not any(
        row["sha256"] == digest(pcg_path) for row in transition["source_manifests"]
    ):
        raise ValueError("Review queue parent identity/grid mismatch")
    audit = json.loads(
        (transition_path.parent / "hydrology-topology-review.json").read_text(
            encoding="utf8"
        )
    )
    candidates = audit["unverified_gap_candidates"]
    if len(candidates) != transition["counts"]["unverified_gap_candidates"]:
        raise ValueError("Unresolved candidate count differs from manifest")
    with rasterio.open(pcg_path.parent / "exclusion-reasons.tif") as ds:
        reasons = ds.read(1)
    rows = [locate_gap(candidate, pcg["grid"], reasons) for candidate in candidates]
    report = {
        "schema_version": 1,
        "status": "REVIEW_QUEUE_ONLY",
        "geometry_mutation": False,
        "hard_exclusions_modified": False,
        "human_visual_acceptance": "PENDING",
        "production_planting": "NOT_ADMITTED",
        "source_manifests": [
            {"path": p.parent.name + "/" + p.name, "sha256": digest(p)}
            for p in [transition_path, pcg_path]
        ],
        "grid": pcg["grid"],
        "count": len(rows),
        "overlap_candidate_counts": {
            name: sum(row["overlap_cells"][name] > 0 for row in rows)
            for name in REASONS.values()
        },
        "overlap_semantics": "All-touched cells on unchanged hard masks; overlaps are not additive and do not prove a road crossing, culvert, actual water extent or a topology error",
        "review_decisions": {
            "larger_gaps": "Keep all candidates unjoined pending source/visual review",
            "bob": "Retain original conservative rectangles and outward-only fade",
            "unknown": "Remain ineligible; no material/species inference",
        },
        "candidates": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transition-manifest", required=True, type=Path)
    parser.add_argument("--pcg-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = prepare(args.transition_manifest, args.pcg_manifest, args.output)
    print(
        json.dumps(
            {
                "count": report["count"],
                "overlap_candidate_counts": report["overlap_candidate_counts"],
            }
        )
    )

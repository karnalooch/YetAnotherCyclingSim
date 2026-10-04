"""Inspect pinned road Z against native ground; never admit or alter a profile."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.assets.prepare_ma2141_diagnostic import sample_encoded

SOURCE = (
    ROOT
    / "worldgen/terrain/benchmarks/sa_calobra/current_landscape_igr_roads_2026-10-03.json"
)
SOURCE_SHA = "0b959ed9ae741d64721669531edd33fac7fe1f1969cd1be58b77785d6eb05ea5"
TERRAIN_SHA = "6092a48a949b7b7e8ccf120cb46d59cfd7fdd3522085e8a55162fd52fe5a139a"


def validate_collection(source):
    features = source["features"]
    if (
        not features
        or source["numberMatched"] != len(features)
        or source["numberReturned"] != len(features)
    ):
        raise ValueError("Incomplete pinned road collection")
    ids = [feature["id"] for feature in features]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate road source identity")
    return features


def compare_vertices(coordinates, project_xy, terrain_height):
    """Compare original XYZ observations only; chainage uses planar SI metres."""
    result = []
    chainage = 0.0
    previous = None
    for coordinate in coordinates:
        if len(coordinate) != 3 or not all(math.isfinite(float(v)) for v in coordinate):
            raise ValueError("Finite source XYZ required")
        x, y = project_xy(coordinate[0], coordinate[1])
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Finite projected XY required")
        if previous is not None:
            chainage += math.dist(previous, (x, y))
        previous = (x, y)
        ground = terrain_height(x, y)
        if ground is None:
            continue
        if not math.isfinite(ground):
            raise ValueError("Finite native ground required")
        result.append(
            {
                "source_chainage_m": chainage,
                "easting_m": x,
                "northing_m": y,
                "source_z_m": coordinate[2],
                "native_ground_z_m": ground,
                "source_minus_ground_m": coordinate[2] - ground,
            }
        )
    return result


def audit(prepared, exact_sha):
    if len(exact_sha) != 40 or any(c not in "0123456789abcdef" for c in exact_sha):
        raise ValueError("Exact lowercase SHA required")
    source_bytes = SOURCE.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != SOURCE_SHA:
        raise ValueError("Pinned road source changed")
    manifest_bytes = (prepared / "terrain-import.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    payload = (prepared / "terrain.r16").read_bytes()
    if (
        manifest["region_id"] != "sa_calobra"
        or manifest["source_crs"] != "EPSG:25831"
        or manifest["vertices"] != [4033, 4033]
        or manifest["nodata_sample_count"] != 0
        or manifest["source_sha256"] != TERRAIN_SHA
        or len(payload) != 4033 * 4033 * 2
        or hashlib.sha256(payload).hexdigest() != manifest["heightmap_sha256"]
    ):
        raise ValueError("Unadmitted native terrain")
    terrain = np.frombuffer(payload, dtype="<u2").reshape(4033, 4033)
    origin_x, origin_y = manifest["origin_epsg_m"]

    def ground(x, y):
        if not (0 <= (x - origin_x) / 0.5 < 4032 and 0 <= (origin_y - y) / 0.5 < 4032):
            return None
        return sample_encoded(terrain, manifest, x, y)

    project = Transformer.from_crs(4326, 25831, always_xy=True).transform
    features = []
    for feature in validate_collection(json.loads(source_bytes)):
        geometry = feature["geometry"]
        if geometry["type"] != "LineString":
            raise ValueError("Unexpected pinned road geometry")
        observations = compare_vertices(geometry["coordinates"], project, ground)
        residuals = np.asarray([p["source_minus_ground_m"] for p in observations])
        stats = (
            None
            if not observations
            else {
                "min_m": float(np.min(residuals)),
                "median_m": float(np.median(residuals)),
                "max_m": float(np.max(residuals)),
                "p95_absolute_m": float(np.percentile(np.abs(residuals), 95)),
            }
        )
        features.append(
            {
                "id": feature["id"],
                "source_properties": feature["properties"],
                "source_vertex_count": len(geometry["coordinates"]),
                "inside_vertex_count": len(observations),
                "outside_vertex_count": len(geometry["coordinates"])
                - len(observations),
                "residuals": stats,
                "observations": observations,
            }
        )
    return {
        "schema_version": 1,
        "exact_sha": exact_sha,
        "source_sha256": SOURCE_SHA,
        "terrain_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "heightmap_sha256": manifest["heightmap_sha256"],
        "status": "SOURCE_HEIGHT_DATUM_AND_ACCURACY_UNVERIFIED",
        "units": "metres",
        "method": "ORIGINAL_SOURCE_VERTICES_VS_BILINEAR_NATIVE_GROUND",
        "source_vertex_spacing_is_not_survey_resolution": True,
        "source_height_authoritative": False,
        "road_height_changed": False,
        "canonical_xy_changed": False,
        "road_admitted": False,
        "full_road_coverage_verified": False,
        "features": features,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-terrain", required=True, type=Path)
    parser.add_argument("--exact-sha", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = audit(args.prepared_terrain, args.exact_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    for feature in report["features"]:
        print(json.dumps({k: v for k, v in feature.items() if k != "observations"}))

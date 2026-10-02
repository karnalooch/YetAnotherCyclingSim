"""Prepare a bounded Ma-2141 alignment diagnostic from immutable official XY.

Native terrain Z is a sampling diagnostic, not reconstructed asphalt elevation.
No flattening, width inference, road carving or road-physics admission occurs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely import wkt
from shapely.geometry import LineString, Point, box
from shapely.ops import substring, transform

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    ROOT
    / "worldgen/terrain/benchmarks/sa_calobra/ma2141_cartociudad_source_2026-10-02.json"
)
SOURCE_SHA = "6520b92486b5d1c63353b8253d388ab21d380c78fda119849311be8344d8ae36"
IGR_SOURCE = SOURCE.with_name("ma2141_igr_rt_source_2026-10-02.json")
IGR_SOURCE_SHA = "ebc7c1c985caae5b7727719856646d52824463803d13095462f8d7ef1fcd7d5f"


def compare_igr_profile(points: list[dict], source: Path = IGR_SOURCE) -> dict:
    """Compare raw third coordinates; never promote them to asphalt truth."""
    if sha256(source) != IGR_SOURCE_SHA:
        raise ValueError("Official IGR-RT source hash mismatch")
    raw = json.loads(source.read_text(encoding="utf-8"))
    features = [f for f in raw["features"] if f["id"] == "VIAL_TR70190001272"]
    if len(features) != 1 or features[0]["geometry"]["type"] != "LineString":
        raise ValueError("IGR-RT source identity/geometry mismatch")
    feature = features[0]
    coords = np.asarray(feature["geometry"]["coordinates"], dtype=float)
    if coords.shape != (223, 3) or not np.isfinite(coords).all():
        raise ValueError("IGR-RT requires finite pinned XYZ coordinates")
    x, y = Transformer.from_crs(4326, 25831, always_xy=True).transform(
        coords[:, 0], coords[:, 1]
    )
    xy = np.column_stack([x, y])
    lengths = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    if (lengths <= 0).any():
        raise ValueError("IGR-RT contains duplicate consecutive XY")
    source_stations = np.r_[0, np.cumsum(lengths)]
    line = LineString(xy)
    samples = [Point(p["easting_m"], p["northing_m"]) for p in points]
    if len(samples) < 2:
        raise ValueError("IGR-RT comparison requires at least two samples")
    offsets = np.array([line.distance(p) for p in samples])
    if offsets.max() > 0.001:
        raise ValueError("IGR-RT XY does not match the selected source alignment")
    stations = np.array([line.project(p) for p in samples])
    station_steps = np.diff(stations)
    if (station_steps < -1e-7).any() or not (station_steps > 1e-7).any():
        raise ValueError("IGR-RT station order is ambiguous")
    source_z = np.interp(stations, source_stations, coords[:, 2])
    dtm_z = np.array([p["native_dtm_z_m"] for p in points], dtype=float)
    if not np.isfinite(dtm_z).all():
        raise ValueError("Comparison terrain heights must be finite")
    difference = source_z - dtm_z
    return {
        "status": "REQUIRES_REVIEW",
        "source_sha256": IGR_SOURCE_SHA,
        "feature_id": feature["id"],
        "source_properties": feature["properties"],
        "max_xy_difference_m": float(offsets.max()),
        "independent_xy_validation": False,
        "vertical_datum": "UNVERIFIED",
        "numeric_z_comparison_only": True,
        "source_minus_dtm_min": float(difference.min()),
        "source_minus_dtm_median": float(np.median(difference)),
        "source_minus_dtm_max": float(difference.max()),
        "source_minus_dtm_rms": float(np.sqrt(np.mean(difference**2))),
        "source_linear_profile_max_abs_slope": float(
            np.max(
                np.abs(
                    np.diff(source_z)[station_steps > 1e-7]
                    / station_steps[station_steps > 1e-7]
                )
            )
        ),
        "earthwork_input_admitted": False,
        "physics_input_admitted": False,
        "reasons": [
            "Vertical datum and feature-specific accuracy are unverified",
            "Source fictitious=true needs interpretation and positional review",
            "Road width and bicycle access remain unknown",
            "Paved category does not specify asphalt composition or physics",
        ],
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_alignment(source: Path = SOURCE):
    if sha256(source) != SOURCE_SHA:
        raise ValueError("Official Ma-2141 source hash mismatch")
    raw = json.loads(source.read_text(encoding="utf-8"))
    if (
        raw["id"] != "604000000293"
        or raw["address"] != "Ma-2141"
        or raw["type"] != "carretera"
    ):
        raise ValueError("Official road source identity mismatch")
    geometry = transform(
        Transformer.from_crs(4326, 25831, always_xy=True).transform,
        wkt.loads(raw["geom"]),
    )
    if geometry.geom_type != "MultiLineString" or len(geometry.geoms) != 6:
        raise ValueError("Official road multipart topology changed")
    line = geometry.geoms[3]
    coordinates = list(line.coords)
    station = sum(math.dist(coordinates[i], coordinates[i + 1]) for i in range(43))
    clip = substring(line, station - 150.0, station + 150.0)
    if not clip.is_simple or not box(483010, 4407510, 485006.5, 4409506.5).covers(clip):
        raise ValueError(
            "Bounded hairpin has ambiguous XY or falls outside terrain margin"
        )
    return line, clip, station


def sample_encoded(
    heights: np.ndarray, manifest: dict, x_m: float, y_m: float
) -> float:
    origin_x, origin_y = manifest["origin_epsg_m"]
    column = (x_m - origin_x) / 0.5
    row = (origin_y - y_m) / 0.5
    if not (0 <= row < 4032 and 0 <= column < 4032):
        raise ValueError("Road sample outside native terrain")
    x0, y0 = int(math.floor(column)), int(math.floor(row))
    dx, dy = column - x0, row - y0
    encoded = (
        float(heights[y0, x0]) * (1 - dx) * (1 - dy)
        + float(heights[y0, x0 + 1]) * dx * (1 - dy)
        + float(heights[y0 + 1, x0]) * (1 - dx) * dy
        + float(heights[y0 + 1, x0 + 1]) * dx * dy
    )
    return (
        (encoded - 32768) * manifest["scale_z"] / 128 + manifest["location_z_cm"]
    ) / 100


def prepare(prepared_terrain: Path, output: Path, exact_sha: str) -> dict:
    if len(exact_sha) != 40 or any(c not in "0123456789abcdef" for c in exact_sha):
        raise ValueError("Exact lowercase commit SHA required")
    if output.exists():
        raise FileExistsError("Existing road diagnostic is preserved")
    manifest = json.loads(
        (prepared_terrain / "terrain-import.json").read_text(encoding="utf-8")
    )
    if (
        manifest["region_id"] != "sa_calobra"
        or manifest["nodata_sample_count"] != 0
        or manifest["source_crs"] != "EPSG:25831"
        or manifest["vertices"] != [4033, 4033]
        or manifest["source_sha256"]
        != "6092a48a949b7b7e8ccf120cb46d59cfd7fdd3522085e8a55162fd52fe5a139a"
    ):
        raise ValueError("Unadmitted terrain diagnostic source")
    r16 = prepared_terrain / "terrain.r16"
    if (
        r16.stat().st_size != 4033 * 4033 * 2
        or sha256(r16) != manifest["heightmap_sha256"]
    ):
        raise ValueError("Native terrain diagnostic hash/size mismatch")
    heights = np.fromfile(r16, dtype="<u2").reshape(4033, 4033)
    line, clip, station = select_alignment()
    # Linear source-segment interpolation keeps every sample on official XY.
    # It adds no curvature detail and does not smooth or move source vertices.
    source_stations = [0.0]
    coordinates = list(line.coords)
    for a, b in zip(coordinates, coordinates[1:]):
        source_stations.append(source_stations[-1] + math.dist(a, b))
    # Keep original vertices when a uniform sample is numerically coincident.
    # A plain set retains 150.0 and 150.00000000000023 as distinct stations.
    stations = [s for s in source_stations if station - 150 <= s <= station + 150]
    for s in [station - 150 + i for i in range(301)]:
        if not any(abs(s - original) < 1e-7 for original in stations):
            stations.append(s)
    stations.sort()
    points = []
    for s in stations:
        xy = line.interpolate(s)
        z = sample_encoded(heights, manifest, xy.x, xy.y)
        points.append(
            {
                "station_m": s - (station - 150),
                "easting_m": xy.x,
                "northing_m": xy.y,
                "native_dtm_z_m": z,
                "x_cm": (xy.x - manifest["origin_epsg_m"][0]) * 100,
                "y_cm": (manifest["origin_epsg_m"][1] - xy.y) * 100,
                "z_cm": z * 100,
            }
        )
    result = {
        "schema_version": 1,
        "exact_sha": exact_sha,
        "region_id": "sa_calobra",
        "source_id": "604000000293",
        "source_sha256": SOURCE_SHA,
        "terrain_source_sha256": manifest["source_sha256"],
        "heightmap_sha256": manifest["heightmap_sha256"],
        "source_part_index": 3,
        "focus_source_vertex_index": 43,
        "length_m": clip.length,
        "source_station_bounds_m": [station - 150, station + 150],
        "alignment_status": "DIAGNOSTIC_ONLY",
        "source_xy_preserved": True,
        "height_interpretation": "bilinear native DTM diagnostic; not reconstructed road/asphalt height",
        "width_m": None,
        "surface": "UNKNOWN",
        "bicycle_access": "UNKNOWN",
        "canonical_route_status": "NOT_ADMITTED",
        "road_physics_status": "NOT_ADMITTED",
        "road_earthworks_status": "NOT_AUTHORED",
        "learning_case_status": "NOT_ELIGIBLE",
        "igr_rt_source_comparison": compare_igr_profile(points),
        "points_ue_cm": points,
        "policy": {
            "presentation_only": True,
            "authoritative_route_geometry": False,
            "authoritative_physics": False,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-terrain", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--exact-sha", required=True)
    args = parser.parse_args()
    result = prepare(args.prepared_terrain, args.output, args.exact_sha)
    print(
        f"Ma-2141 native alignment diagnostic: {len(result['points_ue_cm'])} points, {result['length_m']:.3f} m; authority/earthworks NOT ADMITTED"
    )


if __name__ == "__main__":
    main()

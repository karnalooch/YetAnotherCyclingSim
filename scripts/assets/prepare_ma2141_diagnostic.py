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
from shapely.geometry import box
from shapely.ops import substring, transform

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    ROOT
    / "worldgen/terrain/benchmarks/sa_calobra/ma2141_cartociudad_source_2026-10-02.json"
)
SOURCE_SHA = "6520b92486b5d1c63353b8253d388ab21d380c78fda119849311be8344d8ae36"


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
    stations = sorted(
        set(
            [station - 150 + i for i in range(301)]
            + [s for s in source_stations if station - 150 <= s <= station + 150]
        )
    )
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

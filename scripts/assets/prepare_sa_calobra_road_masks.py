"""Read frozen road outputs into conservative masks; never execute a road builder."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize
from shapely.geometry import Polygon, box, mapping
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_normalized_context import verify
from verify_sa_calobra_lidar_masks import digest

FROZEN_SHA = "c5573b3cf545c51ce83ad1fb0a5ca3111f5ad7f6"


def squared_distance_axis(f, active_columns=None):
    """Exact separable Euclidean raster distance using parabolic lower envelopes."""
    rows, width = f.shape
    index = np.arange(rows)
    vertices = np.empty((rows, width), dtype=np.int32)
    boundaries = np.empty((rows, width + 1), dtype=np.float64)
    k = np.zeros(rows, dtype=np.int32)
    active = np.arange(width) if active_columns is None else active_columns
    vertices[:, 0] = active[0]
    boundaries[:, 0], boundaries[:, 1] = -np.inf, np.inf
    for q in active[1:]:
        while True:
            v = vertices[index, k]
            crossing = (
                (f[:, q] + q * q) - (f[index, v] + v.astype(np.float64) ** 2)
            ) / (2 * (q - v))
            pop = crossing <= boundaries[index, k]
            if not pop.any():
                break
            k[pop] -= 1
        k += 1
        vertices[index, k] = q
        boundaries[index, k] = crossing
        boundaries[index, k + 1] = np.inf
    result = np.empty_like(f, dtype=np.float64)
    k.fill(0)
    for q in range(width):
        while True:
            advance = boundaries[index, k + 1] < q
            if not advance.any():
                break
            k[advance] += 1
        v = vertices[index, k]
        result[:, q] = (q - v).astype(np.float64) ** 2 + f[index, v]
    return result


def distance_lower_bound(mask, step):
    if not mask.any() or step <= 0 or not np.isfinite(step):
        raise ValueError("Distance requires observed pavement and positive finite step")
    columns = np.arange(mask.shape[1], dtype=np.int32)[None, :]
    left = np.maximum.accumulate(np.where(mask, columns, -mask.shape[1]), axis=1)
    right = np.minimum.accumulate(
        np.where(mask, columns, 2 * mask.shape[1])[:, ::-1], axis=1
    )[:, ::-1]
    horizontal = np.minimum(columns - left, right - columns).astype(np.float64) ** 2
    # Empty rows cannot seed an envelope. Binary horizontal distance is obtained
    # directly by scans, avoiding thousands of sentinel-parabola pops.
    square = squared_distance_axis(horizontal.T, np.flatnonzero(mask.any(axis=1))).T
    # All-touched pavement cells cover the polygon. A cell's centre can be at
    # most half a pixel diagonal from its actual covered part: subtract that
    # uncertainty so the consumer never overestimates polygon clearance.
    metres = np.maximum(0, np.sqrt(square) * step - step / np.sqrt(2))
    values = metres.astype(np.float32)
    return np.maximum(0, np.nextafter(values, np.float32(-np.inf)))


def pavement_polygons(sections):
    data = np.asarray(sections, dtype=np.float64)
    if (
        data.ndim != 3
        or data.shape[1:] != (25, 3)
        or len(data) < 3
        or not np.isfinite(data).all()
    ):
        raise ValueError("Incomplete/nonfinite frozen pavement sections")
    result = []
    for a, b in zip(data, data[1:]):
        strip = []
        # Retain each original top facet diagonal rather than inventing an axis.
        for j in range(24):
            for points in [[a[j], a[j + 1], b[j]], [a[j + 1], b[j + 1], b[j]]]:
                p, q, r = points
                area2 = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
                if area2 >= -1e-9:
                    raise ValueError("Folded/degenerate frozen pavement triangle")
                strip.append(points)
        straight = True
        for row in [a, b]:
            delta = row[-1, :2] - row[0, :2]
            length = np.linalg.norm(delta)
            cross = (row[:, 0] - row[0, 0]) * delta[1] - (
                row[:, 1] - row[0, 1]
            ) * delta[0]
            straight &= length > 0 and np.max(np.abs(cross)) / length <= 1e-7
        # Collinear cross-section vertices do not change the union footprint.
        # Keep full native facets if the section is not straight at sub-micron scale.
        if straight:
            strip = [[a[0], a[-1], b[0]], [a[-1], b[-1], b[0]]]
        for points in strip:
            result.append(
                Polygon([(483000.25 + p[0], 4409516.25 - p[1]) for p in points])
            )
    return result


def load_sources(recipe_path, root):
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    if (
        recipe["accepted_sha"] != FROZEN_SHA
        or recipe["owner_artifact_exception"] is not True
    ):
        raise ValueError("No owner-authorized frozen road artifact identity")
    for item in recipe["inputs"]:
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe frozen source path")
        path = root / relative
        if path.stat().st_size != item["size_bytes"] or digest(path) != item["sha256"]:
            raise ValueError("Frozen source hash/size mismatch: " + item["path"])

    def read(name):
        return json.loads((root / name).read_text(encoding="utf-8-sig"))

    network, native, profile = (
        read("Network/network.json"),
        read("network-native-proof.json"),
        read("ma2141-profile-candidate.json"),
    )
    for report in [network, native, profile]:
        if report["exact_sha"] != FROZEN_SHA:
            raise ValueError("Mixed frozen road revisions")
    constructed = {w["id"]: w for w in native["windows"]}
    if len(constructed) != native["construction_window_count"]:
        raise ValueError("Duplicate/incomplete native construction inventory")
    all_windows = (
        network["approved"] + network["owner_reviewed"] + network["nudo"]["windows"]
    )
    windows = [w for w in all_windows if w["id"] in constructed]
    if len(windows) != len(constructed) or len({w["id"] for w in windows}) != len(
        windows
    ):
        raise ValueError("Native constructed geometry missing/duplicated")
    for w in windows:
        proof = constructed[w["id"]]
        if proof["trace_miss_count"] or proof["asphalt_penetration_count"]:
            raise ValueError("Frozen native geometry has missing/penetrating samples")
        support = proof["support"]
        if (
            support["min_shoulder_extent_m"] < 0.4999
            or support["max_shoulder_extent_m"] > 0.51
        ):
            raise ValueError("Frozen shoulder extent outside inspected bound")
        patch_path = root / "Network" / w["cut_manifest"]
        if digest(patch_path) != w["cut_sha256"]:
            raise ValueError("Frozen CUT manifest identity mismatch")
        patch = read("Network/" + w["cut_manifest"])
        if (
            patch["operation"] != "CUT_ONLY"
            or patch["base_dtm_modified"] is not False
            or patch["save_map"] is not False
        ):
            raise ValueError("Unsupported frozen earthworks operation")
        payload = patch_path.parent / patch["patch_file"]
        if digest(payload) != patch["patch_sha256"]:
            raise ValueError("Frozen CUT payload identity mismatch")
    return recipe, network, native, profile, windows


def prepare(recipe_path, source_root, normalized_manifest, output):
    if output.exists():
        raise FileExistsError("Preserve existing road masks; choose a new directory")
    verified = verify(normalized_manifest)
    normalized = json.loads(normalized_manifest.read_text(encoding="utf-8"))
    recipe, network, native, profile, windows = load_sources(recipe_path, source_root)
    with rasterio.open(normalized_manifest.parent / "elevation.tif") as ds:
        raster_profile, transform, shape = ds.profile, ds.transform, ds.shape
    polygons = []
    for w in windows:
        polygons.extend(pavement_polygons(w["sections"]))
    hairpin = [
        [
            [x, y, z]
            for (x, y), z in zip(
                row["xy_local_m"], row["candidate_ground_m"], strict=True
            )
        ]
        for row in profile["stations"]
    ]
    polygons.extend(pavement_polygons(hairpin))
    aoi = box(*rasterio.transform.array_bounds(*shape, transform))
    pavement = unary_union(polygons).intersection(aoi)
    if pavement.is_empty or not pavement.is_valid:
        raise ValueError("Invalid frozen pavement union")
    # A verified maximum shoulder extent is a conservative exclusion fallback,
    # not a claim of exact surveyed shoulder geometry.
    envelope = pavement.buffer(0.51).intersection(aoi)

    def burn(geometry):
        return rasterize(
            [(mapping(geometry), 1)],
            out_shape=shape,
            transform=transform,
            dtype="uint8",
            all_touched=True,
        )

    road, protected = burn(pavement), burn(envelope)
    shoulder = (protected & ~road).astype(np.uint8)
    # Retain BOB's affected domains without reverse-engineering CUT/FILL from DTM.
    earthworks = np.zeros(shape, dtype=np.uint8)
    patch_rows = [(source_root / "Network" / w["cut_manifest"]) for w in windows] + [
        source_root / "ma2141-cut-patch.json"
    ]
    for path in patch_rows:
        patch = json.loads(path.read_text())
        rect = patch["rect"]
        x0, y0, x1, y1 = [rect[k] for k in ["min_x", "min_y", "max_x", "max_y"]]
        if not (0 <= x0 <= x1 < shape[1] and 0 <= y0 <= y1 < shape[0]):
            raise ValueError("Frozen earthwork rect outside native grid")
        earthworks[y0 : y1 + 1, x0 : x1 + 1] = 1
    distance = distance_lower_bound(road.astype(bool), 0.5)
    output.mkdir(parents=True)
    products = []
    for name, values, meaning in [
        (
            "road-footprint.tif",
            road,
            "all-touched projection of original frozen pavement top facets, network plus hairpin; zero outside recorded pavement",
        ),
        (
            "shoulder-exclusion-envelope.tif",
            shoulder,
            "conservative .51m verified-maximum shoulder envelope outside pavement, not exact shoulder footprint",
        ),
        (
            "road-protected-footprint.tif",
            protected,
            "pavement plus conservative shoulder envelope; consumer must account for asset radius/clearance",
        ),
        (
            "bob-affected-domain.tif",
            earthworks,
            "source CUT patch rectangles, including guards/unchanged cells; conservative review/exclusion, not cut depth or fill",
        ),
        (
            "road-distance-lower-bound.tif",
            distance,
            "planar Euclidean lower bound to raster-covered pavement; subtract half-pixel diagonal and round downward; not route station distance",
        ),
    ]:
        path = output / name
        nodata = -32767 if values.dtype == np.float32 else 255
        with rasterio.open(
            path,
            "w",
            **{
                **raster_profile,
                "dtype": str(values.dtype),
                "count": 1,
                "nodata": nodata,
                "compress": "DEFLATE",
            },
        ) as ds:
            ds.write(values, 1)
        with rasterio.open(path) as ds:
            if (
                ds.transform != transform
                or ds.crs != raster_profile["crs"]
                or not np.array_equal(ds.read(1), values)
            ):
                raise ValueError("Road raster readback mismatch")
        products.append(
            {
                "path": name,
                "sha256": digest(path),
                "size_bytes": path.stat().st_size,
                "logical_sha256": hashlib.sha256(values.tobytes()).hexdigest(),
                "dtype": str(values.dtype),
                "nodata": nodata,
                "semantics": meaning,
            }
        )
    report = {
        "schema_version": 1,
        "status": "FROZEN_PRESENTATION_ROAD_MASKS",
        "geometry_mutation": False,
        "accepted_sha": FROZEN_SHA,
        "source_recipe_sha256": digest(recipe_path),
        "normalized_fingerprint": verified["fingerprint"],
        "grid": normalized["grid"],
        "world_mapping": {
            "origin_epsg_m": [483000.25, 4409516.25],
            "axis": "X east;Y south;local metres",
        },
        "counts": {
            "network_windows": len(windows),
            "hairpin_stations": len(hairpin),
            "road_cells": int(road.sum()),
            "shoulder_envelope_cells": int(shoulder.sum()),
            "bob_affected_cells": int(earthworks.sum()),
        },
        "parameters": {
            "shoulder_max_extent_m": 0.51,
            "distance_cell_uncertainty_m": 0.5 / np.sqrt(2),
            "rasterization": "all_touched",
        },
        "admission": {
            "scope": "owner-authorized frozen visual outputs; presentation exclusions only",
            "collision": False,
            "rideability": False,
            "engineering": False,
            "performance": False,
            "source_native_status": native["status"],
            "source_flags_preserved": True,
        },
        "limitations": [
            "Shoulder is a conservative fallback envelope",
            "BOB patch coverage is not CUT/FILL magnitude or complete inner/outer edge semantics",
            "Unknown asset footprint/clearance must block placement",
            "Does not modify/save/rebuild original road or Landscape",
        ],
        "outputs": products,
        "source_inputs": recipe["inputs"],
        "attribution": "Frozen YACS presentation road/BOB outputs derived from admitted source context; original CNIG/IDEIB notices apply",
        "producer_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
    }
    report["fingerprint"] = hashlib.sha256(
        json.dumps(
            report, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    (output / "road-mask-manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--normalized-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = prepare(
        args.recipe, args.source_root, args.normalized_manifest, args.output
    )
    print(json.dumps({"status": result["status"], "counts": result["counts"]}))

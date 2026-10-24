"""Prepare bounded source-height witnesses, never regional placement admission."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window


ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "worldgen/terrain/benchmarks/sa_calobra/terrain_import_profile.json"
MESH = "/Game/Prototype/Environment/Stage3G/Imported/Meshes/SM_Stage3G_Boulder.SM_Stage3G_Boulder"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare(dtm, inventory_path, inventory_sha, candidates_path, candidates_sha):
    if sha(inventory_path) != inventory_sha or sha(candidates_path) != candidates_sha:
        raise ValueError("Native inventory or XY diagnostic identity drift")
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    if (
        dtm.stat().st_size != profile["source_size_bytes"]
        or sha(dtm) != profile["source_sha256"]
    ):
        raise ValueError("Terrain Authority source identity drift")
    meshes = json.loads(inventory_path.read_text(encoding="utf-8"))
    meshes = [row for row in meshes if row["object_path"] == MESH]
    if len(meshes) != 1:
        raise ValueError("Ambiguous native Boulder inventory")
    origin, extent = meshes[0]["bounds_origin_cm"], meshes[0]["bounds_extent_cm"]
    if not all(math.isfinite(v) for v in origin + extent) or min(extent) <= 0:
        raise ValueError("Invalid native mesh bounds")
    candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
    if (
        candidates["status"] != "CPU_XY_PROBES_ONLY"
        or candidates["placement"] is not False
    ):
        raise ValueError("Only explicit diagnostic XY input is supported")
    selected = [row for row in candidates["candidates"] if row["selected"]]
    if not 1 <= len(selected) <= 16:
        raise ValueError("Bounded measurement requires one to sixteen XYs")
    points = []
    with rasterio.open(dtm) as dataset:
        if list(dataset.bounds) != profile["source_bounds_m"]:
            raise ValueError("Terrain source affine extent drift")
        if (
            str(dataset.crs) != "EPSG:25831"
            or dataset.res != (0.5, 0.5)
            or dataset.nodata != -32767
        ):
            raise ValueError("Terrain source grid or validity policy drift")
        for center in selected:
            samples = []
            for i in range(9):
                for j in range(9):
                    local = [
                        origin[0] - extent[0] + (i + 0.5) * 2 * extent[0] / 9,
                        origin[1] - extent[1] + (j + 0.5) * 2 * extent[1] / 9,
                    ]
                    x, y = [center["world_xy_cm"][k] + local[k] for k in (0, 1)]
                    easting, northing = 483000.25 + x / 100, 4409516.25 - y / 100
                    col, row = (~dataset.transform) * (easting, northing)
                    col, row = col - 0.5, row - 0.5
                    c, r = math.floor(col), math.floor(row)
                    if (
                        c < 0
                        or r < 0
                        or c + 1 >= dataset.width
                        or r + 1 >= dataset.height
                    ):
                        raise ValueError(
                            "Support source interpolation is outside coverage"
                        )
                    values = dataset.read(1, window=Window(c, r, 2, 2), masked=True)
                    if (
                        np.ma.getmaskarray(values).any()
                        or not np.isfinite(values).all()
                    ):
                        raise ValueError("Unknown source support neighbourhood")
                    u, v = col - c, row - r
                    height = float(
                        (1 - v) * ((1 - u) * values[0, 0] + u * values[0, 1])
                        + v * ((1 - u) * values[1, 0] + u * values[1, 1])
                    )
                    samples.append(
                        {
                            "local_xy_cm": local,
                            "world_xy_cm": [x, y],
                            "source_height_m": height,
                            "source_cells": [r, c, r + 1, c + 1],
                        }
                    )
            points.append(
                {
                    "candidate_id": center["candidate_id"],
                    "world_xy_cm": center["world_xy_cm"],
                    "samples": samples,
                }
            )
    if (
        sha(dtm) != profile["source_sha256"]
        or sha(inventory_path) != inventory_sha
        or sha(candidates_path) != candidates_sha
    ):
        raise ValueError("Source changed during contact witness preparation")
    return {
        "schema_version": 1,
        "status": "SOURCE_HEIGHT_MEASUREMENT_INPUT_ONLY",
        "placement": False,
        "source_sha256": profile["source_sha256"],
        "profile_sha256": sha(PROFILE),
        "native_inventory_sha256": inventory_sha,
        "xy_input_sha256": candidates_sha,
        "xy_fingerprint": candidates["fingerprint"],
        "mesh_bounds_cm": {"origin": origin, "extent": extent},
        "source_crs": "EPSG:25831",
        "vertical_basis": "provider orthometric convention inherited; detailed datum not independently verified",
        "profile_declared_mapping": profile["axis_mapping"],
        "interpolation": "bilinear_four_valid_source_pixel_centres",
        "source_validity": "all four source neighbours finite and not NoData; not a new height-mask product",
        "regional_rock_semantics": "NOT_ADMITTED_VEGETATION_SELECTOR_DIAGNOSTIC",
        "contact_limits": "REQUIRED_UNSET_MEASURE_FIRST",
        "points": points,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dtm", "native-inventory", "xy-candidates", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-native-sha", required=True)
    parser.add_argument("--expected-xy-sha", required=True)
    args = parser.parse_args()
    result = prepare(
        args.dtm,
        args.native_inventory,
        args.expected_native_sha,
        args.xy_candidates,
        args.expected_xy_sha,
    )
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "centres": len(result["points"]),
                "sha256": sha(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()

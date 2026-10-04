"""Prepare fail-closed placement evidence; never plants or changes frozen geometry."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize_sa_calobra_context import sha256
from verify_normalized_context import verify


def placement_state(buildings):
    """0 = prohibited; 255 = unresolved. No positive admission exists yet."""
    if not np.isin(buildings, [0, 1, 255]).all():
        raise ValueError("Unrecognized building evidence")
    result = np.full(buildings.shape, 255, dtype=np.uint8)
    result[buildings == 1] = 0
    return result


def prepare(manifest_path, output):
    if output.exists():
        raise FileExistsError("Retain existing products; choose a new output directory")
    checked = verify(manifest_path)
    source = json.loads(manifest_path.read_text(encoding="utf-8"))
    grid = source["grid"]
    if (grid["crs"], grid["width"], grid["height"], grid["transform"]) != (
        "EPSG:25831",
        4033,
        4033,
        [0.5, 0.0, 483000.0, 0.0, -0.5, 4409516.5],
    ):
        raise ValueError("Unadmitted frozen Landscape grid")
    with rasterio.open(manifest_path.parent / "catastro_mapped_footprint.tif") as ds:
        buildings = ds.read(1)
        profile = ds.profile
    # Mapped absence is not proof of current absence, so retain the source semantics.
    states = placement_state(buildings)
    output.mkdir(parents=True)
    products = []
    for name, values, semantics in [
        (
            "building-exclusion.tif",
            buildings,
            {
                "0": "no mapped footprint; not proven clear",
                "1": "exclude mapped footprint",
                "255": "unknown",
            },
        ),
        (
            "placement-state.tif",
            states,
            {
                "0": "prohibited mapped building",
                "1": "eligible (not emitted by this candidate)",
                "255": "unresolved; no planting authorization",
            },
        ),
    ]:
        path = output / name
        with rasterio.open(
            path, "w", **{**profile, "nodata": 255, "compress": "DEFLATE"}
        ) as ds:
            ds.write(values, 1)
        products.append(
            {
                "path": name,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
                "logical_sha256": hashlib.sha256(values.tobytes()).hexdigest(),
                "dtype": "uint8",
                "nodata": 255,
                "semantics": semantics,
                "counts": {str(i): int((values == i).sum()) for i in (0, 1, 255)},
            }
        )
    report = {
        "schema_version": 1,
        "status": "BLOCKED_FOR_PLANTING",
        "geometry_mutation": False,
        "consumer_integration": False,
        "grid": grid,
        "normalized_fingerprint": checked["fingerprint"],
        "source_manifest_sha256": sha256(manifest_path),
        "producer_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "world_mapping": {
            "origin_epsg_m": [483000.25, 4409516.25],
            "axis": "X east; Y south; centimetres",
            "uv": "(UE_XY_cm/50 + 0.5)/4033",
        },
        "outputs": products,
        "blocked_layers": checked["blocked_layers"],
        "authority": "2A evidence candidate; no production PCGEx admission",
        "yellow_relief": "review only; not rock classification, vegetation exclusion or geometry repair",
        "siose_2014": "historical context only; no current planting class",
        "road_policy": "road/shoulder/safety/BOB masks must come from admitted frozen road outputs, never inferred from imagery",
        "restore": "local cache copy plus hashes, or regenerate from pinned normalized candidate; no remote backup",
        "attribution": "DG Catastro INSPIRE Buildings; normalized source notices apply; raw not redistributed",
    }
    report["fingerprint"] = hashlib.sha256(
        json.dumps(
            report, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    (output / "placement-manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalized-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.normalized_manifest, args.output)
    print(json.dumps({"status": result["status"], "outputs": result["outputs"]}))
    # A successful preparation does not claim readiness for planting.
    raise SystemExit(2)

#!/usr/bin/env python3
"""Validate and summarize the bounded Sa Calobra World Data Stack source plan.

This tool intentionally does not guess CNIG filenames and does not download data.
It validates the committed AOI/source manifest and emits deterministic 1 km LiDAR
grid locator hints that can be used to find exact provider records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = (
    ROOT
    / "worldgen"
    / "terrain"
    / "benchmarks"
    / "sa_calobra"
    / "world_data"
    / "working_space_sources.json"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EXACT_FILE_STATES = {"acquired", "included", "derived"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable summary")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def intersecting_grid_cells(bounds: list[float], grid_size_m: int) -> list[str]:
    if len(bounds) != 4:
        raise ValueError("AOI bounds_m must contain min_e, min_n, max_e, max_n")
    min_e, min_n, max_e, max_n = bounds
    if not (min_e < max_e and min_n < max_n):
        raise ValueError("AOI bounds_m are not ordered")

    start_e = math.floor(min_e / grid_size_m)
    end_e = math.floor(math.nextafter(max_e, -math.inf) / grid_size_m)
    start_n = math.floor(min_n / grid_size_m)
    end_n = math.floor(math.nextafter(max_n, -math.inf) / grid_size_m)

    return [
        f"{e}-{n}"
        for n in range(start_n, end_n + 1)
        for e in range(start_e, end_e + 1)
    ]


def validate_exact_files(source: dict[str, Any]) -> None:
    files = source.get("files", [])
    if source.get("status") in EXACT_FILE_STATES and not files:
        raise ValueError(
            f"{source.get('id')}: status={source.get('status')} requires exact files"
        )

    for item in files:
        required = {"name", "size_bytes", "sha256", "detail_url"}
        missing = sorted(required - set(item))
        if missing:
            raise ValueError(f"{source.get('id')}: file is missing {missing}")
        if not isinstance(item["size_bytes"], int) or item["size_bytes"] <= 0:
            raise ValueError(f"{source.get('id')}: invalid file size")
        if not SHA256_RE.fullmatch(str(item["sha256"])):
            raise ValueError(f"{source.get('id')}: invalid SHA-256")


def validate(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("schema_version") not in (1, 2):
        raise ValueError("Unsupported World Data Stack manifest schema")

    aoi = manifest["aoi"]
    if aoi.get("crs") != "EPSG:25831":
        raise ValueError("Sa Calobra working-space AOI must use EPSG:25831")

    bounds = [float(value) for value in aoi["bounds_m"]]
    center = [float(value) for value in aoi["center_m"]]
    min_e, min_n, max_e, max_n = bounds
    calculated_center = [(min_e + max_e) / 2.0, (min_n + max_n) / 2.0]
    if any(abs(a - b) > 1e-6 for a, b in zip(center, calculated_center)):
        raise ValueError("AOI center_m does not match bounds_m")

    width = max_e - min_e
    height = max_n - min_n
    if "size_m" in aoi:
        declared_size = [float(value) for value in aoi["size_m"]]
        if len(declared_size) != 2:
            raise ValueError("AOI size_m must contain width and height")
        if abs(width - declared_size[0]) > 1e-6 or abs(height - declared_size[1]) > 1e-6:
            raise ValueError(
                f"AOI size_m does not match bounds_m: declared={declared_size}, "
                f"calculated={[width, height]}"
            )
    elif "square_half_extent_m" in aoi:
        half_extent = float(aoi["square_half_extent_m"])
        if abs(width - 2.0 * half_extent) > 1e-6 or abs(height - 2.0 * half_extent) > 1e-6:
            raise ValueError("AOI is not the declared square")
    else:
        raise ValueError("AOI must declare size_m or square_half_extent_m")

    selection = manifest["selection"]
    grid_size = int(selection["lidar_grid_size_m"])
    if grid_size != 1000:
        raise ValueError("PNOA LiDAR 3rd-coverage planner expects a 1 km grid")

    calculated_hints = intersecting_grid_cells(bounds, grid_size)
    committed_hints = selection["lidar_grid_locator_hints"]
    if committed_hints != calculated_hints:
        raise ValueError(
            f"LiDAR locator hints drifted: committed={committed_hints}, "
            f"calculated={calculated_hints}"
        )

    raw_root = manifest["cache"]["raw_root"]
    if not raw_root.startswith("ExternalAssets/"):
        raise ValueError("Raw provider cache must remain under ignored ExternalAssets/")

    sources = manifest["sources"]
    source_ids = [source["id"] for source in sources]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Duplicate World Data Stack source id")
    for source in sources:
        validate_exact_files(source)

    return {
        "schema_version": manifest["schema_version"],
        "issue": manifest["issue"],
        "manifest_sha256": None,
        "aoi_id": aoi["id"],
        "aoi_bounds_epsg25831": bounds,
        "aoi_size_m": [width, height],
        "lidar_grid_locator_hints": calculated_hints,
        "sources": [
            {
                "id": source["id"],
                "priority": source["priority"],
                "status": source["status"],
                "exact_file_count": len(source.get("files", [])),
            }
            for source in sources
        ],
        "raw_cache_root": raw_root,
        "raw_sources_committed": bool(manifest["cache"]["commit_raw_sources"]),
    }


def main() -> None:
    args = parse_args()
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary = validate(manifest)
    summary["manifest_sha256"] = sha256(manifest_path)

    if args.json:
        print(json.dumps(summary, indent=2))
        return

    print(f"World Data Stack manifest: {manifest_path}")
    print(f"AOI: {summary['aoi_id']} {summary['aoi_size_m'][0]:.0f} x {summary['aoi_size_m'][1]:.0f} m")
    print("LiDAR locator hints: " + ", ".join(summary["lidar_grid_locator_hints"]))
    for source in summary["sources"]:
        print(
            f"- {source['priority']} {source['id']}: {source['status']} "
            f"(exact files: {source['exact_file_count']})"
        )
    print(f"Manifest SHA-256: {summary['manifest_sha256']}")


if __name__ == "__main__":
    main()

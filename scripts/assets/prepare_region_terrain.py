"""Prepare a hash-verified native DTM window for manifest-driven UE import.

No interpolation, gap filling or road/physics authoring occurs here. A bounded
4033-square valid window is the existing import topology's admission boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window, from_bounds

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = (
    ROOT / "worldgen/terrain/benchmarks/sa_calobra/terrain_import_profile.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_profile(path: Path) -> dict:
    profile = json.loads(path.read_text(encoding="utf-8"))
    if profile.get("schema_version") != 1:
        raise ValueError("Unsupported terrain profile schema")
    if profile.get("nodata_policy") != "reject_in_baseline":
        raise ValueError("Terrain profile must reject NoData in the baseline")
    if profile.get("landscape_vertices") != 4033:
        raise ValueError("The admitted importer requires 4033 vertices")
    digest = profile.get("source_sha256", "")
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Source SHA256 must be lowercase hexadecimal")
    source = Path(profile["source"])
    if source.is_absolute() or ".." in source.parts:
        raise ValueError("Source must be repository-relative")
    if not profile["map_package"].startswith("/Game/Worlds/") or any(
        c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/_"
        for c in profile["map_package"]
    ):
        raise ValueError("Map must be an isolated /Game/Worlds/ package")
    for field in ("source_bounds_m", "baseline_bounds_m"):
        bounds = profile[field]
        if len(bounds) != 4 or not all(math.isfinite(v) for v in bounds):
            raise ValueError(f"Invalid {field}")
        if bounds[0] >= bounds[2] or bounds[1] >= bounds[3]:
            raise ValueError(f"Empty {field}")
    resolution = profile["source_resolution_m"]
    if not math.isfinite(resolution) or resolution <= 0:
        raise ValueError("Invalid native resolution")
    west, south, east, north = profile["baseline_bounds_m"]
    expected = profile["landscape_vertices"] * resolution
    if not math.isclose(east - west, expected, abs_tol=1e-6) or not math.isclose(
        north - south, expected, abs_tol=1e-6
    ):
        raise ValueError("Baseline must contain exactly 4033 native samples per axis")
    return profile


def encode_heights(heights: np.ma.MaskedArray) -> tuple[np.ndarray, dict]:
    if np.ma.count_masked(heights):
        raise ValueError(
            f"Baseline contains {np.ma.count_masked(heights)} NoData samples"
        )
    data = np.asarray(heights, dtype=np.float64)
    if not np.all(np.isfinite(data)):
        raise ValueError("Baseline contains non-finite heights")
    low, high = float(data.min()), float(data.max())
    if not -500.0 <= low < high <= 9000.0:
        raise ValueError("Baseline elevation range is implausible or constant")
    span = high - low
    encoded = np.rint((data - low) * 65535.0 / span).astype("<u2")
    # Exact inverse of UE's (encoded - 32768) / 128 transform. Using 512
    # here would introduce a systematic 65536-vs-65535 height-domain error.
    transform = {
        "scale_z": span * 100.0 * 128.0 / 65535.0,
        "location_z_cm": (low + span * 32768.0 / 65535.0) * 100.0,
        "elevation_min_m": low,
        "elevation_max_m": high,
        "max_quantization_error_m": span / 65535.0 / 2.0,
    }
    return encoded, transform


def read_native_window(dataset, profile: dict) -> tuple[np.ma.MaskedArray, Window]:
    if str(dataset.crs) != profile["source_crs"]:
        raise ValueError(f"CRS mismatch: {dataset.crs}")
    resolution = profile["source_resolution_m"]
    if not np.allclose(dataset.res, (resolution, resolution), rtol=0, atol=1e-9):
        raise ValueError("Native resolution mismatch")
    if dataset.count != 1 or dataset.dtypes[0] != "float32":
        raise ValueError("Source must be one-band Float32 DTM")
    if dataset.nodata != profile["source_nodata"]:
        raise ValueError("NoData sentinel mismatch")
    if dataset.transform.b != 0 or dataset.transform.d != 0 or dataset.transform.e >= 0:
        raise ValueError("Source must be a north-up, unrotated metric grid")
    if not np.allclose(
        tuple(dataset.bounds), profile["source_bounds_m"], rtol=0, atol=1e-6
    ):
        raise ValueError("Source bounds mismatch")
    window = from_bounds(*profile["baseline_bounds_m"], transform=dataset.transform)
    values = (window.col_off, window.row_off, window.width, window.height)
    if not all(math.isclose(v, round(v), abs_tol=1e-6) for v in values):
        raise ValueError("Baseline is not aligned to native pixel boundaries")
    window = Window(*(int(round(v)) for v in values))
    if (
        window.col_off < 0
        or window.row_off < 0
        or window.col_off + window.width > dataset.width
        or window.row_off + window.height > dataset.height
    ):
        raise ValueError("Baseline falls outside source coverage")
    if window.width != 4033 or window.height != 4033:
        raise ValueError("Unexpected baseline sample dimensions")
    return dataset.read(1, window=window, masked=True), window


def prepare(profile_path: Path, output_dir: Path, repo_root: Path = ROOT) -> dict:
    profile = load_profile(profile_path)
    source = repo_root / profile["source"]
    if not source.is_file() or source.stat().st_size != profile["source_size_bytes"]:
        raise ValueError(
            "Source payload missing or byte count mismatched; materialize the pinned LFS file"
        )
    if sha256(source) != profile["source_sha256"]:
        raise ValueError("Source SHA256 mismatch")
    if output_dir.exists():
        raise FileExistsError(
            "Use a new evidence directory; existing terrain output is preserved"
        )
    with rasterio.open(source) as dataset:
        heights, window = read_native_window(dataset, profile)
        encoded, transform = encode_heights(heights)
        origin = dataset.xy(int(window.row_off), int(window.col_off))
    output_dir.mkdir(parents=True, exist_ok=False)
    heightmap = output_dir / "terrain.r16"
    heightmap.write_bytes(encoded.tobytes(order="C"))
    manifest = {
        "schema_version": 1,
        "region_id": profile["region_id"],
        "source_crs": profile["source_crs"],
        "source_sha256": profile["source_sha256"],
        "profile_sha256": sha256(profile_path),
        "map_package": profile["map_package"],
        "vertices": [4033, 4033],
        "heightmap_sha256": sha256(heightmap),
        "heightmap_bytes": heightmap.stat().st_size,
        "baseline_bounds_m": profile["baseline_bounds_m"],
        "origin_epsg_m": list(origin),
        "axis_mapping": profile["axis_mapping"],
        "scale_xy_cm_per_vertex": profile["source_resolution_m"] * 100.0,
        "valid_sample_count": int(encoded.size),
        "nodata_sample_count": 0,
        "resampled": False,
        "presentation_only": True,
        "authoritative_route_geometry": False,
        "authoritative_physics": False,
        **transform,
    }
    (output_dir / "terrain-import.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.profile, args.output_dir), indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Terrain admission failed: {exc}\n")


if __name__ == "__main__":
    main()

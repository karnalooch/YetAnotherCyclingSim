#!/usr/bin/env python3
"""Finalize the Embark-mode Passo Giau heightfield for Unreal Landscape import."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject

from prepare_passo_giau_veneto_lidar import (
    encode_u16,
    hillshade,
    landscape_diagnostics,
    stats,
)

TARGET_CRS = "EPSG:32632"
TARGET_BOUNDS = (730406.587, 5148246.775, 738406.587, 5156246.775)
LANDSCAPE_SIZE = 4033
MAX_SOURCE_CELL_M = 2.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--dcc-handoff-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def landscape_metadata(minimum: float, maximum: float) -> dict[str, Any]:
    span = maximum - minimum
    midpoint = (minimum + maximum) / 2.0
    return {
        "landscape_size_vertices": LANDSCAPE_SIZE,
        "source_fidelity_note": (
            "The Unreal Landscape raster is a deterministic 4033-square resample "
            "of the final 32-bit Houdini heightfield produced after the selected "
            "PDG -> Gaea -> Houdini authoring chain."
        ),
        "recommended_transform": {
            "scale_x_cm_per_vertex": round(
                (TARGET_BOUNDS[2] - TARGET_BOUNDS[0]) * 100.0
                / (LANDSCAPE_SIZE - 1),
                6,
            ),
            "scale_y_cm_per_vertex": round(
                (TARGET_BOUNDS[3] - TARGET_BOUNDS[1]) * 100.0
                / (LANDSCAPE_SIZE - 1),
                6,
            ),
            "scale_z": round(span * 100.0 / 512.0, 6),
            "location_z_cm_for_sea_level_preservation": round(midpoint * 100.0, 3),
        },
        "height_encoding": {
            "format": "unsigned 16-bit",
            "encoded_min": 0,
            "encoded_mid": 32768,
            "encoded_max": 65535,
            "elevation_min_m": round(minimum, 3),
            "elevation_mid_m": round(midpoint, 3),
            "elevation_max_m": round(maximum, 3),
        },
    }


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    dcc_handoff_manifest = args.dcc_handoff_manifest.resolve()
    output_dir = args.output_dir.resolve()

    if not source.is_file():
        print(f"[error] missing conditioned heightfield: {source}", file=sys.stderr)
        return 2
    if not dcc_handoff_manifest.is_file():
        print(f"[error] missing immutable DCC handoff manifest: {dcc_handoff_manifest}", file=sys.stderr)
        return 2

    pipeline = json.loads(dcc_handoff_manifest.read_text(encoding="utf-8"))
    if pipeline.get("pipeline_id") != "passo-giau-embark-landscape-v1":
        print("[error] unexpected pipeline_id in run manifest", file=sys.stderr)
        return 2

    try:
        with rasterio.open(source) as src:
            if src.count != 1:
                raise ValueError(f"expected one heightfield band, got {src.count}")
            if src.crs is None or src.crs.to_epsg() != 32632:
                raise ValueError(f"expected {TARGET_CRS}, got {src.crs}")

            bounds = src.bounds
            actual_bounds = (bounds.left, bounds.bottom, bounds.right, bounds.top)
            for actual, expected in zip(actual_bounds, TARGET_BOUNDS, strict=True):
                if abs(float(actual) - expected) > 1.0:
                    raise ValueError(
                        "conditioned heightfield bounds drifted from canonical AOI: "
                        f"actual={actual_bounds} expected={TARGET_BOUNDS}"
                    )

            cell_x = abs(float(src.transform.a))
            cell_y = abs(float(src.transform.e))
            if cell_x > MAX_SOURCE_CELL_M or cell_y > MAX_SOURCE_CELL_M:
                raise ValueError(
                    "conditioned source cell size exceeds 2 m contract: "
                    f"{cell_x:.6f} x {cell_y:.6f} m"
                )

            raw = src.read(1, masked=True).astype(np.float32)
            if np.ma.count_masked(raw):
                raise ValueError(
                    f"conditioned heightfield contains {int(np.ma.count_masked(raw))} masked samples"
                )
            native = np.asarray(raw, dtype=np.float32)
            if not np.all(np.isfinite(native)):
                raise ValueError("conditioned heightfield contains non-finite samples")

            native_stats = stats(native)
            elevation_min = float(native_stats["minimum"])
            elevation_max = float(native_stats["maximum"])
            if elevation_max <= elevation_min:
                raise ValueError("conditioned heightfield has no vertical relief")

            target_transform = from_bounds(
                *TARGET_BOUNDS,
                width=LANDSCAPE_SIZE,
                height=LANDSCAPE_SIZE,
            )
            landscape = np.full(
                (LANDSCAPE_SIZE, LANDSCAPE_SIZE),
                np.nan,
                dtype=np.float32,
            )
            reproject(
                source=native,
                destination=landscape,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=target_transform,
                dst_crs=TARGET_CRS,
                dst_nodata=np.nan,
                resampling=Resampling.cubic,
            )
    except (OSError, ValueError, rasterio.errors.RasterioError) as exc:
        print(f"[error] conditioned heightfield validation failed: {exc}", file=sys.stderr)
        return 3

    if not np.all(np.isfinite(landscape)):
        print("[error] Unreal resample contains missing samples", file=sys.stderr)
        return 3

    # The DCC chain owns terrain shaping. This final adapter only protects the
    # measured final domain from cubic interpolation overshoot before encoding.
    landscape = np.clip(landscape, elevation_min, elevation_max).astype(
        np.float32,
        copy=False,
    )
    encoded = encode_u16(landscape, elevation_min, elevation_max)

    output_dir.mkdir(parents=True, exist_ok=True)
    landscape_png = output_dir / "passo_giau_embark_ue_landscape_4033_u16.png"
    landscape_r16 = output_dir / "passo_giau_embark_ue_landscape_4033.r16"
    hillshade_png = output_dir / "passo_giau_embark_hillshade.png"
    report_path = output_dir / "terrain-report.json"

    Image.fromarray(encoded, mode="I;16").save(landscape_png)
    landscape_r16.write_bytes(encoded.astype("<u2", copy=False).tobytes(order="C"))

    preview_stride = max(1, int(round(max(native.shape) / 4096)))
    Image.fromarray(
        hillshade(native[::preview_stride, ::preview_stride], cell_x * preview_stride),
        mode="L",
    ).save(hillshade_png)

    report = {
        "schema_version": 3,
        "pipeline_id": "passo-giau-embark-landscape-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_crs": TARGET_CRS,
        "target_aoi": {
            "bounds_epsg32632": {
                "left": TARGET_BOUNDS[0],
                "bottom": TARGET_BOUNDS[1],
                "right": TARGET_BOUNDS[2],
                "top": TARGET_BOUNDS[3],
            },
            "extent_m": [8000.0, 8000.0],
            "landscape_grid": [LANDSCAPE_SIZE, LANDSCAPE_SIZE],
        },
        "conditioned_source": {
            "path": str(source),
            "sha256": sha256_file(source),
            "native_grid": [int(native.shape[1]), int(native.shape[0])],
            "native_cell_m": [round(cell_x, 6), round(cell_y, 6)],
            "dcc_handoff_manifest": str(dcc_handoff_manifest),
            "dcc_handoff_manifest_sha256": sha256_file(dcc_handoff_manifest),
        },
        "elevation_m": native_stats,
        "landscape_diagnostics": landscape_diagnostics(
            landscape,
            encoded,
            elevation_min,
            elevation_max,
        ),
        "landscape_resampling": "cubic-domain-clamped",
        "unreal_landscape_candidate": landscape_metadata(
            elevation_min,
            elevation_max,
        ),
        "outputs": {
            "landscape_u16_png": landscape_png.name,
            "landscape_r16_little_endian": landscape_r16.name,
            "hillshade_png": hillshade_png.name,
        },
        "yacs_policy": {
            "presentation_only": True,
            "authoritative_route_geometry": False,
            "authoritative_physics": False,
            "canonical_route_may_not_be_moved_by_conditioning": True,
        },
    }
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    for path in (landscape_png, landscape_r16, hillshade_png, report_path):
        print(f"[ok] {path}: {path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

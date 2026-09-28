#!/usr/bin/env python3
"""Prepare a Passo Giau GeoTIFF for the Stage 3G R4.1 terrain spike.

The script reads the downloaded TINITALY source DEM and produces:

- a lossless 16-bit PNG at the source raster resolution;
- an Unreal-Landscape-friendly 1009x1009 16-bit PNG;
- a matching little-endian R16 file;
- a grayscale hillshade preview;
- terrain/elevation statistics;
- explicit Unreal import scale metadata.

The 1009x1009 output is a resampled presentation/import candidate. It does not
contain more source detail than the native 10 m TINITALY grid.

External DEM data remains presentation-only. It must never become authoritative
YACS road or physics geometry.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling

DEFAULT_LANDSCAPE_SIZE = 1009
SUPPORTED_LANDSCAPE_SIZES = (505, 1009, 2017, 4033)
DEFAULT_HILLSHADE_AZIMUTH_DEG = 315.0
DEFAULT_HILLSHADE_ALTITUDE_DEG = 45.0


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_source() -> Path:
    return (
        repository_root()
        / "ExternalAssets"
        / "Terrain"
        / "PassoGiau"
        / "TINITALY_1_1"
        / "passo_giau_tinitaly_1_1_8km_10m_epsg32632.tif"
    )


def default_output_dir() -> Path:
    return (
        repository_root()
        / "ExternalAssets"
        / "Terrain"
        / "PassoGiau"
        / "Prepared"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare Passo Giau TINITALY DEM for the R4.1 terrain spike."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=default_source(),
        help="Source GeoTIFF (default: %(default)s).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir(),
        help="Ignored output directory (default: %(default)s).",
    )
    parser.add_argument(
        "--landscape-size",
        type=int,
        choices=SUPPORTED_LANDSCAPE_SIZES,
        default=DEFAULT_LANDSCAPE_SIZE,
        help=(
            "Square Unreal Landscape candidate resolution "
            "(default: %(default)s)."
        ),
    )
    parser.add_argument(
        "--hillshade-azimuth",
        type=float,
        default=DEFAULT_HILLSHADE_AZIMUTH_DEG,
        help="Hillshade light azimuth in degrees (default: %(default)s).",
    )
    parser.add_argument(
        "--hillshade-altitude",
        type=float,
        default=DEFAULT_HILLSHADE_ALTITUDE_DEG,
        help="Hillshade light altitude in degrees (default: %(default)s).",
    )
    parser.add_argument(
        "--flip-y",
        action="store_true",
        help=(
            "Flip prepared heightmaps vertically. Use only if the chosen Unreal "
            "import path proves that the north/south orientation is reversed."
        ),
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if not args.source.is_file():
        raise ValueError(f"source GeoTIFF not found: {args.source}")
    if not (0.0 <= args.hillshade_azimuth < 360.0):
        raise ValueError("--hillshade-azimuth must be in [0, 360)")
    if not (0.0 < args.hillshade_altitude <= 90.0):
        raise ValueError("--hillshade-altitude must be in (0, 90]")


def valid_values(data: np.ma.MaskedArray) -> np.ndarray:
    values = data.compressed()
    if values.size == 0:
        raise ValueError("DEM contains no valid elevation samples")
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        raise ValueError("DEM contains no finite elevation samples")
    return finite.astype(np.float64, copy=False)


def fill_masked_nearest_reasonable(
    data: np.ma.MaskedArray,
    fallback: float,
) -> np.ndarray:
    """Return finite float64 data suitable for preview derivatives.

    TINITALY AOIs are expected to be fully covered. If a small masked border is
    present, fill it with the median elevation rather than allowing NaNs to
    poison gradient calculations. The report records the masked-sample count.
    """

    array = np.ma.filled(data, fill_value=fallback).astype(np.float64)
    array[~np.isfinite(array)] = fallback
    return array


def encode_u16(
    elevation: np.ndarray,
    minimum_m: float,
    maximum_m: float,
) -> np.ndarray:
    span = maximum_m - minimum_m
    if span <= 0.0:
        raise ValueError("DEM elevation range must be positive")
    normalized = (elevation - minimum_m) / span
    normalized = np.clip(normalized, 0.0, 1.0)
    return np.rint(normalized * 65535.0).astype(np.uint16)


def save_u16_png(path: Path, values: np.ndarray) -> None:
    Image.fromarray(values, mode="I;16").save(path)


def save_r16_le(path: Path, values: np.ndarray) -> None:
    path.write_bytes(values.astype("<u2", copy=False).tobytes(order="C"))


def hillshade(
    elevation_m: np.ndarray,
    *,
    cell_x_m: float,
    cell_y_m: float,
    azimuth_deg: float,
    altitude_deg: float,
) -> np.ndarray:
    if cell_x_m <= 0.0 or cell_y_m <= 0.0:
        raise ValueError("DEM cell size must be positive")

    grad_y, grad_x = np.gradient(elevation_m, cell_y_m, cell_x_m)
    slope = np.arctan(np.hypot(grad_x, grad_y))
    aspect = np.arctan2(-grad_x, grad_y)

    azimuth_rad = math.radians(azimuth_deg)
    altitude_rad = math.radians(altitude_deg)

    illumination = (
        math.sin(altitude_rad) * np.cos(slope)
        + math.cos(altitude_rad)
        * np.sin(slope)
        * np.cos(azimuth_rad - aspect)
    )
    illumination = np.clip(illumination, -1.0, 1.0)
    gray = np.rint((illumination + 1.0) * 127.5)
    return gray.astype(np.uint8)


def terrain_diagnostics(
    source_elevation_m: np.ndarray,
    prepared_elevation_m: np.ndarray,
    prepared_u16: np.ndarray,
    elevation_min_m: float,
    elevation_max_m: float,
) -> dict[str, Any]:
    span_m = elevation_max_m - elevation_min_m
    decoded_m = elevation_min_m + (
        prepared_u16.astype(np.float64) / 65535.0
    ) * span_m
    roundtrip_error_m = decoded_m - prepared_elevation_m

    dx = np.abs(np.diff(prepared_elevation_m, axis=1))
    dy = np.abs(np.diff(prepared_elevation_m, axis=0))
    adjacent = np.concatenate((dx.ravel(), dy.ravel()))
    nonzero = adjacent[adjacent > 0.0]

    unique_values = np.unique(prepared_u16)
    flat_share = float(np.mean(adjacent == 0.0))

    def seam_stats(period: int) -> dict[str, Any]:
        seam_deltas = []
        for boundary in range(period, prepared_elevation_m.shape[1], period):
            seam_deltas.append(
                np.abs(
                    prepared_elevation_m[:, boundary]
                    - prepared_elevation_m[:, boundary - 1]
                )
            )
        for boundary in range(period, prepared_elevation_m.shape[0], period):
            seam_deltas.append(
                np.abs(
                    prepared_elevation_m[boundary, :]
                    - prepared_elevation_m[boundary - 1, :]
                )
            )
        if not seam_deltas:
            return {"sample_count": 0}
        values = np.concatenate([arr.ravel() for arr in seam_deltas])
        return {
            "sample_count": int(values.size),
            "mean_abs_delta_m": round(float(values.mean()), 6),
            "p95_abs_delta_m": round(float(np.percentile(values, 95)), 6),
            "p99_abs_delta_m": round(float(np.percentile(values, 99)), 6),
            "max_abs_delta_m": round(float(values.max()), 6),
        }

    return {
        "prepared_u16": {
            "unique_value_count": int(unique_values.size),
            "vertical_quantization_step_m": round(span_m / 65535.0, 9),
            "flat_adjacent_share": round(flat_share, 9),
        },
        "adjacent_elevation_delta_m": {
            "sample_count": int(adjacent.size),
            "smallest_nonzero": (
                round(float(nonzero.min()), 9) if nonzero.size else 0.0
            ),
            "p50": round(float(np.percentile(adjacent, 50)), 6),
            "p95": round(float(np.percentile(adjacent, 95)), 6),
            "p99": round(float(np.percentile(adjacent, 99)), 6),
            "max": round(float(adjacent.max()), 6),
        },
        "r16_roundtrip_error_m": {
            "rmse": round(
                float(np.sqrt(np.mean(np.square(roundtrip_error_m)))),
                9,
            ),
            "max_abs": round(float(np.max(np.abs(roundtrip_error_m))), 9),
        },
        "seams": {
            "subsection_63_quads": seam_stats(63),
            "component_126_quads": seam_stats(126),
        },
        "source_unique_elevation_count": int(
            np.unique(source_elevation_m).size
        ),
    }


def percentile_dict(values: np.ndarray) -> dict[str, float]:
    percentiles = np.percentile(values, [1, 5, 25, 50, 75, 95, 99])
    labels = ("p01", "p05", "p25", "p50", "p75", "p95", "p99")
    return {
        label: round(float(value), 3)
        for label, value in zip(labels, percentiles, strict=True)
    }


def landscape_import_metadata(
    *,
    width_m: float,
    height_m: float,
    elevation_min_m: float,
    elevation_max_m: float,
    landscape_size: int,
) -> dict[str, Any]:
    elevation_range_m = elevation_max_m - elevation_min_m
    center_elevation_m = (elevation_min_m + elevation_max_m) / 2.0

    # Unreal Landscape's 16-bit height domain spans 512 vertical units at
    # Transform Z scale 100. This maps the complete encoded DEM range to the
    # source elevation range while centering the actor around the DEM midpoint.
    recommended_z_scale = elevation_range_m * 100.0 / 512.0

    x_intervals = landscape_size - 1
    y_intervals = landscape_size - 1
    xy_scale_x_cm = width_m * 100.0 / x_intervals
    xy_scale_y_cm = height_m * 100.0 / y_intervals

    return {
        "landscape_size_vertices": landscape_size,
        "source_fidelity_note": (
            "The Landscape-sized raster is resampled for UE compatibility; "
            "source terrain fidelity remains that of the original TINITALY grid."
        ),
        "recommended_transform": {
            "scale_x_cm_per_vertex": round(xy_scale_x_cm, 6),
            "scale_y_cm_per_vertex": round(xy_scale_y_cm, 6),
            "scale_z": round(recommended_z_scale, 6),
            "location_z_cm_for_sea_level_preservation": round(
                center_elevation_m * 100.0,
                3,
            ),
        },
        "height_encoding": {
            "format": "unsigned 16-bit",
            "encoded_min": 0,
            "encoded_mid": 32768,
            "encoded_max": 65535,
            "elevation_min_m": round(elevation_min_m, 3),
            "elevation_mid_m": round(center_elevation_m, 3),
            "elevation_max_m": round(elevation_max_m, 3),
            "mapping": (
                "elevation_m = elevation_min_m + "
                "(encoded / 65535) * elevation_range_m"
            ),
        },
    }


def main() -> int:
    args = parse_args()
    try:
        validate_args(args)
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        with rasterio.open(args.source) as src:
            source = src.read(1, masked=True)
            values = valid_values(source)
            elevation_min_m = float(values.min())
            elevation_max_m = float(values.max())
            median_m = float(np.median(values))

            source_filled = fill_masked_nearest_reasonable(source, median_m)
            source_width = int(src.width)
            source_height = int(src.height)
            bounds = src.bounds
            width_m = float(bounds.right - bounds.left)
            height_m = float(bounds.top - bounds.bottom)
            cell_x_m = abs(float(src.transform.a))
            cell_y_m = abs(float(src.transform.e))

            landscape = src.read(
                1,
                out_shape=(args.landscape_size, args.landscape_size),
                masked=True,
                resampling=Resampling.bilinear,
            )
            landscape_filled = fill_masked_nearest_reasonable(
                landscape,
                median_m,
            )

            source_metadata = {
                "driver": src.driver,
                "dtype": str(src.dtypes[0]),
                "crs": str(src.crs),
                "nodata": src.nodata,
                "width_px": source_width,
                "height_px": source_height,
                "pixel_size_m": {
                    "x": round(cell_x_m, 6),
                    "y": round(cell_y_m, 6),
                },
                "bounds": {
                    "left": float(bounds.left),
                    "bottom": float(bounds.bottom),
                    "right": float(bounds.right),
                    "top": float(bounds.top),
                },
                "extent_m": {
                    "x": round(width_m, 3),
                    "y": round(height_m, 3),
                },
                "masked_samples": int(np.ma.count_masked(source)),
            }
    except (OSError, rasterio.errors.RasterioError, ValueError) as exc:
        print(f"[error] failed to read DEM: {exc}", file=sys.stderr)
        return 3

    if args.flip_y:
        source_filled = np.flipud(source_filled)
        landscape_filled = np.flipud(landscape_filled)

    native_u16 = encode_u16(
        source_filled,
        elevation_min_m,
        elevation_max_m,
    )
    landscape_u16 = encode_u16(
        landscape_filled,
        elevation_min_m,
        elevation_max_m,
    )

    native_png = output_dir / "passo_giau_height_native_u16.png"
    landscape_png = (
        output_dir
        / f"passo_giau_height_ue_landscape_{args.landscape_size}_u16.png"
    )
    landscape_r16 = (
        output_dir
        / f"passo_giau_height_ue_landscape_{args.landscape_size}.r16"
    )
    hillshade_png = output_dir / "passo_giau_hillshade.png"
    report_json = output_dir / "terrain-report.json"

    save_u16_png(native_png, native_u16)
    save_u16_png(landscape_png, landscape_u16)
    save_r16_le(landscape_r16, landscape_u16)

    hillshade_values = hillshade(
        source_filled,
        cell_x_m=cell_x_m,
        cell_y_m=cell_y_m,
        azimuth_deg=args.hillshade_azimuth,
        altitude_deg=args.hillshade_altitude,
    )
    Image.fromarray(hillshade_values, mode="L").save(hillshade_png)

    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "path": str(args.source.resolve()),
            **source_metadata,
        },
        "elevation_m": {
            "minimum": round(elevation_min_m, 3),
            "maximum": round(elevation_max_m, 3),
            "range": round(elevation_max_m - elevation_min_m, 3),
            "mean": round(float(values.mean()), 3),
            "standard_deviation": round(float(values.std()), 3),
            "percentiles": percentile_dict(values),
        },
        "diagnostics": terrain_diagnostics(
            source_filled,
            landscape_filled,
            landscape_u16,
            elevation_min_m,
            elevation_max_m,
        ),
        "orientation": {
            "vertical_flip_applied": bool(args.flip_y),
            "source_raster_row_order": "north_to_south",
        },
        "hillshade": {
            "azimuth_deg": args.hillshade_azimuth,
            "altitude_deg": args.hillshade_altitude,
        },
        "unreal_landscape_candidate": landscape_import_metadata(
            width_m=width_m,
            height_m=height_m,
            elevation_min_m=elevation_min_m,
            elevation_max_m=elevation_max_m,
            landscape_size=args.landscape_size,
        ),
        "outputs": {
            "native_u16_png": native_png.name,
            "landscape_u16_png": landscape_png.name,
            "landscape_r16_little_endian": landscape_r16.name,
            "hillshade_png": hillshade_png.name,
        },
        "yacs_policy": {
            "presentation_only": True,
            "authoritative_route_geometry": False,
            "authoritative_physics": False,
            "stage": "Stage 3G R4.1 Alpine Visual Recovery",
        },
    }
    report_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("Passo Giau terrain preparation")
    print(f"  source:       {args.source.resolve()}")
    print(f"  source grid:  {source_width} x {source_height}")
    print(f"  source cell:  {cell_x_m:.3f} x {cell_y_m:.3f} m")
    print(
        "  elevation:    "
        f"{elevation_min_m:.3f} .. {elevation_max_m:.3f} m "
        f"(range {elevation_max_m - elevation_min_m:.3f} m)"
    )
    print(
        "  landscape:    "
        f"{args.landscape_size} x {args.landscape_size} vertices"
    )
    print(
        "  UE XY scale:  "
        f"{report['unreal_landscape_candidate']['recommended_transform']['scale_x_cm_per_vertex']:.3f} "
        "cm/vertex"
    )
    print(
        "  UE Z scale:   "
        f"{report['unreal_landscape_candidate']['recommended_transform']['scale_z']:.3f}"
    )
    print(f"  output dir:   {output_dir}")
    for path in (
        native_png,
        landscape_png,
        landscape_r16,
        hillshade_png,
        report_json,
    ):
        print(f"[ok] {path.name}: {path.stat().st_size} bytes")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

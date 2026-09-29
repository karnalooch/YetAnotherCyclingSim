#!/usr/bin/env python3
"""Mosaic and prepare Veneto LiDAR-derived 5 m DTM for the Passo Giau spike."""

from __future__ import annotations

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
from rasterio.merge import merge
from rasterio.transform import from_bounds
from rasterio.warp import reproject

SOURCE_CRS = "EPSG:7795"  # RDN2008 / Zone 12 (E,N)
TARGET_CRS = "EPSG:32632"
TARGET_BOUNDS = (730406.587, 5148246.775, 738406.587, 5156246.775)
TARGET_NATIVE_RESOLUTION_M = 5.0
TARGET_NATIVE_SIZE = 1600
LANDSCAPE_SIZE = 4033
NODATA = -9999.0
HILLSHADE_AZIMUTH_DEG = 315.0
HILLSHADE_ALTITUDE_DEG = 45.0


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def input_root() -> Path:
    return (
        repository_root()
        / "ExternalAssets"
        / "Terrain"
        / "PassoGiau"
        / "Veneto_Lidar5m"
    )


def output_root() -> Path:
    return (
        repository_root()
        / "ExternalAssets"
        / "Terrain"
        / "PassoGiau"
        / "PreparedVenetoLidar5m"
    )


def encode_u16(values: np.ndarray, minimum: float, maximum: float) -> np.ndarray:
    span = maximum - minimum
    if not span > 0.0:
        raise ValueError("elevation range must be positive")
    normalized = np.clip((values - minimum) / span, 0.0, 1.0)
    return np.rint(normalized * 65535.0).astype(np.uint16)


def hillshade(values: np.ndarray, cell_m: float) -> np.ndarray:
    grad_y, grad_x = np.gradient(values.astype(np.float64), cell_m, cell_m)
    slope = np.arctan(np.hypot(grad_x, grad_y))
    aspect = np.arctan2(-grad_x, grad_y)
    azimuth = math.radians(HILLSHADE_AZIMUTH_DEG)
    altitude = math.radians(HILLSHADE_ALTITUDE_DEG)
    illumination = (
        math.sin(altitude) * np.cos(slope)
        + math.cos(altitude) * np.sin(slope) * np.cos(azimuth - aspect)
    )
    return np.rint((np.clip(illumination, -1.0, 1.0) + 1.0) * 127.5).astype(
        np.uint8
    )


def stats(values: np.ndarray) -> dict[str, Any]:
    finite = values[np.isfinite(values)].astype(np.float64, copy=False)
    if finite.size == 0:
        raise ValueError("terrain array has no finite samples")
    percentiles = np.percentile(finite, [1, 5, 25, 50, 75, 95, 99])
    return {
        "minimum": round(float(finite.min()), 3),
        "maximum": round(float(finite.max()), 3),
        "range": round(float(finite.max() - finite.min()), 3),
        "mean": round(float(finite.mean()), 3),
        "standard_deviation": round(float(finite.std()), 3),
        "percentiles": {
            key: round(float(value), 3)
            for key, value in zip(
                ("p01", "p05", "p25", "p50", "p75", "p95", "p99"),
                percentiles,
                strict=True,
            )
        },
    }


def adjacent_diagnostics(values: np.ndarray) -> dict[str, Any]:
    dx = np.abs(np.diff(values.astype(np.float64), axis=1))
    dy = np.abs(np.diff(values.astype(np.float64), axis=0))
    adjacent = np.concatenate((dx.ravel(), dy.ravel()))
    nonzero = adjacent[adjacent > 0.0]
    return {
        "flat_adjacent_share": round(float(np.mean(adjacent == 0.0)), 9),
        "smallest_nonzero_m": (
            round(float(nonzero.min()), 9) if nonzero.size else 0.0
        ),
        "p50_m": round(float(np.percentile(adjacent, 50)), 6),
        "p95_m": round(float(np.percentile(adjacent, 95)), 6),
        "p99_m": round(float(np.percentile(adjacent, 99)), 6),
        "max_m": round(float(adjacent.max()), 6),
    }


def r16_roundtrip_diagnostics(
    prepared_elevation_m: np.ndarray,
    prepared_u16: np.ndarray,
    minimum_m: float,
    maximum_m: float,
) -> dict[str, Any]:
    span_m = maximum_m - minimum_m
    quantization_step_m = span_m / 65535.0
    decoded_m = minimum_m + (
        prepared_u16.astype(np.float64) / 65535.0
    ) * span_m
    error_m = decoded_m - prepared_elevation_m.astype(np.float64)
    return {
        "rmse": round(
            float(np.sqrt(np.mean(np.square(error_m)))),
            9,
        ),
        "max_abs": round(float(np.max(np.abs(error_m))), 9),
        "theoretical_half_step_m": round(quantization_step_m / 2.0, 9),
    }


def seam_diagnostics(
    values: np.ndarray,
    period: int,
    global_adjacent_p99_m: float,
) -> dict[str, Any]:
    seam_deltas: list[np.ndarray] = []
    for boundary in range(period, values.shape[1], period):
        seam_deltas.append(
            np.abs(
                values[:, boundary].astype(np.float64)
                - values[:, boundary - 1].astype(np.float64)
            )
        )
    for boundary in range(period, values.shape[0], period):
        seam_deltas.append(
            np.abs(
                values[boundary, :].astype(np.float64)
                - values[boundary - 1, :].astype(np.float64)
            )
        )
    if not seam_deltas:
        return {"sample_count": 0}

    samples = np.concatenate([item.ravel() for item in seam_deltas])
    p99 = float(np.percentile(samples, 99))
    return {
        "period_quads": period,
        "sample_count": int(samples.size),
        "mean_abs_delta_m": round(float(samples.mean()), 6),
        "p95_abs_delta_m": round(float(np.percentile(samples, 95)), 6),
        "p99_abs_delta_m": round(p99, 6),
        "max_abs_delta_m": round(float(samples.max()), 6),
        "p99_to_global_adjacent_p99_ratio": (
            round(p99 / global_adjacent_p99_m, 6)
            if global_adjacent_p99_m > 0.0
            else None
        ),
    }


def slope_diagnostics(values: np.ndarray, cell_m: float) -> dict[str, Any]:
    grad_y, grad_x = np.gradient(
        values.astype(np.float64),
        cell_m,
        cell_m,
    )
    slope_deg = np.degrees(np.arctan(np.hypot(grad_x, grad_y)))
    bin_edges = (0.0, 5.0, 15.0, 30.0, 45.0, 60.0, 90.0)
    counts, _ = np.histogram(slope_deg, bins=bin_edges)
    total = int(slope_deg.size)
    histogram = []
    for index, count in enumerate(counts):
        histogram.append(
            {
                "min_deg": bin_edges[index],
                "max_deg": bin_edges[index + 1],
                "count": int(count),
                "share": round(float(count) / total, 9),
            }
        )
    return {
        "cell_m": round(float(cell_m), 9),
        "p50_deg": round(float(np.percentile(slope_deg, 50)), 6),
        "p95_deg": round(float(np.percentile(slope_deg, 95)), 6),
        "p99_deg": round(float(np.percentile(slope_deg, 99)), 6),
        "max_deg": round(float(slope_deg.max()), 6),
        "histogram": histogram,
    }


def scanline_diagnostics(values: np.ndarray, sample_count: int = 33) -> dict[str, Any]:
    if sample_count < 2:
        raise ValueError("scanline sample_count must be at least 2")
    row = values.shape[0] // 2
    column = values.shape[1] // 2
    x_indices = np.linspace(0, values.shape[1] - 1, sample_count, dtype=int)
    y_indices = np.linspace(0, values.shape[0] - 1, sample_count, dtype=int)
    return {
        "center_row_index": int(row),
        "center_column_index": int(column),
        "center_row_sample_indices": [int(value) for value in x_indices],
        "center_row_elevation_m": [
            round(float(values[row, index]), 3) for index in x_indices
        ],
        "center_column_sample_indices": [int(value) for value in y_indices],
        "center_column_elevation_m": [
            round(float(values[index, column]), 3) for index in y_indices
        ],
    }


def landscape_diagnostics(
    landscape: np.ndarray,
    encoded: np.ndarray,
    minimum_m: float,
    maximum_m: float,
) -> dict[str, Any]:
    adjacent = adjacent_diagnostics(landscape)
    landscape_cell_m = (
        (TARGET_BOUNDS[2] - TARGET_BOUNDS[0]) / (LANDSCAPE_SIZE - 1)
    )
    return {
        **adjacent,
        "unique_u16_count": int(np.unique(encoded).size),
        "vertical_quantization_step_m": round(
            (maximum_m - minimum_m) / 65535.0,
            9,
        ),
        "r16_roundtrip_error_m": r16_roundtrip_diagnostics(
            landscape,
            encoded,
            minimum_m,
            maximum_m,
        ),
        "seams": {
            "subsection_63_quads": seam_diagnostics(
                landscape,
                63,
                float(adjacent["p99_m"]),
            ),
            "component_126_quads": seam_diagnostics(
                landscape,
                126,
                float(adjacent["p99_m"]),
            ),
        },
        "slope_degrees": slope_diagnostics(landscape, landscape_cell_m),
        "scanlines": scanline_diagnostics(landscape),
    }


def landscape_metadata(minimum: float, maximum: float) -> dict[str, Any]:
    span = maximum - minimum
    midpoint = (minimum + maximum) / 2.0
    return {
        "landscape_size_vertices": LANDSCAPE_SIZE,
        "source_fidelity_note": (
            "The 4033-square Landscape raster is a cubic presentation resample "
            "of a real 5 m LiDAR-derived Veneto DTM. Native source detail remains "
            "5 m; the 4033 grid does not create additional measured terrain detail."
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
    root = input_root()
    tiles = sorted((root / "tiles").glob("12_2K_*.asc"))
    if not tiles:
        print(f"[error] no Veneto ASC tiles found under {root / 'tiles'}", file=sys.stderr)
        return 2

    report_path = root / "veneto-lidar-download-report.json"
    if not report_path.is_file():
        print(f"[error] missing download report: {report_path}", file=sys.stderr)
        return 2
    download_report = json.loads(report_path.read_text(encoding="utf-8"))

    datasets = []
    try:
        for tile in tiles:
            src = rasterio.open(tile)
            if src.width != 400 or src.height != 400:
                raise ValueError(f"{tile.name}: expected 400x400, got {src.width}x{src.height}")
            if abs(float(src.transform.a) - 5.0) > 1e-6:
                raise ValueError(f"{tile.name}: unexpected X cell size {src.transform.a}")
            if abs(abs(float(src.transform.e)) - 5.0) > 1e-6:
                raise ValueError(f"{tile.name}: unexpected Y cell size {src.transform.e}")
            datasets.append(src)

        source_mosaic, source_transform = merge(
            datasets,
            nodata=NODATA,
            dtype="float32",
            method="first",
        )
        source = source_mosaic[0]
        source_mask = np.isfinite(source) & (source != NODATA)
        if not np.any(source_mask):
            raise ValueError("merged Veneto mosaic contains no valid elevation samples")

        native_transform = from_bounds(
            *TARGET_BOUNDS,
            width=TARGET_NATIVE_SIZE,
            height=TARGET_NATIVE_SIZE,
        )
        native = np.full(
            (TARGET_NATIVE_SIZE, TARGET_NATIVE_SIZE),
            np.nan,
            dtype=np.float32,
        )
        reproject(
            source=source,
            destination=native,
            src_transform=source_transform,
            src_crs=SOURCE_CRS,
            src_nodata=NODATA,
            dst_transform=native_transform,
            dst_crs=TARGET_CRS,
            dst_nodata=np.nan,
            resampling=Resampling.cubic,
        )

        missing = int(np.count_nonzero(~np.isfinite(native)))
        if missing:
            raise ValueError(
                f"reprojected 8 km AOI has {missing} missing 5 m samples; "
                "WFS tile coverage is incomplete"
            )

        native_stats = stats(native)
        elevation_min = float(native_stats["minimum"])
        elevation_max = float(native_stats["maximum"])

        landscape_transform = from_bounds(
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
            src_transform=native_transform,
            src_crs=TARGET_CRS,
            dst_transform=landscape_transform,
            dst_crs=TARGET_CRS,
            dst_nodata=np.nan,
            resampling=Resampling.cubic,
        )
        if not np.all(np.isfinite(landscape)):
            raise ValueError("4033 Landscape resample contains missing samples")
    except Exception as exc:
        print(f"[error] Veneto terrain preparation failed: {exc}", file=sys.stderr)
        return 3
    finally:
        for src in datasets:
            src.close()

    out = output_root()
    out.mkdir(parents=True, exist_ok=True)

    native_tif = out / "passo_giau_veneto_lidar_5m_8km_epsg32632.tif"
    native_hillshade = out / "passo_giau_veneto_lidar_5m_hillshade.png"
    landscape_png = out / "passo_giau_veneto_lidar_ue_landscape_4033_u16.png"
    landscape_r16 = out / "passo_giau_veneto_lidar_ue_landscape_4033.r16"
    terrain_report = out / "terrain-report.json"

    profile = {
        "driver": "GTiff",
        "height": TARGET_NATIVE_SIZE,
        "width": TARGET_NATIVE_SIZE,
        "count": 1,
        "dtype": "float32",
        "crs": TARGET_CRS,
        "transform": native_transform,
        "compress": "deflate",
        "predictor": 3,
    }
    with rasterio.open(native_tif, "w", **profile) as dst:
        dst.write(native.astype(np.float32), 1)

    Image.fromarray(
        hillshade(native, TARGET_NATIVE_RESOLUTION_M),
        mode="L",
    ).save(native_hillshade)

    encoded = encode_u16(landscape, elevation_min, elevation_max)
    Image.fromarray(encoded, mode="I;16").save(landscape_png)
    landscape_r16.write_bytes(
        encoded.astype("<u2", copy=False).tobytes(order="C")
    )

    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "Regione del Veneto",
        "dataset": "DTM 5 m derivato dai rilievi LiDAR",
        "license": download_report.get("license", "IODL 2.0"),
        "source_crs": SOURCE_CRS,
        "target_crs": TARGET_CRS,
        "tile_count": len(tiles),
        "source_tiles": [tile.name for tile in tiles],
        "target_aoi": {
            "bounds_epsg32632": {
                "left": TARGET_BOUNDS[0],
                "bottom": TARGET_BOUNDS[1],
                "right": TARGET_BOUNDS[2],
                "top": TARGET_BOUNDS[3],
            },
            "native_grid": [TARGET_NATIVE_SIZE, TARGET_NATIVE_SIZE],
            "native_cell_m": TARGET_NATIVE_RESOLUTION_M,
            "extent_m": [8000.0, 8000.0],
        },
        "elevation_m": native_stats,
        "native_diagnostics": {
            **adjacent_diagnostics(native),
            "unique_elevation_count": int(np.unique(native).size),
            "slope_degrees": slope_diagnostics(
                native,
                TARGET_NATIVE_RESOLUTION_M,
            ),
            "scanlines": scanline_diagnostics(native),
        },
        "landscape_diagnostics": landscape_diagnostics(
            landscape,
            encoded,
            elevation_min,
            elevation_max,
        ),
        "landscape_resampling": "cubic",
        "reprojection_resampling": "cubic",
        "unreal_landscape_candidate": landscape_metadata(
            elevation_min,
            elevation_max,
        ),
        "outputs": {
            "native_geotiff": native_tif.name,
            "native_hillshade": native_hillshade.name,
            "landscape_u16_png": landscape_png.name,
            "landscape_r16_little_endian": landscape_r16.name,
        },
        "yacs_policy": {
            "presentation_only": True,
            "authoritative_route_geometry": False,
            "authoritative_physics": False,
            "stage": "Stage 3G R4.1 Alpine Visual Recovery",
        },
    }
    terrain_report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("Passo Giau Veneto LiDAR terrain preparation")
    print(f"  tiles:         {len(tiles)}")
    print(f"  native grid:   {TARGET_NATIVE_SIZE} x {TARGET_NATIVE_SIZE} @ 5 m")
    print(
        "  elevation:     "
        f"{elevation_min:.3f} .. {elevation_max:.3f} m "
        f"(range {elevation_max - elevation_min:.3f} m)"
    )
    print(f"  landscape:     {LANDSCAPE_SIZE} x {LANDSCAPE_SIZE}")
    print(
        "  UE XY scale:   "
        f"{report['unreal_landscape_candidate']['recommended_transform']['scale_x_cm_per_vertex']:.6f}"
    )
    print(
        "  UE Z scale:    "
        f"{report['unreal_landscape_candidate']['recommended_transform']['scale_z']:.6f}"
    )
    for path in (
        native_tif,
        native_hillshade,
        landscape_png,
        landscape_r16,
        terrain_report,
    ):
        print(f"[ok] {path.name}: {path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

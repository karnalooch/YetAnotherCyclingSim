#!/usr/bin/env python3
"""Prepare hybrid Passo Giau terrain with MASE PST 1x1 as the primary source.

MASE PST is authoritative for presentation wherever it has valid LiDAR DTM
samples. The official Veneto LiDAR-derived 5 m DTM fills only uncovered cells
inside the established 8 km YACS authoring square. Route/physics truth remains
independent from both terrain sources.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.merge import merge
from rasterio.transform import from_bounds, rowcol
from rasterio.warp import reproject, transform, transform_bounds

from prepare_passo_giau_veneto_lidar import (
    adjacent_diagnostics,
    encode_u16,
    hillshade,
    landscape_diagnostics,
    scanline_diagnostics,
    slope_diagnostics,
    stats,
)

PRIMARY_SOURCE_CRS = "EPSG:4326"
FALLBACK_SOURCE_CRS = "EPSG:7795"
TARGET_CRS = "EPSG:32632"

# Preserve the exact established 8 km x 8 km extent from the proven Veneto
# candidate so road/camera alignment and the UE XY scale do not move when the
# higher-resolution MASE source is introduced.
TARGET_BOUNDS = (730406.587, 5148246.775, 738406.587, 5156246.775)
TARGET_NATIVE_RESOLUTION_M = 1.0
TARGET_NATIVE_SIZE = 8000
LANDSCAPE_SIZE = 4033
NODATA = -9999.0

EXPECTED_MASE_TILE_COUNT = 89
EXPECTED_MASE_PIXEL_DEG = 0.00001
MIN_MASE_COVERAGE_SHARE = 0.50
PASSO_GIAU_WGS84 = (12.05321, 46.48284)
PASSO_GIAU_REPORT_RADIUS_M = 500
OVERLAP_SAMPLE_STRIDE = 8
MAX_VERTICAL_ALIGNMENT_ABS_M = 10.0
MAX_OVERLAP_RESIDUAL_P95_M = 20.0


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def mase_input_root() -> Path:
    return (
        repository_root()
        / "ExternalAssets"
        / "Terrain"
        / "PassoGiau"
        / "MASE_PST_Lidar1x1"
    )


def veneto_input_root() -> Path:
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
        / "PreparedMasePstLidar1x1"
    )


def landscape_metadata(minimum: float, maximum: float) -> dict[str, Any]:
    span = maximum - minimum
    midpoint = (minimum + maximum) / 2.0
    return {
        "landscape_size_vertices": LANDSCAPE_SIZE,
        "source_fidelity_note": (
            "The 4033-square Landscape raster is a presentation resample of a "
            "hybrid metric working grid: valid MASE PST DTM 1x1 samples have "
            "priority after EPSG:4326 -> EPSG:32632 reprojection, while uncovered "
            "cells are filled from the official Veneto LiDAR-derived 5 m DTM. "
            "The fallback is never represented as measured 1 m terrain."
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


def validate_mase_tile(src: rasterio.io.DatasetReader, tile: Path) -> None:
    if src.width != 1000 or src.height != 1000:
        raise ValueError(
            f"{tile.name}: expected 1000x1000, got {src.width}x{src.height}"
        )
    if src.crs is None or src.crs.to_epsg() != 4326:
        raise ValueError(f"{tile.name}: expected EPSG:4326, got {src.crs}")
    if abs(float(src.transform.a) - EXPECTED_MASE_PIXEL_DEG) > 1e-10:
        raise ValueError(
            f"{tile.name}: unexpected X pixel size {src.transform.a}"
        )
    if abs(abs(float(src.transform.e)) - EXPECTED_MASE_PIXEL_DEG) > 1e-10:
        raise ValueError(
            f"{tile.name}: unexpected Y pixel size {src.transform.e}"
        )
    if src.nodata is None or abs(float(src.nodata) - NODATA) > 1e-6:
        raise ValueError(f"{tile.name}: expected NoData={NODATA}, got {src.nodata}")


def validate_veneto_tile(src: rasterio.io.DatasetReader, tile: Path) -> None:
    if src.width != 400 or src.height != 400:
        raise ValueError(
            f"{tile.name}: expected 400x400 fallback tile, "
            f"got {src.width}x{src.height}"
        )
    if abs(float(src.transform.a) - 5.0) > 1e-6:
        raise ValueError(f"{tile.name}: unexpected fallback X cell size")
    if abs(abs(float(src.transform.e)) - 5.0) > 1e-6:
        raise ValueError(f"{tile.name}: unexpected fallback Y cell size")


def reproject_mase(
    tiles: list[Path],
    native_transform: rasterio.Affine,
) -> np.ndarray:
    datasets: list[rasterio.io.DatasetReader] = []
    try:
        for tile in tiles:
            src = rasterio.open(tile)
            validate_mase_tile(src, tile)
            datasets.append(src)

        source_bounds = transform_bounds(
            TARGET_CRS,
            PRIMARY_SOURCE_CRS,
            *TARGET_BOUNDS,
            densify_pts=21,
        )
        source_mosaic, source_transform = merge(
            datasets,
            bounds=source_bounds,
            nodata=NODATA,
            dtype="float32",
            method="first",
        )
        source = source_mosaic[0]
        valid = np.isfinite(source) & (source != NODATA)
        if not np.any(valid):
            raise ValueError("merged MASE mosaic contains no valid elevation samples")

        destination = np.full(
            (TARGET_NATIVE_SIZE, TARGET_NATIVE_SIZE),
            np.nan,
            dtype=np.float32,
        )
        reproject(
            source=source,
            destination=destination,
            src_transform=source_transform,
            src_crs=PRIMARY_SOURCE_CRS,
            src_nodata=NODATA,
            dst_transform=native_transform,
            dst_crs=TARGET_CRS,
            dst_nodata=np.nan,
            resampling=Resampling.cubic,
        )
        return destination
    finally:
        for src in datasets:
            src.close()


def reproject_veneto_fallback(
    tiles: list[Path],
    native_transform: rasterio.Affine,
) -> np.ndarray:
    datasets: list[rasterio.io.DatasetReader] = []
    try:
        for tile in tiles:
            src = rasterio.open(tile)
            validate_veneto_tile(src, tile)
            datasets.append(src)

        source_mosaic, source_transform = merge(
            datasets,
            nodata=NODATA,
            dtype="float32",
            method="first",
        )
        source = source_mosaic[0]
        valid = np.isfinite(source) & (source != NODATA)
        if not np.any(valid):
            raise ValueError("merged Veneto fallback contains no valid samples")

        destination = np.full(
            (TARGET_NATIVE_SIZE, TARGET_NATIVE_SIZE),
            np.nan,
            dtype=np.float32,
        )
        reproject(
            source=source,
            destination=destination,
            src_transform=source_transform,
            src_crs=FALLBACK_SOURCE_CRS,
            src_nodata=NODATA,
            dst_transform=native_transform,
            dst_crs=TARGET_CRS,
            dst_nodata=np.nan,
            resampling=Resampling.cubic,
        )
        missing = int(np.count_nonzero(~np.isfinite(destination)))
        if missing:
            raise ValueError(
                f"Veneto 5 m fallback leaves {missing} cells uncovered "
                "inside the established 8 km AOI"
            )
        return destination
    finally:
        for src in datasets:
            src.close()


def overlap_alignment(
    mase_native: np.ndarray,
    veneto_native: np.ndarray,
) -> dict[str, Any]:
    mase_sample = mase_native[::OVERLAP_SAMPLE_STRIDE, ::OVERLAP_SAMPLE_STRIDE]
    veneto_sample = veneto_native[
        ::OVERLAP_SAMPLE_STRIDE,
        ::OVERLAP_SAMPLE_STRIDE,
    ]
    overlap = np.isfinite(mase_sample) & np.isfinite(veneto_sample)
    if not np.any(overlap):
        raise ValueError("MASE/Veneto sources have no sampled overlap")

    delta = (
        mase_sample[overlap].astype(np.float64)
        - veneto_sample[overlap].astype(np.float64)
    )
    offset = float(np.median(delta))
    if abs(offset) > MAX_VERTICAL_ALIGNMENT_ABS_M:
        raise ValueError(
            "MASE/Veneto median vertical delta is implausible: "
            f"{offset:.3f} m"
        )

    residual = delta - offset
    abs_residual = np.abs(residual)
    p95 = float(np.percentile(abs_residual, 95))
    if p95 > MAX_OVERLAP_RESIDUAL_P95_M:
        raise ValueError(
            "MASE/Veneto overlap residual p95 is implausibly large after "
            f"alignment: {p95:.3f} m"
        )

    return {
        "sample_stride": OVERLAP_SAMPLE_STRIDE,
        "sample_count": int(delta.size),
        "median_mase_minus_veneto_m": round(offset, 6),
        "abs_residual_after_alignment_m": {
            "p50": round(float(np.percentile(abs_residual, 50)), 6),
            "p95": round(p95, 6),
            "p99": round(float(np.percentile(abs_residual, 99)), 6),
            "max": round(float(abs_residual.max()), 6),
        },
    }


def source_boundary_diagnostics(
    values: np.ndarray,
    primary_mask: np.ndarray,
) -> dict[str, Any]:
    horizontal_boundary = primary_mask[:, 1:] != primary_mask[:, :-1]
    vertical_boundary = primary_mask[1:, :] != primary_mask[:-1, :]

    horizontal_delta = np.abs(
        values[:, 1:].astype(np.float64)
        - values[:, :-1].astype(np.float64)
    )[horizontal_boundary]
    vertical_delta = np.abs(
        values[1:, :].astype(np.float64)
        - values[:-1, :].astype(np.float64)
    )[vertical_boundary]

    if horizontal_delta.size + vertical_delta.size == 0:
        return {"sample_count": 0}

    samples = np.concatenate((horizontal_delta, vertical_delta))
    return {
        "sample_count": int(samples.size),
        "mean_abs_delta_m": round(float(samples.mean()), 6),
        "p95_abs_delta_m": round(float(np.percentile(samples, 95)), 6),
        "p99_abs_delta_m": round(float(np.percentile(samples, 99)), 6),
        "max_abs_delta_m": round(float(samples.max()), 6),
    }


def passo_giau_coverage(
    mase_mask: np.ndarray,
    native_transform: rasterio.Affine,
) -> dict[str, Any]:
    xs, ys = transform(
        PRIMARY_SOURCE_CRS,
        TARGET_CRS,
        [PASSO_GIAU_WGS84[0]],
        [PASSO_GIAU_WGS84[1]],
    )
    row, column = rowcol(native_transform, xs[0], ys[0])
    row = int(row)
    column = int(column)

    if not (0 <= row < TARGET_NATIVE_SIZE and 0 <= column < TARGET_NATIVE_SIZE):
        raise ValueError("Passo Giau reference point is outside target AOI")

    on_mase = bool(mase_mask[row, column])

    radius = PASSO_GIAU_REPORT_RADIUS_M
    r0 = max(0, row - radius)
    r1 = min(TARGET_NATIVE_SIZE, row + radius + 1)
    c0 = max(0, column - radius)
    c1 = min(TARGET_NATIVE_SIZE, column + radius + 1)
    local_mask = mase_mask[r0:r1, c0:c1]
    local_share = float(np.mean(local_mask))
    valid_local = np.argwhere(local_mask)
    if valid_local.size == 0:
        raise ValueError(
            f"MASE has no valid terrain sample within {radius} m of Passo Giau"
        )

    center_local_row = row - r0
    center_local_column = column - c0
    nearest_distance_m = float(
        np.min(
            np.hypot(
                valid_local[:, 0] - center_local_row,
                valid_local[:, 1] - center_local_column,
            )
        )
    )

    return {
        "wgs84": {
            "lon": PASSO_GIAU_WGS84[0],
            "lat": PASSO_GIAU_WGS84[1],
        },
        "target_pixel": {"row": row, "column": column},
        "mase_1m_at_reference_point": on_mase,
        "neighborhood_radius_m": radius,
        "mase_valid_samples_in_neighborhood": int(valid_local.shape[0]),
        "coverage_share_in_neighborhood": round(local_share, 9),
        "nearest_mase_sample_distance_m": round(nearest_distance_m, 3),
        "terrain_truth_note": (
            "Landscape is presentation-only. Canonical road elevation/grade comes "
            "from the road/route pipeline, so an isolated NoData/fallback cell at "
            "the pass does not redefine cycling physics."
        ),
    }


def main() -> int:
    mase_root = mase_input_root()
    mase_tiles = sorted(
        list((mase_root / "tiles").glob("*.tif"))
        + list((mase_root / "tiles").glob("*.tiff"))
    )
    if len(mase_tiles) != EXPECTED_MASE_TILE_COUNT:
        print(
            f"[error] expected {EXPECTED_MASE_TILE_COUNT} MASE GeoTIFF tiles, "
            f"found {len(mase_tiles)} under {mase_root / 'tiles'}",
            file=sys.stderr,
        )
        return 2

    mase_report_path = mase_root / "mase-pst-download-report.json"
    if not mase_report_path.is_file():
        print(f"[error] missing MASE download report: {mase_report_path}", file=sys.stderr)
        return 2
    mase_report = json.loads(mase_report_path.read_text(encoding="utf-8"))

    veneto_root = veneto_input_root()
    veneto_tiles = sorted((veneto_root / "tiles").glob("12_2K_*.asc"))
    if not veneto_tiles:
        print(
            f"[error] no Veneto 5 m fallback tiles under {veneto_root / 'tiles'}",
            file=sys.stderr,
        )
        return 2

    veneto_report_path = veneto_root / "veneto-lidar-download-report.json"
    if not veneto_report_path.is_file():
        print(
            f"[error] missing Veneto fallback report: {veneto_report_path}",
            file=sys.stderr,
        )
        return 2
    veneto_report = json.loads(veneto_report_path.read_text(encoding="utf-8"))

    native_transform = from_bounds(
        *TARGET_BOUNDS,
        width=TARGET_NATIVE_SIZE,
        height=TARGET_NATIVE_SIZE,
    )

    try:
        mase_native = reproject_mase(mase_tiles, native_transform)
        mase_mask = np.isfinite(mase_native)
        mase_valid = int(np.count_nonzero(mase_mask))
        total = int(mase_mask.size)
        mase_missing = total - mase_valid
        mase_share = mase_valid / total
        if mase_share < MIN_MASE_COVERAGE_SHARE:
            raise ValueError(
                "MASE coverage is below the minimum useful share: "
                f"{mase_share:.6f} < {MIN_MASE_COVERAGE_SHARE:.6f}"
            )

        giau_coverage = passo_giau_coverage(mase_mask, native_transform)

        veneto_native = reproject_veneto_fallback(
            veneto_tiles,
            native_transform,
        )
        alignment = overlap_alignment(mase_native, veneto_native)
        fallback_offset = float(alignment["median_mase_minus_veneto_m"])
        veneto_aligned = veneto_native + fallback_offset

        native = np.where(
            mase_mask,
            mase_native,
            veneto_aligned,
        ).astype(np.float32, copy=False)
        remaining_missing = int(np.count_nonzero(~np.isfinite(native)))
        if remaining_missing:
            raise ValueError(
                f"hybrid terrain still has {remaining_missing} missing samples"
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

        # Cubic interpolation may overshoot the measured source elevation
        # domain by a fraction of a metre near sharp terrain transitions.
        # Do not encode invented extrema into the R16 transform: clamp the
        # presentation resample to the valid hybrid source min/max first.
        preclip_min = float(landscape.min())
        preclip_max = float(landscape.max())
        clipped_below_count = int(np.count_nonzero(landscape < elevation_min))
        clipped_above_count = int(np.count_nonzero(landscape > elevation_max))
        landscape_resampling_guard = {
            "preclip_min_m": round(preclip_min, 6),
            "preclip_max_m": round(preclip_max, 6),
            "clipped_below_count": clipped_below_count,
            "clipped_above_count": clipped_above_count,
            "max_undershoot_m": round(max(0.0, elevation_min - preclip_min), 6),
            "max_overshoot_m": round(max(0.0, preclip_max - elevation_max), 6),
            "policy": "clip cubic presentation resample to measured hybrid source domain before R16 encoding",
        }
        landscape = np.clip(
            landscape,
            elevation_min,
            elevation_max,
        ).astype(np.float32, copy=False)
    except Exception as exc:
        print(f"[error] hybrid terrain preparation failed: {exc}", file=sys.stderr)
        return 3

    out = output_root()
    out.mkdir(parents=True, exist_ok=True)

    native_tif = out / "passo_giau_mase_pst_hybrid_1m_8km_epsg32632.tif"
    native_hillshade = out / "passo_giau_mase_pst_hybrid_2m_preview_hillshade.png"
    coverage_png = out / "passo_giau_mase_pst_primary_coverage_4m.png"
    landscape_png = out / "passo_giau_mase_pst_ue_landscape_4033_u16.png"
    landscape_r16 = out / "passo_giau_mase_pst_ue_landscape_4033.r16"
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
        hillshade(native[::2, ::2], TARGET_NATIVE_RESOLUTION_M * 2.0),
        mode="L",
    ).save(native_hillshade)
    Image.fromarray(
        (mase_mask[::4, ::4].astype(np.uint8) * 255),
        mode="L",
    ).save(coverage_png)

    encoded = encode_u16(landscape, elevation_min, elevation_max)
    Image.fromarray(encoded, mode="I;16").save(landscape_png)
    landscape_r16.write_bytes(
        encoded.astype("<u2", copy=False).tobytes(order="C")
    )

    native_diag_stride = 4
    native_diag = native[::native_diag_stride, ::native_diag_stride]
    mask_diag = mase_mask[::native_diag_stride, ::native_diag_stride]

    report = {
        "schema_version": 2,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "primary_source": {
            "provider": "Ministero dell'Ambiente e della Sicurezza Energetica (MASE)",
            "dataset": "PST LiDAR DTM grigliato 1x1",
            "license": mase_report.get("license", "CC BY 4.0"),
            "release_tag": mase_report.get("release_tag"),
            "archive": mase_report.get("archive"),
            "source_crs": PRIMARY_SOURCE_CRS,
            "source_pixel_size_degrees": EXPECTED_MASE_PIXEL_DEG,
            "tile_count": len(mase_tiles),
        },
        "fallback_source": {
            "provider": "Regione del Veneto",
            "dataset": "DTM 5 m derivato dai rilievi LiDAR",
            "license": veneto_report.get("license", "IODL 2.0"),
            "source_crs": FALLBACK_SOURCE_CRS,
            "tile_count": len(veneto_tiles),
            "role": "gap fill only where MASE has no valid DTM sample",
            "vertical_alignment_offset_m": round(fallback_offset, 6),
        },
        "target_crs": TARGET_CRS,
        "tile_count": len(mase_tiles),
        "source_tiles": [tile.name for tile in mase_tiles],
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
        "coverage": {
            "total_samples": total,
            "mase_valid_samples": mase_valid,
            "mase_missing_samples_filled_by_veneto": mase_missing,
            "mase_share": round(mase_share, 9),
            "minimum_required_mase_share": MIN_MASE_COVERAGE_SHARE,
            "remaining_missing_samples": remaining_missing,
            "passo_giau": giau_coverage,
            "overlap_alignment": alignment,
            "source_boundary_diagnostics_4m": source_boundary_diagnostics(
                native_diag,
                mask_diag,
            ),
        },
        "elevation_m": native_stats,
        "native_diagnostics": {
            "sample_stride": native_diag_stride,
            "sample_cell_m": TARGET_NATIVE_RESOLUTION_M * native_diag_stride,
            **adjacent_diagnostics(native_diag),
            "sampled_unique_elevation_count": int(
                np.unique(native_diag[::2, ::2]).size
            ),
            "slope_degrees": slope_diagnostics(
                native_diag,
                TARGET_NATIVE_RESOLUTION_M * native_diag_stride,
            ),
            "scanlines": scanline_diagnostics(native_diag),
        },
        "landscape_diagnostics": landscape_diagnostics(
            landscape,
            encoded,
            elevation_min,
            elevation_max,
        ),
        "landscape_resampling": "cubic",
        "landscape_resampling_guard": landscape_resampling_guard,
        "reprojection_resampling": "cubic",
        "unreal_landscape_candidate": landscape_metadata(
            elevation_min,
            elevation_max,
        ),
        "outputs": {
            "native_geotiff": native_tif.name,
            "native_hillshade": native_hillshade.name,
            "primary_coverage_mask": coverage_png.name,
            "landscape_u16_png": landscape_png.name,
            "landscape_r16_little_endian": landscape_r16.name,
        },
        "yacs_policy": {
            "presentation_only": True,
            "authoritative_route_geometry": False,
            "authoritative_physics": False,
            "stage": "Stage 3G R4.1 Alpine Visual Recovery",
            "degrees_are_not_meters": True,
            "fallback_is_not_claimed_as_1m_measurement": True,
        },
    }
    terrain_report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("Passo Giau hybrid MASE 1x1 + Veneto 5 m terrain preparation")
    print(f"  MASE tiles:      {len(mase_tiles)}")
    print(f"  Veneto fallback: {len(veneto_tiles)} tiles")
    print(
        "  MASE coverage:   "
        f"{mase_valid}/{total} = {mase_share * 100.0:.2f}%"
    )
    print(
        "  Passo Giau MASE: "
        f"point={giau_coverage['mase_1m_at_reference_point']}, "
        f"nearest={giau_coverage['nearest_mase_sample_distance_m']:.1f} m, "
        f"local={giau_coverage['coverage_share_in_neighborhood'] * 100.0:.1f}%"
    )
    print(
        "  fallback offset: "
        f"{fallback_offset:.3f} m (median MASE - Veneto overlap)"
    )
    print(f"  native grid:     {TARGET_NATIVE_SIZE} x {TARGET_NATIVE_SIZE} @ 1 m")
    print(
        "  elevation:       "
        f"{elevation_min:.3f} .. {elevation_max:.3f} m "
        f"(range {elevation_max - elevation_min:.3f} m)"
    )
    print(f"  landscape:       {LANDSCAPE_SIZE} x {LANDSCAPE_SIZE}")
    print(
        "  UE XY scale:     "
        f"{report['unreal_landscape_candidate']['recommended_transform']['scale_x_cm_per_vertex']:.6f}"
    )
    print(
        "  UE Z scale:      "
        f"{report['unreal_landscape_candidate']['recommended_transform']['scale_z']:.6f}"
    )
    for output_path in (
        native_tif,
        native_hillshade,
        coverage_png,
        landscape_png,
        landscape_r16,
        terrain_report,
    ):
        print(f"[ok] {output_path.name}: {output_path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

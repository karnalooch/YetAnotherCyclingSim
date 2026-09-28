#!/usr/bin/env python3
"""Prepare the immutable MASE PST LiDAR DTM 1x1 for the Passo Giau UE spike."""

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
from rasterio.transform import from_bounds
from rasterio.warp import reproject, transform_bounds

from prepare_passo_giau_veneto_lidar import (
    adjacent_diagnostics,
    encode_u16,
    hillshade,
    landscape_diagnostics,
    scanline_diagnostics,
    slope_diagnostics,
    stats,
)

SOURCE_CRS = "EPSG:4326"
TARGET_CRS = "EPSG:32632"
# Preserve the established 8 km Landscape size and UE XY scale. The previous
# square is shifted 40 m south so the rotated UTM extent remains inside the
# immutable MASE tile-union north edge at 46.52 N.
TARGET_BOUNDS = (730406.587, 5148206.775, 738406.587, 5156206.775)
TARGET_NATIVE_RESOLUTION_M = 1.0
TARGET_NATIVE_SIZE = 8000
LANDSCAPE_SIZE = 4033
NODATA = -9999.0
EXPECTED_TILE_COUNT = 89
EXPECTED_SOURCE_PIXEL_DEG = 0.00001


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def input_root() -> Path:
    return (
        repository_root()
        / "ExternalAssets"
        / "Terrain"
        / "PassoGiau"
        / "MASE_PST_Lidar1x1"
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
            "The 4033-square Landscape raster is a cubic presentation resample "
            "of the MASE PST LiDAR DTM 1x1 after explicit EPSG:4326 -> "
            "EPSG:32632 metric reprojection. The UE grid never creates measured "
            "terrain detail beyond the source samples."
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


def validate_tile(src: rasterio.io.DatasetReader, tile: Path) -> None:
    if src.width != 1000 or src.height != 1000:
        raise ValueError(
            f"{tile.name}: expected 1000x1000, got {src.width}x{src.height}"
        )
    if src.crs is None or src.crs.to_epsg() != 4326:
        raise ValueError(f"{tile.name}: expected EPSG:4326, got {src.crs}")
    if abs(float(src.transform.a) - EXPECTED_SOURCE_PIXEL_DEG) > 1e-10:
        raise ValueError(
            f"{tile.name}: unexpected X pixel size {src.transform.a}"
        )
    if abs(abs(float(src.transform.e)) - EXPECTED_SOURCE_PIXEL_DEG) > 1e-10:
        raise ValueError(
            f"{tile.name}: unexpected Y pixel size {src.transform.e}"
        )
    if src.nodata is None or abs(float(src.nodata) - NODATA) > 1e-6:
        raise ValueError(f"{tile.name}: expected NoData={NODATA}, got {src.nodata}")


def main() -> int:
    root = input_root()
    tiles = sorted(
        list((root / "tiles").glob("*.tif"))
        + list((root / "tiles").glob("*.tiff"))
    )
    if len(tiles) != EXPECTED_TILE_COUNT:
        print(
            f"[error] expected {EXPECTED_TILE_COUNT} MASE GeoTIFF tiles, "
            f"found {len(tiles)} under {root / 'tiles'}",
            file=sys.stderr,
        )
        return 2

    report_path = root / "mase-pst-download-report.json"
    if not report_path.is_file():
        print(f"[error] missing download report: {report_path}", file=sys.stderr)
        return 2
    download_report = json.loads(report_path.read_text(encoding="utf-8"))

    datasets: list[rasterio.io.DatasetReader] = []
    try:
        for tile in tiles:
            src = rasterio.open(tile)
            validate_tile(src, tile)
            datasets.append(src)

        source_bounds = transform_bounds(
            TARGET_CRS,
            SOURCE_CRS,
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
        source_mask = np.isfinite(source) & (source != NODATA)
        if not np.any(source_mask):
            raise ValueError("merged MASE mosaic contains no valid elevation samples")

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
                f"reprojected 8 km AOI has {missing} missing 1 m samples; "
                "MASE release tile coverage is incomplete"
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
        print(f"[error] MASE terrain preparation failed: {exc}", file=sys.stderr)
        return 3
    finally:
        for src in datasets:
            src.close()

    out = output_root()
    out.mkdir(parents=True, exist_ok=True)

    native_tif = out / "passo_giau_mase_pst_1m_8km_epsg32632.tif"
    native_hillshade = out / "passo_giau_mase_pst_2m_preview_hillshade.png"
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

    encoded = encode_u16(landscape, elevation_min, elevation_max)
    Image.fromarray(encoded, mode="I;16").save(landscape_png)
    landscape_r16.write_bytes(
        encoded.astype("<u2", copy=False).tobytes(order="C")
    )

    native_diag_stride = 4
    native_diag = native[::native_diag_stride, ::native_diag_stride]

    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "Ministero dell'Ambiente e della Sicurezza Energetica (MASE)",
        "dataset": "PST LiDAR DTM grigliato 1x1",
        "license": download_report.get("license", "CC BY 4.0"),
        "release_tag": download_report.get("release_tag"),
        "source_archive": download_report.get("archive"),
        "source_crs": SOURCE_CRS,
        "source_pixel_size_degrees": EXPECTED_SOURCE_PIXEL_DEG,
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
            "degrees_are_not_meters": True,
        },
    }
    terrain_report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("Passo Giau MASE PST LiDAR DTM 1x1 terrain preparation")
    print(f"  tiles:         {len(tiles)}")
    print(f"  native grid:   {TARGET_NATIVE_SIZE} x {TARGET_NATIVE_SIZE} @ 1 m")
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

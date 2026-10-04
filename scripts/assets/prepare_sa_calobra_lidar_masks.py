"""Stream retained NPC03 LAZ into native-grid evidence; frozen ground is read-only."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize_sa_calobra_context import sha256
from verify_normalized_context import verify

ROOT = Path(__file__).resolve().parents[2]
NODATA = -32767.0
GROUPS = ((2,), (3,), (4,), (5,), (6, 71, 72, 73, 74))


def grid_indices(x, y, grid):
    left, top = grid["transform"][2], grid["transform"][5]
    step = grid["pixel_size_m"]
    right, bottom = left + grid["width"] * step, top - grid["height"] * step
    valid = (
        np.isfinite(x)
        & np.isfinite(y)
        & (x >= left)
        & (x < right)
        & (y > bottom)
        & (y <= top)
    )
    cols = np.floor((x[valid] - left) / step).astype(np.int64)
    rows = np.floor((top - y[valid]) / step).astype(np.int64)
    return valid, rows * grid["width"] + cols


def return_fraction(vegetation, first):
    result = np.full(first.shape, NODATA, dtype=np.float32)
    np.divide(vegetation, first, out=result, where=first > 0)
    return result


def block_return_fraction(vegetation, first, shape, block_size=10):
    """Aggregate counts over 5 m support; retain exact native grid and edge clipping."""
    rows = np.arange(0, shape[0], block_size)
    cols = np.arange(0, shape[1], block_size)

    def aggregate(values):
        return np.add.reduceat(
            np.add.reduceat(values.reshape(shape).astype(np.uint64), rows, axis=0),
            cols,
            axis=1,
        )

    fraction = return_fraction(aggregate(vegetation), aggregate(first))
    return np.repeat(np.repeat(fraction, block_size, axis=0), block_size, axis=1)[
        : shape[0], : shape[1]
    ].ravel()


def prepare(manifest_path, cache, output, chunk_size=1_000_000):
    if output.exists():
        raise FileExistsError("Preserve existing masks; select a new output directory")
    import laspy

    checked = verify(manifest_path)
    source = json.loads(manifest_path.read_text(encoding="utf-8"))
    grid = source["grid"]
    if (grid["crs"], grid["width"], grid["height"], grid["transform"]) != (
        "EPSG:25831",
        4033,
        4033,
        [0.5, 0.0, 483000.0, 0.0, -0.5, 4409516.5],
    ):
        raise ValueError("Unadmitted frozen grid")
    if chunk_size < 1:
        raise ValueError("Chunk size must be positive")
    catalog = json.loads(
        (ROOT / "tools/julka/data/catalog.json").read_text(encoding="utf-8")
    )
    inputs = sorted(
        (a for a in catalog["assets"] if a["path"].endswith(".laz")),
        key=lambda a: a["path"],
    )
    if len(inputs) != 9:
        raise ValueError("Expected nine pinned NPC03 inputs")
    headers = []
    paths = []
    for asset in inputs:
        relative = Path(asset["path"])
        if relative.parts[0] != "sa-calobra-working-v1" or ".." in relative.parts:
            raise ValueError("Unsafe source path")
        path = cache.joinpath(*relative.parts[1:])
        if (
            path.stat().st_size != asset["size_bytes"]
            or sha256(path) != asset["sha256"]
        ):
            raise ValueError("LAZ identity mismatch: " + path.name)
        with laspy.open(path) as reader:
            h = reader.header
            crs = h.parse_crs()
            if (
                crs is None
                or crs.to_epsg() != 25831
                or h.point_format.id != 8
                or str(h.version) != "1.4"
            ):
                raise ValueError("Unadmitted LAZ CRS/format/version: " + path.name)
            if not all(np.isfinite(h.mins)) or not all(np.isfinite(h.maxs)):
                raise ValueError("Invalid LAZ bounds")
            headers.append(
                {
                    "file": path.name,
                    "points": h.point_count,
                    "crs": crs.to_string(),
                    "version": str(h.version),
                    "point_format": h.point_format.id,
                    "bounds": [h.mins.tolist(), h.maxs.tolist()],
                    "scales": h.scales.tolist(),
                    "offsets": h.offsets.tolist(),
                    "vertical": "Horizontal CRS only in inspected header; provider orthometric convention inherited, not independently remeasured",
                }
            )
        paths.append(path)
    with rasterio.open(manifest_path.parent / "elevation.tif") as ds:
        ground = ds.read(1).ravel()
        profile = ds.profile
    with rasterio.open(manifest_path.parent / "roughness.tif") as ds:
        relief = ds.read(1).ravel()
    cells = grid["width"] * grid["height"]
    counts = np.zeros((6, cells), dtype=np.uint32)
    first = np.zeros(cells, dtype=np.uint32)
    vegetation_first = np.zeros(cells, dtype=np.uint32)
    height = np.full(cells, -np.inf, dtype=np.float32)
    quality = np.zeros(cells, dtype=np.uint8)
    quality[relief > 10] |= 2
    histogram = np.zeros(256, dtype=np.uint64)
    tile_stats = []
    ground_residual_counts = np.zeros(7, dtype=np.uint64)
    # Histogram is a measurement diagnostic, never a vertical correction.
    residual_edges = np.array([-np.inf, -10, -1, -0.25, 0.25, 1, 10, np.inf])
    for path, header in zip(paths, headers):
        read_count, kept_count, rejected_count = 0, 0, 0
        tile_histogram = np.zeros(256, dtype=np.uint64)
        with laspy.open(path) as reader:
            for points in reader.chunk_iterator(chunk_size):
                read_count += len(points)
                x, y, z = (
                    np.asarray(points.x),
                    np.asarray(points.y),
                    np.asarray(points.z),
                )
                valid, indices = grid_indices(x, y, grid)
                cls = np.asarray(points.classification)[valid]
                z = z[valid]
                tile_histogram += np.bincount(cls, minlength=256).astype(np.uint64)
                accepted = (
                    ~np.asarray(points.withheld, dtype=bool)[valid]
                    & ~np.asarray(points.synthetic, dtype=bool)[valid]
                    & ~np.asarray(points.overlap, dtype=bool)[valid]
                    & ~np.isin(cls, [7, 12, 18])
                )
                rejected_count += int((~accepted).sum())
                indices, cls, z = indices[accepted], cls[accepted], z[accepted]
                returns = np.asarray(points.return_number)[valid][accepted]
                kept_count += len(indices)
                histogram += np.bincount(cls, minlength=256).astype(np.uint64)
                grouped = np.zeros(len(cls), dtype=bool)
                for i, group in enumerate(GROUPS):
                    matched = np.isin(cls, group)
                    np.add.at(counts[i], indices[matched], 1)
                    grouped |= matched
                np.add.at(counts[5], indices[~grouped], 1)
                is_first = returns == 1
                is_vegetation = np.isin(cls, [3, 4, 5])
                np.add.at(first, indices[is_first], 1)
                np.add.at(vegetation_first, indices[is_first & is_vegetation], 1)
                veg_indices = indices[is_vegetation]
                above_ground = z[is_vegetation] - ground[veg_indices]
                usable = (
                    np.isfinite(above_ground)
                    & (ground[veg_indices] != NODATA)
                    & (above_ground >= 0)
                )
                np.bitwise_or.at(quality, veg_indices[~usable], 1)
                np.maximum.at(
                    height, veg_indices[usable], above_ground[usable].astype(np.float32)
                )
                ground_points = cls == 2
                residuals = z[ground_points] - ground[indices[ground_points]]
                ground_residual_counts += np.histogram(residuals, bins=residual_edges)[
                    0
                ].astype(np.uint64)
        if read_count != header["points"]:
            raise ValueError("Partial LAZ decode: " + path.name)
        tile_stats.append(
            {
                "file": path.name,
                "decoded": read_count,
                "accepted_aoi": kept_count,
                "excluded_aoi_flags_noise": rejected_count,
                "aoi_raw_class_histogram": {
                    str(i): int(v) for i, v in enumerate(tile_histogram) if v
                },
            }
        )
        print(json.dumps(tile_stats[-1]), flush=True)
    total = counts.sum(axis=0, dtype=np.uint64)
    if not np.any(counts[0]) or not np.any(counts[1:4]):
        raise ValueError("No ground/vegetation evidence in complete decode")
    occupancy = np.zeros(cells, dtype=np.uint8)
    for i in range(6):
        occupancy[counts[i] > 0] |= 1 << i
    occupancy[total == 0] = 255
    # No return, no vegetation, or invalid normalization is unknown, not zero height.
    height[~np.isfinite(height) | ((quality & 1) != 0)] = NODATA
    density = return_fraction(vegetation_first, first)
    block_density = block_return_fraction(
        vegetation_first, first, (grid["height"], grid["width"])
    )
    output.mkdir(parents=True)
    products = []
    for name, values, nodata, meaning in [
        (
            "class-counts.tif",
            counts,
            4294967295,
            "bands: ground, low/medium/high vegetation, building/roof/facade, other; accepted return counts; zero is not absence proof",
        ),
        (
            "class-occupancy.tif",
            occupancy,
            255,
            "bits 1 ground,2 low,4 medium,8 high,16 building,32 other;255 no accepted samples",
        ),
        (
            "first-return-count.tif",
            first,
            4294967295,
            "accepted first-return sample count; zero=no observations",
        ),
        (
            "vegetation-first-return-count.tif",
            vegetation_first,
            4294967295,
            "first returns in source vegetation classes 3/4/5",
        ),
        (
            "canopy-height-candidate.tif",
            height,
            NODATA,
            "maximum accepted vegetation Z minus nearest native DTM pixel; not tree positions; no gap filling; suspect negatives unknown",
        ),
        (
            "vegetation-return-fraction.tif",
            density,
            NODATA,
            "vegetation first returns / accepted first returns; sampling proxy, not crown-area density or planting density",
        ),
        (
            "vegetation-return-fraction-5m.tif",
            block_density,
            NODATA,
            "count-weighted first-return fraction over native 10x10 cells (5m support); repeated on native grid; clipped last 3-cell edge; not 0.5m density accuracy or planting density",
        ),
        (
            "height-review-flags.tif",
            quality,
            255,
            "bit1 invalid/negative vegetation normalization;bit2 native relief>10m review only;no automatic rock class",
        ),
    ]:
        layers = values.reshape((-1, grid["height"], grid["width"]))
        path = output / name
        with rasterio.open(
            path,
            "w",
            **{
                **profile,
                "dtype": str(values.dtype),
                "count": layers.shape[0],
                "nodata": nodata,
                "compress": "DEFLATE",
            },
        ) as ds:
            ds.write(layers)
        products.append(
            {
                "path": name,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
                "logical_sha256": hashlib.sha256(layers.tobytes()).hexdigest(),
                "bands": layers.shape[0],
                "dtype": str(values.dtype),
                "nodata": nodata,
                "semantics": meaning,
            }
        )
    # Separate prepared image for the existing registered world-space overlay path.
    colors = np.full((cells, 3), 150, dtype=np.uint8)
    colors[counts[0] > 0] = [174, 148, 111]
    colors[counts[1] > 0] = [170, 220, 90]
    colors[counts[2] > 0] = [65, 175, 75]
    colors[counts[3] > 0] = [15, 95, 45]
    colors[counts[4] > 0] = [0, 230, 255]
    Image.fromarray(colors.reshape((grid["height"], grid["width"], 3))).save(
        output / "lidar-class-context.png"
    )
    image_path = output / "lidar-class-context.png"
    products.append(
        {
            "path": image_path.name,
            "size_bytes": image_path.stat().st_size,
            "sha256": sha256(image_path),
            "semantics": "class presence context; building>high>medium>low>ground priority;gray other/no samples;not planting eligibility",
        }
    )
    report = {
        "schema_version": 1,
        "status": "LIDAR_EVIDENCE_CANDIDATE",
        "geometry_mutation": False,
        "consumer_integration": False,
        "grid": grid,
        "normalized_fingerprint": checked["fingerprint"],
        "source_manifest_sha256": sha256(manifest_path),
        "inputs": [
            {"path": a["path"], "size_bytes": a["size_bytes"], "sha256": a["sha256"]}
            for a in inputs
        ],
        "headers": headers,
        "tiles": tile_stats,
        "class_histogram_accepted_aoi": {
            str(i): int(v) for i, v in enumerate(histogram) if v
        },
        "parameters": {
            "chunk_size": chunk_size,
            "aoi_boundary": "left/top inclusive;right/bottom exclusive",
            "ground_sampling": "nearest containing native pixel; no interpolation",
            "excluded": "withheld/synthetic/overlap flags; noise 7/18; overlap class12",
            "groups": GROUPS,
        },
        "versions": {
            p: importlib.metadata.version(p)
            for p in ["laspy", "lazrs", "numpy", "rasterio", "pyproj"]
        },
        "producer_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "counts": {
            "decoded_all_tiles": sum(h["points"] for h in headers),
            "accepted_aoi": int(total.sum()),
            "observed_cells": int((total > 0).sum()),
            "unobserved_cells": int((total == 0).sum()),
            "vegetation_cells": int((counts[1:4].sum(axis=0) > 0).sum()),
            "building_cells": int((counts[4] > 0).sum()),
            "canopy_height_valid_cells": int((height != NODATA).sum()),
            "invalid_height_review_cells": int(((quality & 1) != 0).sum()),
        },
        "ground_vs_dtm_residual_histogram": {
            "edges_m": ["-inf", -10, -1, -0.25, 0.25, 1, 10, "inf"],
            "counts": ground_residual_counts.tolist(),
            "interpretation": "read-only diagnostic; steep-cell sampling and datum disagreement unresolved, never used to move ground",
        },
        "outputs": products,
        "world_mapping": {
            "origin_epsg_m": [483000.25, 4409516.25],
            "uv": "(UE_XY_cm/50 + 0.5)/4033",
        },
        "confidence": "source-class evidence plus sample counts/normalization review; no calibrated per-pixel probability; no species or crown location inference",
        "planting": "BLOCKED: no admitted current cover, safety/road/BOB exclusions or production graph; fraction is not planting density",
        "blocked_layers": checked["blocked_layers"],
        "primary_sources": [
            "https://pnoa.ign.es/pnoa-lidar/procesamiento-de-los-datos",
            "https://pnoa.ign.es/resources/archivos/EspTec/Definicion_Clases_241004-LID3-SPC-LID-00122-IGN_Ed_2.0_NP.pdf",
            "https://laspy.readthedocs.io/en/latest/basic.html",
        ],
        "attribution": "Obra derivada de LiDAR-PNOA-cob3 2022-2025 CC-BY 4.0 scne.es",
    }
    report["fingerprint"] = hashlib.sha256(
        json.dumps(
            report, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    (output / "lidar-manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalized-manifest", required=True, type=Path)
    parser.add_argument("--cache-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = prepare(args.normalized_manifest, args.cache_root, args.output)
        print(json.dumps({"status": result["status"], "counts": result["counts"]}))
    except Exception as exc:
        if isinstance(exc, FileExistsError):
            raise
        if not args.output.exists():
            args.output.mkdir(parents=True)
        failure = args.output / "failure-receipt.json"
        if not failure.exists():
            failure.write_text(
                json.dumps(
                    {
                        "status": "FAIL",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        raise

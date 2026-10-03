#!/usr/bin/env python3
"""Build the bounded Sa Calobra MDT50cm terrain benchmark.

The 17 official CNIG/IGN COG tiles are intentionally cached under the ignored
``ExternalAssets/`` tree.  This script verifies their exact bytes, mosaics only
the requested 8 km x 8 km area and writes a GeoTIFF plus a provenance report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pyproj
import rasterio
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.merge import merge


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIR = (
    REPOSITORY_ROOT / "ExternalAssets" / "Terrain" / "SaCalobra" / "CNIG_MDT50CM" / "source"
)
DEFAULT_OUTPUT_DIR = (
    REPOSITORY_ROOT / "worldgen" / "terrain" / "benchmarks" / "sa_calobra"
)
OUTPUT_NAME = "sa_calobra_8x8km_mdt50cm_epsg25831.tif"
REPORT_NAME = "sa_calobra_8x8km_mdt50cm_epsg25831.json"

PRODUCT_URL = "https://centrodedescargas.cnig.es/CentroDescargas/modelo-digital-terreno-mdt50cm"
LICENSE_URL = "https://www.scne.es/"
ATTRIBUTION = "Obra derivada de MDT50cm-cob3 2022-2025 CC-BY 4.0 scne.es"

EXPECTED_INPUTS = (
    ("MDT50CM-ETRS89-H31-0643-7-8-COB3-V1.tif", 37499279, "76551315e06902fe9902148049cd411f9bc97614f43b8cdc06378429dfb53acc"),
    ("MDT50CM-ETRS89-H31-0643-8-7-COB3-V1.tif", 25586926, "fc746a8792ca7b1ca31eaf29235670b1a1932df22bb71f03be6dfe1f0c0c29cc"),
    ("MDT50CM-ETRS89-H31-0643-8-8-COB3-V1.tif", 114852248, "5c5bdf7b005070ab9866df2d1dd564629bfb600506ea49d74daa0ac4608bc105"),
    ("MDT50CM-ETRS89-H31-0644-1-6-COB3-V1.tif", 2068529, "cc965d0cc2ac487e5f7d6b152cbb35c616bf8be5e1294f0127873699763b0c9e"),
    ("MDT50CM-ETRS89-H31-0644-1-7-COB3-V1.tif", 71681708, "fa885bd6ff052f8419cd6512933bbd9e2730f308a4b96ec7ba4a7493bf731136"),
    ("MDT50CM-ETRS89-H31-0644-1-8-COB3-V1.tif", 117496115, "aac08bad7d10938a9789cb59f0a7f2ec196984f1f1a534bc55539e142607fe3a"),
    ("MDT50CM-ETRS89-H31-0644-2-6-COB3-V1.tif", 56839976, "70cce352e7158988b498606359a32408fdc9f6fb665e3d64c5b8f5b0ca20e2e5"),
    ("MDT50CM-ETRS89-H31-0644-2-7-COB3-V1.tif", 115320376, "ffaaca25b3463ef9a813c7865b418b56e1e7534381447b1e554bcfed66820e7d"),
    ("MDT50CM-ETRS89-H31-0644-2-8-COB3-V1.tif", 103568495, "52f8cf6f38a0a91aa33b7d20fdcb0c8bc15b65162bc49099276b8912f7f47d2e"),
    ("MDT50CM-ETRS89-H31-0670-7-1-COB3-V1.tif", 110225444, "5b12b247f159b8c109693455640fcb44a393e5475caea7269e1cad745048917f"),
    ("MDT50CM-ETRS89-H31-0670-7-2-COB3-V1.tif", 112302996, "00447e5681cbe7d59833baf4a65fc900a3bd294687debfc8bc30ec9f5653ad4b"),
    ("MDT50CM-ETRS89-H31-0670-8-1-COB3-V1.tif", 114913540, "e4f8d3cfd4c3af3bd5d88a0934325de3316e387e2ee8b71fb6ed6c8a704a0d57"),
    ("MDT50CM-ETRS89-H31-0670-8-2-COB3-V1.tif", 115047131, "211e4e18ae6b6a60f24f6d922b605e4d72ca15be5f32c9c174226992ebe22528"),
    ("MDT50CM-ETRS89-H31-0671-1-1-COB3-V1.tif", 112026604, "6b10f6fac934139712848474d2b06d6c1556acc46a5504406871a754028846b0"),
    ("MDT50CM-ETRS89-H31-0671-1-2-COB3-V1.tif", 110724573, "ff463c7b6d4b77330690fab18f6cdff894cdcd4ab3ee6fe49deef98dd33b316e"),
    ("MDT50CM-ETRS89-H31-0671-2-1-COB3-V1.tif", 105141698, "db80d05275630e0646584a57f30c0d0f141a4778c7ae1151b369034c0a2ee413"),
    ("MDT50CM-ETRS89-H31-0671-2-2-COB3-V1.tif", 114019379, "15c952d11d7a508ee7549876df844cc29261a716e66e1315615a5c1d29835849"),
)

# Official IGN named-place coordinates in ETRS89 geographic coordinates.
BENCHMARK_POINTS = {
    "Port de sa Calobra": (2.799688121, 39.850378170),
    "Coll de Cal Reis": (2.81811561100005, 39.8275145580001),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--force", action="store_true", help="Replace an existing output pair.")
    return parser.parse_args()


def validate_inputs(source_dir: Path) -> tuple[list[Path], list[dict[str, object]]]:
    paths: list[Path] = []
    records: list[dict[str, object]] = []
    for name, expected_size, expected_sha256 in EXPECTED_INPUTS:
        path = source_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"Missing CNIG tile: {path}")
        actual_size = path.stat().st_size
        actual_sha256 = sha256(path)
        if actual_size != expected_size or actual_sha256 != expected_sha256:
            raise ValueError(
                f"CNIG tile verification failed for {name}: "
                f"size={actual_size}, sha256={actual_sha256}"
            )
        paths.append(path)
        records.append({"name": name, "size_bytes": actual_size, "sha256": actual_sha256})
    return paths, records


def output_statistics(dataset: rasterio.io.DatasetReader) -> dict[str, float | int]:
    valid_count = 0
    value_sum = 0.0
    minimum = float("inf")
    maximum = float("-inf")
    for _, window in dataset.block_windows(1):
        band = dataset.read(1, window=window, masked=True)
        values = band.compressed()
        if not values.size:
            continue
        valid_count += int(values.size)
        value_sum += float(values.sum(dtype=np.float64))
        minimum = min(minimum, float(values.min()))
        maximum = max(maximum, float(values.max()))
    total_count = dataset.width * dataset.height
    return {
        "valid_pixel_count": valid_count,
        "valid_percent": (valid_count / total_count) * 100.0,
        "elevation_min_m": minimum,
        "elevation_max_m": maximum,
        "elevation_mean_m": value_sum / valid_count,
    }


def main() -> None:
    args = parse_args()
    source_dir = args.source_dir.resolve()
    output_dir = args.output_dir.resolve()
    output = output_dir / OUTPUT_NAME
    report = output_dir / REPORT_NAME
    if not args.force and (output.exists() or report.exists()):
        raise FileExistsError("Output exists; pass --force to replace the output pair.")

    paths, input_records = validate_inputs(source_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    transformer = Transformer.from_crs("EPSG:4258", "EPSG:25831", always_xy=True)
    projected_points = {
        name: transformer.transform(longitude, latitude)
        for name, (longitude, latitude) in BENCHMARK_POINTS.items()
    }
    points = list(projected_points.values())
    center_x = round(((points[0][0] + points[1][0]) / 2.0) * 2.0) / 2.0
    center_y = round(((points[0][1] + points[1][1]) / 2.0) * 2.0) / 2.0
    bounds = (center_x - 4000.0, center_y - 4000.0, center_x + 4000.0, center_y + 4000.0)

    sources = [rasterio.open(path) for path in paths]
    try:
        for source in sources:
            # CNIG declares EPSG:3043 (formal N-E axes), while GeoTIFF transforms
            # use x=easting/y=northing and are numerically equivalent to EPSG:25831.
            if source.crs is None or source.crs.to_epsg() not in (3043, 25831):
                raise ValueError(f"Unexpected CRS in {source.name}: {source.crs}")
            if tuple(round(value, 6) for value in source.res) != (0.5, 0.5):
                raise ValueError(f"Unexpected resolution in {source.name}: {source.res}")

        dtype = sources[0].dtypes[0]
        nodata = sources[0].nodata
        merge(
            sources,
            bounds=bounds,
            res=(0.5, 0.5),
            nodata=nodata,
            dtype=dtype,
            method="first",
            target_aligned_pixels=True,
            mem_limit=512,
            dst_path=output,
            dst_kwds={
                "driver": "GTiff",
                "compress": "ZSTD",
                "zstd_level": 9,
                "predictor": 3 if dtype.startswith("float") else 2,
                "tiled": True,
                "blockxsize": 512,
                "blockysize": 512,
                "bigtiff": "YES",
                "num_threads": "ALL_CPUS",
                "sparse_ok": True,
            },
        )
    finally:
        for source in sources:
            source.close()

    with rasterio.open(output, "r+") as dataset:
        dataset.crs = CRS.from_epsg(25831)
        dataset.update_tags(
            AREA="Sa Calobra and Coll de Cal Reis, Mallorca",
            ATTRIBUTION=ATTRIBUTION,
            LICENSE="CNIG general-use license compatible with CC BY 4.0",
            SOURCE="CNIG/IGN PNOA-LiDAR third coverage, MDT50cm v1",
        )

    with rasterio.open(output) as dataset:
        if dataset.width != 16000 or dataset.height != 16000:
            raise ValueError(f"Unexpected output dimensions: {dataset.width} x {dataset.height}")
        point_samples = {
            name: float(value[0])
            for name, value in zip(projected_points, dataset.sample(projected_points.values()))
        }
        output_record = {
            "width": dataset.width,
            "height": dataset.height,
            "count": dataset.count,
            "dtype": dataset.dtypes[0],
            "crs": str(dataset.crs),
            "resolution_m": list(dataset.res),
            "bounds_epsg25831": list(dataset.bounds),
            "nodata": dataset.nodata,
            "compression": dataset.compression.name if dataset.compression else None,
            "statistics": output_statistics(dataset),
            "benchmark_elevations_m": point_samples,
        }

    metadata = {
        "schema_version": 1,
        "file": output.name,
        "sha256": sha256(output),
        "size_bytes": output.stat().st_size,
        "area": "Sa Calobra and Coll de Cal Reis, Mallorca",
        "output": output_record,
        "center_epsg25831": [center_x, center_y],
        "benchmark_points_epsg4258": {name: list(value) for name, value in BENCHMARK_POINTS.items()},
        "inputs": input_records,
        "source": {
            "provider": "CNIG/IGN",
            "product": "MDT50 cm - 3rd coverage (2022-2025), v1",
            "product_url": PRODUCT_URL,
            "retrieved_utc_date": "2026-10-01",
            "source_crs": "EPSG:3043 (ETRS89 / UTM zone 31N, formal N-E axes)",
        },
        "license": {
            "name": "CNIG general-use license compatible with CC BY 4.0",
            "url": LICENSE_URL,
            "attribution": ATTRIBUTION,
        },
        "tools": {
            "rasterio": rasterio.__version__,
            "gdal": rasterio.__gdal_version__,
            "pyproj": pyproj.__version__,
        },
    }
    report.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()

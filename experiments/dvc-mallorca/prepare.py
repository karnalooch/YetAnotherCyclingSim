#!/usr/bin/env python3
"""Prepare the bounded Mallorca MDT05 sample deterministically.

This module is intentionally isolated from YACS production world generation.
It converts one experimental GeoTIFF into a square little-endian float32
heightfield and a deterministic provenance/fingerprint report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import Resampling

SUPPORTED_RESAMPLING = {
    "bilinear": Resampling.bilinear,
    "nearest": Resampling.nearest,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_source_metadata(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("source metadata must use schema_version 1")
    expected = payload.get("expected_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError("source metadata requires a 64-character expected_sha256")
    return payload


def canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def prepare_heightfield(
    *,
    source: Path,
    source_metadata_path: Path,
    output: Path,
    report_path: Path,
    size: int,
    resampling_name: str,
    producer_version: int,
) -> dict[str, Any]:
    if size < 2 or size > 4097:
        raise ValueError("size must be inside 2..4097")
    if resampling_name not in SUPPORTED_RESAMPLING:
        raise ValueError(
            f"unsupported resampling {resampling_name!r}; "
            f"choose from {sorted(SUPPORTED_RESAMPLING)}"
        )
    if producer_version < 1:
        raise ValueError("producer_version must be positive")
    if not source.is_file():
        raise ValueError(f"source GeoTIFF not found: {source}")

    metadata = load_source_metadata(source_metadata_path)
    source_sha256 = sha256_file(source)
    if source_sha256 != metadata["expected_sha256"]:
        raise ValueError(
            "source SHA-256 mismatch: "
            f"expected {metadata['expected_sha256']}, got {source_sha256}"
        )

    resampling = SUPPORTED_RESAMPLING[resampling_name]
    with rasterio.open(source) as dataset:
        if dataset.count != 1:
            raise ValueError(f"expected one elevation band, found {dataset.count}")
        source_grid = dataset.read(1, masked=True)
        valid = source_grid.compressed()
        valid = valid[np.isfinite(valid)]
        if valid.size == 0:
            raise ValueError("source contains no finite elevation samples")

        prepared = dataset.read(
            1,
            out_shape=(size, size),
            masked=True,
            resampling=resampling,
        )
        fill_value = float(np.median(valid))
        prepared_array = np.ma.filled(prepared, fill_value=fill_value).astype(
            "<f4",
            copy=False,
        )
        prepared_array[~np.isfinite(prepared_array)] = fill_value

        source_description = {
            "sha256": source_sha256,
            "size_bytes": source.stat().st_size,
            "driver": dataset.driver,
            "dtype": str(dataset.dtypes[0]),
            "crs": str(dataset.crs),
            "width_px": dataset.width,
            "height_px": dataset.height,
            "bounds": [round(float(value), 9) for value in dataset.bounds],
            "nodata": dataset.nodata,
            "valid_sample_count": int(valid.size),
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(prepared_array.tobytes(order="C"))
    output_sha256 = sha256_file(output)

    fingerprint_inputs = {
        "producer": "yacs-dvc-mallorca-prepare",
        "producer_version": producer_version,
        "source_sha256": source_sha256,
        "size": size,
        "resampling": resampling_name,
        "output_format": "float32-little-endian-row-major",
    }
    report = {
        "schema_version": 1,
        "source_id": metadata["id"],
        "source": source_description,
        "preparation": fingerprint_inputs,
        "artifact_fingerprint_sha256": canonical_hash(fingerprint_inputs),
        "elevation_m": {
            "minimum": round(float(prepared_array.min()), 6),
            "maximum": round(float(prepared_array.max()), 6),
            "mean": round(float(prepared_array.mean(dtype=np.float64)), 6),
        },
        "output": {
            "sha256": output_sha256,
            "size_bytes": output.stat().st_size,
        },
        "policy": {
            "experimental_only": True,
            "production_authority": False,
            "unreal_content": False,
        },
    }
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument(
        "--resampling",
        choices=sorted(SUPPORTED_RESAMPLING),
        required=True,
    )
    parser.add_argument("--producer-version", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = prepare_heightfield(
        source=args.source,
        source_metadata_path=args.source_metadata,
        output=args.output,
        report_path=args.report,
        size=args.size,
        resampling_name=args.resampling,
        producer_version=args.producer_version,
    )
    print("Mallorca MDT05 preparation: PASS")
    print(f"source sha256: {report['source']['sha256']}")
    print(f"artifact fingerprint: {report['artifact_fingerprint_sha256']}")
    print(f"output sha256: {report['output']['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

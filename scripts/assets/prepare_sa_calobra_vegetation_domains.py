"""Separate source vegetation presence from height review on the frozen grid."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio

try:
    from .verify_sa_calobra_lidar_masks import digest, verify
except ImportError:
    from verify_sa_calobra_lidar_masks import digest, verify


def domains(counts, quality):
    """Keep overlapping classes and unknown samples; never infer shrub species."""
    observed = counts.sum(axis=0, dtype=np.uint64) > 0
    presence = (counts[1:4] > 0).astype(np.uint8)
    presence[:, ~observed] = 255
    flags = (quality & 3).astype(np.uint8)
    flags[counts[4] > 0] |= 4
    flags[~observed] = 255
    pink = observed & ((quality & 1) != 0)
    low, medium, high = counts[1:4] > 0

    def count(mask):
        return int(np.count_nonzero(mask))

    audit = {
        "observed_cells": count(observed),
        "unknown_cells": count(~observed),
        "low_presence_cells": count(low),
        "medium_presence_cells": count(medium),
        "high_presence_cells": count(high),
        "height_review_cells": count(pink),
        "height_review_low_overlap": count(pink & low),
        "height_review_medium_overlap": count(pink & medium),
        "height_review_high_overlap": count(pink & high),
        "height_review_partition": {
            "with_high": count(pink & high),
            "low_or_medium_without_high": count(pink & (low | medium) & ~high),
            "without_vegetation_class": count(pink & ~(low | medium | high)),
        },
        "height_review_building_overlap": count(pink & (counts[4] > 0)),
        "height_review_relief_overlap": count(pink & ((quality & 2) != 0)),
    }
    return presence, flags, audit


def prepare(source_manifest, output):
    if output.exists():
        raise FileExistsError("Preserve existing domains; select a new directory")
    checked = verify(source_manifest)
    source = json.loads(source_manifest.read_text(encoding="utf-8"))
    with rasterio.open(source_manifest.parent / "class-counts.tif") as ds:
        counts, profile = ds.read(), ds.profile
    with rasterio.open(source_manifest.parent / "height-review-flags.tif") as ds:
        quality = ds.read(1)
    presence, flags, audit = domains(counts, quality)
    output.mkdir(parents=True)
    products = []
    for name, values, descriptions in [
        (
            "vegetation-presence.tif",
            presence,
            ["low_source_class_3", "medium_source_class_4", "high_source_class_5"],
        ),
        (
            "vegetation-review-flags.tif",
            flags[np.newaxis],
            ["bit1_height_review_bit2_relief_review_bit4_source_building_overlap"],
        ),
    ]:
        path = output / name
        with rasterio.open(
            path,
            "w",
            **{**profile, "count": len(values), "dtype": "uint8", "nodata": 255},
        ) as ds:
            ds.write(values)
            for band, description in enumerate(descriptions, 1):
                ds.set_band_description(band, description)
        # Independent persisted read: every grid field and cell must survive writing.
        with rasterio.open(path) as ds:
            if (
                ds.transform != profile["transform"]
                or ds.crs != profile["crs"]
                or ds.nodata != 255
                or ds.dtypes != ("uint8",) * len(values)
                or not np.array_equal(ds.read(), values)
            ):
                raise ValueError("Domain readback mismatch: " + name)
        products.append(
            {
                "path": name,
                "size_bytes": path.stat().st_size,
                "sha256": digest(path),
                "logical_sha256": hashlib.sha256(values.tobytes()).hexdigest(),
                "bands": descriptions,
                "nodata": 255,
            }
        )
    report = {
        "schema_version": 1,
        "status": "VEGETATION_DOMAIN_CANDIDATE",
        "geometry_mutation": False,
        "planting": "BLOCKED pending admitted current-cover and road/safety/BOB exclusions",
        "source_manifest_sha256": digest(source_manifest),
        "source_fingerprint": checked["fingerprint"],
        "grid": source["grid"],
        "producer_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "semantics": {
            "presence": "Three overlapping bands: 1=source class present; 0=no return of that class, not proven absence; 255=no accepted samples",
            "review_flags": "bit1 invalid/negative height; bit2 relief>10m; bit4 source building overlap; 255 unknown; not complete safety exclusions",
            "height": "Existing unknown heights remain unknown; class presence does not repair normalization",
            "character": "Low may represent grass/low shrubs; medium/high do not identify species or individual tree positions",
            "audit": "Overlap counts are not additive; height_review_partition is disjoint",
        },
        "counts": audit,
        "attribution": source["attribution"],
        "outputs": products,
    }
    report["fingerprint"] = hashlib.sha256(
        json.dumps(
            report, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    (output / "vegetation-manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lidar-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = prepare(args.lidar_manifest, args.output)
    print(json.dumps({"status": result["status"], "counts": result["counts"]}))

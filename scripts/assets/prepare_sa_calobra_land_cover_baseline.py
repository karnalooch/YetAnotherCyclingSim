"""Emit coarse historical cover weights; never infer current pixel geography."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_normalized_context import verify
from verify_sa_calobra_lidar_masks import digest

NODATA = -32767.0
GROUPS = {
    "forest": ("CONIFERAS", "FRONDOSAS_CADUCIFOLIAS", "FRONDOSAS_PERENNIFOLIAS"),
    "grass": ("PASTIZAL", "ALTA_MONTANA_PASTIZAL"),
    "shrub": ("MATORRAL",),
    "cropland": (
        "CULTIVO_HERBACEO_NO_ARROZ",
        "FRUTALES_CITRICOS",
        "FRUTALES_NO_CITRICOS",
        "OLIVAR",
        "OTROS_LENOSOS",
        "VINEDO",
        "HUERTA_FAMILIAR",
    ),
    "open_rock": ("AFLORA_ROCOSO_Y_ROQUEDO", "CANCHALES", "ACANTILADOS_MARINOS"),
    "bare_ground": (
        "SUELO_DESNUDO",
        "ROTURADOS_SUELO_DESNUDO",
        "ZONA_EROSIONADA_DESNUDO",
    ),
}


def cover_lookup(features):
    """Areas are provider hectares in the full polygon, not clipped AOI areas."""
    ids = [f["properties"]["OBJECTID"] for f in features]
    if ids != sorted(set(ids)) or len(features) >= 65535:
        raise ValueError("Cover feature order differs from normalized index")
    lookup = np.full((len(GROUPS), len(features) + 1), NODATA, dtype=np.float32)
    for column, feature in enumerate(features, 1):
        p = feature["properties"]
        total = float(p["SUP_HA"])
        if not np.isfinite(total) or total <= 0:
            raise ValueError("Invalid provider polygon area")
        for band, keys in enumerate(GROUPS.values()):
            areas = [0.0 if p.get(k) is None else float(p[k]) for k in keys]
            if not np.isfinite(areas).all() or min(areas) < 0:
                raise ValueError("Invalid provider component area")
            fraction = sum(areas) / total
            # Provider hectare fields are rounded independently; tolerate 0.01%.
            if fraction > 1.0001:
                raise ValueError("Component area exceeds provider polygon")
            lookup[band, column] = min(fraction, 1.0)
    return lookup


def indexed_weights(index, lookup, band):
    if np.any((index != 65535) & (index >= lookup.shape[1])):
        raise ValueError("Unknown historical feature index")
    safe = np.where(index == 65535, 0, index)
    return lookup[band, safe]


def prepare(manifest_path, output):
    if output.exists():
        raise FileExistsError("Preserve previous mask baseline")
    verify(manifest_path)
    source = json.loads(manifest_path.read_text(encoding="utf8"))
    grid = source["grid"]
    if (grid["crs"], grid["width"], grid["height"], grid["transform"]) != (
        "EPSG:25831",
        4033,
        4033,
        [0.5, 0, 483000, 0, -0.5, 4409516.5],
    ):
        raise ValueError("Unadmitted frozen grid")
    features = json.loads(
        (manifest_path.parent / "siose_2014_aoi.json").read_text(encoding="utf8")
    )["features"]
    lookup = cover_lookup(features)
    with rasterio.open(manifest_path.parent / "siose_2014_feature_index.tif") as ds:
        index, profile = ds.read(1), ds.profile
    # Validate every index before emitting files.
    indexed_weights(index, lookup, 0)
    output.mkdir(parents=True)
    products = []
    for band, name in enumerate(GROUPS):
        values = indexed_weights(index, lookup, band)
        path = output / (name + "-historical-weight.tif")
        with rasterio.open(
            path,
            "w",
            **{
                **profile,
                "count": 1,
                "dtype": "float32",
                "nodata": NODATA,
                "compress": "DEFLATE",
            },
        ) as ds:
            ds.write(values, 1)
            ds.set_band_description(1, name + "_siose_2014_polygon_area_share")
        with rasterio.open(path) as ds:
            if (
                ds.transform != profile["transform"]
                or ds.crs != profile["crs"]
                or ds.nodata != NODATA
                or not np.array_equal(ds.read(1), values)
            ):
                raise ValueError("Cover mask readback mismatch")
        products.append(
            {
                "path": path.name,
                "sha256": digest(path),
                "size_bytes": path.stat().st_size,
                "logical_sha256": hashlib.sha256(values.tobytes()).hexdigest(),
                "positive_cells": int(np.count_nonzero(values > 0)),
                "unknown_cells": int(np.count_nonzero(values == NODATA)),
                "provider_fields": list(GROUPS[name]),
            }
        )
    report = {
        "schema_version": 1,
        "status": "HISTORICAL_COVER_BASELINE_CANDIDATE",
        "geometry_mutation": False,
        "hard_exclusions_modified": False,
        "current_cover_admitted": False,
        "human_visual_acceptance": "PENDING",
        "production_planting": "NOT_ADMITTED",
        "grid": grid,
        "source_manifest_sha256": digest(manifest_path),
        "producer_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "semantics": {
            "weights": "Provider component hectares / full provider polygon SUP_HA; uniform within the historical polygon; no subpolygon location or calibrated confidence",
            "zero": "No mapped historical component; not proven present-day absence",
            "unknown": "-32767 for missing/conflicting polygon index; no gap filling",
            "resolution": "Native 0.5m registration, source reference scale 1:25000; resampling does not improve thematic accuracy",
            "authority": "SIOSE 2014 (SPOT5 2014 / PNOA 2015) context only; never replaces current-cover evidence, LiDAR class presence or hard exclusions",
            "groups": "Explicit field groups are partial thematic context; unlisted components are not redistributed or normalized",
        },
        "primary_source": "https://ideib.caib.es/geoserveis/rest/services/public/GOIB_SIOSE14_IB/MapServer",
        "provenance": "Inherited pinned normalized source/license ledger; no new acquisition",
        "outputs": products,
    }
    report["fingerprint"] = hashlib.sha256(
        json.dumps(
            report, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    (output / "land-cover-manifest.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalized-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.normalized_manifest, args.output)
    print(json.dumps({"status": result["status"], "outputs": result["outputs"]}))

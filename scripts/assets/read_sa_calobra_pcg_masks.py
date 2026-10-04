"""Bounded mask-consumer read proof; does not spawn Unreal/PCGEx assets."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_sa_calobra_pcg_masks import verified_manifest


def evaluate(selectors, distances, x_cm, y_cm, band, radius_m, clearance_m):
    if (
        band not in (0, 1, 2)
        or not all(math.isfinite(v) for v in [x_cm, y_cm, radius_m, clearance_m])
        or radius_m <= 0
        or clearance_m < 0
    ):
        raise ValueError(
            "Explicit finite positive asset radius and nonnegative clearance required"
        )
    height, width = distances.shape
    col, row = math.floor(x_cm / 50 + 0.5), math.floor(y_cm / 50 + 0.5)
    if not (0 <= col < width and 0 <= row < height):
        return {"selected": False, "reason": "outside_aoi"}
    if (
        min(x_cm + 25, y_cm + 25, (width - 0.5) * 50 - x_cm, (height - 0.5) * 50 - y_cm)
        < radius_m * 100
    ):
        return {"selected": False, "reason": "asset_footprint_outside_aoi"}
    state = int(selectors[band, row, col])
    if state not in (0, 1, 255):
        raise ValueError("Unrecognized selector state")
    if state != 1:
        return {
            "selected": False,
            "reason": "unknown" if state == 255 else "not_selected",
        }
    distance = float(distances[row, col])
    if not math.isfinite(distance) or distance < 0:
        return {"selected": False, "reason": "unknown_clearance"}
    point_offset_m = math.hypot(x_cm - col * 50, y_cm - row * 50) / 100
    lower_bound = max(0, distance - point_offset_m)
    admitted = lower_bound >= radius_m + clearance_m
    return {
        "selected": admitted,
        "reason": "source_domain_and_clearance"
        if admitted
        else "insufficient_clearance",
        "clearance_lower_bound_m": lower_bound,
    }


def load(manifest_path):
    manifest = verified_manifest(manifest_path)
    if manifest["status"] != "READY_FOR_BOUNDED_MASK_CONSUMER_WITH_FALLBACKS":
        raise ValueError("Unsupported PCG candidate")
    with rasterio.open(manifest_path.parent / "vegetation-selectors.tif") as ds:
        selectors = ds.read()
    with rasterio.open(
        manifest_path.parent / "exclusion-distance-lower-bound.tif"
    ) as ds:
        distances = ds.read(1)
    if selectors.shape != (3, 4033, 4033) or distances.shape != (4033, 4033):
        raise ValueError("Unsupported PCG native grid")
    return manifest, selectors, distances


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    manifest, selectors, distances = load(args.manifest)
    results = []
    for band in range(3):
        candidates = np.argwhere((selectors[band] == 1) & (distances >= 2))
        if len(candidates) < 10:
            raise ValueError("Insufficient source-supported bounded consumer samples")
        for row, col in candidates[np.linspace(0, len(candidates) - 1, 20, dtype=int)]:
            sample = evaluate(
                selectors, distances, float(col * 50), float(row * 50), band, 0.5, 0.5
            )
            if sample["selected"]:
                results.append(
                    {
                        "band": band,
                        "world_xy_cm": [int(col * 50), int(row * 50)],
                        **sample,
                    }
                )
    if not all(any(r["band"] == band for r in results) for band in range(3)):
        raise ValueError("Consumer proof lacks one vegetation domain")
    print(
        json.dumps(
            {
                "status": "PASS_MASK_READ_ONLY",
                "fingerprint": manifest["fingerprint"],
                "example_radius_m": 0.5,
                "example_clearance_m": 0.5,
                "not_real_asset_admission": True,
                "samples": results,
            },
            indent=2,
        )
    )

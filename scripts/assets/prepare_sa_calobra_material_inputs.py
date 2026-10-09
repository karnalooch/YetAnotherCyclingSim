"""Prepare presentation-only 2B blend weights from pinned 2A fallback evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_sa_calobra_pcg_masks import verified_manifest  # noqa: E402
from verify_sa_calobra_lidar_masks import digest  # noqa: E402

GRID = ("EPSG:25831", 4033, 4033, [0.5, 0, 483000, 0, -0.5, 4409516.5])


def blend_weights(selectors, reasons, historical_rock, blend_radius=0):
    """Visual fallback amplitudes; never current-cover confidence or planting masks."""
    if selectors.shape != (3, *reasons.shape) or historical_rock.shape != reasons.shape:
        raise ValueError("Material input dimensions differ")
    if not np.isin(selectors, [0, 1, 255]).all():
        raise ValueError("Invalid selector states")
    if not np.isfinite(historical_rock).all() or np.any(
        (historical_rock != -32767) & ((historical_rock < 0) | (historical_rock > 1))
    ):
        raise ValueError("Invalid historical shares")
    observed = (
        np.all(selectors != 255, axis=0) & ((reasons & 128) == 0) & (reasons != 65535)
    )
    eligible = observed & (reasons == 0)
    forest = eligible & np.any(selectors[1:] == 1, axis=0)
    low = eligible & (selectors[0] == 1) & ~forest
    rock = np.where(
        eligible & ~forest & ~low & (historical_rock != -32767), historical_rock, 0
    )
    result = np.zeros((*reasons.shape, 4), dtype=np.uint8)
    result[..., 0] = low.astype(np.uint8) * 255
    result[..., 1] = forest.astype(np.uint8) * 255
    result[..., 2] = np.rint(rock * 255).astype(np.uint8)
    result[..., 3] = observed.astype(np.uint8) * 255
    if type(blend_radius) is not int or not 0 <= blend_radius <= 2:
        raise ValueError("Presentation blend radius exceeds the bounded 2-pixel limit")
    if blend_radius:
        # Filter only visual amplitudes. Reapply exact native-grid holdbacks after
        # filtering so unknown/excluded samples cannot acquire any surface class.
        softened = np.asarray(
            Image.fromarray(result[..., :3]).filter(ImageFilter.BoxBlur(blend_radius))
        ).copy()
        softened[~eligible] = 0
        totals = softened.astype(np.uint16).sum(axis=2)
        excess = np.maximum(totals, 255) - 255
        largest = np.argmax(softened, axis=2)
        for channel in range(3):
            plane = softened[..., channel]
            selected = largest == channel
            plane[selected] -= excess[selected].astype(np.uint8)
        result[..., :3] = softened
    return result


def prepare(pcg_path: Path, cover_path: Path, output: Path):
    if output.exists():
        raise FileExistsError("Preserve previous material inputs")
    pcg, cover = verified_manifest(pcg_path), verified_manifest(cover_path)
    for manifest in (pcg, cover):
        grid = manifest["grid"]
        if (grid["crs"], grid["width"], grid["height"], grid["transform"]) != GRID:
            raise ValueError("Material grid is not the frozen native grid")
    if (
        pcg["status"] != "READY_FOR_BOUNDED_MASK_CONSUMER_WITH_FALLBACKS"
        or cover["status"] != "HISTORICAL_COVER_BASELINE_CANDIDATE"
    ):
        raise ValueError("Unexpected material input admission")
    with rasterio.open(pcg_path.parent / "vegetation-selectors.tif") as ds:
        selectors = ds.read()
    with rasterio.open(pcg_path.parent / "exclusion-reasons.tif") as ds:
        reasons = ds.read(1)
    with rasterio.open(cover_path.parent / "open_rock-historical-weight.tif") as ds:
        rock = ds.read(1)
    values = blend_weights(selectors, reasons, rock, blend_radius=2)
    output.mkdir(parents=True)
    path = output / "material-weights.png"
    Image.fromarray(values).save(path)
    if not np.array_equal(np.asarray(Image.open(path)), values):
        raise ValueError("Packed material weights readback differs")
    report = {
        "schema_version": 1,
        "status": "PRESENTATION_FALLBACK_MATERIAL_INPUTS",
        "geometry_mutation": False,
        "current_cover_admitted": False,
        "production_planting": "NOT_ADMITTED",
        "grid": pcg["grid"],
        "world_mapping": pcg["world_mapping"],
        "sources": [
            {"path": str(p), "sha256": digest(p)} for p in (pcg_path, cover_path)
        ],
        "outputs": [
            {
                "path": path.name,
                "sha256": digest(path),
                "size_bytes": path.stat().st_size,
                "logical_sha256": hashlib.sha256(values.tobytes()).hexdigest(),
            }
        ],
        "semantics": {
            "R": "Low class presentation fallback; may be grass or shrubs; no species claim",
            "G": "Medium/high source class: forest-floor presentation fallback, not measured ground cover",
            "B": "Dated SIOSE polygon open-rock share, only without selected vegetation; no subpolygon classification",
            "A": "Accepted sample availability, not calibrated confidence; zero preserves unknown",
            "holdbacks": "All upstream hard exclusions suppress R/G/B before and after visual filtering; unknown samples remain zero; no source-mask mutation or gap filling",
            "presentation_filter": "Radius-2-pixel box filter (2.5 m window) of presentation amplitudes only, followed by exact native-grid holdback; not cover classification or planting authority",
            "neutral": "Residual and excluded/unknown pixels use a named neutral ground presentation fallback; no soil classification claim",
            "red_overlay": "Deferred review evidence is not consumed",
        },
        "counts": {
            "unknown": int(np.count_nonzero(values[..., 3] == 0)),
            "excluded": int(np.count_nonzero(reasons != 0)),
        },
        "producer_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
    }
    report["fingerprint"] = hashlib.sha256(
        json.dumps(
            report, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    (output / "material-input-manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pcg-manifest", required=True, type=Path)
    parser.add_argument("--cover-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = prepare(args.pcg_manifest, args.cover_manifest, args.output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "fingerprint": result["fingerprint"],
                "counts": result["counts"],
            }
        )
    )

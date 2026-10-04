"""Prepare no-save Landscape review of PCG selectors and explicit holdbacks."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_sa_calobra_pcg_masks import verified_manifest
from verify_sa_calobra_lidar_masks import digest


def prepare(pcg_manifest, baseline_manifest, output):
    if output.exists():
        raise FileExistsError("Preserve previous PCG review")
    pcg = verified_manifest(pcg_manifest)
    baseline = json.loads(baseline_manifest.read_text(encoding="utf-8"))
    if baseline["grid"] != pcg["grid"] or baseline["geometry_mutation"] is not False:
        raise ValueError("Review/PCG grid mismatch")
    for row in baseline["outputs"]:
        p = baseline_manifest.parent / row["path"]
        if (
            p.parent != baseline_manifest.parent
            or p.stat().st_size != row["size_bytes"]
            or digest(p) != row["sha256"]
        ):
            raise ValueError("Baseline review identity mismatch")
    image = np.array(
        Image.open(baseline_manifest.parent / "orthophoto.png").convert("RGB")
    )
    with rasterio.open(pcg_manifest.parent / "vegetation-selectors.tif") as ds:
        bands = ds.read()
    with rasterio.open(pcg_manifest.parent / "exclusion-reasons.tif") as ds:
        reasons = ds.read(1)
    for band, color in enumerate([[170, 220, 90], [65, 175, 75], [15, 95, 45]]):
        selected = bands[band] == 1
        image[selected] = np.rint(
            0.55 * image[selected] + 0.45 * np.array(color)
        ).astype(np.uint8)
    # Review/exclusion domains are explicit presentation choices, not measured
    # errors or permission to modify source geometry.
    for bit, color in [
        (128, [185, 185, 185]),
        (64, [130, 120, 110]),
        (4, [175, 105, 205]),
        (16, [35, 115, 245]),
        (32, [255, 166, 0]),
        (8, [0, 230, 255]),
        (2, [245, 210, 130]),
        (1, [245, 245, 245]),
    ]:
        image[(reasons & bit) != 0] = color
    output.mkdir(parents=True)
    for name in ["orthophoto.png", "historical-context.png"]:
        shutil.copyfile(baseline_manifest.parent / name, output / name)
    Image.fromarray(image).save(output / "review-overlay.png")
    report = {
        **baseline,
        "status": "pcg_mask_contract_review",
        "review_atmosphere": True,
        "pcg_manifest_sha256": digest(pcg_manifest),
        "pcg_fingerprint": pcg["fingerprint"],
        "baseline_review_sha256": digest(baseline_manifest),
        "legend": {
            "green_shades": "low/medium/high vegetation selectors outside exclusions; candidate source classes, not exact tree positions",
            "white": "frozen pavement projection; no road rebuilt",
            "sand": "conservative .51m shoulder envelope",
            "purple": "BOB affected-domain holdback, not measured CUT/FILL",
            "blue": "water context plus 5m decorative holdback for lines/points, not channel width or flood boundary",
            "cyan": "Catastro/LiDAR building exclusion evidence",
            "amber": "mapped infrastructure holdback; not measured geometry error",
            "gray": "no LiDAR samples",
            "brown_gray": "other LiDAR source classes held back",
            "sky": "native session-only SkyAtmosphere and sun; no save",
        },
        "counts": {"pcg": pcg["counts"]},
        "outputs": [
            {"path": p.name, "size_bytes": p.stat().st_size, "sha256": digest(p)}
            for p in sorted(output.iterdir())
        ],
        "producer_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "geometry_mutation": False,
        "admission": "Diagnostic contract review; previous green character acceptance does not automatically accept new holdbacks; no production planting/performance claim",
    }
    (output / "review-manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pcg-manifest", required=True, type=Path)
    parser.add_argument("--baseline-review", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = prepare(args.pcg_manifest, args.baseline_review, args.output)
    print(json.dumps({"status": result["status"], "outputs": len(result["outputs"])}))

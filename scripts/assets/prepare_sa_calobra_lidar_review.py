"""Prepare verified LiDAR diagnostic colors for the existing no-save UE consumer."""

from __future__ import annotations
import argparse
import hashlib
import json
import shutil
from pathlib import Path
import numpy as np
import rasterio
from PIL import Image
from verify_sa_calobra_lidar_masks import verify, digest


def prepare(lidar_manifest, review_manifest, output):
    if output.exists():
        raise FileExistsError("Keep existing review payloads")
    checked = verify(lidar_manifest)
    lidar = json.loads(lidar_manifest.read_text(encoding="utf-8"))
    baseline = json.loads(review_manifest.read_text(encoding="utf-8"))
    if baseline["grid"] != lidar["grid"] or baseline["geometry_mutation"] is not False:
        raise ValueError("Review/LiDAR frozen grid mismatch")
    for row in baseline["outputs"]:
        path = review_manifest.parent / row["path"]
        if (
            path.parent != review_manifest.parent
            or path.stat().st_size != row["size_bytes"]
            or digest(path) != row["sha256"]
        ):
            raise ValueError("Baseline review identity mismatch")
    rgb = np.asarray(
        Image.open(review_manifest.parent / "orthophoto.png").convert("RGB")
    )
    context = np.asarray(
        Image.open(lidar_manifest.parent / "lidar-class-context.png").convert("RGB")
    )
    with rasterio.open(lidar_manifest.parent / "height-review-flags.tif") as ds:
        quality = ds.read(1)
    with rasterio.open(review_manifest.parent / "review-class.tif") as ds:
        review = ds.read(1)
    overlay = np.rint(0.55 * rgb + 0.45 * context).astype(np.uint8)
    # Building and existing high-relief review markings retain separate priorities.
    overlay[(quality & 1) != 0] = [220, 90, 200]
    overlay[review == 1] = [255, 166, 0]
    overlay[review == 2] = [0, 230, 255]
    overlay[review == 3] = [185, 185, 185]
    output.mkdir(parents=True)
    for name in ["orthophoto.png", "historical-context.png"]:
        shutil.copyfile(review_manifest.parent / name, output / name)
    Image.fromarray(overlay).save(output / "review-overlay.png")
    report = {
        **baseline,
        "status": "lidar_diagnostic_candidate",
        "review_atmosphere": True,
        "lidar_manifest_sha256": digest(lidar_manifest),
        "lidar_fingerprint": checked["fingerprint"],
        "baseline_review_manifest_sha256": digest(review_manifest),
        "producer_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "legend": {
            **baseline["legend"],
            "green_shades": "source low/medium/high vegetation presence blended with ortho; not species or planting authorization",
            "brown": "source ground-class presence; not bare-soil/rock classifier",
            "magenta": "invalid/negative vegetation minus native DTM normalization; review only; not measured Landscape error",
            "gray_lidar": "other/no source samples",
            "cyan_lidar": "source building-class presence; Catastro footprint cyan retains priority",
            "sky": "native session-only SkyAtmosphere and sun; no map save",
        },
        "counts": {"baseline_diagnostic": baseline["counts"], "lidar": lidar["counts"]},
        "outputs": [
            {"path": p.name, "size_bytes": p.stat().st_size, "sha256": digest(p)}
            for p in sorted(output.iterdir())
        ],
        "attribution": baseline["attribution"] + [lidar["attribution"]],
    }
    (output / "review-manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lidar-manifest", required=True, type=Path)
    parser.add_argument("--review-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = prepare(args.lidar_manifest, args.review_manifest, args.output)
    print(json.dumps({"status": result["status"], "outputs": len(result["outputs"])}))

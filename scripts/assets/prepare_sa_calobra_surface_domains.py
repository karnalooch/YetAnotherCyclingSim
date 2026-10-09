"""Derive shading domains independently of immutable placement holdbacks.

Embark reference: layered biome content and reproducible terrain export; the
classification priorities and dry-channel width below are YACS art decisions.
These are data masks, not generated albedo or newly measured ground cover.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageFilter
from rasterio.features import rasterize
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_sa_calobra_pcg_masks import selectors, verified_manifest  # noqa: E402
from prepare_sa_calobra_material_inputs import blend_weights  # noqa: E402
from verify_sa_calobra_lidar_masks import digest, verify as verify_lidar  # noqa: E402


def shading_selectors(counts, quality):
    """Recover observed classes before decorative/placement exclusions."""
    if counts.ndim != 3 or counts.shape[0] != 6:
        raise ValueError("Expected six retained LiDAR count bands")
    if quality.shape != counts.shape[1:]:
        raise ValueError("Quality grid mismatch")
    return selectors(counts, quality, np.zeros(quality.shape, dtype=bool))


def channel_shapes(features, half_width_m=1.0):
    """Only mapped water lines; no springs/reservoirs promoted to river beds."""
    if not 0 < half_width_m <= 2:
        raise ValueError("Dry-channel art width outside bounded recipe")
    return [
        (shape(row["geometry"]).buffer(half_width_m).__geo_interface__, 1)
        for row in features
        if row["group"] == "water"
        and shape(row["geometry"]).geom_type in ("LineString", "MultiLineString")
    ]


def prepare(root: Path, output: Path):
    if output.exists():
        raise FileExistsError("Preserve previous surface-domain package")
    pcg_path = root / "pcg-masks-v1-2026-10-04/pcg-mask-manifest.json"
    lidar_path = root / "lidar-masks-v1b-2026-10-04/lidar-manifest.json"
    cover_path = root / "land-cover-baseline-v1a-2026-10-04/land-cover-manifest.json"
    context_path = root / "context-exclusions-v2-2026-10-04/context-mask-manifest.json"
    old_path = root / "material-foundation-v3-2026-10-05/material-input-manifest.json"
    pcg, cover, context = [
        verified_manifest(path) for path in (pcg_path, cover_path, context_path)
    ]
    old = json.loads(old_path.read_text(encoding="utf-8"))
    old_content = {k: v for k, v in old.items() if k != "fingerprint"}
    if (
        hashlib.sha256(
            json.dumps(
                old_content, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
        != old["fingerprint"]
    ):
        raise ValueError("Stale comparison material manifest")
    for row in old["outputs"]:
        if Path(row["path"]).name != row["path"]:
            raise ValueError("Unsafe comparison product")
        if digest(old_path.parent / row["path"]) != row["sha256"]:
            raise ValueError("Stale comparison mask")
    verify_lidar(lidar_path)
    lidar = json.loads(lidar_path.read_text(encoding="utf-8"))
    if any(value["grid"] != pcg["grid"] for value in (cover, context, old, lidar)):
        raise ValueError("Surface inputs do not share the frozen grid")
    with rasterio.open(lidar_path.parent / "class-counts.tif") as ds:
        counts, transform = ds.read(), ds.transform
    with rasterio.open(lidar_path.parent / "height-review-flags.tif") as ds:
        quality = ds.read(1)
    with rasterio.open(cover_path.parent / "open_rock-historical-weight.tif") as ds:
        historical_rock = ds.read(1)
    with rasterio.open(pcg_path.parent / "exclusion-reasons.tif") as ds:
        placement_reasons = ds.read(1)
    recovered = shading_selectors(counts, quality)
    # Unknowns survive. No placement reason is allowed to erase shading classes.
    values = blend_weights(
        recovered, np.zeros(quality.shape, dtype=np.uint16), historical_rock, 2
    )
    availability = values[..., 3].copy()
    vectors = json.loads(
        (context_path.parent / "context-exclusions.json").read_text(encoding="utf-8")
    )["features"]
    shapes = channel_shapes(vectors)
    bed = (
        rasterize(
            shapes,
            out_shape=quality.shape,
            transform=transform,
            dtype="uint8",
            all_touched=True,
        )
        if shapes
        else np.zeros(quality.shape, dtype=np.uint8)
    )
    bed = np.asarray(Image.fromarray(bed * 255).filter(ImageFilter.BoxBlur(2))).copy()
    # Keep buildings and the road surface clear of artistic channel overlays.
    # Water decoration does not alter the original five-metre planting holdback.
    bed[(placement_reasons & (1 | 8)) != 0] = 0
    values[..., 3] = bed
    previous = np.asarray(Image.open(old_path.parent / "material-weights.png"))
    source_zero = previous[..., :3].sum(axis=2) == 0
    new_zero = values[..., :3].sum(axis=2) == 0
    output.mkdir(parents=True)
    products = {"material-weights.png": values, "sample-availability.png": availability}
    rows = []
    for name, pixels in products.items():
        path = output / name
        Image.fromarray(pixels).save(path)
        if not np.array_equal(np.asarray(Image.open(path)), pixels):
            raise ValueError("Surface data readback differs")
        rows.append(
            {
                "path": name,
                "sha256": digest(path),
                "size_bytes": path.stat().st_size,
                "logical_sha256": hashlib.sha256(pixels.tobytes()).hexdigest(),
            }
        )
    report = {
        "schema_version": 1,
        "status": "PRESENTATION_FALLBACK_MATERIAL_INPUTS",
        "geometry_mutation": False,
        "current_cover_admitted": False,
        "production_planting": "NOT_ADMITTED",
        "grid": pcg["grid"],
        "world_mapping": pcg["world_mapping"],
        "producer_file": "scripts/assets/prepare_sa_calobra_surface_domains.py",
        "producer_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "sources": [
            {"path": str(p), "sha256": digest(p)}
            for p in (pcg_path, lidar_path, cover_path, context_path, old_path)
        ],
        "outputs": rows,
        "semantics": {
            "R": "Observed low LiDAR class shading fallback, not planting permission",
            "G": "Observed medium/high class forest-floor shading fallback; invalid high rejected",
            "B": "Dated polygon open-rock share, not measured fine ground cover",
            "A": "Artistic dry-channel appearance along mapped water lines; NOT sample availability or water presence",
            "availability": "Separate sample-availability.png: accepted samples 255, unknown 0",
            "placement": "Original PCG selectors, reasons and clearance remain byte-identical and binding",
            "neutral": "Mineral remainder; slope fallback for zero RGB is artistic only",
            "water": "1m half-width plus radius-2 pixel soft edge; excludes road/building pixels; not surveyed bed width, flow or flood extent",
        },
        "counts": {
            "source_zero_rgb": int(source_zero.sum()),
            "new_zero_rgb": int(new_zero.sum()),
            "restored_source_zero_rgb": int((source_zero & ~new_zero).sum()),
            "unknown_samples": int((availability == 0).sum()),
            "dry_channel_pixels": int((bed > 0).sum()),
            "dry_channel_over_road_building": int(
                ((bed > 0) & ((placement_reasons & 9) != 0)).sum()
            ),
        },
        "reference": [
            "https://www.sidefx.com/learn/talks/embark-landscape-creation/",
            "https://medium.com/embarkstudios/working-with-photogrammetry-in-practice-1f9dada77606",
            "https://medium.com/embarkstudios/from-photos-to-in-game-assets-23c2f5e5d08",
        ],
        "substitution": "Pinned GIS/LiDAR masks plus native UE/TextureGraph shading; no Houdini dependency or Embark-private algorithm claim",
    }
    report["fingerprint"] = hashlib.sha256(
        json.dumps(
            report, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    (output / "material-input-manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.root, args.output)["counts"]))

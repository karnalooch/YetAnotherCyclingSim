"""Read frozen CUT-only patches into evidence masks; never author earthworks."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_sa_calobra_road_masks import load_sources
from verify_normalized_context import verify
from verify_sa_calobra_lidar_masks import digest

NODATA = -32767.0
# Native 754.29m / 65535 encoding: half-step <5.76mm, plus rounded
# import metadata and float32 centimetre payload uncertainty. No terrain filter.
ERROR_BOUND_M = 0.007


def accumulate_patch(depth, base, target_cm, rect):
    x0, y0, x1, y1 = (rect[k] for k in ("min_x", "min_y", "max_x", "max_y"))
    if not (0 <= x0 <= x1 < base.shape[1] and 0 <= y0 <= y1 < base.shape[0]):
        raise ValueError("Patch outside frozen grid")
    expected = (y1 - y0 + 1, x1 - x0 + 1)
    if (rect["height"], rect["width"]) != expected or target_cm.shape != expected:
        raise ValueError("Patch dimensions disagree")
    source = base[y0 : y1 + 1, x0 : x1 + 1]
    if not np.isfinite(target_cm).all():
        raise ValueError("Nonfinite CUT payload")
    valid = np.isfinite(source) & (source != NODATA)
    delta = source.astype(np.float64) - target_cm.astype(np.float64) / 100
    if np.any(delta[valid] < -ERROR_BOUND_M):
        raise ValueError("CUT-only patch raises ground beyond encoding uncertainty")
    lower = np.maximum(0, delta - ERROR_BOUND_M).astype(np.float32)
    region = depth[y0 : y1 + 1, x0 : x1 + 1]
    region[valid] = np.maximum(region[valid], lower[valid])


def prepare(recipe_path, source_root, normalized_path, output):
    if output.exists():
        raise FileExistsError("Preserve existing earthworks evidence")
    verify(normalized_path)
    normalized = json.loads(normalized_path.read_text(encoding="utf8"))
    recipe, _, _, _, windows = load_sources(recipe_path, source_root)
    grid = normalized["grid"]
    if (grid["crs"], grid["width"], grid["height"], grid["transform"]) != (
        "EPSG:25831",
        4033,
        4033,
        [0.5, 0, 483000, 0, -0.5, 4409516.5],
    ):
        raise ValueError("Unadmitted frozen grid")
    with rasterio.open(normalized_path.parent / "elevation.tif") as ds:
        base, profile = ds.read(1), ds.profile
    depth = np.full(base.shape, NODATA, dtype=np.float32)
    patches = [source_root / "Network" / w["cut_manifest"] for w in windows]
    patches.append(source_root / "ma2141-cut-patch.json")
    for path in patches:
        patch = json.loads(path.read_text(encoding="utf8"))
        if (
            patch["operation"] != "CUT_ONLY"
            or patch["world_space_unit"] != "centimeter"
            or patch["blend_mode"] != "Min"
            or patch["fill_authoring_permitted"] is not False
            or patch["base_dtm_modified"] is not False
            or patch["save_map"] is not False
        ):
            raise ValueError("Unsupported frozen patch semantics")
        payload = path.parent / patch["patch_file"]
        if digest(payload) != patch["patch_sha256"]:
            raise ValueError("CUT payload hash mismatch")
        rect = patch["rect"]
        target = np.fromfile(payload, dtype="<f4").reshape(
            rect["height"], rect["width"]
        )
        accumulate_patch(depth, base, target, rect)
    observed = depth != NODATA
    cut = np.full(base.shape, 255, dtype=np.uint8)
    cut[observed] = (depth[observed] > 0).astype(np.uint8)
    fill = np.full(base.shape, 255, dtype=np.uint8)
    fill[observed] = 0  # No FILL authored in these CUT-only source artifacts.
    output.mkdir(parents=True)
    products = []
    for name, values, nodata in [
        ("cut-depth-lower-bound.tif", depth, NODATA),
        ("cut-evidence.tif", cut, 255),
        ("fill-authoring-state.tif", fill, 255),
    ]:
        path = output / name
        with rasterio.open(
            path,
            "w",
            **{
                **profile,
                "count": 1,
                "dtype": values.dtype.name,
                "nodata": nodata,
                "compress": "DEFLATE",
            },
        ) as ds:
            ds.write(values, 1)
        with rasterio.open(path) as ds:
            if (
                ds.transform != profile["transform"]
                or ds.crs != profile["crs"]
                or ds.nodata != nodata
                or not np.array_equal(ds.read(1), values)
            ):
                raise ValueError("Earthworks evidence readback mismatch")
        products.append(
            {
                "path": name,
                "sha256": digest(path),
                "size_bytes": path.stat().st_size,
                "logical_sha256": hashlib.sha256(values.tobytes()).hexdigest(),
            }
        )
    report = {
        "schema_version": 1,
        "status": "FROZEN_EARTHWORKS_EVIDENCE_CANDIDATE",
        "geometry_mutation": False,
        "grid": grid,
        "accepted_source_sha": recipe["accepted_sha"],
        "source_recipe_sha256": digest(recipe_path),
        "normalized_manifest_sha256": digest(normalized_path),
        "producer_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "error_bound_m": ERROR_BOUND_M,
        "patch_count": len(patches),
        "counts": {
            "covered_cells": int(observed.sum()),
            "resolved_cut_cells": int((cut == 1).sum()),
            "unknown_cells": int((~observed).sum()),
            "maximum_cut_lower_bound_m": float(depth[observed].max()),
        },
        "semantics": {
            "cut_depth": "metres; max over overlapping frozen CUT-only targets of max(0, native DTM-target-0.007m); -32767 outside verified patch/ground coverage",
            "cut_evidence": "1=resolved lowering beyond encoding bound; 0=no resolved lowering, not proof of exactly zero cut; 255=unknown",
            "fill_authoring": "0=FILL NOT_AUTHORED in source CUT-only patch domain; 255=uncovered/unknown; not a physical fill footprint or safety admission",
            "limits": "Read-only derivation from frozen visual artifacts, not engineering acceptance; original BOB rectangles and hard exclusions remain unchanged",
        },
        "remaining": [
            "Authoritative FILL geometry",
            "Inner/outer road-edge semantics",
            "Current-cover/confidence refinement and whole-2A admission",
        ],
        "human_visual_acceptance": "PENDING",
        "production_planting": "NOT_ADMITTED",
        "outputs": products,
    }
    report["fingerprint"] = hashlib.sha256(
        json.dumps(
            report, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    (output / "earthworks-mask-manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-recipe", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--normalized-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = prepare(
        args.source_recipe, args.source_root, args.normalized_manifest, args.output
    )
    print(json.dumps({"status": report["status"], "counts": report["counts"]}))

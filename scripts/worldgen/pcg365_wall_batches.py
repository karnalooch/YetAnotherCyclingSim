"""Repack native PCGEx wall inputs into bounded raster batches.

This is a data adapter: PCGEx owns region selection, joining and triangulation.
Adjacent batches share one row/column of vertices, never a whole grid cell.
No source raster, Landscape height, exclusion, or existing material is edited.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

GRID_SIZE = 4033
GRID_STEP_CM = 50
PROTECTED_BITS = 63
MIN_CLEARANCE_CM = 125
MAX_BATCH_CELLS = 512
MAX_READBACK_POINTS = 256


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_pixels(rgba, eligible, clearance_cm, reasons):
    if rgba.shape != (GRID_SIZE, GRID_SIZE, 4):
        raise ValueError("Input must retain the accepted 4033 x 4033 RGBA grid")
    if any(a.shape != rgba.shape[:2] for a in (eligible, clearance_cm, reasons)):
        raise ValueError("Source grids differ")
    selected = rgba[:, :, 3] > 0
    if not np.array_equal(selected, eligible):
        raise ValueError("Texture eligibility differs from authenticated inputs")
    if np.any(selected & ((reasons & PROTECTED_BITS) != 0)):
        raise ValueError("Protected exclusion present in wall inputs")
    if np.any(selected & (~np.isfinite(clearance_cm) | (clearance_cm < MIN_CLEARANCE_CM))):
        raise ValueError("Unknown or insufficient source clearance")
    encoded = rgba[:, :, 0].astype(np.float64) * 10
    if np.any(selected & (encoded > clearance_cm + 1e-4)):
        raise ValueError("Encoded clearance overstates the source clearance")
    return selected


def batches(shape, cells=MAX_BATCH_CELLS):
    if len(shape) != 2 or min(shape) < 2 or not 1 <= cells <= MAX_BATCH_CELLS:
        raise ValueError("Invalid bounded raster batch dimensions")
    for row in range(0, shape[0] - 1, cells):
        for col in range(0, shape[1] - 1, cells):
            yield row, col, min(row + cells, shape[0] - 1), min(col + cells, shape[1] - 1)


def texture_transform(bounds):
    r0, c0, r1, c1 = bounds
    return dict(location=dict(x=(c0+c1)*GRID_STEP_CM/2, y=(r0+r1)*GRID_STEP_CM/2, z=1000000),
                scale=dict(x=(c1-c0+1)*GRID_STEP_CM/2, y=(r1-r0+1)*GRID_STEP_CM/2, z=1))


def require_small_native_probe(point_count):
    """Call only after a native node has reduced the actual data collection.

GetNodeDataView start/end range did not prevent a live whole-area request from
blocking the editor's MCP thread. A small requested range alone is not a guard.
"""
    if type(point_count) is not int or not 0 <= point_count <= MAX_READBACK_POINTS:
        raise ValueError("Reduce data to <=256 points in native PCG before MCP inspection")


def prepare(input_dir, output):
    input_dir, output = Path(input_dir), Path(output)
    if output.exists():
        raise ValueError("Preserve previous evidence: output directory already exists")
    manifest = json.loads((input_dir / "input-manifest.json").read_text())
    if manifest["protected_reason_bits"] != PROTECTED_BITS or manifest["grid_step_cm"] != GRID_STEP_CM:
        raise ValueError("Source contract differs")
    if digest(input_dir / "eligible-surface.png") != manifest["texture_sha256"]:
        raise ValueError("Derived input texture changed")
    for source in manifest["sources"]:
        if digest(source["path"]) != source["sha256"]:
            raise ValueError("Authoritative source changed: " + source["path"])
    selector_root = Path(manifest["sources"][0]["path"]).parent
    for item in manifest["selector_products"].values():
        if digest(selector_root / item["path"]) != item["sha256"]:
            raise ValueError("Selector product changed")
    rgba = np.array(Image.open(input_dir / "eligible-surface.png"))
    with np.load(input_dir / "input-validation.npz", allow_pickle=False) as proof:
        selected = validate_pixels(rgba, proof["eligible"], proof["clearance_cm"], proof["reasons"])
    output.mkdir(parents=True)
    results = []
    for r0, c0, r1, c1 in batches(selected.shape):
        crop = rgba[r0:r1+1, c0:c1+1]
        count = int(np.count_nonzero(crop[:, :, 3]))
        if not count:
            continue
        name = f"surface_r{r0}_c{c0}.png"
        Image.fromarray(crop).save(output / name)
        results.append(dict(path=name, sha256=digest(output/name), bounds_rc=[r0,c0,r1,c1],
                            selected_vertices=count, texture_transform=texture_transform([r0,c0,r1,c1])))
    result = dict(schema_version=1, source_manifest_sha256=digest(input_dir/"input-manifest.json"),
                  producer_sha256=digest(__file__), native_mesh_generation="NOT_RUN",
                  source_rasters_modified=False, protected_reason_bits=PROTECTED_BITS,
                  unique_selected_vertices=int(selected.sum()), batch_maximum_cells=MAX_BATCH_CELLS,
                  batch_maximum_vertices=(MAX_BATCH_CELLS+1)**2, batches=results,
                  native_readback_limit=MAX_READBACK_POINTS, native_readback_requires_upstream_reduction=True,
                  editor_restarted=False, whole_area_rollout=False, owner_visual_acceptance=False,
                  performance_pass=False)
    (output / "batch-manifest.json").write_text(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.input_dir, args.output)
    print(json.dumps({k: v if k != "batches" else len(v) for k,v in result.items()}))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Extract a real 256x256 sample from immutable Sa Calobra L06 caches.

Strictly source-only and bounded output: never recompute base/masks, edit UE,
overwrite cached terrain, or promote this crop to whole-world proof.

Each source file is loaded by its OWN fresh hython process. This limits peak
memory compared with loading all seven 16000x16000 volumes simultaneously.
The native Houdini voxel grid is accessed at exact indices, not interpolated.
"""
from __future__ import annotations
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import re
import time

GRID = (16000, 16000, 1)
CROP = 256
SITE_WORLD = (44.647972106933594, 0.0, -1844.250244140625)
BASE_AND_MASKS = {
    "base": {
        "name": "stage1_base.bgeo.sc",
        "bytes": 519575557,
        "sha256": "08586f0e1aa6aa033cf7364a929d2c260c87c41d6dc11445c981e10ec6ba2952",
        "layers": ("height", "mask", "Alpha"),
    },
    "masks": {
        "name": "stage2_masks.bgeo.sc",
        "bytes": 1167222140,
        "sha256": "203d46ea79a0a697d46256f631271135a0cd8766ba8768f7432ea315512c16a8",
        "layers": ("grass_mask", "sand_mask", "cliff_mask", "ramp_layer"),
    },
}
INPUT_ROOT = Path("D:/yacs/work/lesson06-unified-20261019")
OUTPUT_ROOT = Path("D:/yacs/work/lesson07-cc0-real-crops")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_source(path: Path, spec: dict) -> dict:
    before = path.stat()
    if not path.is_file() or before.st_size != spec["bytes"]:
        raise ValueError(f"Source size/type does not match the accepted L06 pin: {path}")
    observed_sha = sha256(path)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("Source changed while hashing")
    if observed_sha != spec["sha256"]:
        raise ValueError(f"Source hash differs from accepted L06 receipt: {path}")
    return {"source_path": str(path), "source_size": before.st_size,
            "source_sha256": observed_sha, "source_mtime_ns": before.st_mtime_ns}


def compute_window(center: tuple[int, int, int], resolution=GRID,
                   size=CROP) -> tuple[int, int, int, int]:
    if not (isinstance(size, int) and 64 <= size <= 256):
        raise ValueError("Crop size must remain bounded to 64..256")
    if not (len(center) == 3 and center[2] == 0 and resolution == GRID):
        raise ValueError("Unexpected heightfield volume/lattice index")
    i, j = center[:2]
    x0, y0 = i - size // 2, j - size // 2
    if not (0 <= x0 < x0 + size <= GRID[0] and 0 <= y0 < y0 + size <= GRID[1]):
        raise ValueError("Geographic sample lies outside accepted heightfield")
    return x0, y0, x0 + size, y0 + size


def require_memory() -> dict:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.ue.lesson06_memory_guard import require_headroom
    state = require_headroom(gib=30)
    if state["available_physical_bytes"] < 12 * 1024**3:
        raise ValueError(f"Insufficient physical memory for isolated native source read: {state}")
    return state


def check_lattice(volume, hou) -> tuple[int,int,int,int]:
    if not isinstance(volume, hou.Volume) or tuple(volume.resolution()) != GRID:
        raise ValueError("Unexpected native volume type/size")
    center = tuple(int(v) for v in volume.posToIndex(SITE_WORLD))
    window = compute_window(center)
    first = tuple(float(v) for v in volume.indexToPos((window[0], window[1], 0)))
    last = tuple(float(v) for v in volume.indexToPos((window[2] - 1, window[3] - 1, 0)))
    if not all(abs(v - target) <= 1.0 for v, target in zip(
            tuple(volume.indexToPos((0, 0, 0))), (-3999.75, 0.0, 3999.75))):
        raise ValueError("Source origin/rotation differs from accepted Sa Calobra")
    if abs(last[0]-first[0]) < 127.0 or abs(last[2]-first[2]) < 127.0:
        raise ValueError("Crop voxel scale does not match accepted 0.5m lattice")
    if any(abs(v-target) > 1.0 for v,target in zip(first,(-19.35,0.0,-1780.25))):
        # Bounded geographic sanity: from observed scree-site and 0.5m grid.
        raise ValueError(f"Unexpected scree-site geographic mapping: {first}")
    return window


def read_crop(primitive, window, np):
    x0, y0, x1, y1 = window
    pixels = np.fromiter(
        (primitive.voxel((i, j, 0)) for j in range(y0, y1) for i in range(x0, x1)),
        dtype=np.float32,
        count=(x1-x0) * (y1-y0),
    ).reshape((y1-y0, x1-x0))
    if pixels.dtype != np.float32 or pixels.shape != (CROP, CROP) or not np.isfinite(pixels).all():
        raise ValueError("Cropped source contains nonfinite values or has wrong shape")
    return pixels


def run(stage: str, token: str, hou, np, output: Path) -> dict:
    if hou.isUIAvailable() or tuple(hou.applicationVersion()) != (22, 0, 466):
        raise ValueError("Fresh headless Houdini 22.0.466 required")
    if hou.node("/obj").children():
        raise ValueError("Unexpected nodes in fresh hython")
    spec = BASE_AND_MASKS[stage]
    source = INPUT_ROOT / spec["name"]
    before_identity = check_source(source, spec)
    memory_before = require_memory()
    geo = hou.Geometry()
    started = time.monotonic()
    geo.loadFromFile(str(source))
    raw = {primitive.attribValue("name"): primitive
           for primitive in geo.prims() if isinstance(primitive, hou.Volume)}
    if set(raw) != set(spec["layers"]):
        raise ValueError(f"Unexpected cached native layer names: {sorted(raw)}")
    window = check_lattice(raw[spec["layers"][0]], hou)
    arrays = {}
    lattice = {}
    for layer in spec["layers"]:
        volume = raw[layer]
        if check_lattice(volume, hou) != window:
            raise ValueError(f"{layer} has different geographic mapping")
        cropped = read_crop(volume, window, np)
        arrays[layer] = cropped
        lattice[layer] = {
            "sha256_float32_le": hashlib.sha256(cropped.astype("<f4").tobytes()).hexdigest(),
            "min": float(cropped.min()), "max": float(cropped.max()),
            "nonzero": int(np.count_nonzero(cropped)),
            "first_voxel_world_xyz": list(map(float,volume.indexToPos((window[0],window[1],0)))),
            "last_voxel_world_xyz": list(map(float,volume.indexToPos((window[2]-1,window[3]-1,0))))
        }
    del geo, raw
    gc.collect()
    source_after = check_source(source, spec)
    if before_identity != source_after:
        raise ValueError("L06 cache identity changed during sample")
    output.mkdir(parents=True, exist_ok=True)
    destination = output / f"{stage}-real-crop.npz"
    metadata = output / f"{stage}-real-crop.json"
    if destination.exists() or metadata.exists():
        raise ValueError("Never overwrite an existing crop or receipt")
    tmp = output / f"{stage}-real-crop.npz.partial"
    with tmp.open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    os.replace(tmp, destination)
    report = {
        "status": "REAL_ACCEPTED_L06_SOURCE_CROP_REOPEN_REQUIRED",
        "stage": stage, "run_token": token, "source": before_identity,
        "original_16000_grid": list(GRID), "crop_size": CROP,
        "crop_index_window": list(window), "source_site_xyz": list(SITE_WORLD),
        "layer_metadata": lattice, "crop_path": str(destination),
        "crop_bytes": destination.stat().st_size, "crop_sha256": sha256(destination),
        "native_houdini_version": hou.applicationVersionString(),
        "elapsed_sec": time.monotonic() - started,
        "memory_before": memory_before,
        "heightfield_modified": False, "source_masks_modified": False,
        "original_full_caches_touched": False,
        "houdini_material_cook": False, "unreal_import": False,
    }
    metadata.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", choices=tuple(BASE_AND_MASKS), required=True)
    ap.add_argument("--token", required=True)
    args=ap.parse_args()
    if not re.fullmatch(r"[0-9]{9,13}-[1-9][0-9]*", args.token):
        raise ValueError("Expected GitHub run-attempt token")
    if os.name=="nt" and str(OUTPUT_ROOT).lower().replace("/","\\") != "d:\\yacs\\work\\lesson07-cc0-real-crops":
        raise ValueError("Cannot change fixed isolated target")
    import hou
    import numpy as np
    output = OUTPUT_ROOT / args.token
    result=run(args.stage,args.token,hou,np,output)
    print(json.dumps({"status":result["status"],"stage":args.stage,"sha256":result["crop_sha256"],
        "layer_counts":{k:v["nonzero"] for k,v in result["layer_metadata"].items()},
        "crop_file":result["crop_path"],"elapsed_sec":result["elapsed_sec"]}),flush=True)


if __name__=="__main__":
    main()

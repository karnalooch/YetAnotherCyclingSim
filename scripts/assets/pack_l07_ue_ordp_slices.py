#!/usr/bin/env python3
"""Pack the 5 user-selected Poly Haven CC0 2K material families into Unreal Texture2DArray slices.

Slot order (F6 / Gate G08):
  0: mossy_rock
  1: sparse_grass
  2: gravel_floor_02
  3: dark_rock_02
  4: coast_sand_rocks_02

For each slot, writes three 2048x2048 RGBA8 PNG slices:
  - slice_<idx>_<slug>_colour.png (sRGB BaseColor, with optional neutral Rec.709 luminance on slot 3 dark_rock_02)
  - slice_<idx>_<slug>_normal.png (Linear DirectX normal from nor_dx_2k.png)
  - slice_<idx>_<slug>_masks.png  (Linear ORD(p) packing verified from M_Landscape_YACS: R=AO, G=Roughness, B=Displacement, A=AO)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

import numpy as np
from PIL import Image

from scripts.assets.prepare_lesson07_surface_repair import (
    SIZE,
    neutral_albedo,
    png_header,
    rgba_u8,
    save_png_exact,
    scalar_u8,
    sha256,
)

SOURCE_ROOT = Path("D:/yacs/work/lesson07-polyhaven-cc0-v1")
OUTPUT_ROOT = Path("D:/yacs/work/lesson07-ue-slices-v1")

EXPECTED_SLOTS = (
    (0, "mossy_rock"),
    (1, "sparse_grass"),
    (2, "gravel_floor_02"),
    (3, "dark_rock_02"),
    (4, "coast_sand_rocks_02"),
)


def decode_rgba_2k(path: Path) -> np.ndarray:
    if path.suffix.lower() == ".png":
        bits, ctype = png_header(path)
        if bits == 16 and ctype == 6:
            return rgba_u8(path)
    with Image.open(path) as im:
        if im.size != SIZE:
            raise ValueError(f"Unexpected dimensions {im.size} for {path.name}")
        arr = np.asarray(im.convert("RGBA"), dtype=np.uint8).copy()
    arr[:, :, 3] = 255
    return arr


def decode_scalar_2k(path: Path) -> np.ndarray:
    if path.suffix.lower() == ".png":
        bits, ctype = png_header(path)
        if bits == 16 and ctype == 0:
            return scalar_u8(path)
    with Image.open(path) as im:
        if im.size != SIZE:
            raise ValueError(f"Unexpected dimensions {im.size} for {path.name}")
        raw = np.asarray(im)
        if raw.ndim == 3:
            raw = raw[:, :, 0]
        if raw.dtype == np.uint16:
            return np.rint(raw.astype(np.float64) / 257.0).astype(np.uint8)
        if raw.dtype == np.uint8:
            return raw.copy()
        raise ValueError(f"Unsupported scalar dtype {raw.dtype} in {path.name}")


def pack_slices(source_root: Path, out_dir: Path, neutral_cliff_albedo: bool = True) -> dict:
    bindings_path = source_root / "bindings-v1.json"
    bindings = json.loads(bindings_path.read_text(encoding="utf-8"))
    if bindings.get("status") != "SOURCE_BINDINGS_VERIFIED_NO_MATERIAL_IMPORT":
        raise ValueError("Source bindings not verified")
    ue_slots = bindings.get("unreal", [])
    if [(s["index"], s["slug"]) for s in ue_slots] != list(EXPECTED_SLOTS):
        raise ValueError("Unreal array slot order in bindings-v1.json does not match EXPECTED_SLOTS")

    if out_dir.exists():
        raise FileExistsError(f"Refuse to overwrite existing slice output directory: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=False)

    slot_manifests = []
    for slot_entry in ue_slots:
        idx = int(slot_entry["index"])
        slug = str(slot_entry["slug"])
        files = slot_entry["files"]
        verified_inputs = {}
        for kind in ("diff", "rough", "nor_dx", "ao", "disp"):
            fmeta = files[kind]
            p = Path(fmeta["path"])
            if not p.is_file() or p.stat().st_size != fmeta["bytes"] or sha256(p) != fmeta["sha256"]:
                raise ValueError(f"2K input verification failed for slot {idx} ({slug}) {kind}")
            verified_inputs[kind] = {"path": str(p), "sha256": fmeta["sha256"], "bytes": fmeta["bytes"]}

        colour = decode_rgba_2k(Path(files["diff"]["path"]))
        if slug == "dark_rock_02" and neutral_cliff_albedo:
            colour = neutral_albedo(colour)
            albedo_mode = "neutral_rec709_luminance_achromatic_srgb_yacs_adaptation"
        else:
            albedo_mode = "original_cc0_srgb"

        normal = decode_rgba_2k(Path(files["nor_dx"]["path"]))
        ao = decode_scalar_2k(Path(files["ao"]["path"]))
        rough = decode_scalar_2k(Path(files["rough"]["path"]))
        disp = decode_scalar_2k(Path(files["disp"]["path"]))
        masks = np.stack([ao, rough, disp, ao], axis=2)

        c_name = f"slice_{idx}_{slug}_colour.png"
        n_name = f"slice_{idx}_{slug}_normal.png"
        m_name = f"slice_{idx}_{slug}_masks.png"
        c_path = out_dir / c_name
        n_path = out_dir / n_name
        m_path = out_dir / m_name

        save_png_exact(c_path, colour)
        save_png_exact(n_path, normal)
        save_png_exact(m_path, masks)

        slot_manifests.append({
            "index": idx,
            "slug": slug,
            "albedo_mode": albedo_mode,
            "normal_convention": "DirectX",
            "ordp_channel_packing": {"R": "AO", "G": "Roughness", "B": "Displacement", "A": "AO"},
            "verified_2k_inputs": verified_inputs,
            "slices": {
                "colour": {
                    "file": c_name,
                    "path": str(c_path),
                    "bytes": c_path.stat().st_size,
                    "sha256": sha256(c_path),
                    "mean_rgb": [float(colour[:, :, c].mean()) for c in range(3)],
                },
                "normal": {
                    "file": n_name,
                    "path": str(n_path),
                    "bytes": n_path.stat().st_size,
                    "sha256": sha256(n_path),
                    "mean_rgb": [float(normal[:, :, c].mean()) for c in range(3)],
                },
                "masks": {
                    "file": m_name,
                    "path": str(m_path),
                    "bytes": m_path.stat().st_size,
                    "sha256": sha256(m_path),
                    "mean_ordp_rgb": [float(masks[:, :, c].mean()) for c in range(3)],
                },
            },
        })

    manifest = {
        "schema_version": 1,
        "status": "FIVE_SLOT_2K_CC0_ORDP_SLICES_PACKED_AND_VERIFIED",
        "size": list(SIZE),
        "slot_count": len(slot_manifests),
        "slice_file_count": len(slot_manifests) * 3,
        "ordp_contract": {
            "R": "AO (Ambient Occlusion)",
            "G": "Roughness",
            "B": "Displacement / Height",
            "A": "AO",
            "verified_against": "docs/assets/lesson07-sidefx-source-20261021/one-to-one-material-contract.json",
        },
        "slots": slot_manifests,
    }
    manifest_path = out_dir / "f6-ordp-slice-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--token", required=True)
    p.add_argument("--no-neutral-cliff-albedo", action="store_true")
    args = p.parse_args()
    if not re.fullmatch(r"[0-9]{9,13}-[1-9][0-9]*", args.token):
        raise ValueError("Invalid run token")
    if os.name == "nt" and not str(OUTPUT_ROOT).lower().replace("/", "\\").startswith("d:\\yacs\\work\\"):
        raise ValueError("Slice output must remain under D:/yacs/work")
    target = OUTPUT_ROOT / args.token
    res = pack_slices(SOURCE_ROOT, target, neutral_cliff_albedo=not args.no_neutral_cliff_albedo)
    print(json.dumps({"status": res["status"], "slice_file_count": res["slice_file_count"], "manifest": str(target / "f6-ordp-slice-manifest.json")}), flush=True)


if __name__ == "__main__":
    main()

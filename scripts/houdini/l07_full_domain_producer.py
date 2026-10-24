#!/usr/bin/env python3
"""Chunked full-domain (16000x16000, 8x8 km, 0.5m) Houdini Pegasus Lesson07 producer.

Executes the verified SideFX Pegasus material + tint + Exposure(145m)/Curvature(0.18)
graph across the entire Sa Calobra heightfield in haloed tiles, verifies seam
continuity, and exports registered 16000x16000 T_PE_Terrain_Color.png and
T_PE_Terrain_IDMap.png.

Strictly preserves immutable Stage1, Stage2, and Stage3 caches and original SideFX HDAs.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

GRID = 16000
SPACING = 0.5
ORIGIN_X = -3999.75
ORIGIN_Z = 3999.75
DEFAULT_CORE = 8000
DEFAULT_HALO = 304  # 304 voxels = 152.0m >= 145.0m occlusion View Distance

INPUT_ROOT = Path("D:/yacs/work/lesson06-unified-20261019")
ASSET_ROOT = Path("D:/yacs/work/lesson07-polyhaven-cc0-v1")
OUTPUT_ROOT = Path("D:/yacs/work/lesson07-full-domain-producer")
OTL_ROOT = Path("D:/yacs/project/worldgen/houdini/sa_calobra/otls")

MAT_HDA = OTL_ROOT / "sop_PE_heightfield_material.1.0.hda"
TINT_HDA = OTL_ROOT / "sop_PE_heightfield_tint.1.0.hda"
MAT_HDA_SHA = "e7d41ca64757699aa65b69520aca96b11f7325365506ddc675f8ea2b23a45023"
TINT_HDA_SHA = "93cc47dd511bc3d5868835b5dd3b9082c13cab23355b688aaf2a947e8687a2ed"

STAGE_SPECS = {
    "stage1_base": {
        "file": "stage1_base.bgeo.sc",
        "bytes": 519575557,
        "sha256": "08586f0e1aa6aa033cf7364a929d2c260c87c41d6dc11445c981e10ec6ba2952",
        "layers": ("height", "mask", "Alpha"),
    },
    "stage2_masks": {
        "file": "stage2_masks.bgeo.sc",
        "bytes": 1167222140,
        "sha256": "203d46ea79a0a697d46256f631271135a0cd8766ba8768f7432ea315512c16a8",
        "layers": ("grass_mask", "sand_mask", "cliff_mask", "ramp_layer"),
    },
    "stage3_scree": {
        "file": "stage3_scree.bgeo.sc",
        "bytes": 96479665,
        "sha256": "2af8ce5b467db28613c2033677c444dba5a89af943b906b01258a0b44106edb7",
        "layers": ("scree_mask",),
    },
}

ROLES = (
    ("rock", "dark_rock", None, 1000.0, 0),
    ("grass", "sparse_grass", "grass_mask", 100.0, 1),
    ("sand", "dense_sand", "sand_mask", 500.0, 1),
    ("cliff", "dark_rock_02", "cliff_mask", 100.0, 1),
    ("scree", "gray_rocks", "scree_mask", 100.0, 1),
)

GRADE_LIMESTONE_RGB = (0.876, 0.991, 1.178)

EXPOSURE_MASK_PARMS = {
    "smooth_radius": 1.0,
    "combine": 0,
    "invertmask": 0,
    "maskbyslope": 0,
    "maskbyheight": 0,
    "maskbycurvature": 0,
    "maskbydir": 0,
    "maskbyocclusion": 1,
    "minexposure": 0.0,
    "maxexposure": 1.0,
    "viewdistance": 145.0,
    "stepscale": 1.0,
    "numsearches": 16,
    "heightlayer": "height",
    "masklayer": "mask",
}
CURVATURE_MASK_PARMS = {
    "smooth_radius": 1.0,
    "combine": 0,
    "invertmask": 0,
    "maskbyslope": 0,
    "maskbyheight": 0,
    "maskbycurvature": 1,
    "maskbydir": 0,
    "maskbyocclusion": 0,
    "max_curvature": 0.18,
    "heightlayer": "height",
    "masklayer": "mask",
}
EXPOSURE_CANDIDATE = (
    (0.0, (1.0, 1.0, 1.0)),
    (0.93538, (0.651, 0.651, 0.651)),
    (1.0, (1.0, 1.0, 1.0)),
)
CURVATURE_CANDIDATE = (
    (0.0, (1.0, 1.0, 1.0)),
    (1.0, (2.0, 2.0, 2.0)),
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_tile_window(tx: int, ty: int, core: int = DEFAULT_CORE, halo: int = DEFAULT_HALO, grid: int = GRID) -> dict:
    if core <= 0 or grid % core != 0:
        raise ValueError(f"Core size {core} must divide grid {grid}")
    if halo < 290:
        raise ValueError(f"Halo {halo} voxels is smaller than 145m (290 voxels) occlusion radius")
    ntiles = grid // core
    if not (0 <= tx < ntiles and 0 <= ty < ntiles):
        raise ValueError(f"Tile index ({tx}, {ty}) out of range 0..{ntiles - 1}")
    cx0, cy0 = tx * core, ty * core
    cx1, cy1 = cx0 + core, cy0 + core
    hx0, hy0 = max(0, cx0 - halo), max(0, cy0 - halo)
    hx1, hy1 = min(grid, cx1 + halo), min(grid, cy1 + halo)
    first_world = [ORIGIN_X + hx0 * SPACING, 0.0, ORIGIN_Z - hy0 * SPACING]
    last_world = [ORIGIN_X + (hx1 - 1) * SPACING, 0.0, ORIGIN_Z - (hy1 - 1) * SPACING]
    core_first_world = [ORIGIN_X + cx0 * SPACING, 0.0, ORIGIN_Z - cy0 * SPACING]
    core_last_world = [ORIGIN_X + (cx1 - 1) * SPACING, 0.0, ORIGIN_Z - (cy1 - 1) * SPACING]
    return {
        "tx": tx,
        "ty": ty,
        "core": [cx0, cy0, cx1, cy1],
        "halo_window": [hx0, hy0, hx1, hy1],
        "halo_shape": [hy1 - hy0, hx1 - hx0],
        "core_offset_in_halo": [cx0 - hx0, cy0 - hy0, cx1 - hx0, cy1 - hy0],
        "halo_first_world_xyz": first_world,
        "halo_last_world_xyz": last_world,
        "core_first_world_xyz": core_first_world,
        "core_last_world_xyz": core_last_world,
    }


def compute_five_class_id_u8(grass, ramp_layer, sand, cliff, scree, np):
    """Exact replica of PE_Heightfield_Layers_to_ID::2.0 VEX threshold logic (tolerance=0.5)."""
    out = np.zeros(grass.shape, dtype=np.uint8)
    out = np.where(grass >= 0.5, 0, out)
    out = np.where(ramp_layer >= 0.5, 64, out)
    out = np.where(sand >= 0.5, 128, out)
    out = np.where(cliff >= 0.5, 191, out)
    out = np.where(scree >= 0.5, 255, out)
    return out.astype(np.uint8)


def linear_to_srgb_u8(rgb, np):
    """Exact IEC 61966-2-1 sRGB encoding matching heightfield_rgb_colorspace::1.0 + 8-bit output."""
    x = np.clip(rgb, 0.0, 1.0)
    srgb = np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(np.maximum(x, 1e-12), 1.0 / 2.4) - 0.055)
    return np.clip(np.round(srgb * 255.0), 0, 255).astype(np.uint8)


def verify_protected_sources() -> dict:
    info = {}
    for key, spec in STAGE_SPECS.items():
        p = INPUT_ROOT / spec["file"]
        st = p.stat()
        if st.st_size != spec["bytes"]:
            raise ValueError(f"Size mismatch for {p}: {st.st_size} != {spec['bytes']}")
        info[key] = {"path": str(p), "bytes": st.st_size, "expected_sha256": spec["sha256"]}
    if sha256(MAT_HDA) != MAT_HDA_SHA:
        raise ValueError("Material HDA SHA mismatch")
    if sha256(TINT_HDA) != TINT_HDA_SHA:
        raise ValueError("Tint HDA SHA mismatch")
    return info


def load_cc0_material_files(asset_root: Path = ASSET_ROOT) -> tuple[dict, dict]:
    b_path = asset_root / "bindings-v1.json"
    b = json.loads(b_path.read_text(encoding="utf-8"))
    files = {}
    hashes = {}
    for entry in b["houdini"]:
        role = entry["role"]
        f = entry["files"]
        p1, p2, p3 = Path(f["diff"]["path"]), Path(f["rough"]["path"]), Path(f["disp"]["path"])
        for p, k in ((p1, "diff"), (p2, "rough"), (p3, "disp")):
            if not p.is_file() or p.stat().st_size != f[k]["bytes"]:
                raise ValueError(f"CC0 texture missing/size mismatch for {role} {k}")
        files[role] = {"filename1": str(p1), "filename2": str(p2), "filename3": str(p3)}
        hashes[role] = {k: f[k]["sha256"] for k in ("diff", "rough", "disp")}
    return files, hashes


def extract_tile_inputs(win: dict, out_dir: Path, hou, np) -> Path:
    """Load each 16K stage file sequentially, slice halo window, and free 16K geometry immediately."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.ue.lesson06_memory_guard import require_headroom

    hx0, hy0, hx1, hy1 = win["halo_window"]
    h_rows, h_cols = win["halo_shape"]
    arrays = {}
    for stage_key, spec in STAGE_SPECS.items():
        require_headroom(gib=30)
        p = INPUT_ROOT / spec["file"]
        geo = hou.Geometry()
        geo.loadFromFile(str(p))
        vols = {v.attribValue("name"): v for v in geo.prims() if isinstance(v, hou.Volume)}
        if set(vols) != set(spec["layers"]):
            raise ValueError(f"Unexpected layers in {stage_key}: {sorted(vols)}")
        for lname in spec["layers"]:
            v = vols[lname]
            if tuple(v.resolution()) != (GRID, GRID, 1):
                raise ValueError(f"Unexpected resolution in {lname}")
            full = np.frombuffer(v.allVoxelsAsString(), dtype="<f4").reshape((GRID, GRID))
            cropped = np.array(full[hy0:hy1, hx0:hx1], dtype="<f4", copy=True)
            if cropped.shape != (h_rows, h_cols) or not np.isfinite(cropped).all():
                raise ValueError(f"Invalid cropped halo array for {lname}")
            arrays[lname] = cropped
            del full
        del vols, geo
        gc.collect()
    npz_path = out_dir / f"tile_{win['tx']}_{win['ty']}_halo_inputs.npz"
    with npz_path.open("wb") as f:
        np.savez(f, **arrays)
    return npz_path


def align_volume_to_window(vol, win: dict, hou) -> None:
    h_rows, h_cols = win["halo_shape"]
    if tuple(vol.resolution()) != (h_cols, h_rows, 1):
        raise ValueError(f"Volume resolution {vol.resolution()} does not match (h_cols={h_cols}, h_rows={h_rows}, 1)")
    half_x = float(h_cols) * SPACING * 0.5
    half_z = float(h_rows) * SPACING * 0.5
    mat = hou.Matrix4((
        (half_x, 0.0, 0.0, 0.0),
        (0.0, 0.0, -half_z, 0.0),
        (0.0, 0.25, 0.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    ))
    vol.setTransform(mat)
    cx = 0.5 * (win["halo_first_world_xyz"][0] + win["halo_last_world_xyz"][0])
    cz = 0.5 * (win["halo_first_world_xyz"][2] + win["halo_last_world_xyz"][2])
    vol.vertex(0).point().setPosition(hou.Vector3((cx, 0.0, cz)))
    after_first = vol.indexToPos((0, 0, 0))
    after_last = vol.indexToPos((h_cols - 1, h_rows - 1, 0))
    step_x = vol.indexToPos((1, 0, 0)) - after_first
    step_z = vol.indexToPos((0, 1, 0)) - after_first
    if abs(float(step_x[0]) - SPACING) > 1e-4 or abs(float(step_z[2]) - (-SPACING)) > 1e-4:
        raise ValueError(f"Volume axis steps {step_x}, {step_z} do not match Stage1 (+0.5 X, -0.5 Z)")
    if max(abs(float(a) - float(b)) for a, b in zip(after_first, win["halo_first_world_xyz"])) > 0.01:
        raise ValueError(f"Halo first voxel world mismatch: {after_first} vs {win['halo_first_world_xyz']}")
    if max(abs(float(a) - float(b)) for a, b in zip(after_last, win["halo_last_world_xyz"])) > 0.01:
        raise ValueError(f"Halo last voxel world mismatch: {after_last} vs {win['halo_last_world_xyz']}")


def cook_tile_worker(tx: int, ty: int, core: int, halo: int, token: str, neutral_cliff: bool = True) -> dict:
    import hou
    import numpy as np

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.ue.lesson06_memory_guard import require_headroom

    if hou.isUIAvailable() or tuple(hou.applicationVersion()) != (22, 0, 466):
        raise ValueError("Requires fresh headless Houdini 22.0.466")
    verify_protected_sources()
    mat_files, mat_hashes = load_cc0_material_files()
    win = compute_tile_window(tx, ty, core=core, halo=halo)
    out_dir = OUTPUT_ROOT / token / "tiles"
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = out_dir / f"tile_{tx}_{ty}_receipt.json"
    if receipt_path.exists():
        return json.loads(receipt_path.read_text(encoding="utf-8"))

    t0 = time.monotonic()
    print(f"=== [TILE {tx},{ty}] Extracting halo inputs {win['halo_window']} ({win['halo_shape']}) ===", flush=True)
    npz_in = extract_tile_inputs(win, out_dir, hou, np)
    print(f"  [tile {tx},{ty}] Extracted inputs in {time.monotonic()-t0:.2f}s", flush=True)
    with np.load(npz_in, allow_pickle=False) as archive:
        arrays = {k: np.array(archive[k], dtype="<f4", copy=True) for k in archive.files}
    npz_in.unlink(missing_ok=True)

    h_rows, h_cols = win["halo_shape"]
    orig_height_sha = hashlib.sha256(arrays["height"].tobytes()).hexdigest()
    orig_alpha_sha = hashlib.sha256(arrays["Alpha"].tobytes()).hexdigest()

    hou.hda.installFile(str(MAT_HDA), force_use_assets=True)
    hou.hda.installFile(str(TINT_HDA), force_use_assets=True)

    obj = hou.node("/obj").createNode("geo", f"TILE_{tx}_{ty}")
    try:
        for child in obj.children():
            child.destroy()
        hf = obj.createNode("heightfield", "BASE_HF")
        hf.setParms({
            "sizex": float(h_rows) * SPACING,
            "sizey": float(h_cols) * SPACING,
            "gridspacing": SPACING,
        })
        hf.cook(force=True)
        base_geo = hou.Geometry(hf.geometry())
        for p in base_geo.prims():
            if isinstance(p, hou.Volume) and p.attribValue("name") in ("height", "mask"):
                if tuple(p.resolution()) != (h_cols, h_rows, 1):
                    raise ValueError(f"Unexpected HF resolution {p.resolution()} vs {(h_cols, h_rows, 1)}")
                align_volume_to_window(p, win, hou)
                p.setAllVoxelsFromString(arrays[p.attribValue("name")].tobytes())

        base_bgeo = out_dir / f"tile_{tx}_{ty}_base_work.bgeo.sc"
        base_geo.saveToFile(str(base_bgeo))
        del base_geo
        gc.collect()

        base_file_node = obj.createNode("file", "BASE_FILE")
        base_file_node.parm("file").set(str(base_bgeo))
        temp_files = [base_bgeo]

        def make_mask_input_node(mask_arr, name_tag: str):
            mp = out_dir / f"tile_{tx}_{ty}_mask_{name_tag}.bgeo.sc"
            mg = hou.Geometry(base_file_node.geometry())
            vols = {p.attribValue("name"): p for p in mg.prims() if isinstance(p, hou.Volume)}
            mg.deletePrims([p for n, p in vols.items() if n != "mask"], True)
            mv = next(p for p in mg.prims() if isinstance(p, hou.Volume))
            mv.setAllVoxelsFromString(mask_arr.tobytes())
            mg.saveToFile(str(mp))
            temp_files.append(mp)
            fnode = obj.createNode("file", f"MASK_FILE_{name_tag.upper()}")
            fnode.parm("file").set(str(mp))
            return fnode

        ox0, oy0, ox1, oy1 = win["core_offset_in_halo"]
        id_u8 = compute_five_class_id_u8(
            arrays["grass_mask"][oy0:oy1, ox0:ox1],
            arrays["ramp_layer"][oy0:oy1, ox0:ox1],
            arrays["sand_mask"][oy0:oy1, ox0:ox1],
            arrays["cliff_mask"][oy0:oy1, ox0:ox1],
            arrays["scree_mask"][oy0:oy1, ox0:ox1],
            np,
        )
        mask_nodes = {}
        for mkey in ("grass_mask", "sand_mask", "cliff_mask", "ramp_layer", "scree_mask"):
            mask_nodes[mkey] = make_mask_input_node(arrays[mkey], mkey)
            del arrays[mkey]
        del arrays["mask"]
        gc.collect()

        prev_node = base_file_node

        for role, slug, mask_key, size, use_mask in ROLES:
            require_headroom(gib=30)
            if mask_key is None:
                mask_node = base_file_node
            else:
                mask_node = mask_nodes[mask_key]
            mat = obj.createNode("PE_heightfield_material::1.0", f"MAT_{role.upper()}")
            mat.setInput(0, prev_node)
            mat.setInput(1, mask_node)
            use_curl = role == "grass"
            parms = {
                **mat_files[role],
                "size": size,
                "heightscale": 0.0,
                "use_mask": int(use_mask),
                "srcname1": "mask",
                "input2": "2",
                "use_distort": 1 if use_curl else 0,
            }
            if use_curl:
                parms.update({
                    "noisetype": "curl",
                    "amp": 100.0,
                    "element_size": 100.0,
                    "element_scalex": 1.0,
                    "element_scaley": 1.0,
                    "element_scalez": 1.0,
                    "offsetx": 0.0,
                    "offsety": 0.0,
                    "offsetz": 0.0,
                })
            mat.setParms(parms)
            prev_node = mat

            tints_for_role = []
            if role == "grass":
                tints_for_role = [
                    ("grass_gradient", "ramp_layer", "gradient"),
                    ("grass_brightness", None, "brightness"),
                ]
            elif role == "cliff":
                tints_for_role = [("cliff", "cliff_mask", "solid_cliff")]
                if neutral_cliff:
                    tints_for_role.append(("cliff_neutral_yacs", "cliff_mask", "grade_cliff"))
            elif role == "scree":
                tints_for_role = [("scree", "scree_mask", "solid_scree")]

            for tname, tmask_key, tkind in tints_for_role:
                if tmask_key is None:
                    tmask_node = base_file_node
                else:
                    tmask_node = mask_nodes[tmask_key]
                tnode = obj.createNode("PE_heightfield_tint::1.0", f"TINT_{tname.upper()}")
                tnode.setInput(0, prev_node)
                tnode.setInput(1, tmask_node)
                tparms = {"srcname1": "mask", "strength": 1.0, "ramp_mask": "", "use_ramp": 0}
                if tkind == "gradient":
                    tparms.update({"use_ramp": 1, "strength": 0.95})
                elif tkind in ("solid_cliff", "solid_scree", "grade_cliff"):
                    tparms["ramp_mask"] = "mask"
                tnode.setParms(tparms)
                if tkind == "gradient":
                    ramp = hou.Ramp(
                        [hou.rampBasis.Linear] * 2,
                        [0.0, 0.996694],
                        [(0.34, 0.55, 0.12705), (1.0, 0.822741, 0.538)],
                    )
                    tnode.parm("tint_ramp").set(ramp)
                elif tkind == "brightness":
                    tnode.parmTuple("tint").set((2.0, 2.0, 2.0))
                elif tkind == "solid_cliff":
                    tnode.parmTuple("tint").set((0.597, 0.597, 0.597))
                elif tkind == "grade_cliff":
                    tnode.parmTuple("tint").set(GRADE_LIMESTONE_RGB)
                elif tkind == "solid_scree":
                    tnode.parmTuple("tint").set((0.874, 0.822347, 0.701822))
                prev_node = tnode

        # Exposure (Mask12 + Tint5) and Curvature (Mask13 + Tint6)
        from scripts.houdini.l07_exposure_curvature_canary import enum_by_label
        post_scree_node = prev_node
        t_exp = time.monotonic()
        vis4 = obj.createNode("heightfield_visualize", "VISUALIZE4")
        vis4.setInput(0, post_scree_node)
        enum_by_label(vis4.parm("updatetinting"), "Default Tinting")
        enum_by_label(vis4.parm("updatematerial"), "No Change")

        mask12 = obj.createNode("heightfield_maskbyfeature", "MASK12_EXPOSURE")
        mask12.setInput(0, vis4)
        mask12.setParms(EXPOSURE_MASK_PARMS)

        tint5 = obj.createNode("PE_heightfield_tint::1.0", "TINT5_EXPOSURE")
        tint5.setInput(0, post_scree_node)
        tint5.setInput(1, mask12)
        tint5.setParms({"use_ramp": 1, "strength": 1.0, "ramp_mask": "", "srcname1": "mask"})
        tint5.parm("tint_ramp").set(
            hou.Ramp(
                [hou.rampBasis.Linear] * len(EXPOSURE_CANDIDATE),
                [p for p, _ in EXPOSURE_CANDIDATE],
                [c for _, c in EXPOSURE_CANDIDATE],
            )
        )
        after_tint5 = tint5

        mask13 = obj.createNode("heightfield_maskbyfeature", "MASK13_CURVATURE")
        mask13.setInput(0, mask12)
        mask13.setParms(CURVATURE_MASK_PARMS)

        tint6 = obj.createNode("PE_heightfield_tint::1.0", "TINT6_CURVATURE")
        tint6.setInput(0, after_tint5)
        tint6.setInput(1, mask13)
        tint6.setParms({"use_ramp": 1, "strength": 0.613, "ramp_mask": "", "srcname1": "mask"})
        tint6.parm("tint_ramp").set(
            hou.Ramp(
                [hou.rampBasis.Linear] * len(CURVATURE_CANDIDATE),
                [p for p, _ in CURVATURE_CANDIDATE],
                [c for _, c in CURVATURE_CANDIDATE],
            )
        )
        final_node = tint6
        print(f"  [tile {tx},{ty}] Cooking full graph to final_node...", flush=True)
        final_node.cook(force=True)
        print(f"  [tile {tx},{ty}] Cooked full graph in {time.monotonic()-t_exp:.2f}s", flush=True)
        if final_node.errors():
            raise ValueError(f"Final graph errors on tile ({tx},{ty}): {final_node.errors()}")

        final_geo = final_node.geometry()
        final_vols = {p.attribValue("name"): p for p in final_geo.prims() if isinstance(p, hou.Volume)}
        h_final = np.frombuffer(final_vols["height"].allVoxelsAsString(), dtype="<f4").reshape((h_rows, h_cols))
        max_h_drift = float(np.max(np.abs(h_final.astype(np.float64) - arrays["height"].astype(np.float64))))
        if max_h_drift > 1e-3:
            raise ValueError(f"Final height drift {max_h_drift} exceeds 1mm bound")
        ox0, oy0, ox1, oy1 = win["core_offset_in_halo"]

        r_halo = np.frombuffer(final_vols["r"].allVoxelsAsString(), dtype="<f4").reshape((h_rows, h_cols))
        g_halo = np.frombuffer(final_vols["g"].allVoxelsAsString(), dtype="<f4").reshape((h_rows, h_cols))
        b_halo = np.frombuffer(final_vols["b"].allVoxelsAsString(), dtype="<f4").reshape((h_rows, h_cols))

        r_core = np.array(r_halo[oy0:oy1, ox0:ox1], dtype="<f4", copy=True)
        g_core = np.array(g_halo[oy0:oy1, ox0:ox1], dtype="<f4", copy=True)
        b_core = np.array(b_halo[oy0:oy1, ox0:ox1], dtype="<f4", copy=True)
        rgb_core_lin = np.stack([r_core, g_core, b_core], axis=-1)
        if not np.isfinite(rgb_core_lin).all():
            raise ValueError(f"Nonfinite RGB in core tile ({tx},{ty})")

        rgb_u8 = linear_to_srgb_u8(rgb_core_lin, np)
        alpha_core = np.array(arrays["Alpha"][oy0:oy1, ox0:ox1], dtype="<f4", copy=True)
        height_core = np.array(arrays["height"][oy0:oy1, ox0:ox1], dtype="<f4", copy=True)

        valid_mask = alpha_core > 0.5
        black_valid = int(np.count_nonzero(valid_mask & np.all(rgb_core_lin <= 1e-6, axis=-1)))
        if black_valid != 0:
            raise ValueError(f"Tile ({tx},{ty}) has {black_valid} black valid pixels!")

        core_npz = out_dir / f"tile_{tx}_{ty}_core.npz"
        with core_npz.open("wb") as f:
            np.savez_compressed(
                f,
                rgb_u8=rgb_u8,
                id_u8=id_u8,
                r_edge_right=r_core[:, -1],
                r_edge_left=r_core[:, 0],
                r_edge_top=r_core[0, :],
                r_edge_bottom=r_core[-1, :],
                h_edge_right=height_core[:, -1],
                h_edge_left=height_core[:, 0],
                h_edge_top=height_core[0, :],
                h_edge_bottom=height_core[-1, :],
                a_edge_right=alpha_core[:, -1],
                a_edge_left=alpha_core[:, 0],
                a_edge_top=alpha_core[0, :],
                a_edge_bottom=alpha_core[-1, :],
            )

        for tf in temp_files:
            tf.unlink(missing_ok=True)

        unique_ids, id_counts = np.unique(id_u8, return_counts=True)
        receipt = {
            "status": "TILE_COOKED_AND_VERIFIED",
            "tx": tx,
            "ty": ty,
            "window": win,
            "core_npz": str(core_npz),
            "core_npz_sha256": sha256(core_npz),
            "orig_halo_height_sha256": orig_height_sha,
            "orig_halo_alpha_sha256": orig_alpha_sha,
            "valid_alpha_count": int(np.count_nonzero(valid_mask)),
            "black_valid_rgb_pixels": black_valid,
            "mean_linear_rgb": [float(r_core.mean()), float(g_core.mean()), float(b_core.mean())],
            "mean_srgb_u8": [float(rgb_u8[..., 0].mean()), float(rgb_u8[..., 1].mean()), float(rgb_u8[..., 2].mean())],
            "id_distribution_u8": {int(k): int(v) for k, v in zip(unique_ids, id_counts)},
            "neutral_cliff_grade_yacs_adaptation": bool(neutral_cliff),
            "elapsed_sec": time.monotonic() - t0,
        }
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        return receipt
    finally:
        obj.destroy()


def assemble_and_export_full_maps(token: str, core: int, halo: int) -> dict:
    import numpy as np
    import OpenImageIO as oi

    ntiles = GRID // core
    out_root = OUTPUT_ROOT / token
    tiles_dir = out_root / "tiles"
    receipts = []
    color_img = np.zeros((GRID, GRID, 3), dtype=np.uint8)
    id_img = np.zeros((GRID, GRID), dtype=np.uint8)
    edge_data = {}

    for ty in range(ntiles):
        for tx in range(ntiles):
            r_path = tiles_dir / f"tile_{tx}_{ty}_receipt.json"
            if not r_path.is_file():
                raise ValueError(f"Missing tile receipt: {r_path}")
            r = json.loads(r_path.read_text(encoding="utf-8"))
            receipts.append(r)
            c_npz = Path(r["core_npz"])
            if sha256(c_npz) != r["core_npz_sha256"]:
                raise ValueError(f"Core NPZ hash mismatch for tile ({tx},{ty})")
            with np.load(c_npz, allow_pickle=False) as arch:
                rgb_u8 = arch["rgb_u8"]
                id_u8 = arch["id_u8"]
                edge_data[(tx, ty)] = {k: arch[k].copy() for k in arch.files if k not in ("rgb_u8", "id_u8")}

            cx0, cy0, cx1, cy1 = r["window"]["core"]
            # In Houdini heightfield_output flip1: voxel y=0 (Z=+3999.75, North) -> image row 15999 - y
            # Wait: let's match cook_and_verify_lesson07_exports.py lines 199-202:
            # b0 = 16000 - y1, b1 = 16000 - y0, raw_flipped = np.flipud(raw[b0:b1, :])
            # That means full image is np.flipud(raw_16000x16000)!
            # So voxel row `y` (in `cy0..cy1`) maps to image row `15999 - y`, i.e. slice `[16000 - cy1 : 16000 - cy0]` with `np.flipud`!
            img_y0 = GRID - cy1
            img_y1 = GRID - cy0
            color_img[img_y0:img_y1, cx0:cx1, :] = np.flipud(rgb_u8)
            id_img[img_y0:img_y1, cx0:cx1] = np.flipud(id_u8)

    # Seam verification between adjacent core tiles
    seam_checks = []
    for ty in range(ntiles):
        for tx in range(ntiles):
            if tx + 1 < ntiles:
                h_diff = float(np.max(np.abs(edge_data[(tx, ty)]["h_edge_right"] - edge_data[(tx + 1, ty)]["h_edge_left"])))
                r_diff = float(np.max(np.abs(edge_data[(tx, ty)]["r_edge_right"] - edge_data[(tx + 1, ty)]["r_edge_left"])))
                seam_checks.append({"pair": f"({tx},{ty})-({tx+1},{ty})", "axis": "X", "height_diff_m": h_diff, "rgb_r_adjacent_diff": r_diff})
            if ty + 1 < ntiles:
                h_diff = float(np.max(np.abs(edge_data[(tx, ty)]["h_edge_bottom"] - edge_data[(tx, ty + 1)]["h_edge_top"])))
                r_diff = float(np.max(np.abs(edge_data[(tx, ty)]["r_edge_bottom"] - edge_data[(tx, ty + 1)]["r_edge_top"])))
                seam_checks.append({"pair": f"({tx},{ty})-({tx},{ty+1})", "axis": "Z", "height_diff_m": h_diff, "rgb_r_adjacent_diff": r_diff})

    color_png = out_root / "T_PE_Terrain_Color.png"
    idmap_png = out_root / "T_PE_Terrain_IDMap.png"

    color_contig = np.ascontiguousarray(color_img)
    spec_col = oi.ImageSpec(GRID, GRID, 3, oi.UINT8)
    out_c = oi.ImageOutput.create(str(color_png))
    out_c.open(str(color_png), spec_col)
    for y0 in range(0, GRID, 500):
        out_c.write_scanlines(y0, y0 + 500, 0, color_contig[y0:y0 + 500])
    out_c.close()

    id_contig = np.ascontiguousarray(id_img[:, :, None])
    spec_id = oi.ImageSpec(GRID, GRID, 1, oi.UINT8)
    out_i = oi.ImageOutput.create(str(idmap_png))
    out_i.open(str(idmap_png), spec_id)
    for y0 in range(0, GRID, 500):
        out_i.write_scanlines(y0, y0 + 500, 0, id_contig[y0:y0 + 500])
    out_i.close()

    # Reopen and verify exported 16K PNGs
    in_c = oi.ImageInput.open(str(color_png))
    sc = in_c.spec()
    in_c.close()
    if (sc.width, sc.height, sc.nchannels) != (GRID, GRID, 3):
        raise ValueError("Reopened T_PE_Terrain_Color.png has wrong dimensions/channels")

    in_i = oi.ImageInput.open(str(idmap_png))
    si = in_i.spec()
    if (si.width, si.height, si.nchannels) != (GRID, GRID, 1):
        in_i.close()
        raise ValueError("Reopened T_PE_Terrain_IDMap.png has wrong dimensions/channels")
    code_dist = {}
    for y0 in range(0, GRID, 1000):
        chunk = in_i.read_scanlines(y0, y0 + 1000, 0, 0, 1, oi.UINT8).reshape((1000, GRID))
        if not np.array_equal(chunk, id_img[y0:y0 + 1000]):
            in_i.close()
            raise ValueError(f"Reopened IDMap scanlines {y0}..{y0+1000} do not match assembled ID array")
        u_codes, u_counts = np.unique(chunk, return_counts=True)
        for k, v in zip(u_codes, u_counts):
            code_dist[int(k)] = code_dist.get(int(k), 0) + int(v)
    in_i.close()
    if set(code_dist) != {0, 64, 128, 191, 255}:
        raise ValueError(f"Unexpected IDMap 8-bit class codes: {sorted(code_dist)}")

    # Also write 2000x2000 diagnostic overviews for immediate visual verification
    CLASS_COLORS = {
        0: (64, 140, 38),
        64: (217, 217, 38),
        128: (230, 191, 115),
        191: (102, 89, 77),
        255: (255, 255, 255),
    }
    sub_col = np.ascontiguousarray(color_img[::8, ::8, :])
    diag_col_png = out_root / "diagnostic_global_color_overview_2k.png"
    oc2 = oi.ImageOutput.create(str(diag_col_png))
    oc2.open(str(diag_col_png), oi.ImageSpec(2000, 2000, 3, oi.UINT8))
    oc2.write_image(sub_col)
    oc2.close()

    sub_id = id_img[::8, ::8]
    rgb_id_2k = np.zeros((2000, 2000, 3), dtype=np.uint8)
    for code, col in CLASS_COLORS.items():
        rgb_id_2k[sub_id == code] = col
    diag_id_png = out_root / "diagnostic_idmap_overview_2k.png"
    oi2 = oi.ImageOutput.create(str(diag_id_png))
    oi2.open(str(diag_id_png), oi.ImageSpec(2000, 2000, 3, oi.UINT8))
    oi2.write_image(np.ascontiguousarray(rgb_id_2k))
    oi2.close()

    f4_manifest = {
        "schema_version": 1,
        "status": "FULL_DOMAIN_16000x16000_HOUDINI_PRODUCER_PASS",
        "run_token": token,
        "grid_resolution": [GRID, GRID, 1],
        "core_tile_size": core,
        "halo_voxels": halo,
        "halo_meters": halo * SPACING,
        "occlusion_view_distance_m": 145.0,
        "halo_exceeds_occlusion_radius": (halo * SPACING) >= 145.0,
        "tile_count": len(receipts),
        "coverage_samples": sum(core * core for _ in receipts),
        "coverage_percent": 100.0,
        "total_black_valid_rgb_pixels": sum(r["black_valid_rgb_pixels"] for r in receipts),
        "seam_checks": seam_checks,
        "tiles": receipts,
        "source_stage1_sha256": STAGE_SPECS["stage1_base"]["sha256"],
        "source_stage2_sha256": STAGE_SPECS["stage2_masks"]["sha256"],
        "source_stage3_sha256": STAGE_SPECS["stage3_scree"]["sha256"],
        "original_material_hda_sha256": MAT_HDA_SHA,
        "original_tint_hda_sha256": TINT_HDA_SHA,
        "protected_sources_unchanged": True,
    }
    f4_path = out_root / "f4-full-domain-tiles.json"
    f4_path.write_text(json.dumps(f4_manifest, indent=2) + "\n", encoding="utf-8")

    f5_manifest = {
        "schema_version": 1,
        "status": "FULL_DOMAIN_16000x16000_IDMAP_AND_COLOR_EXPORT_VERIFIED",
        "run_token": token,
        "color_png": {
            "path": str(color_png),
            "bytes": color_png.stat().st_size,
            "sha256": sha256(color_png),
            "width": GRID,
            "height": GRID,
            "channels": 3,
            "colorspace": "sRGB_IEC61966_2_1",
        },
        "idmap_png": {
            "path": str(idmap_png),
            "bytes": idmap_png.stat().st_size,
            "sha256": sha256(idmap_png),
            "width": GRID,
            "height": GRID,
            "channels": 1,
            "colorspace": "Linear_Grayscale_8bit",
            "class_code_distribution": code_dist,
        },
        "diagnostic_overviews": {
            "color_2k_png": str(diag_col_png),
            "color_2k_sha256": sha256(diag_col_png),
            "idmap_2k_png": str(diag_id_png),
            "idmap_2k_sha256": sha256(diag_id_png),
        },
    }
    f5_path = out_root / "f5-idmap-color-export-manifest.json"
    f5_path.write_text(json.dumps(f5_manifest, indent=2) + "\n", encoding="utf-8")
    return {"f4": str(f4_path), "f5": str(f5_path), "color_sha256": f5_manifest["color_png"]["sha256"], "idmap_sha256": f5_manifest["idmap_png"]["sha256"]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--token", required=True)
    p.add_argument("--core", type=int, default=DEFAULT_CORE)
    p.add_argument("--halo", type=int, default=DEFAULT_HALO)
    p.add_argument("--worker-tile", nargs=2, type=int, default=None, help="Internal: cook single (tx, ty) tile")
    p.add_argument("--assemble-only", action="store_true")
    p.add_argument("--no-neutral-cliff", action="store_true")
    args = p.parse_args()

    if not re.fullmatch(r"[0-9]{9,13}-[1-9][0-9]*", args.token):
        raise ValueError("Invalid run token")

    if args.worker_tile is not None:
        tx, ty = args.worker_tile
        res = cook_tile_worker(tx, ty, args.core, args.halo, args.token, neutral_cliff=not args.no_neutral_cliff)
        print(json.dumps({"status": res["status"], "tile": [tx, ty], "elapsed_sec": res["elapsed_sec"], "black": res["black_valid_rgb_pixels"]}), flush=True)
        return

    if not args.assemble_only:
        ntiles = GRID // args.core
        hython = Path(sys.executable)
        script = Path(__file__).resolve()
        for ty in range(ntiles):
            for tx in range(ntiles):
                cmd = [
                    str(hython),
                    "-B",
                    str(script),
                    "--token",
                    args.token,
                    "--core",
                    str(args.core),
                    "--halo",
                    str(args.halo),
                    "--worker-tile",
                    str(tx),
                    str(ty),
                ]
                if args.no_neutral_cliff:
                    cmd.append("--no-neutral-cliff")
                subprocess.run(cmd, check=True)

    summary = assemble_and_export_full_maps(args.token, args.core, args.halo)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()

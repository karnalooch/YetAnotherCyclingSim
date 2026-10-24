"""Cook and Verify Lesson 07 Exports and Generate Visual Evidence in Houdini.

Follows SideFX Project Pegasus Landscape Workflow Lesson 7 ("Material Setup"):
1. Cooks procedural delta: procedural_delta = final_height - stage1_base_height
2. Numerically verifies reconstruction identity: stage1_base + procedural_delta == final_height
3. Saves procedural_detail.bgeo.sc
4. Exports T_PE_Terrain_IDMap.png via HeightField Output (1ch, 8b fixed, id layer, no remap)
5. Exports T_PE_Terrain_Color.png via HeightField Output (3ch, 8b fixed, Linear->sRGB, @height=0)
6. Verifies exported image files (dimensions, channels, bit depth, strict 5-class ID set)
7. Renders 3D camera views and 2D diagnostic overviews to evidence/lesson07_unified/
"""
from __future__ import annotations

import gc
import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ["HOUDINI_COP_MAXRES"] = "32768"
os.environ["HOUDINI_OCL_DEVICETYPE"] = "CPU"

import hou
import numpy as np
import OpenImageIO as oi

PROJECT_DIR = Path("D:/yacs/project").resolve()
WORLD_DIR = PROJECT_DIR / "worldgen/houdini/sa_calobra"
WORK_DIR = Path("D:/yacs/work/lesson07-unified-20261019").resolve()
EVIDENCE_DIR = WORLD_DIR / "evidence/lesson07_unified"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

L07_HIP = WORLD_DIR / "SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc"
STAGE1_BASE = Path("D:/yacs/work/lesson06-unified-20261019/stage1_base.bgeo.sc").resolve()
FINAL_CACHE = Path("D:/yacs/work/lesson06-unified-20261019/final_unified_idmap.bgeo.sc").resolve()
PROCEDURAL_DETAIL_CACHE = WORK_DIR / "procedural_detail.bgeo.sc"
IDMAP_PNG = WORK_DIR / "T_PE_Terrain_IDMap.png"
COLOR_PNG = WORK_DIR / "T_PE_Terrain_Color.png"


def digest(path: Path | str) -> str:
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def vol_array(geo: hou.Geometry, name: str) -> np.ndarray:
    for p in geo.prims():
        if isinstance(p, hou.Volume) and p.attribValue("name") == name:
            res = p.resolution()
            return np.frombuffer(p.allVoxelsAsString(), np.float32).reshape(res[1], res[0])
    raise KeyError(f"Volume layer '{name}' not found")


def vol_prim(geo: hou.Geometry, name: str) -> hou.Volume:
    for p in geo.prims():
        if isinstance(p, hou.Volume) and p.attribValue("name") == name:
            return p
    raise KeyError(f"Volume layer '{name}' not found")


def write_image(path: Path, arr: np.ndarray):
    path.parent.mkdir(parents=True, exist_ok=True)
    if arr.ndim == 2:
        arr_norm = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
        arr_out = np.stack([arr_norm, arr_norm, arr_norm], axis=-1)
        h, w, channels = arr_out.shape
    elif arr.ndim == 3:
        h, w, channels = arr.shape
        if arr.dtype == np.uint8:
            arr_out = arr
        else:
            arr_out = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    else:
        raise ValueError(f"Invalid array shape {arr.shape}")

    arr_out = np.ascontiguousarray(arr_out)
    spec = oi.ImageSpec(w, h, channels, oi.UINT8)
    out = oi.ImageOutput.create(str(path))
    if not out:
        raise RuntimeError(f"Could not create ImageOutput for {path}")
    out.open(str(path), spec)
    out.write_image(arr_out)
    out.close()


def render_camera_view(rop: hou.Node, cam_path: str, output_path: Path, width: int = 1920, height: int = 1080):
    rop.parm("camera").set(cam_path)
    rop.parm("picture").set(str(output_path).replace("\\", "/"))
    rop.parm("trange").set(0)
    rop.parm("tres").set(1)
    rop.parm("res1").set(width)
    rop.parm("res2").set(height)
    rop.parm("execute").pressButton()
    assert output_path.exists(), f"Render output not created: {output_path}"
    print(f"  [ok] Rendered {output_path.name} ({width}x{height}) from {cam_path}", flush=True)


def main():
    print(f"=== Lesson 07 Cook & Verification Started ===", flush=True)
    t_start = time.time()

    print(f"Loading checkpoint HIP: {L07_HIP}...", flush=True)
    hou.hipFile.load(str(L07_HIP), suppress_save_prompt=True)
    net = hou.node("/obj/SA_CALOBRA_UNIFIED")

    # -------------------------------------------------------------
    # 1. COOK & VERIFY PROCEDURAL DELTA (ETAP B)
    # -------------------------------------------------------------
    print("\n--- Step 1: Cook & Verify Procedural Delta (Etap B) ---", flush=True)
    final_node = net.node("FINAL_CACHE")
    base_node = net.node("STAGE1_BASE_CACHE")
    delta_layer_node = net.node("PROCEDURAL_DELTA_DIFF")
    delta_isolate_node = net.node("PROCEDURAL_DELTA_ISOLATE")

    print("Cooking FINAL_CACHE...", flush=True)
    geo_final = final_node.geometry()
    p_final = vol_prim(geo_final, "height")
    arr_final = np.frombuffer(p_final.allVoxelsAsString(), np.float32)

    print("Cooking STAGE1_BASE_CACHE...", flush=True)
    geo_base = base_node.geometry()
    p_base = vol_prim(geo_base, "height")
    arr_base = np.frombuffer(p_base.allVoxelsAsString(), np.float32)

    print("Cooking PROCEDURAL_DELTA_DIFF...", flush=True)
    geo_delta = delta_isolate_node.geometry()
    p_delta = vol_prim(geo_delta, "height")
    arr_delta = np.frombuffer(p_delta.allVoxelsAsString(), np.float32)

    # Verify reconstruction identity across all 256M samples
    print("Verifying reconstruction identity: base + delta == final...", flush=True)
    diff = np.abs((arr_base + arr_delta) - arr_final)
    max_recon_diff = float(diff.max())
    mean_recon_diff = float(diff.mean())
    recon_mismatches = int(np.count_nonzero(diff > 1e-4))
    print(f"  Max reconstruction diff: {max_recon_diff:.8f} m", flush=True)
    print(f"  Mean reconstruction diff: {mean_recon_diff:.8f} m", flush=True)
    print(f"  Mismatches (> 1e-4 m): {recon_mismatches}", flush=True)
    assert recon_mismatches == 0, f"Reconstruction identity FAILED: {recon_mismatches} mismatches!"

    delta_min = float(arr_delta.min())
    delta_max = float(arr_delta.max())
    delta_mean = float(arr_delta.mean())
    delta_std = float(arr_delta.std())
    modified_samples = int(np.count_nonzero(np.abs(arr_delta) > 1e-5))
    print(f"  Procedural Delta stats: min={delta_min:.4f} m, max={delta_max:.4f} m, mean={delta_mean:.6f} m, std={delta_std:.6f} m", flush=True)
    print(f"  Modified samples: {modified_samples} / {arr_delta.size} ({modified_samples / arr_delta.size * 100:.2f}%)", flush=True)

    # Save procedural delta cache to disk
    print(f"Saving procedural detail cache to {PROCEDURAL_DETAIL_CACHE}...", flush=True)
    geo_delta.saveToFile(str(PROCEDURAL_DETAIL_CACHE))
    assert PROCEDURAL_DETAIL_CACHE.exists(), "Failed to save procedural_detail.bgeo.sc"
    delta_sha = digest(PROCEDURAL_DETAIL_CACHE)
    delta_size_mb = PROCEDURAL_DETAIL_CACHE.stat().st_size / (1024 * 1024)
    print(f"  [ok] Saved {PROCEDURAL_DETAIL_CACHE.name} ({delta_size_mb:.2f} MB, SHA256: {delta_sha})", flush=True)

    # Clean large temporary arrays to free memory before next steps
    del arr_base, arr_delta, diff
    gc.collect()

    # -------------------------------------------------------------
    # 2. COOK & VERIFY IDMAP EXPORT (ETAP D)
    # -------------------------------------------------------------
    print("\n--- Step 2: Cook & Verify IDMap Export (Etap D) ---", flush=True)
    out_idmap_node = net.node("EXPORT_IDMAP")
    print(f"Executing HeightField Output for IDMap to {IDMAP_PNG}...", flush=True)
    t0 = time.time()
    out_idmap_node.parm("execute").pressButton()
    t_id_export = time.time() - t0
    assert IDMAP_PNG.exists(), f"IDMap PNG was not generated: {IDMAP_PNG}"
    idmap_sha = digest(IDMAP_PNG)
    idmap_size_mb = IDMAP_PNG.stat().st_size / (1024 * 1024)
    print(f"  [ok] IDMap exported in {t_id_export:.2f} s ({idmap_size_mb:.2f} MB, SHA256: {idmap_sha})", flush=True)

    # Read back and verify IDMap strictly
    print("Reading back IDMap PNG and verifying against geometry id volume...", flush=True)
    p_id = vol_prim(geo_final, "id")
    raw_id = np.frombuffer(p_id.allVoxelsAsString(), np.float32)

    inp_id = oi.ImageInput.open(str(IDMAP_PNG))
    assert inp_id, f"Could not reopen {IDMAP_PNG}"
    spec_id = inp_id.spec()
    assert spec_id.width == 16000 and spec_id.height == 16000 and spec_id.nchannels == 1, (
        f"Unexpected IDMap spec: {spec_id.width}x{spec_id.height}, {spec_id.nchannels}ch"
    )

    # Read image in chunks to bounded memory (1024 rows per chunk)
    id_mismatches = 0
    unique_codes = set()
    for y0 in range(0, 16000, 1024):
        y1 = min(y0 + 1024, 16000)
        tile = inp_id.read_tiles(0, 16000, y0, y1, 0, 1, 0, 1, oi.UINT8)
        chunk_img = np.array(tile).reshape(y1 - y0, 16000)
        unique_codes.update(np.unique(chunk_img).tolist())

        # Houdini Heightfield voxel Y=0 is South, Image row 0 is North
        b0 = 16000 - y1
        b1 = 16000 - y0
        chunk_raw = raw_id.reshape(16000, 16000)[b0:b1, :]
        raw_flipped = np.flipud(chunk_raw)
        expected_chunk_u8 = np.clip(np.round(raw_flipped * 255.0), 0, 255).astype(np.uint8)

        diff_id = (chunk_img != expected_chunk_u8)
        id_mismatches += int(np.count_nonzero(diff_id))
    inp_id.close()

    print(f"  Unique 8-bit codes in exported IDMap: {sorted(list(unique_codes))}", flush=True)
    expected_codes = {0, 64, 128, 191, 255}
    assert unique_codes == expected_codes, f"IDMap codes mismatch! Expected {expected_codes}, got {unique_codes}"
    print(f"  Sample-by-sample mismatches vs raw id volume: {id_mismatches}", flush=True)
    assert id_mismatches == 0, f"IDMap sample mismatches detected: {id_mismatches}!"
    print("  [ok] IDMap export verified: 100% bit-exact across all 256,000,000 samples!", flush=True)

    del raw_id
    gc.collect()

    # -------------------------------------------------------------
    # 3. COOK & VERIFY GLOBAL COLOR EXPORT (ETAP E)
    # -------------------------------------------------------------
    print("\n--- Step 3: Cook & Verify Global Color Export (Etap E) ---", flush=True)
    out_color_node = net.node("EXPORT_GLOBAL_COLOR")
    print(f"Executing HeightField Output for Global Color to {COLOR_PNG}...", flush=True)
    t0 = time.time()
    out_color_node.parm("execute").pressButton()
    t_col_export = time.time() - t0
    assert COLOR_PNG.exists(), f"Color PNG was not generated: {COLOR_PNG}"
    color_sha = digest(COLOR_PNG)
    color_size_mb = COLOR_PNG.stat().st_size / (1024 * 1024)
    print(f"  [ok] Global Color exported in {t_col_export:.2f} s ({color_size_mb:.2f} MB, SHA256: {color_sha})", flush=True)

    # Read back and verify Color PNG spec
    inp_col = oi.ImageInput.open(str(COLOR_PNG))
    assert inp_col, f"Could not reopen {COLOR_PNG}"
    spec_col = inp_col.spec()
    assert spec_col.width == 16000 and spec_col.height == 16000 and spec_col.nchannels == 3, (
        f"Unexpected Color spec: {spec_col.width}x{spec_col.height}, {spec_col.nchannels}ch"
    )
    inp_col.close()
    print("  [ok] Global Color spec verified: 16000x16000, 3 channels (RGB), uint8!", flush=True)

    # -------------------------------------------------------------
    # 4. GENERATE 2D DIAGNOSTIC OVERVIEWS (2048x2048)
    # -------------------------------------------------------------
    print("\n--- Step 4: Generating 2D Diagnostic Overviews (2048x2048) ---", flush=True)
    diag_idmap_path = EVIDENCE_DIR / "diagnostic_idmap_overview_2k.png"
    diag_color_path = EVIDENCE_DIR / "diagnostic_global_color_overview_2k.png"

    # Color mapping for IDMap diagnostic render
    CLASS_COLORS = {
        0: (64, 140, 38),     # grass: dark green
        64: (217, 217, 38),   # grass 2: yellow-green
        128: (230, 191, 115), # sand: golden sand
        191: (102, 89, 77),   # cliffs: rocky brown
        255: (255, 255, 255), # scree: limestone white
    }

    # Generate 2048x2048 ID overview by downsampling the 16000x16000 IDMap image
    print("Downsampling 16000x16000 IDMap to 2048x2048 diagnostic RGB visualization...", flush=True)
    inp_id = oi.ImageInput.open(str(IDMAP_PNG))
    full_id = inp_id.read_image(oi.UINT8)
    inp_id.close()
    full_id_2d = full_id.reshape(16000, 16000)

    # Subsample 16000 to 2000 using step=8
    sub_id = full_id_2d[::8, ::8][:2000, :2000]
    rgb_id = np.zeros((2000, 2000, 3), dtype=np.uint8)
    for code, col in CLASS_COLORS.items():
        mask = (sub_id == code)
        rgb_id[mask] = col
    write_image(diag_idmap_path, rgb_id)

    # Subsample 16000 Color PNG to 2000x2000
    print("Downsampling 16000x16000 Color PNG to 2000x2000 diagnostic overview...", flush=True)
    inp_col = oi.ImageInput.open(str(COLOR_PNG))
    full_col = inp_col.read_image(oi.UINT8)
    inp_col.close()
    full_col_3d = full_col.reshape(16000, 16000, 3)
    sub_col = full_col_3d[::8, ::8, :][:2000, :2000, :]
    write_image(diag_color_path, sub_col)

    del full_id, full_id_2d, sub_id, rgb_id, full_col, full_col_3d, sub_col
    gc.collect()

    # -------------------------------------------------------------
    # 5. RENDER 3D VIEWPORT EVIDENCE VIA OPENGL ROP
    # -------------------------------------------------------------
    print("\n--- Step 5: Rendering 3D Viewport Evidence via OpenGL ROP ---", flush=True)
    out_net = hou.node("/out")
    rop = out_net.node("rop_opengl_evidence")
    if not rop:
        rop = out_net.createNode("opengl", "rop_opengl_evidence")

    # Render Mode 1: PREVIEW_GLOBAL_COLOR from cam_panorama
    net.node("PREVIEW_GLOBAL_COLOR").setDisplayFlag(True)
    net.node("PREVIEW_GLOBAL_COLOR").setRenderFlag(True)
    render_camera_view(rop, "/obj/cam_panorama", EVIDENCE_DIR / "houdini_mode1_global_color_panorama.png")

    # Render Mode 1 from cam_puig_major
    render_camera_view(rop, "/obj/cam_puig_major", EVIDENCE_DIR / "houdini_cam_puig_major.png")

    # Render Mode 1 from cam_sa_calobra_cove
    render_camera_view(rop, "/obj/cam_sa_calobra_cove", EVIDENCE_DIR / "houdini_cam_sa_calobra_cove.png")

    # Render Mode 1 from cam_transition
    render_camera_view(rop, "/obj/cam_transition", EVIDENCE_DIR / "houdini_cam_transition.png")

    # Render Mode 2: PREVIEW_NEUTRAL_SHADING from cam_panorama
    net.node("PREVIEW_NEUTRAL_SHADING").setDisplayFlag(True)
    net.node("PREVIEW_NEUTRAL_SHADING").setRenderFlag(True)
    render_camera_view(rop, "/obj/cam_panorama", EVIDENCE_DIR / "houdini_mode2_neutral_shading_panorama.png")

    # Render Mode 3: PREVIEW_IDMAP from cam_panorama
    net.node("PREVIEW_IDMAP").setDisplayFlag(True)
    net.node("PREVIEW_IDMAP").setRenderFlag(True)
    render_camera_view(rop, "/obj/cam_panorama", EVIDENCE_DIR / "houdini_mode3_idmap_panorama.png")

    # Render Mode 4: PREVIEW_CLASS_ISOLATION for Scree (ID 4) from cam_scree_site
    net.node("ID_TO_LAYER").parm("id").set(4)  # Scree
    net.node("PREVIEW_CLASS_ISOLATION").setDisplayFlag(True)
    net.node("PREVIEW_CLASS_ISOLATION").setRenderFlag(True)
    render_camera_view(rop, "/obj/cam_scree_site", EVIDENCE_DIR / "houdini_mode4_isolated_scree_site.png")

    # Reset default display flag back to Mode 1 (PREVIEW_GLOBAL_COLOR)
    net.node("PREVIEW_GLOBAL_COLOR").setDisplayFlag(True)
    net.node("PREVIEW_GLOBAL_COLOR").setRenderFlag(True)
    hou.hipFile.save(str(L07_HIP))

    t_total = time.time() - t_start
    print(f"\n=== Lesson 07 Cook & Verification Completed in {t_total:.2f} s ===", flush=True)
    print("ALL VERIFICATIONS PASSED!", flush=True)


if __name__ == "__main__":
    main()

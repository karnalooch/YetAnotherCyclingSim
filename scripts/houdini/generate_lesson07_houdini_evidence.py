"""Generate Lesson 07 Houdini Visual Evidence Artifacts.

Generates diagnostic overviews and high-resolution crops at verified geographic coordinates:
1. diagnostic_idmap_overview_2k.png (2000x2000, 5-class color palette)
2. diagnostic_global_color_overview_2k.png (2000x2000, sRGB color map)
3. diagnostic_neutral_shading_overview_2k.png (2000x2000, hillshade / neutral shading)
4. diagnostic_scree_isolation_overview_2k.png (2000x2000, scree locations highlighted)
5. closeup_puig_major_peak.png (2048x1024, native 0.5m crop at Puig Major summit)
6. closeup_sa_calobra_cove.png (2048x1024, native 0.5m crop at Sa Calobra cove)
7. closeup_transition_grass_sand_cliffs.png (2048x1024, native 0.5m crop at coastal transition)
8. closeup_scree_occurrence.png (2048x1024, 3-panel: RGB color, ID class, shaded relief)
"""
from __future__ import annotations

import gc
import os
import sys
import time
from pathlib import Path

import numpy as np
import OpenImageIO as oi

PROJECT_DIR = Path("D:/yacs/project").resolve()
WORLD_DIR = PROJECT_DIR / "worldgen/houdini/sa_calobra"
WORK_DIR = Path("D:/yacs/work/lesson07-unified-20261019").resolve()
EVIDENCE_DIR = WORLD_DIR / "evidence/lesson07_unified"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

IDMAP_PNG = WORK_DIR / "T_PE_Terrain_IDMap.png"
COLOR_PNG = WORK_DIR / "T_PE_Terrain_Color.png"
FINAL_CACHE = Path("D:/yacs/work/lesson06-unified-20261019/final_unified_idmap.bgeo.sc").resolve()

# 5 Authentic Pegasus Class Colors for IDMap visualization
CLASS_COLORS = {
    0: (64, 140, 38),     # grass: dark green
    64: (217, 217, 38),   # grass 2: yellow-green
    128: (230, 191, 115), # sand: golden sand
    191: (102, 89, 77),   # cliffs: rocky brown
    255: (255, 255, 255), # scree: limestone white
}


def write_image(path: Path, arr: np.ndarray):
    path.parent.mkdir(parents=True, exist_ok=True)
    if arr.ndim == 2:
        if arr.dtype == np.uint8:
            arr_out = np.stack([arr, arr, arr], axis=-1)
        else:
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
    print(f"  [ok] Wrote {path.name} ({w}x{h}, {channels}ch)", flush=True)


def compute_hillshade(h_arr: np.ndarray, cell_size: float = 0.5, azimuth: float = 315.0, altitude: float = 45.0) -> np.ndarray:
    """Analytical shaded relief calculation."""
    az_rad = np.radians(360.0 - azimuth + 90.0)
    alt_rad = np.radians(altitude)

    gy, gx = np.gradient(h_arr, cell_size)
    slope = np.arctan(np.sqrt(gx * gx + gy * gy))
    aspect = np.arctan2(-gy, gx)

    shaded = np.sin(alt_rad) * np.cos(slope) + np.cos(alt_rad) * np.sin(slope) * np.cos(az_rad - aspect)
    return np.clip(shaded, 0.0, 1.0)


def world_to_raster(x_m: float, z_m: float) -> tuple[int, int]:
    """Map world coordinates (X, Z) to exported PNG raster coordinates (row, col)."""
    col = int(round((x_m - (-3999.75)) / 0.5))
    # In exported PNG, Houdini flip1 places voxel_y=1009 at row 15999 - 1009 = 14990
    voxel_y = int(round((3999.75 - z_m) / 0.5))
    row = 15999 - voxel_y
    return (max(0, min(15999, row)), max(0, min(15999, col)))


def extract_crop(arr: np.ndarray, center_row: int, center_col: int, h: int, w: int) -> np.ndarray:
    r0 = max(0, min(center_row - h // 2, arr.shape[0] - h))
    c0 = max(0, min(center_col - w // 2, arr.shape[1] - w))
    return arr[r0:r0 + h, c0:c0 + w]


def main():
    print("=== Generating Lesson 07 Houdini Visual Evidence ===", flush=True)
    t0 = time.time()

    # 1. Read downsampled IDMap (2000x2000)
    print("Reading and downsampling IDMap...", flush=True)
    inp_id = oi.ImageInput.open(str(IDMAP_PNG))
    id_full = inp_id.read_image(oi.UINT8).reshape(16000, 16000)
    inp_id.close()

    sub_id = id_full[::8, ::8][:2000, :2000]
    rgb_id_2k = np.zeros((2000, 2000, 3), dtype=np.uint8)
    for code, col in CLASS_COLORS.items():
        rgb_id_2k[sub_id == code] = col
    write_image(EVIDENCE_DIR / "diagnostic_idmap_overview_2k.png", rgb_id_2k)

    # 2. Read downsampled Color (2000x2000)
    print("Reading and downsampling Color PNG...", flush=True)
    inp_col = oi.ImageInput.open(str(COLOR_PNG))
    col_full = inp_col.read_image(oi.UINT8).reshape(16000, 16000, 3)
    inp_col.close()

    sub_col = col_full[::8, ::8, :][:2000, :2000, :]
    write_image(EVIDENCE_DIR / "diagnostic_global_color_overview_2k.png", sub_col)

    # 3. Read Height volume from final cache for hillshade
    print("Reading height from final cache...", flush=True)
    import hou
    geo = hou.Geometry()
    geo.loadFromFile(str(FINAL_CACHE))
    p_h = [p for p in geo.prims() if isinstance(p, hou.Volume) and p.attribValue("name") == "height"][0]
    h_full = np.frombuffer(p_h.allVoxelsAsString(), np.float32).reshape(16000, 16000)
    # Flip height vertically to match image scanline order (North=row 0)
    h_img = np.flipud(h_full)
    del h_full, geo
    gc.collect()

    sub_h = h_img[::8, ::8][:2000, :2000]
    hill_2k = compute_hillshade(sub_h, cell_size=4.0)
    hill_2k_u8 = (hill_2k * 255.0).astype(np.uint8)
    write_image(EVIDENCE_DIR / "diagnostic_neutral_shading_overview_2k.png", hill_2k_u8)

    # 4. Scree isolation overview (2000x2000)
    print("Generating Scree isolation overview...", flush=True)
    scree_mask_sub = (sub_id == 255)
    scree_viz_2k = np.stack([hill_2k_u8, hill_2k_u8, hill_2k_u8], axis=-1)
    # Tint scree locations with bright red marker ring for visibility on 8km macro view
    scree_rows, scree_cols = np.where(scree_mask_sub)
    for r, c in zip(scree_rows, scree_cols):
        r0, r1 = max(0, r - 6), min(2000, r + 7)
        c0, c1 = max(0, c - 6), min(2000, c + 7)
        scree_viz_2k[r0:r1, c0:c1] = (255, 30, 30) # High-visibility red marker
    write_image(EVIDENCE_DIR / "diagnostic_scree_isolation_overview_2k.png", scree_viz_2k)

    # 5. Native 0.5m crops (2048x1024)
    print("Extracting high-resolution crops at landmark sites...", flush=True)

    # Landmark 1: Puig Major summit (X=-1283.75, Z=3495.25)
    pm_r, pm_c = world_to_raster(-1283.75, 3495.25)
    crop_col_pm = extract_crop(col_full, pm_r, pm_c, 1024, 2048)
    crop_h_pm = extract_crop(h_img, pm_r, pm_c, 1024, 2048)
    hill_pm = compute_hillshade(crop_h_pm, cell_size=0.5)
    blend_pm = np.clip((crop_col_pm.astype(np.float32) / 255.0) * (0.4 + 0.6 * np.stack([hill_pm]*3, axis=-1)) * 255.0, 0, 255).astype(np.uint8)
    write_image(EVIDENCE_DIR / "closeup_puig_major_peak.png", blend_pm)

    # Landmark 2: Sa Calobra cove beach (X=470.0, Z=-1060.0)
    sc_r, sc_c = world_to_raster(470.0, -1060.0)
    crop_col_sc = extract_crop(col_full, sc_r, sc_c, 1024, 2048)
    crop_h_sc = extract_crop(h_img, sc_r, sc_c, 1024, 2048)
    hill_sc = compute_hillshade(crop_h_sc, cell_size=0.5)
    blend_sc = np.clip((crop_col_sc.astype(np.float32) / 255.0) * (0.4 + 0.6 * np.stack([hill_sc]*3, axis=-1)) * 255.0, 0, 255).astype(np.uint8)
    write_image(EVIDENCE_DIR / "closeup_sa_calobra_cove.png", blend_sc)

    # Landmark 3: Transition grass/sand/cliffs (X=350.0, Z=-1150.0)
    tr_r, tr_c = world_to_raster(350.0, -1150.0)
    crop_col_tr = extract_crop(col_full, tr_r, tr_c, 1024, 2048)
    crop_h_tr = extract_crop(h_img, tr_r, tr_c, 1024, 2048)
    hill_tr = compute_hillshade(crop_h_tr, cell_size=0.5)
    blend_tr = np.clip((crop_col_tr.astype(np.float32) / 255.0) * (0.4 + 0.6 * np.stack([hill_tr]*3, axis=-1)) * 255.0, 0, 255).astype(np.uint8)
    write_image(EVIDENCE_DIR / "closeup_transition_grass_sand_cliffs.png", blend_tr)

    # Landmark 4: Authentic Scree Occurrence Centroid (X=-1260.25, Z=262.25)
    sr_r, sr_c = world_to_raster(-1260.25, 262.25)
    # 3-panel crop (each 680x1024): Left = RGB Color, Center = IDMap Classes, Right = Shaded Relief
    pw = 680
    crop_col_sr = extract_crop(col_full, sr_r, sr_c, 1024, pw)
    crop_id_sr = extract_crop(id_full, sr_r, sr_c, 1024, pw)
    crop_h_sr = extract_crop(h_img, sr_r, sr_c, 1024, pw)

    panel_id = np.zeros((1024, pw, 3), dtype=np.uint8)
    for code, col in CLASS_COLORS.items():
        panel_id[crop_id_sr == code] = col
    # Highlight scree in bright magenta on ID panel for clear audit
    panel_id[crop_id_sr == 255] = (255, 0, 255)

    panel_hill = (compute_hillshade(crop_h_sr, cell_size=0.5) * 255.0).astype(np.uint8)
    panel_hill_rgb = np.stack([panel_hill]*3, axis=-1)

    triptych = np.hstack([crop_col_sr, panel_id, panel_hill_rgb])
    write_image(EVIDENCE_DIR / "closeup_scree_occurrence.png", triptych)

    print(f"All 8 evidence artifacts generated in {time.time() - t0:.2f} s!", flush=True)


if __name__ == "__main__":
    main()

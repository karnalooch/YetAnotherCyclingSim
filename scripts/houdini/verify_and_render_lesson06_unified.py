"""Verification and Evidence Generation for Unified Sa Calobra Lesson 06.

Validates Invariants A, B, and C, and generates diagnostic rendering artifacts
demonstrating the single unified 16000x16000 (0.5m) terrain quality and complete
elimination of Working/Context boundary seams, streaks, and blur patches.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

# Ensure required environment variables
os.environ["HOUDINI_COP_MAXRES"] = "32768"
os.environ["HOUDINI_OCL_DEVICETYPE"] = "CPU"

import hou
import numpy as np
import OpenImageIO as oi

PROJECT_DIR = Path("D:/yacs/project").resolve()
WORLD_DIR = PROJECT_DIR / "worldgen/houdini/sa_calobra"
WORK_DIR = Path("D:/yacs/work/lesson06-unified-20261019").resolve()
EVIDENCE_DIR = WORLD_DIR / "evidence/lesson06_unified"
CHECKPOINT_HIP = WORLD_DIR / "SaCalobra_Pegasus_Lesson06_Unified_v001.hiplc"

CORPUS_OTLS = Path("C:/Users/akarn/OneDrive/Dokumenty/Codex/2026-10-16/referenced-chatgpt-conversation-this-is-an/outputs/Pegasus_Komplet/P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls").resolve()

NAMES = ["grass", "grass 2", "sand", "cliffs", "scree"]
ID_COLORS = {
    0: (64, 140, 38),     # grass: dark green
    1: (217, 217, 38),   # grass 2: yellowish green
    2: (230, 191, 115),  # sand: golden sand
    3: (102, 89, 77),    # cliffs: rocky brown
    4: (153, 153, 153),  # scree: neutral limestone grey
}


ID_CODES = [0, 64, 128, 191, 255]
ID_FLOATS = [c / 255.0 for c in ID_CODES]


def map_to_class_indices(arr: np.ndarray) -> np.ndarray:
    out = np.zeros(arr.shape, dtype=np.int32)
    for idx, target in enumerate(ID_FLOATS):
        out[np.isclose(arr, target, atol=0.03)] = idx
    return out


def digest(path: Path | str) -> str:
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def install_hdas():
    hdas = [
        WORLD_DIR / "otls/sop_PE_heightfield_material.1.0.hda",
        WORLD_DIR / "otls/sop_PE_heightfield_tint.1.0.hda",
        CORPUS_OTLS / "sop_PE_heightfield_layerslump.hda",
        WORLD_DIR / "otls/sop_PE_Heightfield_Layers_to_ID.2.0.hda",
        WORLD_DIR / "otls/lesson06_reviewed/sop_PE_heightield_idmap_layers.hda",
        WORLD_DIR / "otls/lesson06_reviewed/sop_PE_Heightfield_id_to_layer.hda"
    ]
    for h in hdas:
        assert h.exists(), f"Missing HDA: {h}"
        hou.hda.installFile(str(h), force_use_assets=True)


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
    print(f"Saved: {path} ({w}x{h}, {channels} channels)", flush=True)


# ==============================================================================
# INVARIANT VERIFICATION
# ==============================================================================
def verify_invariants():
    print("=== [VERIFICATION] CHECKING INVARIANTS A, B, C ===", flush=True)
    install_hdas()

    pre_cache_file = WORK_DIR / "pre_id_cache.bgeo.sc"
    idmap_file = WORK_DIR / "final_unified_idmap.bgeo.sc"

    assert pre_cache_file.exists(), f"Missing pre-ID cache: {pre_cache_file}"
    assert idmap_file.exists(), f"Missing IDMap cache: {idmap_file}"

    g_pre = hou.Geometry()
    g_pre.loadFromFile(str(pre_cache_file))

    g_id = hou.Geometry()
    g_id.loadFromFile(str(idmap_file))

    # --- INVARIANT A: Macro-relief preservation & Lattice ---
    print("\n--- Invariant A: Domain & Relief Audit ---", flush=True)
    p_h = vol_prim(g_id, "height")
    res = list(p_h.resolution())
    orig = list(p_h.indexToPos((0, 0, 0)))
    dx = list(p_h.indexToPos((1, 0, 0)) - p_h.indexToPos((0, 0, 0)))
    dy = list(p_h.indexToPos((0, 1, 0)) - p_h.indexToPos((0, 0, 0)))

    h_arr = vol_array(g_id, "height")
    h_min = float(h_arr.min())
    h_max = float(h_arr.max())
    h_mean = float(h_arr.mean(dtype=np.float64))

    print(f"Resolution: {res}")
    print(f"Origin: {orig}")
    print(f"Step X: {dx[0]:.4f}m, Step Y: {dy[2]:.4f}m")
    print(f"Elevation: min={h_min:.2f}m, max={h_max:.2f}m, mean={h_mean:.2f}m")

    assert res == [16000, 16000, 1], f"Expected 16000x16000, got {res}"
    np.testing.assert_allclose(orig, [-3999.75, 0.0, 3999.75], atol=0.01)
    np.testing.assert_allclose(dx[0], 0.5, atol=1e-4)
    np.testing.assert_allclose(dy[2], -0.5, atol=1e-4)
    # Peak Puig Major is ~1436.5m in raw DTM; must be within natural range [1430, 1445]
    assert 1430.0 <= h_max <= 1445.0, f"Peak elevation altered: {h_max}"

    # Check Alpha valid samples
    a_arr = vol_array(g_id, "Alpha") if "Alpha" in [p.attribValue("name") for p in g_id.prims()] else vol_array(g_pre, "Alpha")
    valid_samples = int(np.count_nonzero(a_arr > 0))
    valid_pct = valid_samples / a_arr.size * 100.0
    print(f"Valid Samples (Alpha > 0): {valid_samples:,} ({valid_pct:.2f}%)")
    assert valid_pct >= 95.0, f"Alpha coverage dropped below 95%: {valid_pct:.2f}%"

    # --- INVARIANT B: Pre-ID vs Post-ID Bit-Exactness ---
    print("\n--- Invariant B: Pre-ID vs Post-ID Equality ---", flush=True)
    shared_layers = ["height", "r", "g", "b"]
    diffs = {}
    for layer in shared_layers:
        arr_pre = vol_array(g_pre, layer)
        arr_post = vol_array(g_id, layer)
        max_diff = float(np.max(np.abs(arr_pre - arr_post)))
        diffs[layer] = max_diff
        print(f"Layer '{layer}' max absolute diff: {max_diff:.8f}")
        assert max_diff == 0.0, f"Invariant B VIOLATED: Layer '{layer}' altered by IDMap generation! max_diff={max_diff}"

    # --- INVARIANT C: Fresh Hython Process Decode & Coverage ---
    print("\n--- Invariant C: IDMap Decode and Class Distribution ---", flush=True)
    id_arr = vol_array(g_id, "id")
    id_indices = map_to_class_indices(id_arr)
    unique_indices, counts = np.unique(id_indices, return_counts=True)
    total_voxels = id_arr.size

    distribution = {}
    for u, c in zip(unique_indices, counts):
        name = NAMES[int(u)]
        pct = float(c / total_voxels * 100.0)
        code = ID_CODES[int(u)]
        distribution[name] = {"id": int(u), "code": code, "float_val": ID_FLOATS[int(u)], "count": int(c), "pct": pct}
        print(f"  ID {int(u)} (code={code:3d}, float={ID_FLOATS[int(u)]:.4f}) - {name:8s}: {int(c):10,d} voxels ({pct:5.2f}%)")

    # All 5 classes must have non-zero representation
    for name in NAMES:
        assert name in distribution, f"Class '{name}' missing in IDMap!"
        assert distribution[name]["count"] > 0, f"Class '{name}' has 0 samples!"

    # Verify ID_TO_LAYER decoder from checkpoint HIP
    print("\n--- Verifying Pegasus ID_TO_LAYER Decoder in Saved HIP ---", flush=True)
    hou.hipFile.load(str(CHECKPOINT_HIP), suppress_save_prompt=True)
    decoder = hou.node("/obj/SA_CALOBRA_UNIFIED/ID_TO_LAYER")
    assert decoder is not None, "ID_TO_LAYER node missing in checkpoint HIP"
    decoder.parm("srcname1").set("id")
    decoder.parm("dstname1").set("mask")

    for idx, name in enumerate(NAMES):
        code = ID_CODES[idx]
        decoder.parm("id_layer").set(str(code))
        decoder.cook(force=True)
        dec_arr = vol_array(decoder.geometry(), "mask")
        dec_count = int(np.count_nonzero(dec_arr > 0.5))
        expected_count = distribution[name]["count"]
        print(f"  Decoded '{name:8s}': {dec_count:10,d} samples (expected {expected_count:10,d})")
        assert dec_count == expected_count, f"Mismatch in decoded {name}: got {dec_count}, expected {expected_count}"

    print("\nALL INVARIANTS A, B, C PASSED SUCCESSFULLY!", flush=True)

    verification_receipt = {
        "status": "LESSON06_FULL_IDMAP_PASS",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "resolution": res,
        "origin": orig,
        "gridspacing": 0.5,
        "height_stats": {"min": h_min, "max": h_max, "mean": h_mean},
        "valid_samples_pct": valid_pct,
        "invariant_b_layer_diffs": diffs,
        "id_distribution": distribution,
        "pre_id_cache_sha256": digest(pre_cache_file),
        "final_unified_idmap_sha256": digest(idmap_file),
        "checkpoint_hip_sha256": digest(CHECKPOINT_HIP)
    }
    (WORK_DIR / "verification_receipt.json").write_text(json.dumps(verification_receipt, indent=2))
    return verification_receipt


# ==============================================================================
# EVIDENCE RENDERING
# ==============================================================================
def render_evidence():
    print("\n=== [EVIDENCE] GENERATING DIAGNOSTIC RENDERS ===", flush=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    g_id = hou.Geometry()
    g_id.loadFromFile(str(WORK_DIR / "final_unified_idmap.bgeo.sc"))

    r = vol_array(g_id, "r")
    g = vol_array(g_id, "g")
    b = vol_array(g_id, "b")
    id_arr = vol_array(g_id, "id")

    # Full RGB stack
    rgb_full = np.stack([r, g, b], axis=-1)

    # 1. Global Overview Downsampled 8x (2000x2000)
    print("Generating Global RGB Overview (2000x2000)...", flush=True)
    step = 8
    rgb_overview = rgb_full[::step, ::step, :]
    write_image(EVIDENCE_DIR / "global_rgb_overview.png", rgb_overview)

    # 2. Global IDMap Overview Downsampled 8x (2000x2000)
    print("Generating Global IDMap Overview (2000x2000)...", flush=True)
    id_down = map_to_class_indices(id_arr[::step, ::step])
    h_down, w_down = id_down.shape
    id_rgb = np.zeros((h_down, w_down, 3), dtype=np.float32)
    for id_val, color in ID_COLORS.items():
        mask = (id_down == id_val)
        id_rgb[mask, 0] = color[0] / 255.0
        id_rgb[mask, 1] = color[1] / 255.0
        id_rgb[mask, 2] = color[2] / 255.0
    write_image(EVIDENCE_DIR / "global_idmap_overview.png", id_rgb)

    # 3. Decoded Semantic Masks (2000x2000)
    for id_val, name in enumerate(NAMES):
        print(f"Generating Mask Overview for '{name}'...", flush=True)
        m_down = (id_down == id_val).astype(np.float32)
        safe_name = name.replace(" ", "_")
        write_image(EVIDENCE_DIR / f"decoded_mask_{safe_name}.png", m_down)

    # 4. High-Res Closeups (1024x1024 native 0.5m samples = 512m x 512m window)
    def render_native_crop(center_world_x: float, center_world_z: float, filename: str, label: str):
        ix = int(round((center_world_x - (-3999.75)) / 0.5))
        iy = int(round((3999.75 - center_world_z) / 0.5))

        half_w = 512
        x0 = max(0, ix - half_w)
        x1 = min(16000, ix + half_w)
        y0 = max(0, iy - half_w)
        y1 = min(16000, iy + half_w)

        crop_rgb = rgb_full[y0:y1, x0:x1, :]
        crop_id = map_to_class_indices(id_arr[y0:y1, x0:x1])

        crop_id_rgb = np.zeros_like(crop_rgb)
        for id_val, color in ID_COLORS.items():
            mask = (crop_id == id_val)
            crop_id_rgb[mask, 0] = color[0] / 255.0
            crop_id_rgb[mask, 1] = color[1] / 255.0
            crop_id_rgb[mask, 2] = color[2] / 255.0

        sbs = np.concatenate([crop_rgb, crop_id_rgb], axis=1)
        write_image(EVIDENCE_DIR / filename, sbs)
        print(f"Saved closeup '{label}' at ({center_world_x:.1f}, {center_world_z:.1f}) -> {filename}", flush=True)

    # Former Northern Seam (z ~ +1500m to +2500m on the old Working boundary)
    print("\nGenerating Detailed Closeups at Former Seam & Landmark Locations...", flush=True)
    render_native_crop(0.0, 2100.0, "closeup_former_north_seam.png", "Former North Seam (Z=+2100)")
    render_native_crop(0.0, -2100.0, "closeup_former_south_seam.png", "Former South Seam (Z=-2100)")
    render_native_crop(1100.0, -1800.0, "closeup_puig_major_peak.png", "Puig Major Summit Area")
    render_native_crop(-1200.0, 1400.0, "closeup_sa_calobra_cove.png", "Torrent de Pareis / Sa Calobra Cove")

    print("\nALL EVIDENCE RENDERS SUCCESSFULLY GENERATED!", flush=True)


def main():
    verify_invariants()
    render_evidence()


if __name__ == "__main__":
    main()

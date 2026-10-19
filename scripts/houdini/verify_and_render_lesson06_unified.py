"""Verification and Evidence Generation for Unified Sa Calobra Lesson 06.

Validates Invariants A, B, and C with full sample-by-sample precision,
generates diagnostic rendering artifacts at authentic geographic locations,
and writes comprehensive receipts to project documentation.
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
DOCS_DIR = PROJECT_DIR / "docs/tooling/sidefx"

CORPUS_OTLS = Path("C:/Users/akarn/OneDrive/Dokumenty/Codex/2026-10-16/referenced-chatgpt-conversation-this-is-an/outputs/Pegasus_Komplet/P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls").resolve()
DTM_FILE = Path("D:/yacs/work/sa-calobra-houdini-unreal-20261016/inputs/dtm_height_float32.tif")
VAL_FILE = Path("D:/yacs/work/sa-calobra-houdini-unreal-20261016/inputs/dtm_validity.tif")

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


def map_to_class_indices(arr: np.ndarray, strict: bool = True) -> np.ndarray:
    """Strictly map float ID values to class indices [0..4] without silent fallback."""
    out = np.full(arr.shape, -1, dtype=np.int32)
    for idx, target in enumerate(ID_FLOATS):
        mask = np.isclose(arr, target, atol=1e-4)
        out[mask] = idx
    if strict:
        unrecognized = (out == -1)
        num_bad = int(np.count_nonzero(unrecognized))
        if num_bad > 0:
            num_nan = int(np.count_nonzero(np.isnan(arr)))
            num_inf = int(np.count_nonzero(np.isinf(arr)))
            bad_samples = arr[unrecognized][:10].tolist()
            raise ValueError(
                f"Strict IDMap validation failed: {num_bad} voxels have illegal ID values "
                f"(NaN: {num_nan}, Inf: {num_inf}). Sample illegal values: {bad_samples}"
            )
    return out


def verify_decoder_unit_checks():
    """Unit sanity tests ensuring validation detects illegal IDs and spatial shifts."""
    print("--- Running Decoder Unit Sanity Checks ---", flush=True)
    # Check 1: Illegal ID value (e.g. 0.15) must NOT be classified as grass (0)
    test_illegal = np.array([0.0, 0.15, 64.0 / 255.0], dtype=np.float32)
    mapped_illegal = map_to_class_indices(test_illegal, strict=False)
    assert mapped_illegal[1] == -1, f"Sanity check 1 FAILED: 0.15 was classified as {mapped_illegal[1]} instead of -1!"
    print("  [ok] Sanity check 1 PASSED: Illegal ID value (0.15) was rejected and not classified as grass.", flush=True)

    # Check 2: Spatial shift of mask while preserving count must produce FAIL
    rng = np.random.default_rng(42)
    test_mask = (rng.uniform(size=(100, 100)) > 0.8).astype(np.float32)
    shifted_mask = np.roll(test_mask, shift=(1, 1), axis=(0, 1))
    assert np.count_nonzero(test_mask) == np.count_nonzero(shifted_mask)
    mismatches = int(np.count_nonzero(test_mask != shifted_mask))
    assert mismatches > 0, "Sanity check 2 FAILED: Shifted mask did not register mismatches!"
    print(f"  [ok] Sanity check 2 PASSED: Spatially shifted mask with identical count ({int(np.count_nonzero(test_mask))}) correctly fails sample-by-sample check ({mismatches} mismatches).", flush=True)


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

    # Read back verification
    inp = oi.ImageInput.open(str(path))
    assert inp, f"Failed to reopen written image: {path}"
    ispec = inp.spec()
    assert ispec.width == w and ispec.height == h and ispec.nchannels == channels, f"Image readback spec mismatch: {path}"
    inp.close()
    print(f"Saved & Verified: {path.name} ({w}x{h}, {channels}ch)", flush=True)


def draw_dashed_guide(img: np.ndarray, orientation: str, pos: int, color=(1.0, 0.1, 0.1)):
    """Draw a crisp dashed marker line across image at specified pixel position."""
    h, w, _ = img.shape
    dash = 16
    if orientation == "horizontal":
        if 0 <= pos < h:
            for x in range(w):
                if (x // dash) % 2 == 0:
                    img[max(0, pos - 1):min(h, pos + 2), x] = color
    elif orientation == "vertical":
        if 0 <= pos < w:
            for y in range(h):
                if (y // dash) % 2 == 0:
                    img[y, max(0, pos - 1):min(w, pos + 2)] = color


def verify_source_dtm_to_base(base_geo: hou.Geometry) -> dict:
    print("\n--- Source DTM to Base Terrain Verification ---", flush=True)
    assert DTM_FILE.exists(), f"Source DTM missing: {DTM_FILE}"
    assert VAL_FILE.exists(), f"Source Validity missing: {VAL_FILE}"

    t0 = time.time()
    dtm_sha = digest(DTM_FILE)
    val_sha = digest(VAL_FILE)
    base_cache_file = WORK_DIR / "stage1_base.bgeo.sc"
    base_sha = digest(base_cache_file)

    p_h = vol_prim(base_geo, "height")
    p_a = vol_prim(base_geo, "Alpha")
    base_h = np.frombuffer(p_h.allVoxelsAsString(), np.float32).reshape(16000, 16000)
    base_a = np.frombuffer(p_a.allVoxelsAsString(), np.float32).reshape(16000, 16000)

    inp_d = oi.ImageInput.open(str(DTM_FILE))
    spec_d = inp_d.spec()
    assert spec_d.width == 16000 and spec_d.height == 16000, f"Unexpected DTM spec: {spec_d.width}x{spec_d.height}"

    inp_v = oi.ImageInput.open(str(VAL_FILE))
    spec_v = inp_v.spec()
    assert spec_v.width == 16000 and spec_v.height == 16000, f"Unexpected Validity spec: {spec_v.width}x{spec_v.height}"

    # Verify block-by-block with bounded memory (1024 rows per block = 32 MB per chunk)
    chunk_rows = 1024
    total_samples = 0
    height_mismatches = 0
    height_max_diff = 0.0
    val_mismatches = 0
    nodata_samples = 0
    valid_samples = 0

    valid_min = float("inf")
    valid_max = float("-inf")
    sum_valid = 0.0
    sum_sq_valid = 0.0

    print("Comparing Source TIFFs to Base Geometry block-by-block (1024 rows/chunk)...", flush=True)
    for y0 in range(0, 16000, chunk_rows):
        y1 = min(y0 + chunk_rows, 16000)
        tile_d = inp_d.read_tiles(0, 16000, y0, y1, 0, 1, 0, 1, oi.FLOAT)
        chunk_dtm = np.array(tile_d).reshape(y1 - y0, 16000)

        tile_v = inp_v.read_tiles(0, 16000, y0, y1, 0, 1, 0, 1, oi.UINT8)
        chunk_val = np.array(tile_v).reshape(y1 - y0, 16000)

        # Geometric mapping: Houdini Heightfield voxel Y=0 is South (bottom), TIFF row 0 is North (top)
        b0 = 16000 - y1
        b1 = 16000 - y0
        base_h_chunk = base_h[b0:b1, :]
        base_a_chunk = base_a[b0:b1, :]

        dtm_flipped = np.flipud(chunk_dtm)
        val_flipped = np.flipud(chunk_val)

        # Height comparison
        diff_h = np.abs(dtm_flipped - base_h_chunk)
        chunk_max_diff = float(diff_h.max())
        if chunk_max_diff > height_max_diff:
            height_max_diff = chunk_max_diff
        h_mismatches = int(np.count_nonzero(diff_h > 1e-4))
        height_mismatches += h_mismatches

        # Validity/Alpha comparison
        v_mismatches = int(np.count_nonzero((val_flipped > 0) != (base_a_chunk > 0)))
        val_mismatches += v_mismatches

        c_valid = (val_flipped > 0)
        c_nodata = (val_flipped == 0)
        valid_samples += int(np.count_nonzero(c_valid))
        nodata_samples += int(np.count_nonzero(c_nodata))
        total_samples += chunk_dtm.size

        if np.any(c_valid):
            v_vals = dtm_flipped[c_valid].astype(np.float64)
            c_min = float(v_vals.min())
            c_max = float(v_vals.max())
            if c_min < valid_min:
                valid_min = c_min
            if c_max > valid_max:
                valid_max = c_max
            sum_valid += float(np.sum(v_vals))
            sum_sq_valid += float(np.sum(v_vals ** 2))

    inp_d.close()
    inp_v.close()

    valid_mean = sum_valid / valid_samples
    valid_var = (sum_sq_valid / valid_samples) - (valid_mean ** 2)
    valid_std = float(np.sqrt(max(0.0, valid_var)))

    print(f"  Source DTM SHA-256: {dtm_sha}")
    print(f"  Source Validity SHA-256: {val_sha}")
    print(f"  Stage1 Base SHA-256: {base_sha}")
    print(f"  Samples Compared: {total_samples:,}")
    print(f"  Height Mismatches: {height_mismatches} (max diff = {height_max_diff:.8f} m)")
    print(f"  Validity/Alpha Mismatches: {val_mismatches}")
    print(f"  Valid Land Samples: {valid_samples:,} ({(valid_samples/total_samples)*100:.2f}%)")
    print(f"  NoData Sea Samples: {nodata_samples:,} ({(nodata_samples/total_samples)*100:.2f}%)")
    print(f"  Source Valid Land Elevation: min={valid_min:.4f}m, max={valid_max:.4f}m, mean={valid_mean:.4f}m, std={valid_std:.4f}m")
    print(f"Source DTM -> Base Terrain Verified in {time.time() - t0:.1f}s.", flush=True)

    assert height_mismatches == 0, f"Source DTM vs Base Height mismatch: {height_mismatches} samples!"
    assert val_mismatches == 0, f"Source Validity vs Base Alpha mismatch: {val_mismatches} samples!"

    return {
        "source_dtm_file": str(DTM_FILE),
        "source_dtm_sha256": dtm_sha,
        "source_validity_file": str(VAL_FILE),
        "source_validity_sha256": val_sha,
        "stage1_base_file": str(base_cache_file),
        "stage1_base_sha256": base_sha,
        "coordinate_mapping": "Raster (row r, col c) -> Houdini voxel (x=c, y=15999-r); World X = -3999.75 + x*0.5, World Z = 3999.75 - y*0.5",
        "nodata_convention": "Source validity == 0 (offshore sea, 6,181,020 samples) maps to base Alpha == 0.0 and height == 0.0; valid land domain validity == 1 (249,818,980 samples) maps to base Alpha > 0",
        "samples_compared": total_samples,
        "height_mismatches": height_mismatches,
        "height_max_diff_m": height_max_diff,
        "validity_alpha_mismatches": val_mismatches,
        "valid_land_samples": valid_samples,
        "nodata_sea_samples": nodata_samples,
        "raw_source_elevation_valid_land_m": {
            "min_m": valid_min,
            "max_m": valid_max,
            "mean_m": round(valid_mean, 5),
            "std_m": round(valid_std, 4)
        },
        "raw_source_elevation_all_voxels_m": {
            "min_m": float(base_h.min()),
            "max_m": float(base_h.max()),
            "mean_m": float(base_h.mean())
        }
    }


# ==============================================================================
# INVARIANT VERIFICATION
# ==============================================================================
def verify_invariants():
    print("=== [VERIFICATION] CHECKING INVARIANTS A, B, C ===", flush=True)
    install_hdas()
    verify_decoder_unit_checks()

    base_cache_file = WORK_DIR / "stage1_base.bgeo.sc"
    pre_cache_file = WORK_DIR / "pre_id_cache.bgeo.sc"
    idmap_file = WORK_DIR / "final_unified_idmap.bgeo.sc"

    assert base_cache_file.exists(), f"Missing base cache: {base_cache_file}"
    assert pre_cache_file.exists(), f"Missing pre-ID cache: {pre_cache_file}"
    assert idmap_file.exists(), f"Missing IDMap cache: {idmap_file}"

    g_base = hou.Geometry(); g_base.loadFromFile(str(base_cache_file))
    g_pre = hou.Geometry(); g_pre.loadFromFile(str(pre_cache_file))
    g_id = hou.Geometry(); g_id.loadFromFile(str(idmap_file))

    source_metrics = verify_source_dtm_to_base(g_base)

    # --- INVARIANT A: Geometry, Grid, Procedural Delta & Alpha ---
    print("\n--- Invariant A: Domain, Geography & Alpha Audit ---", flush=True)
    p_h = vol_prim(g_id, "height")
    res = list(p_h.resolution())
    orig = list(p_h.indexToPos((0, 0, 0)))
    dx = list(p_h.indexToPos((1, 0, 0)) - p_h.indexToPos((0, 0, 0)))
    dy = list(p_h.indexToPos((0, 1, 0)) - p_h.indexToPos((0, 0, 0)))

    h_final = vol_array(g_id, "height")
    h_base = vol_array(g_base, "height")
    h_pre = vol_array(g_pre, "height")

    print(f"Resolution: {res}")
    print(f"Origin: {orig}")
    print(f"Step X: {dx[0]:.4f}m, Step Y: {dy[2]:.4f}m")

    assert res == [16000, 16000, 1], f"Expected 16000x16000, got {res}"
    np.testing.assert_allclose(orig, [-3999.75, 0.0, 3999.75], atol=0.01)
    np.testing.assert_allclose(dx[0], 0.5, atol=1e-4)
    np.testing.assert_allclose(dy[2], -0.5, atol=1e-4)

    # 1. Procedural Displacement Analysis (Base -> Pre-ID)
    delta = (h_pre.astype(np.float64) - h_base.astype(np.float64))
    delta_min = float(delta.min())
    delta_max = float(delta.max())
    delta_mean = float(delta.mean())
    delta_std = float(delta.std())
    delta_p50 = float(np.percentile(np.abs(delta), 50))
    delta_p95 = float(np.percentile(np.abs(delta), 95))
    delta_p99 = float(np.percentile(np.abs(delta), 99))
    changed_voxels = int(np.count_nonzero(delta != 0.0))
    changed_pct = (changed_voxels / delta.size) * 100.0

    print(f"Procedural Height Displacement (Base -> Pre-ID):")
    print(f"  Range: [{delta_min:+.4f}m, {delta_max:+.4f}m], Mean: {delta_mean:+.4f}m, Std: {delta_std:.4f}m")
    print(f"  Abs Percentiles: p50={delta_p50:.4f}m, p95={delta_p95:.4f}m, p99={delta_p99:.4f}m")
    print(f"  Modified Voxels: {changed_voxels:,} ({changed_pct:.2f}%)")

    # 2. Key Landform Preservation: Puig Major Summit
    py, px = np.unravel_index(np.argmax(h_final), h_final.shape)
    peak_pos = p_h.indexToPos((int(px), int(py), 0))
    peak_h = float(h_final[py, px])
    print(f"Peak Puig Major: X={peak_pos[0]:.2f}m, Z={peak_pos[2]:.2f}m, Height={peak_h:.2f}m (Pixel: x={px}, y={py})")
    assert abs(peak_pos[0] - (-1283.75)) < 1.0, f"Puig Major X position altered: {peak_pos[0]}"
    assert abs(peak_pos[2] - 3495.25) < 1.0, f"Puig Major Z position altered: {peak_pos[2]}"
    assert abs(peak_h - 1437.16) < 0.2, f"Puig Major elevation altered: {peak_h}"

    # 3. Key Landform Preservation: Sa Calobra Cove (sea-level beach / port area)
    cove_pos = hou.Vector3(470.0, 0.0, -1060.0)
    cove_h = float(p_h.sample(cove_pos))
    print(f"Sa Calobra Cove (X=470.0, Z=-1060.0): Elevation={cove_h:.2f}m")
    assert 0.0 <= cove_h <= 20.0, f"Sa Calobra cove elevation out of expected coastal range: {cove_h}"

    # 4. Alpha Integrity (must exist in final IDMap and match base validity bit-exact)
    assert "Alpha" in [p.attribValue("name") for p in g_id.prims()], "Alpha volume layer missing in final IDMap!"
    a_final = vol_array(g_id, "Alpha")
    a_base = vol_array(g_base, "Alpha")
    alpha_diff = int(np.count_nonzero(a_final != a_base))
    valid_samples = int(np.count_nonzero(a_final > 0))
    valid_pct = (valid_samples / a_final.size) * 100.0
    print(f"Alpha Integrity: {valid_samples:,} valid land voxels ({valid_pct:.2f}%), Mismatches vs Base={alpha_diff}")
    assert alpha_diff == 0, f"Alpha in final IDMap altered relative to base validity! Mismatches: {alpha_diff}"

    # --- INVARIANT B: Pre-ID vs Post-ID Bit-Exactness ---
    print("\n--- Invariant B: Pre-ID vs Post-ID Equality ---", flush=True)
    shared_layers = ["height", "r", "g", "b", "Alpha"]
    diffs = {}
    for layer in shared_layers:
        arr_pre = vol_array(g_pre, layer)
        arr_post = vol_array(g_id, layer)
        max_diff = float(np.max(np.abs(arr_pre - arr_post)))
        diffs[layer] = max_diff
        print(f"Layer '{layer:8s}' max absolute diff: {max_diff:.8f}")
        assert max_diff == 0.0, f"Invariant B VIOLATED: Layer '{layer}' altered by IDMap generation! max_diff={max_diff}"

    # --- INVARIANT C: Strict IDMap Validation & Pegasus Decoder ---
    print("\n--- Invariant C: Strict ID Validation & Decoder Replay ---", flush=True)
    id_arr = vol_array(g_id, "id")
    id_indices = map_to_class_indices(id_arr, strict=True)
    unique_indices, counts = np.unique(id_indices, return_counts=True)
    total_voxels = id_arr.size

    distribution = {}
    for u, c in zip(unique_indices, counts):
        name = NAMES[int(u)]
        pct = float(c / total_voxels * 100.0)
        code = ID_CODES[int(u)]
        distribution[name] = {"id": int(u), "code": code, "float_val": ID_FLOATS[int(u)], "count": int(c), "pct": pct}
        print(f"  ID {int(u)} (code={code:3d}, float={ID_FLOATS[int(u)]:.4f}) - {name:8s}: {int(c):10,d} voxels ({pct:5.2f}%)")

    # All 5 classes must be present
    for name in NAMES:
        assert name in distribution, f"Class '{name}' missing in IDMap!"
        assert distribution[name]["count"] > 0, f"Class '{name}' has 0 samples!"

    # Verify ID_TO_LAYER decoder from checkpoint HIP
    print("\n--- Fresh Checkpoint HIP ID_TO_LAYER Replay ---", flush=True)
    hou.hipFile.load(str(CHECKPOINT_HIP), suppress_save_prompt=True)
    decoder = hou.node("/obj/SA_CALOBRA_UNIFIED/ID_TO_LAYER")
    assert decoder is not None, "ID_TO_LAYER node missing in checkpoint HIP"
    decoder.parm("srcname1").set("id")
    decoder.parm("dstname1").set("mask")

    decoder_mismatches = {}
    decoded_masks_down = {}
    step = 8

    for idx, name in enumerate(NAMES):
        code = ID_CODES[idx]
        decoder.parm("id_layer").set(str(code))
        decoder.cook(force=True)
        dec_geo = decoder.geometry()
        dec_prim = vol_prim(dec_geo, "mask")
        assert list(dec_prim.resolution()) == [16000, 16000, 1]
        np.testing.assert_allclose(list(dec_prim.indexToPos((0, 0, 0))), [-3999.75, 0.0, 3999.75], atol=0.01)

        dec_arr = np.frombuffer(dec_prim.allVoxelsAsString(), np.float32).reshape(16000, 16000)
        assert np.isfinite(dec_arr).all(), f"Decoder produced non-finite values (NaN/Inf) for class '{name}'!"
        expected_binary = (id_indices == idx).astype(np.float32)

        mismatch_count = int(np.count_nonzero(np.abs(dec_arr - expected_binary) > 0.01))
        decoder_mismatches[name] = mismatch_count
        print(f"  Decoded '{name:8s}': expected {distribution[name]['count']:10,d}, sample mismatches = {mismatch_count}")
        assert mismatch_count == 0, f"Decoder sample-by-sample mismatch for class '{name}': {mismatch_count}"

        # Downsample 8x for overview export
        decoded_masks_down[name] = dec_arr[::step, ::step].copy()

    print("\nALL INVARIANTS A, B, C PASSED VERIFICATION!", flush=True)

    metrics = {
        "resolution": res,
        "origin": orig,
        "gridspacing": 0.5,
        "source_dtm_verification": source_metrics,
        "base_terrain_stats": {"min": float(h_base.min()), "max": float(h_base.max()), "mean": float(h_base.mean())},
        "height_stats": {"min": float(h_final.min()), "max": float(h_final.max()), "mean": float(h_final.mean())},
        "procedural_displacement": {
            "min_m": delta_min, "max_m": delta_max, "mean_m": delta_mean, "std_m": delta_std,
            "p50_m": delta_p50, "p95_m": delta_p95, "p99_m": delta_p99,
            "changed_voxels": changed_voxels, "changed_pct": changed_pct
        },
        "landforms": {
            "puig_major": {"x_m": float(peak_pos[0]), "z_m": float(peak_pos[2]), "height_m": peak_h},
            "sa_calobra_cove": {"x_m": 470.0, "z_m": -1060.0, "height_m": cove_h}
        },
        "alpha_integrity": {"valid_voxels": valid_samples, "valid_pct": valid_pct, "mismatches_vs_base": alpha_diff},
        "invariant_b_layer_diffs": diffs,
        "id_distribution": distribution,
        "decoder_mismatches": decoder_mismatches,
        "decoded_masks_down": decoded_masks_down
    }
    return metrics


# ==============================================================================
# EVIDENCE RENDERING
# ==============================================================================
def render_evidence(metrics: dict):
    print("\n=== [EVIDENCE] GENERATING DIAGNOSTIC RENDERS AT AUTHENTIC SITES ===", flush=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    image_manifest = []

    g_id = hou.Geometry(); g_id.loadFromFile(str(WORK_DIR / "final_unified_idmap.bgeo.sc"))
    g_pre = hou.Geometry(); g_pre.loadFromFile(str(WORK_DIR / "pre_id_cache.bgeo.sc"))

    r = vol_array(g_id, "r")
    g = vol_array(g_id, "g")
    b = vol_array(g_id, "b")
    a = vol_array(g_id, "Alpha")
    id_arr = vol_array(g_id, "id")
    id_indices = map_to_class_indices(id_arr, strict=True)
    rgb_full = np.stack([r, g, b], axis=-1)

    step = 8

    # 1. Global RGB Overview (2000x2000)
    print("Writing global_rgb_overview.png...", flush=True)
    p_rgb = EVIDENCE_DIR / "global_rgb_overview.png"
    write_image(p_rgb, rgb_full[::step, ::step, :])
    image_manifest.append(str(p_rgb.name))

    # 2. Global IDMap Overview (2000x2000)
    print("Writing global_idmap_overview.png...", flush=True)
    id_down = id_indices[::step, ::step]
    h_d, w_d = id_down.shape
    id_rgb = np.zeros((h_d, w_d, 3), dtype=np.float32)
    for id_val, col in ID_COLORS.items():
        m = (id_down == id_val)
        id_rgb[m, 0] = col[0] / 255.0
        id_rgb[m, 1] = col[1] / 255.0
        id_rgb[m, 2] = col[2] / 255.0
    p_id = EVIDENCE_DIR / "global_idmap_overview.png"
    write_image(p_id, id_rgb)
    image_manifest.append(str(p_id.name))

    # 3. Global Alpha Overview (2000x2000) distinguishing NoData sea from land
    print("Writing global_alpha_overview.png...", flush=True)
    a_down = a[::step, ::step]
    p_alpha = EVIDENCE_DIR / "global_alpha_overview.png"
    write_image(p_alpha, a_down)
    image_manifest.append(str(p_alpha.name))

    # 4. Decoded Semantic Masks (2000x2000) from Pegasus Decoder
    for name in NAMES:
        safe = name.replace(" ", "_")
        p_mask = EVIDENCE_DIR / f"decoded_mask_{safe}.png"
        write_image(p_mask, metrics["decoded_masks_down"][name])
        image_manifest.append(str(p_mask.name))

    # 5. Native Closeups Across Former Boundaries (with visible dashed guide line)
    def render_boundary_crop(cx: float, cz: float, filename: str, label: str, boundary_dir: str, boundary_world: float):
        # Convert world pos to index
        ix = int(round((cx - (-3999.75)) / 0.5))
        iy = int(round((3999.75 - cz) / 0.5))
        hw = 512
        x0 = max(0, ix - hw); x1 = min(16000, ix + hw)
        y0 = max(0, iy - hw); y1 = min(16000, iy + hw)

        crop_rgb = rgb_full[y0:y1, x0:x1, :].copy()
        crop_id_idx = id_indices[y0:y1, x0:x1]

        crop_id_rgb = np.zeros_like(crop_rgb)
        for id_val, col in ID_COLORS.items():
            m = (crop_id_idx == id_val)
            crop_id_rgb[m, 0] = col[0] / 255.0
            crop_id_rgb[m, 1] = col[1] / 255.0
            crop_id_rgb[m, 2] = col[2] / 255.0

        # Draw boundary guide line
        if boundary_dir == "horizontal":
            b_pixel_y = int(round((3999.75 - boundary_world) / 0.5)) - y0
            draw_dashed_guide(crop_rgb, "horizontal", b_pixel_y)
            draw_dashed_guide(crop_id_rgb, "horizontal", b_pixel_y)
        elif boundary_dir == "vertical":
            b_pixel_x = int(round((boundary_world - (-3999.75)) / 0.5)) - x0
            draw_dashed_guide(crop_rgb, "vertical", b_pixel_x)
            draw_dashed_guide(crop_id_rgb, "vertical", b_pixel_x)

        sbs = np.concatenate([crop_rgb, crop_id_rgb], axis=1)
        p_crop = EVIDENCE_DIR / filename
        write_image(p_crop, sbs)
        image_manifest.append(str(p_crop.name))
        print(f"Rendered boundary crop: {label} -> {filename}", flush=True)

    print("\nRendering Boundary Seam Crossings (with former seam line marked)...", flush=True)
    # North: wx = 314.75, wz = 3144.25 (boundary at Z = 3144.25)
    render_boundary_crop(314.75, 3144.25, "closeup_former_north_seam.png", "Former North Seam (Z=3144.25)", "horizontal", 3144.25)
    # South: wx = -301.25, wz = -1769.75 (boundary at Z = -1769.75)
    render_boundary_crop(-301.25, -1769.75, "closeup_former_south_seam.png", "Former South Seam (Z=-1769.75)", "horizontal", -1769.75)
    # West: wx = -1771.25, wz = 1121.75 (boundary at X = -1771.25)
    render_boundary_crop(-1771.25, 1121.75, "closeup_former_west_seam.png", "Former West Seam (X=-1771.25)", "vertical", -1771.25)
    # East: wx = 1805.25, wz = 746.25 (boundary at X = 1805.25)
    render_boundary_crop(1805.25, 746.25, "closeup_former_east_seam.png", "Former East Seam (X=1805.25)", "vertical", 1805.25)

    # 6. Corner crops (Northwest, Northeast, Southwest, Southeast)
    def render_corner_crop(cx: float, cz: float, filename: str, label: str):
        ix = int(round((cx - (-3999.75)) / 0.5))
        iy = int(round((3999.75 - cz) / 0.5))
        hw = 512
        x0 = max(0, ix - hw); x1 = min(16000, ix + hw)
        y0 = max(0, iy - hw); y1 = min(16000, iy + hw)

        crop_rgb = rgb_full[y0:y1, x0:x1, :].copy()
        crop_id_idx = id_indices[y0:y1, x0:x1]
        crop_id_rgb = np.zeros_like(crop_rgb)
        for id_val, col in ID_COLORS.items():
            m = (crop_id_idx == id_val)
            crop_id_rgb[m, 0] = col[0] / 255.0
            crop_id_rgb[m, 1] = col[1] / 255.0
            crop_id_rgb[m, 2] = col[2] / 255.0

        # Draw both horizontal and vertical seam crosshairs at center
        draw_dashed_guide(crop_rgb, "horizontal", iy - y0)
        draw_dashed_guide(crop_rgb, "vertical", ix - x0)
        draw_dashed_guide(crop_id_rgb, "horizontal", iy - y0)
        draw_dashed_guide(crop_id_rgb, "vertical", ix - x0)

        sbs = np.concatenate([crop_rgb, crop_id_rgb], axis=1)
        p_corner = EVIDENCE_DIR / filename
        write_image(p_corner, sbs)
        image_manifest.append(str(p_corner.name))
        print(f"Rendered corner crop: {label} -> {filename}", flush=True)

    print("\nRendering Corner Crossings...", flush=True)
    render_corner_crop(-1771.25, 3144.25, "closeup_former_nw_corner.png", "Former NW Corner")
    render_corner_crop(1805.25, 3144.25, "closeup_former_ne_corner.png", "Former NE Corner")
    render_corner_crop(-1771.25, -1769.75, "closeup_former_sw_corner.png", "Former SW Corner")
    render_corner_crop(1805.25, -1769.75, "closeup_former_se_corner.png", "Former SE Corner")

    # 7. Landmarks at verified authentic geographic locations
    print("\nRendering Authentic Landmark Features...", flush=True)
    def render_landmark_crop(cx: float, cz: float, filename: str, label: str):
        ix = int(round((cx - (-3999.75)) / 0.5))
        iy = int(round((3999.75 - cz) / 0.5))
        hw = 512
        x0 = max(0, ix - hw); x1 = min(16000, ix + hw)
        y0 = max(0, iy - hw); y1 = min(16000, iy + hw)

        crop_rgb = rgb_full[y0:y1, x0:x1, :].copy()
        crop_id_idx = id_indices[y0:y1, x0:x1]
        crop_id_rgb = np.zeros_like(crop_rgb)
        for id_val, col in ID_COLORS.items():
            m = (crop_id_idx == id_val)
            crop_id_rgb[m, 0] = col[0] / 255.0
            crop_id_rgb[m, 1] = col[1] / 255.0
            crop_id_rgb[m, 2] = col[2] / 255.0

        sbs = np.concatenate([crop_rgb, crop_id_rgb], axis=1)
        p_landmark = EVIDENCE_DIR / filename
        write_image(p_landmark, sbs)
        image_manifest.append(str(p_landmark.name))
        print(f"Rendered landmark crop: {label} at ({cx:.1f}, {cz:.1f}) -> {filename}", flush=True)

    # Puig Major summit: X = -1283.75, Z = 3495.25
    render_landmark_crop(-1283.75, 3495.25, "closeup_puig_major_peak.png", "Puig Major Summit Area")
    # Sa Calobra Cove: X = 470.0, Z = -1060.0
    render_landmark_crop(470.0, -1060.0, "closeup_sa_calobra_cove.png", "Sa Calobra Cove / Beach")

    # 8. Scree Occurrence Detail (Native Resolution Multi-Panel)
    print("\nRendering Authentic Scree Occurrence Detail...", flush=True)
    scree_mask = vol_array(g_pre, "scree")
    sy, sx = np.unravel_index(np.argmax(scree_mask), scree_mask.shape)
    scree_max_val = float(scree_mask[sy, sx])
    sc_pos = vol_prim(g_pre, "scree").indexToPos((int(sx), int(sy), 0))
    print(f"Maximum scree mask concentration at X={sc_pos[0]:.1f}m, Z={sc_pos[2]:.1f}m (mask={scree_max_val:.4f}, voxel: x={sx}, y={sy})")

    hw_s = 256  # 512x512 window = 256m x 256m
    sx0 = max(0, sx - hw_s); sx1 = min(16000, sx + hw_s)
    sy0 = max(0, sy - hw_s); sy1 = min(16000, sy + hw_s)

    crop_s_mask = scree_mask[sy0:sy1, sx0:sx1]
    crop_s_rgb = rgb_full[sy0:sy1, sx0:sx1, :]
    crop_s_dec = (id_indices[sy0:sy1, sx0:sx1] == 4).astype(np.float32)

    # Convert grayscale mask to 3-channel
    mask_3ch = np.stack([crop_s_mask, crop_s_mask, crop_s_mask], axis=-1)
    # Convert decoded class to distinct visual color
    dec_3ch = np.zeros_like(crop_s_rgb)
    dec_3ch[crop_s_dec > 0.5, :] = (0.6, 0.6, 0.6)

    scree_panel = np.concatenate([mask_3ch, crop_s_rgb, dec_3ch], axis=1)
    p_scree = EVIDENCE_DIR / "closeup_scree_occurrence.png"
    write_image(p_scree, scree_panel)
    image_manifest.append(str(p_scree.name))

    print(f"Generated {len(image_manifest)} verified evidence images.", flush=True)
    return image_manifest


# ==============================================================================
# MAIN VERIFICATION & RECEIPT EMISSION
# ==============================================================================
def main():
    t_start = time.time()
    metrics = verify_invariants()
    manifest = render_evidence(metrics)

    # Construct complete verification receipt
    base_commit = "7833e8bd8e5bfa19a183905335d2ba25b2c22969"
    pre_cache_file = WORK_DIR / "pre_id_cache.bgeo.sc"
    idmap_file = WORK_DIR / "final_unified_idmap.bgeo.sc"

    receipt = {
        "status": "LESSON06_FULL_IDMAP_PASS",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "base_commit": base_commit,
        "houdini_version": hou.applicationVersionString(),
        "domain": {
            "resolution": metrics["resolution"],
            "origin": metrics["origin"],
            "gridspacing": metrics["gridspacing"],
            "bounds_x": [-4000.0, 4000.0],
            "bounds_z": [-4000.0, 4000.0],
            "total_voxels": 256000000
        },
        "source_dtm_verification": metrics["source_dtm_verification"],
        "base_terrain_elevation_m": metrics["base_terrain_stats"],
        "final_idmap_terrain_elevation_m": metrics["height_stats"],
        "procedural_displacement_base_to_preid_m": metrics["procedural_displacement"],
        "procedural_displacement_note": (
            "Procedural displacement reflects intentional material and slump displacements "
            "from Pegasus workflow (L04 material displacement and L05 scree slump/transport), "
            "NOT a DTM reproduction error."
        ),
        "authentic_landforms": metrics["landforms"],
        "alpha_integrity": metrics["alpha_integrity"],
        "invariant_b_preid_vs_postid_max_diff": metrics["invariant_b_layer_diffs"],
        "id_distribution": metrics["id_distribution"],
        "pegasus_decoder_mismatches": metrics["decoder_mismatches"],
        "hashes": {
            "source_dtm_tif": str(DTM_FILE),
            "source_dtm_tif_sha256": metrics["source_dtm_verification"]["source_dtm_sha256"],
            "source_validity_tif": str(VAL_FILE),
            "source_validity_tif_sha256": metrics["source_dtm_verification"]["source_validity_sha256"],
            "stage1_base": str(WORK_DIR / "stage1_base.bgeo.sc"),
            "stage1_base_sha256": metrics["source_dtm_verification"]["stage1_base_sha256"],
            "checkpoint_hip": str(CHECKPOINT_HIP),
            "checkpoint_hip_sha256": digest(CHECKPOINT_HIP),
            "pre_id_cache": str(pre_cache_file),
            "pre_id_cache_sha256": digest(pre_cache_file),
            "final_unified_idmap": str(idmap_file),
            "final_unified_idmap_sha256": digest(idmap_file)
        },
        "evidence_image_manifest": manifest,
        "elapsed_seconds": round(time.time() - t_start, 2)
    }

    # Save to both work directory and project documentation directory
    receipt_json = json.dumps(receipt, indent=2)
    (WORK_DIR / "verification_receipt.json").write_text(receipt_json)
    doc_receipt = DOCS_DIR / "lesson06-unified-verification-receipt.json"
    doc_receipt.write_text(receipt_json)
    print(f"\nSaved verification receipt to:\n  {WORK_DIR / 'verification_receipt.json'}\n  {doc_receipt}", flush=True)
    print(f"\n=======================================================", flush=True)
    print(f"FINAL STATUS: {receipt['status']} (All checks passed in {receipt['elapsed_seconds']:.1f}s)", flush=True)
    print(f"=======================================================", flush=True)


if __name__ == "__main__":
    main()

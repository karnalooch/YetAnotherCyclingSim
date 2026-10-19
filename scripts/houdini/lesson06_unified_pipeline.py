"""Unified Sa Calobra Lesson 06 Pipeline.

Executes Pegasus Landscape Workflow (Lessons 3-6) on the full, single,
unified 16000x16000 (0.5m) domain covering 100% of Working and 100% of Context.
Preserves original Pegasus HDAs, methods, and metric parameters.
Stages each phase into versioned .bgeo.sc caches to guarantee bounded memory.
"""
from __future__ import annotations

import argparse
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
CORPUS_OTLS = Path("C:/Users/akarn/OneDrive/Dokumenty/Codex/2026-10-16/referenced-chatgpt-conversation-this-is-an/outputs/Pegasus_Komplet/P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls").resolve()
EVIDENCE_DIR = WORLD_DIR / "evidence/lesson06_unified"

DTM_FILE = Path("D:/yacs/work/sa-calobra-houdini-unreal-20261016/inputs/dtm_height_float32.tif")
VAL_FILE = Path("D:/yacs/work/sa-calobra-houdini-unreal-20261016/inputs/dtm_validity.tif")

TEX_DIR = WORLD_DIR / "inputs/textures"
SCREE_TEX_DIR = Path("D:/yacs/work/lesson05-material-forge-20261018/run-a/mediterranean_soil/limestone_scree_v1/export")
SCREE_ADAPTER_DIR = Path("D:/yacs/work/lesson05-houdini-20261018")

NAMES = ["grass", "grass 2", "sand", "cliffs", "scree"]


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


def vol_layer(geo: hou.Geometry, name: str) -> tuple[np.ndarray, hou.Volume]:
    for p in geo.prims():
        if isinstance(p, hou.Volume) and p.attribValue("name") == name:
            arr = np.frombuffer(p.allVoxelsAsString(), np.float32).reshape(p.resolution()[1], p.resolution()[0])
            return arr, p
    raise KeyError(f"Volume layer {name} not found in geometry")


def stats(arr: np.ndarray) -> dict:
    assert np.isfinite(arr).all(), "Array contains NaN or Inf"
    return {
        "min": float(arr.min()),
        "max": float(arr.max()),
        "mean": float(arr.mean(dtype=np.float64)),
        "count": int(arr.size)
    }


def linear_ramp(points, vals):
    return hou.Ramp([hou.rampBasis.Linear] * len(points), points, vals)


# ==============================================================================
# STAGE 1: BASE TERRAIN & VALIDITY
# ==============================================================================
def stage1_base(force: bool = False):
    print("=== [STAGE 1] BUILDING UNIFIED BASE TERRAIN & VALIDITY ===", flush=True)
    out_file = WORK_DIR / "stage1_base.bgeo.sc"
    if out_file.exists() and not force:
        print(f"Stage 1 cache already exists: {out_file}, skipping cook.", flush=True)
        return

    t0 = time.time()
    g = hou.node("/obj").createNode("geo", "BUILD_STAGE1")

    # 1. Read DTM height
    dtm = g.createNode("heightfield_file", "READ_DTM")
    dtm.setParms({
        "filename": str(DTM_FILE),
        "sizemethod": "divsize",
        "gridspacing": 0.5,
        "doclampmin": 0
    })

    xform_dtm = g.createNode("xform", "XFORM_DTM")
    xform_dtm.setInput(0, dtm)
    xform_dtm.setParms({"ry": 90.0})

    # 2. Read Validity mask -> Alpha
    val = g.createNode("heightfield_file", "READ_VALIDITY")
    val.setParms({
        "filename": str(VAL_FILE),
        "type": 1,
        "layer": "Alpha",
        "sizemethod": "divsize",
        "gridspacing": 0.5,
        "heightscale": 255.0,
        "doclampmin": 0
    })

    xform_val = g.createNode("xform", "XFORM_VAL")
    xform_val.setInput(0, val)
    xform_val.setParms({"ry": 90.0})

    xform_dtm.cook(force=True)
    geo_dtm = hou.Geometry()
    geo_dtm.merge(xform_dtm.geometry())

    xform_val.cook(force=True)
    geo_val = hou.Geometry()
    geo_val.merge(xform_val.geometry())
    # Keep only mask from validity and rename to Alpha
    val_vols = [p for p in geo_val.prims() if isinstance(p, hou.Volume) and p.attribValue("name") == "mask"]
    assert val_vols, "No mask volume found in validity file"
    val_vols[0].setAttribValue("name", "Alpha")
    geo_val.deletePrims([p for p in geo_val.prims() if p.attribValue("name") != "Alpha"], True)

    # Merge into base geometry
    geo_dtm.merge(geo_val)
    geo = geo_dtm

    h_arr, ph = vol_layer(geo, "height")
    a_arr, pa = vol_layer(geo, "Alpha")

    h_stats = stats(h_arr)
    a_stats = stats(a_arr)
    res = list(ph.resolution())
    o = list(ph.indexToPos((0, 0, 0)))

    print(f"Height stats: {h_stats}", flush=True)
    print(f"Alpha stats: {a_stats}", flush=True)
    print(f"Resolution: {res}, Origin: {o}", flush=True)

    assert res == [16000, 16000, 1], f"Unexpected resolution {res}"
    np.testing.assert_allclose(o, [-3999.75, 0.0, 3999.75], atol=0.01)

    geo.saveToFile(str(out_file))
    receipt = {
        "stage": "stage1_base",
        "output_file": str(out_file),
        "sha256": digest(out_file),
        "height": h_stats,
        "alpha": a_stats,
        "resolution": res,
        "origin": o,
        "seconds": time.time() - t0
    }
    (WORK_DIR / "stage1_base.json").write_text(json.dumps(receipt, indent=2))
    g.destroy()
    print(f"=== [STAGE 1 COMPLETE in {receipt['seconds']:.1f}s] ===", flush=True)


# ==============================================================================
# STAGE 2: PROCEDURAL MASKS (Grass, Sand, Cliff, Tint Ramp)
# ==============================================================================
def stage2_masks(force: bool = False):
    print("=== [STAGE 2] COMPUTING PROCEDURAL MASKS ===", flush=True)
    out_file = WORK_DIR / "stage2_masks.bgeo.sc"
    if out_file.exists() and not force:
        print(f"Stage 2 cache already exists: {out_file}, skipping cook.", flush=True)
        return

    t0 = time.time()
    g = hou.node("/obj").createNode("geo", "BUILD_STAGE2")

    base = g.createNode("file", "LOAD_BASE")
    base.parm("file").set(str(WORK_DIR / "stage1_base.bgeo.sc"))

    # 1. Grass Mask
    m_grass = g.createNode("heightfield_maskbyfeature", "MASK_GRASS")
    m_grass.setInput(0, base)
    m_grass.setParms({
        "maskbyslope": 1,
        "min_slopeangle": 0.0,
        "max_slopeangle": 32.0,
        "maskbyheight": 1,
        "minheight": 8.0,
        "maxheight": 1500.0,
        "maskbyocclusion": 0
    })

    # 2. Sand Mask
    m_sand = g.createNode("heightfield_maskbyfeature", "MASK_SAND")
    m_sand.setInput(0, base)
    m_sand.setParms({
        "maskbyheight": 1,
        "minheight": -50.0,
        "maxheight": 25.0,
        "maskbyslope": 1,
        "min_slopeangle": 0.0,
        "max_slopeangle": 18.0,
        "maskbyocclusion": 0
    })

    # 3. Cliff Mask (smooth radius 6.0 voxels = 3.0 m)
    m_cliff = g.createNode("heightfield_maskbyfeature", "MASK_CLIFF")
    m_cliff.setInput(0, base)
    m_cliff.setParms({
        "maskbyslope": 1,
        "min_slopeangle": 28.0,
        "max_slopeangle": 90.0,
        "maskbyheight": 0,
        "maskbyocclusion": 0,
        "smooth_radius": 6.0
    })

    # 4. Tint Ramp (height gradient + slope gradient - occlusion micro-variation)
    t_hgt = g.createNode("heightfield_maskbyfeature", "TINT_RAMP_HEIGHT")
    t_hgt.setInput(0, base)
    t_hgt.setParms({
        "maskbyheight": 1,
        "minheight": 0.0,
        "maxheight": 1440.0,
        "maskbyslope": 0,
        "maskbyocclusion": 0,
        "heightramp": linear_ramp([0.0, 1.0], [0.0, 1.0])
    })

    t_slope = g.createNode("heightfield_maskbyfeature", "TINT_RAMP_SLOPE")
    t_slope.setInput(0, t_hgt)
    t_slope.setParms({
        "maskbyslope": 1,
        "min_slopeangle": 0.0,
        "max_slopeangle": 90.0,
        "maskbyheight": 0,
        "maskbyocclusion": 0,
        "combine": "add",
        "sloperamp": linear_ramp([0.0, 1.0], [0.0, 1.0])
    })

    t_occ = g.createNode("heightfield_maskbyfeature", "TINT_RAMP_OCCLUSION")
    t_occ.setInput(0, t_slope)
    t_occ.setParms({
        "maskbyocclusion": 1,
        "maskbyslope": 0,
        "maskbyheight": 0,
        "viewdistance": 25.0,
        "combine": "subtract",
        "invertmask": 1
    })

    # Extract layers and rename
    out_geo = hou.Geometry()

    print("Cooking Grass Mask...", flush=True)
    m_grass.cook(force=True)
    g_grass = m_grass.geometry()
    mg = hou.Geometry(); mg.merge(g_grass); mg.deletePrims([p for p in mg.prims() if p.attribValue("name") != "mask"])
    vol_layer(mg, "mask")[1].setAttribValue("name", "grass_mask")
    out_geo.merge(mg)

    print("Cooking Sand Mask...", flush=True)
    m_sand.cook(force=True)
    g_sand = m_sand.geometry()
    ms = hou.Geometry(); ms.merge(g_sand); ms.deletePrims([p for p in ms.prims() if p.attribValue("name") != "mask"])
    vol_layer(ms, "mask")[1].setAttribValue("name", "sand_mask")
    out_geo.merge(ms)

    print("Cooking Cliff Mask...", flush=True)
    m_cliff.cook(force=True)
    g_cliff = m_cliff.geometry()
    mc = hou.Geometry(); mc.merge(g_cliff); mc.deletePrims([p for p in mc.prims() if p.attribValue("name") != "mask"])
    vol_layer(mc, "mask")[1].setAttribValue("name", "cliff_mask")
    out_geo.merge(mc)

    print("Cooking Tint Ramp Layer...", flush=True)
    t_occ.cook(force=True)
    g_tint = t_occ.geometry()
    mt = hou.Geometry(); mt.merge(g_tint); mt.deletePrims([p for p in mt.prims() if p.attribValue("name") != "mask"])
    vol_layer(mt, "mask")[1].setAttribValue("name", "ramp_layer")
    out_geo.merge(mt)

    out_geo.saveToFile(str(out_file))

    receipt = {
        "stage": "stage2_masks",
        "output_file": str(out_file),
        "sha256": digest(out_file),
        "grass_mask": stats(vol_layer(out_geo, "grass_mask")[0]),
        "sand_mask": stats(vol_layer(out_geo, "sand_mask")[0]),
        "cliff_mask": stats(vol_layer(out_geo, "cliff_mask")[0]),
        "ramp_layer": stats(vol_layer(out_geo, "ramp_layer")[0]),
        "seconds": time.time() - t0
    }
    (WORK_DIR / "stage2_masks.json").write_text(json.dumps(receipt, indent=2))
    g.destroy()
    print(f"=== [STAGE 2 COMPLETE in {receipt['seconds']:.1f}s] ===", flush=True)


# ==============================================================================
# STAGE 3: SCREE MASKS (Slump + Pockets + Transport)
# ==============================================================================
def stage3_scree(force: bool = False):
    print("=== [STAGE 3] COMPUTING SCREE SLUMP & TRANSPORT ===", flush=True)
    out_file = WORK_DIR / "stage3_scree.bgeo.sc"
    if out_file.exists() and not force:
        print(f"Stage 3 cache already exists: {out_file}, skipping cook.", flush=True)
        return

    install_hdas()
    t0 = time.time()
    g = hou.node("/obj").createNode("geo", "BUILD_STAGE3")

    base = g.createNode("file", "LOAD_L04_MATERIAL")
    base.parm("file").set(str(WORK_DIR / "stage4c_cliff.bgeo.sc"))

    # 1. Slump source (slope 35-90 deg)
    s_src = g.createNode("heightfield_maskbyfeature", "SCREE_SOURCE_SLOPE")
    s_src.setInput(0, base)
    s_src.setParms({
        "maskbyslope": 1,
        "min_slopeangle": 35.0,
        "max_slopeangle": 90.0,
        "maskbyheight": 0,
        "maskbyocclusion": 0
    })
    s_src.parm("sloperamp").set(linear_ramp([0.0, 0.15, 1.0], [0.0, 1.0, 1.0]))

    # 2. HeightField Slump (20 iterations, repose angle 30)
    slump = g.createNode("heightfield_slump", "SCREE_DOWNHILL")
    slump.setInput(0, s_src)
    slump.setParms({
        "iterations": 20,
        "repose_angle": 30.0,
        "doerosion": 0,
        "add_to_bedrock": 0,
        "flow_enable": 0,
        "materiallayer": "mask",
        "bedrocklayer": "height"
    })

    print("Cooking Slump...", flush=True)
    slump.cook(force=True)
    slump_max = float(vol_layer(slump.geometry(), "mask")[0].max())
    print(f"Slump max mask: {slump_max:.4f}", flush=True)

    # 3. Remap slump
    rem_slump = g.createNode("heightfield_remap", "REMAP_SLUMP")
    rem_slump.setInput(0, slump)
    rem_slump.setParms({
        "layer": "mask",
        "inputmin": 0.0,
        "inputmax": slump_max,
        "outputmin": 0.0,
        "outputmax": 1.0
    })

    # 4. Pockets (occlusion viewdistance 5m)
    pockets = g.createNode("heightfield_maskbyfeature", "LOCAL_POCKETS")
    pockets.setInput(0, base)
    pockets.setParms({
        "maskbyslope": 0,
        "maskbyheight": 0,
        "maskbyocclusion": 1,
        "viewdistance": 5.0
    })
    pockets.parm("ramp").set(linear_ramp([0.0, 1.0], [1.0, 0.0]))

    cp_pockets = g.createNode("heightfield_copylayer", "COPY_POCKETS")
    cp_pockets.setInput(0, pockets)
    cp_pockets.setParms({"srcname1": "mask", "dstname1": "pockets"})

    # 5. Layer Slump with Pockets
    lslump = g.createNode("PE_heightfield_layerslump", "LAYER_SLUMP")
    lslump.setInput(0, rem_slump)
    lslump.setInput(1, cp_pockets)
    lslump.setParms({
        "srcname1": "mask",
        "srcname2": "pockets",
        "input": 1,
        "iterations": 20
    })

    print("Cooking Layer Slump...", flush=True)
    lslump.cook(force=True)
    lslump_max = float(vol_layer(lslump.geometry(), "mask")[0].max())
    print(f"Layer Slump max mask: {lslump_max:.4f}", flush=True)

    # 6. Final Remap
    rem_final = g.createNode("heightfield_remap", "REMAP_FINAL")
    rem_final.setInput(0, lslump)
    rem_final.setParms({
        "layer": "mask",
        "inputmin": 0.0,
        "inputmax": lslump_max,
        "outputmin": 0.0,
        "outputmax": 1.0
    })
    rem_final.parm("remap").set(linear_ramp([0.0, 0.05, 0.4, 1.0], [0.0, 0.0, 0.45, 1.0]))

    # 7. Clamp dry valid support
    clamp_wrangle = g.createNode("volumewrangle", "VALID_DRY_SUPPORT")
    clamp_wrangle.setInput(0, rem_final)
    clamp_wrangle.setParms({"snippet": "if (@height <= 0 || @Alpha <= 0) @mask = 0;"})

    clamp_wrangle.cook(force=True)
    geo = clamp_wrangle.geometry()

    out_geo = hou.Geometry()
    mg = hou.Geometry(); mg.merge(geo); mg.deletePrims([p for p in mg.prims() if p.attribValue("name") != "mask"])
    vol_layer(mg, "mask")[1].setAttribValue("name", "scree_mask")
    out_geo.merge(mg)

    out_geo.saveToFile(str(out_file))

    receipt = {
        "stage": "stage3_scree",
        "output_file": str(out_file),
        "sha256": digest(out_file),
        "slump_max": slump_max,
        "layerslump_max": lslump_max,
        "scree_mask": stats(vol_layer(out_geo, "scree_mask")[0]),
        "seconds": time.time() - t0
    }
    (WORK_DIR / "stage3_scree.json").write_text(json.dumps(receipt, indent=2))
    g.destroy()
    print(f"=== [STAGE 3 COMPLETE in {receipt['seconds']:.1f}s] ===", flush=True)


# ==============================================================================
# STAGE 4: MATERIALS, TINTS & PRE-ID CACHE (STAGED FOR BOUNDED MEMORY)
# ==============================================================================
def stage4a_grass():
    print("=== [STAGE 4a] APPLYING GRASS MATERIAL ===", flush=True)
    out_file = WORK_DIR / "stage4a_grass.bgeo.sc"
    if out_file.exists():
        print(f"Stage 4a cache already exists: {out_file}, skipping.", flush=True)
        return

    install_hdas()
    t0 = time.time()
    g = hou.node("/obj").createNode("geo", "STAGE4A_GRASS")

    base = g.createNode("file", "LOAD_BASE")
    base.parm("file").set(str(WORK_DIR / "stage1_base.bgeo.sc"))

    masks = g.createNode("file", "LOAD_MASKS")
    masks.parm("file").set(str(WORK_DIR / "stage2_masks.bgeo.sc"))

    bl = g.createNode("blast", "BLAST_GRASS")
    bl.setInput(0, masks)
    bl.setParms({"group": "@name=grass_mask", "negate": 1})
    cl = g.createNode("heightfield_copylayer", "COPY_GRASS")
    cl.setInput(0, bl)
    cl.setParms({"srcname1": "grass_mask", "dstname1": "mask"})

    mat_grass = g.createNode("PE_heightfield_material::1.0", "MAT_GRASS")
    mat_grass.setInput(0, base)
    mat_grass.setInput(1, cl)
    mat_grass.setParms({
        "filename1": str(TEX_DIR / "SaCalobra_Grass_BaseColor.png"),
        "filename2": str(TEX_DIR / "SaCalobra_Grass_Roughness.png"),
        "filename3": str(TEX_DIR / "tlonbisya_4K_Displacement.exr"),
        "size": 12.0,
        "heightscale": 0.0,
        "use_mask": 1,
        "srcname1": "mask",
        "input2": "2",
        "use_distort": 1,
        "noisetype": "simplex",
        "amp": 3.5,
        "element_size": 15.0,
        "rough": 0.5,
        "maxoctave": 3
    })

    print("Cooking Grass Material...", flush=True)
    mat_grass.cook(force=True)
    mat_grass.geometry().saveToFile(str(out_file))
    g.destroy()
    print(f"=== [STAGE 4a COMPLETE in {time.time() - t0:.1f}s] ===", flush=True)


def stage4b_sand():
    print("=== [STAGE 4b] APPLYING SAND MATERIAL & TINT RAMP ===", flush=True)
    out_file = WORK_DIR / "stage4b_sand.bgeo.sc"
    if out_file.exists():
        print(f"Stage 4b cache already exists: {out_file}, skipping.", flush=True)
        return

    install_hdas()
    t0 = time.time()
    g = hou.node("/obj").createNode("geo", "STAGE4B_SAND")

    prev = g.createNode("file", "LOAD_PREV")
    prev.parm("file").set(str(WORK_DIR / "stage4a_grass.bgeo.sc"))

    masks = g.createNode("file", "LOAD_MASKS")
    masks.parm("file").set(str(WORK_DIR / "stage2_masks.bgeo.sc"))

    # Sand mask
    bl_sand = g.createNode("blast", "BLAST_SAND")
    bl_sand.setInput(0, masks)
    bl_sand.setParms({"group": "@name=sand_mask", "negate": 1})
    cl_sand = g.createNode("heightfield_copylayer", "COPY_SAND")
    cl_sand.setInput(0, bl_sand)
    cl_sand.setParms({"srcname1": "sand_mask", "dstname1": "mask"})

    # Ramp layer
    bl_ramp = g.createNode("blast", "BLAST_RAMP")
    bl_ramp.setInput(0, masks)
    bl_ramp.setParms({"group": "@name=ramp_layer", "negate": 1})
    cl_ramp = g.createNode("heightfield_copylayer", "COPY_RAMP")
    cl_ramp.setInput(0, bl_ramp)
    cl_ramp.setParms({"srcname1": "ramp_layer", "dstname1": "mask"})

    mat_sand = g.createNode("PE_heightfield_material::1.0", "MAT_SAND")
    mat_sand.setInput(0, prev)
    mat_sand.setInput(1, cl_sand)
    mat_sand.setParms({
        "filename1": str(TEX_DIR / "coast_sand_01_diff_2k.jpg"),
        "filename2": str(TEX_DIR / "coast_sand_01_rough_2k.jpg"),
        "filename3": str(TEX_DIR / "coast_sand_01_disp_2k.png"),
        "size": 8.0,
        "heightscale": 0.08,
        "use_mask": 1,
        "srcname1": "mask",
        "use_distort": 0,
        "input2": "2"
    })

    tint_node = g.createNode("PE_heightfield_tint::1.0", "HEIGHTFIELD_TINT")
    tint_node.setInput(0, mat_sand)
    tint_node.setInput(1, cl_ramp)
    tint_node.setParms({
        "use_ramp": 1,
        "srcname1": "mask",
        "ramp_mask": "",
        "strength": 0.85
    })
    tint_node.parm("tint_ramp").set(linear_ramp([0.0, 0.5, 1.0], [(0.42, 0.56, 0.22), (0.58, 0.54, 0.28), (0.74, 0.64, 0.36)]))

    print("Cooking Sand Material & Tint...", flush=True)
    tint_node.cook(force=True)
    tint_node.geometry().saveToFile(str(out_file))
    g.destroy()
    print(f"=== [STAGE 4b COMPLETE in {time.time() - t0:.1f}s] ===", flush=True)


def stage4c_cliff():
    print("=== [STAGE 4c] APPLYING CLIFF MATERIAL ===", flush=True)
    out_file = WORK_DIR / "stage4c_cliff.bgeo.sc"
    if out_file.exists():
        print(f"Stage 4c cache already exists: {out_file}, skipping.", flush=True)
        return

    install_hdas()
    t0 = time.time()
    g = hou.node("/obj").createNode("geo", "STAGE4C_CLIFF")

    prev = g.createNode("file", "LOAD_PREV")
    prev.parm("file").set(str(WORK_DIR / "stage4b_sand.bgeo.sc"))

    masks = g.createNode("file", "LOAD_MASKS")
    masks.parm("file").set(str(WORK_DIR / "stage2_masks.bgeo.sc"))

    bl_cliff = g.createNode("blast", "BLAST_CLIFF")
    bl_cliff.setInput(0, masks)
    bl_cliff.setParms({"group": "@name=cliff_mask", "negate": 1})
    cl_cliff = g.createNode("heightfield_copylayer", "COPY_CLIFF")
    cl_cliff.setInput(0, bl_cliff)
    cl_cliff.setParms({"srcname1": "cliff_mask", "dstname1": "mask"})

    mat_cliff = g.createNode("PE_heightfield_material::1.0", "MAT_CLIFF")
    mat_cliff.setInput(0, prev)
    mat_cliff.setInput(1, cl_cliff)
    mat_cliff.setParms({
        "filename1": str(TEX_DIR / "SaCalobra_PaleLimestone_BaseColor.png"),
        "filename2": str(TEX_DIR / "SaCalobra_PaleLimestone_Roughness.png"),
        "filename3": str(TEX_DIR / "wepoeaw_4K_Displacement.exr"),
        "size": 20.0,
        "heightscale": 0.35,
        "use_mask": 1,
        "srcname1": "mask",
        "input2": "2"
    })

    print("Cooking Cliff Material...", flush=True)
    mat_cliff.cook(force=True)
    mat_cliff.geometry().saveToFile(str(out_file))
    g.destroy()
    print(f"=== [STAGE 4c COMPLETE in {time.time() - t0:.1f}s] ===", flush=True)


def stage4d_scree(force: bool = False):
    print("=== [STAGE 4d] APPLYING SCREE MATERIAL, TINTS & COMPILING PRE-ID CACHE ===", flush=True)
    out_file = WORK_DIR / "pre_id_cache.bgeo.sc"
    if out_file.exists() and not force:
        print(f"Pre-ID cache already exists: {out_file}, skipping.", flush=True)
        return

    install_hdas()
    t0 = time.time()
    g = hou.node("/obj").createNode("geo", "STAGE4D_SCREE")

    prev = g.createNode("file", "LOAD_PREV")
    prev.parm("file").set(str(WORK_DIR / "stage4c_cliff.bgeo.sc"))

    masks = g.createNode("file", "LOAD_MASKS")
    masks.parm("file").set(str(WORK_DIR / "stage2_masks.bgeo.sc"))

    scree = g.createNode("file", "LOAD_SCREE")
    scree.parm("file").set(str(WORK_DIR / "stage3_scree.bgeo.sc"))

    # Scree mask
    bl_scree = g.createNode("blast", "BLAST_SCREE")
    bl_scree.setInput(0, scree)
    bl_scree.setParms({"group": '@name="scree_mask"', "negate": 1})
    cl_scree = g.createNode("heightfield_copylayer", "COPY_SCREE")
    cl_scree.setInput(0, bl_scree)
    cl_scree.setParms({"srcname1": "scree_mask", "dstname1": "mask"})

    # Cliff mask for tint
    bl_cliff = g.createNode("blast", "BLAST_CLIFF")
    bl_cliff.setInput(0, masks)
    bl_cliff.setParms({"group": '@name="cliff_mask"', "negate": 1})
    cl_cliff = g.createNode("heightfield_copylayer", "COPY_CLIFF")
    cl_cliff.setInput(0, bl_cliff)
    cl_cliff.setParms({"srcname1": "cliff_mask", "dstname1": "mask"})

    # 1. Scree Material
    mat_scree = g.createNode("PE_heightfield_material::1.0", "MAT_SCREE")
    mat_scree.setInput(0, prev)
    mat_scree.setInput(1, cl_scree)
    mat_scree.setParms({
        "filename1": str(SCREE_TEX_DIR / "YACS_Material_BaseColor.png"),
        "filename2": str(SCREE_ADAPTER_DIR / "Roughness_Pegasus.exr"),
        "filename3": str(SCREE_ADAPTER_DIR / "Height_Pegasus.exr"),
        "size": 4.0,
        "heightscale": 0.1,
        "use_mask": 1,
        "srcname1": "mask",
        "use_distort": 0
    })

    # 2. Cliff Tint
    t_cliff = g.createNode("PE_heightfield_tint::1.0", "CLIFF_TINT")
    t_cliff.setInput(0, mat_scree)
    t_cliff.setInput(1, cl_cliff)
    t_cliff.setParms({"strength": 0.15, "use_ramp": 0, "srcname1": "mask", "ramp_mask": "mask"})
    t_cliff.parmTuple("tint").set((0.94, 0.96, 1.0))

    # 3. Scree Tint
    t_scree = g.createNode("PE_heightfield_tint::1.0", "SCREE_TINT")
    t_scree.setInput(0, t_cliff)
    t_scree.setInput(1, cl_scree)
    t_scree.setParms({"strength": 0.2, "use_ramp": 0, "srcname1": "mask", "ramp_mask": "mask"})
    t_scree.parmTuple("tint").set((1.0, 0.98, 0.95))

    # 4. Exposure Tint (computed on lesson 04 post-material height)
    m_exp = g.createNode("heightfield_maskbyfeature", "BROAD_EXPOSURE")
    m_exp.setInput(0, prev)
    m_exp.setParms({"maskbyslope": 0, "maskbyheight": 0, "maskbyocclusion": 1, "viewdistance": 25.0})

    t_exp = g.createNode("PE_heightfield_tint::1.0", "EXPOSURE_TINT")
    t_exp.setInput(0, t_scree)
    t_exp.setInput(1, m_exp)
    t_exp.setParms({"strength": 0.2, "use_ramp": 1, "srcname1": "mask", "ramp_mask": ""})
    t_exp.parm("tint_ramp").set(linear_ramp([0.0, 0.5, 1.0], [(1.0, 1.0, 1.0), (0.93, 0.95, 0.92), (1.0, 1.0, 1.0)]))

    # 5. Curvature Tint (computed on lesson 04 post-material height)
    m_curv = g.createNode("heightfield_maskbyfeature", "CURVATURE_MASK")
    m_curv.setInput(0, prev)
    m_curv.setParms({"maskbyslope": 0, "maskbyheight": 0, "maskbyocclusion": 0, "maskbycurvature": 1})
    m_curv.parm("computercurvature").pressButton()

    t_curv = g.createNode("PE_heightfield_tint::1.0", "CURVATURE_TINT")
    t_curv.setInput(0, t_exp)
    t_curv.setInput(1, m_curv)
    t_curv.setParms({"strength": 0.1, "use_ramp": 1, "srcname1": "mask", "ramp_mask": ""})
    t_curv.parm("tint_ramp").set(linear_ramp([0.0, 0.5, 1.0], [(1.0, 1.0, 1.0), (1.02, 1.02, 1.02), (1.05, 1.05, 1.05)]))

    print("Cooking Scree & Tint Stack...", flush=True)
    t_curv.cook(force=True)
    cooked = t_curv.geometry()

    # 6. Merge the 5 semantic masks into named volume layers
    final_pre = hou.Geometry()
    final_pre.merge(cooked)

    geo_masks = hou.Geometry()
    geo_masks.loadFromFile(str(WORK_DIR / "stage2_masks.bgeo.sc"))
    geo_scree = hou.Geometry()
    geo_scree.loadFromFile(str(WORK_DIR / "stage3_scree.bgeo.sc"))

    def copy_vol_as(src_geo, src_layer, dst_layer):
        mg = hou.Geometry()
        mg.merge(src_geo)
        mg.deletePrims([p for p in mg.prims() if p.attribValue("name") != src_layer])
        vol_layer(mg, src_layer)[1].setAttribValue("name", dst_layer)
        final_pre.merge(mg)

    copy_vol_as(geo_masks, "grass_mask", "grass")
    copy_vol_as(geo_masks, "ramp_layer", "grass 2")
    copy_vol_as(geo_masks, "sand_mask", "sand")
    copy_vol_as(geo_masks, "cliff_mask", "cliffs")
    copy_vol_as(geo_scree, "scree_mask", "scree")

    final_pre.saveToFile(str(out_file))

    h_stats = stats(vol_layer(final_pre, "height")[0])
    r_stats = stats(vol_layer(final_pre, "r")[0])
    g_stats = stats(vol_layer(final_pre, "g")[0])
    b_stats = stats(vol_layer(final_pre, "b")[0])

    receipt = {
        "stage": "stage4_materials_and_tints",
        "output_file": str(out_file),
        "sha256": digest(out_file),
        "height": h_stats,
        "r": r_stats,
        "g": g_stats,
        "b": b_stats,
        "layers": [p.attribValue("name") for p in final_pre.prims() if isinstance(p, hou.Volume)],
        "seconds": time.time() - t0
    }
    (WORK_DIR / "pre_id_cache.json").write_text(json.dumps(receipt, indent=2))
    g.destroy()
    print(f"=== [STAGE 4 COMPLETE in {receipt['seconds']:.1f}s] ===", flush=True)


def stage4_materials_and_tints(force: bool = False):
    stage4a_grass()
    stage4b_sand()
    stage4c_cliff()
    stage3_scree(force=force)
    stage4d_scree(force=force)


# ==============================================================================
# STAGE 5: LESSON 06 IDMAP GENERATION & HIP CHECKPOINT
# ==============================================================================
def stage5_idmap(force: bool = False):
    print("=== [STAGE 5] GENERATING LESSON 06 UNIFIED IDMAP ===", flush=True)
    out_file = WORK_DIR / "final_unified_idmap.bgeo.sc"
    checkpoint_hip = WORLD_DIR / "SaCalobra_Pegasus_Lesson06_Unified_v001.hiplc"
    if out_file.exists() and not force:
        print(f"Final unified IDMap cache already exists: {out_file}, skipping cook.", flush=True)
        return

    install_hdas()
    t0 = time.time()
    g = hou.node("/obj").createNode("geo", "SA_CALOBRA_UNIFIED")

    # 1. Load Pre-ID Cache
    pre_cache = g.createNode("file", "PRE_ID_CACHE")
    pre_cache.parm("file").set(str(WORK_DIR / "pre_id_cache.bgeo.sc"))

    # 2. Extract each of the 5 masks to a clean heightfield stream
    def extract_id_mask(layer_name, node_name):
        bl = g.createNode("blast", node_name)
        bl.setInput(0, pre_cache)
        bl.setParms({"group": f'@name="{layer_name}"', "negate": 1})
        cl = g.createNode("heightfield_copylayer", f"COPY_{node_name}")
        cl.setInput(0, bl)
        cl.setParms({"srcname1": f'"{layer_name}"', "dstname1": "mask"})
        n = g.createNode("null", f"OUT_MASK_{node_name}")
        n.setInput(0, cl)
        return n

    m_grass = extract_id_mask("grass", "GRASS")
    m_grass2 = extract_id_mask("grass 2", "GRASS_2")
    m_sand = extract_id_mask("sand", "SAND")
    m_cliffs = extract_id_mask("cliffs", "CLIFFS")
    m_scree = extract_id_mask("scree", "SCREE")

    # 3. ID Map Layers metadata definition
    id_layers = g.createNode("PE_heightield_idmap_layers", "ID_MAP_LAYERS")
    id_layers.setParms({
        "layers": 5,
        "name_0": "grass", "colour_0r": 0.25, "colour_0g": 0.55, "colour_0b": 0.15,
        "name_1": "grass 2", "colour_1r": 0.85, "colour_1g": 0.85, "colour_1b": 0.15,
        "name_2": "sand", "colour_2r": 0.90, "colour_2g": 0.75, "colour_2b": 0.45,
        "name_3": "cliffs", "colour_3r": 0.40, "colour_3g": 0.35, "colour_3b": 0.30,
        "name_4": "scree", "colour_4r": 0.60, "colour_4g": 0.60, "colour_4b": 0.60
    })

    # 4. Layers to ID Stack
    def make_layer(prev_node, mask_null, id_idx, name):
        n = g.createNode("PE_Heightfield_Layers_to_ID::2.0", f"{name}_layer")
        n.setInput(0, prev_node)
        n.setInput(1, mask_null)
        n.setParms({
            "numkeys": 4,
            "id_layer": id_idx,
            "objpath1": id_layers.path(),
            "input": 1,
            "layers": 1,
            "layer_1": "mask",
            "tolerance_1": 0.5
        })
        return n

    l_grass = make_layer(pre_cache, m_grass, 0, "grass")
    l_grass2 = make_layer(l_grass, m_grass2, 1, "grass_2")
    l_sand = make_layer(l_grass2, m_sand, 2, "sand")
    l_cliffs = make_layer(l_sand, m_cliffs, 3, "cliffs")
    l_scree = make_layer(l_cliffs, m_scree, 4, "scree")

    # Explicit validation of GRASS_2 selector and mask
    blast_grass2 = g.node("GRASS_2")
    blast_grass2.cook(force=True)
    b_prims = [p.attribValue("name") for p in blast_grass2.geometry().prims() if isinstance(p, hou.Volume)]
    print(f"Primitives remaining after GRASS_2 blast: {b_prims}", flush=True)
    assert b_prims == ["grass 2"], f"GRASS_2 blast failed to isolate 'grass 2'! Found: {b_prims}"

    copy_grass2 = g.node("COPY_GRASS_2")
    copy_grass2.cook(force=True)
    cg_geo = copy_grass2.geometry()
    cg_vox = vol_layer(cg_geo, "mask")[0]
    src_vox = vol_layer(pre_cache.geometry(), "grass 2")[0]
    cg_res = list(vol_layer(cg_geo, "mask")[1].resolution())
    src_res = list(vol_layer(pre_cache.geometry(), "grass 2")[1].resolution())
    assert cg_res == src_res, f"Resolution mismatch between COPY_GRASS_2 and source: {cg_res} vs {src_res}"

    diff_g2 = float(np.max(np.abs(cg_vox - src_vox)))
    mismatches_g2 = int(np.count_nonzero(cg_vox != src_vox))
    print(f"COPY_GRASS_2 sample-by-sample check vs source 'grass 2': max_diff={diff_g2:.8f}, mismatches={mismatches_g2}", flush=True)
    assert diff_g2 == 0.0 and mismatches_g2 == 0, f"COPY_GRASS_2 does not match source 'grass 2' layer! diff={diff_g2}, mismatches={mismatches_g2}"

    print("Cooking Final Layers-to-ID...", flush=True)
    l_scree.cook(force=True)
    geo = l_scree.geometry()
    assert not l_scree.errors(), l_scree.errors()

    geo.saveToFile(str(out_file))

    # 5. Decoder node & Final Cache node for checkpoint HIP
    final_cache = g.createNode("file", "FINAL_CACHE")
    final_cache.parm("file").set(str(out_file))

    decoder = g.createNode("PE_Heightfield_id_to_layer", "ID_TO_LAYER")
    decoder.setInput(0, final_cache)

    vis = g.createNode("heightfield_visualize", "GLOBAL_COLOR")
    vis.setInput(0, final_cache)

    out_null = g.createNode("null", "OUT_UNIFIED_LANDSCAPE")
    out_null.setInput(0, final_cache)

    # Save Checkpoint HIP
    hou.hipFile.save(str(checkpoint_hip))
    print(f"Saved checkpoint HIP: {checkpoint_hip}", flush=True)

    id_arr, pid = vol_layer(geo, "id")
    id_stats = stats(id_arr)
    unique_ids, counts = np.unique(id_arr, return_counts=True)
    id_distribution = {float(k): int(v) for k, v in zip(unique_ids, counts)}

    receipt = {
        "stage": "stage5_idmap",
        "output_file": str(out_file),
        "sha256": digest(out_file),
        "checkpoint_hip": str(checkpoint_hip),
        "checkpoint_hip_sha256": digest(checkpoint_hip),
        "id_stats": id_stats,
        "id_distribution": id_distribution,
        "seconds": time.time() - t0
    }
    (WORK_DIR / "final_unified_idmap.json").write_text(json.dumps(receipt, indent=2))
    print(f"ID Distribution: {id_distribution}", flush=True)
    print(f"=== [STAGE 5 COMPLETE in {receipt['seconds']:.1f}s] ===", flush=True)


# ==============================================================================
# MAIN CLI
# ==============================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", choices=["base", "masks", "4a", "4b", "4c", "scree", "4d", "materials", "idmap", "all"], default="all")
    ap.add_argument("--force", action="store_true", help="Force recooking even if stage cache exists")
    args = ap.parse_args()

    print(f"Houdini Version: {hou.applicationVersionString()}", flush=True)
    print(f"Project Dir: {PROJECT_DIR}", flush=True)
    print(f"Work Dir: {WORK_DIR}", flush=True)

    if args.stage in ["base", "all"]:
        stage1_base(force=args.force)
    if args.stage in ["masks", "all"]:
        stage2_masks(force=args.force)
    if args.stage in ["4a", "all"]:
        stage4a_grass()
    if args.stage in ["4b", "all"]:
        stage4b_sand()
    if args.stage in ["4c", "all"]:
        stage4c_cliff()
    if args.stage in ["scree", "all"]:
        stage3_scree(force=args.force)
    if args.stage in ["4d", "all"]:
        stage4d_scree(force=args.force)
    if args.stage in ["materials"]:
        stage4_materials_and_tints(force=args.force)
    if args.stage in ["idmap", "all"]:
        stage5_idmap(force=args.force)

    print("ALL REQUESTED STAGES COMPLETED.", flush=True)


if __name__ == "__main__":
    main()

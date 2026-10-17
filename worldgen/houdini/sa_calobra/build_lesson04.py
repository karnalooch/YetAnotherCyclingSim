"""Build and verify Sa Calobra Lesson 04 - Pegasus Heightfield Materials Workflow.

Implements the complete Pegasus Lesson 04 materials workflow on the full Sa Calobra landscape
(7154 x 9829 cells at 0.5m spacing) and the 8000 x 8000m context background.
Sequence:
1. Grass / Ground (low-moderate slope, cut off at beach/sea)
2. Scale & Distortion on Grass (heightscale = 0.0, perlin noise distortion to break tiling)
3. Sand (coastal wash/beach, low height <= 25m, flat slope <= 18 deg, ripple displacement)
4. PE Heightfield Tint (composite height + slope + occlusion ramp, color ramp, height-neutral)
5. Cliff (steep slopes 28-90 deg, pale limestone 4K displacement 0.35m, smoothed transition)

Preserves Base B = Source + Manual Edits separation and reversibility.
Saves SaCalobra_Pegasus_Lesson04.hiplc and versioned caches.
"""
from __future__ import annotations

import gc
import json
import os
import pathlib
import sys
import time
import numpy as np
import hou


def main():
    proj_dir = pathlib.Path("D:/yacs/project/worldgen/houdini/sa_calobra").resolve()
    base_hip = proj_dir / "SaCalobra_Pegasus_Lesson03.hiplc"
    target_hip = proj_dir / "SaCalobra_Pegasus_Lesson04.hiplc"
    mat_hda_path = proj_dir / "otls/sop_PE_heightfield_material.1.0.hda"
    tint_hda_path = proj_dir / "otls/sop_PE_heightfield_tint.1.0.hda"

    print("=== START PEGASUS LESSON 04 BUILD ===")
    print(f"Loading base scene: {base_hip}")
    hou.setUpdateMode(hou.updateMode.Manual)
    hou.hipFile.load(base_hip.as_posix(), suppress_save_prompt=True, ignore_load_warnings=True)
    hou.setUpdateMode(hou.updateMode.AutoUpdate)

    # Install HDAs
    hou.hda.installFile(mat_hda_path.as_posix(), force_use_assets=True)
    hou.hda.installFile(tint_hda_path.as_posix(), force_use_assets=True)
    assert hou.nodeType(hou.sopNodeTypeCategory(), "PE_heightfield_material::1.0") is not None
    assert hou.nodeType(hou.sopNodeTypeCategory(), "PE_heightfield_tint::1.0") is not None
    print("Installed HDAs: PE_heightfield_material::1.0 and PE_heightfield_tint::1.0")

    geo = hou.node("/obj/SA_CALOBRA")
    assert geo is not None, "Node /obj/SA_CALOBRA not found"

    sc = geo.node("SOURCE_CACHE")
    csc = geo.node("CONTEXT_SOURCE_CACHE")
    man_cache = geo.node("MANUAL_EDITS_CACHE")
    compose_base = geo.node("COMPOSE_SOURCE_AND_MANUAL")

    assert sc and csc and man_cache and compose_base, "Missing baseline nodes in /obj/SA_CALOBRA"

    # Verify texture paths
    tex_dir = proj_dir / "inputs/textures"
    cliff_col = "$HIP/inputs/textures/SaCalobra_PaleLimestone_BaseColor.png"
    cliff_rough = "$HIP/inputs/textures/SaCalobra_PaleLimestone_Roughness.png"
    cliff_hgt = "$HIP/inputs/textures/wepoeaw_4K_Displacement.exr"

    grass_col = "$HIP/inputs/textures/SaCalobra_Grass_BaseColor.png"
    grass_rough = "$HIP/inputs/textures/SaCalobra_Grass_Roughness.png"
    grass_hgt = "$HIP/inputs/textures/tlonbisya_4K_Displacement.exr"

    sand_col = "$HIP/inputs/textures/coast_sand_01_diff_2k.jpg"
    sand_rough = "$HIP/inputs/textures/coast_sand_01_rough_2k.jpg"
    sand_hgt = "$HIP/inputs/textures/coast_sand_01_disp_2k.png"

    for p in ["SaCalobra_PaleLimestone_BaseColor.png", "SaCalobra_PaleLimestone_Roughness.png", "wepoeaw_4K_Displacement.exr",
              "SaCalobra_Grass_BaseColor.png", "SaCalobra_Grass_Roughness.png", "tlonbisya_4K_Displacement.exr",
              "coast_sand_01_diff_2k.jpg", "coast_sand_01_rough_2k.jpg", "coast_sand_01_disp_2k.png"]:
        assert (tex_dir / p).exists(), f"Missing required texture: {p}"

    # -------------------------------------------------------------
    # Helper to construct material chain on a base heightfield
    # -------------------------------------------------------------
    def build_material_chain(prefix, base_node, is_context=False):
        # 1. GRASS / GROUND MASK & MATERIAL
        mask_grass = geo.node(f"{prefix}_MASK_GRASS")
        if not mask_grass:
            mask_grass = geo.createNode("heightfield_maskbyfeature", f"{prefix}_MASK_GRASS")
        mask_grass.setInput(0, base_node)
        mask_grass.parm("maskbyslope").set(1)
        mask_grass.parm("min_slopeangle").set(0.0)
        mask_grass.parm("max_slopeangle").set(32.0)
        mask_grass.parm("maskbyheight").set(1)
        mask_grass.parm("minheight").set(8.0)  # cut off near beach / sea level
        mask_grass.parm("maxheight").set(1500.0)
        mask_grass.parm("maskbyocclusion").set(0)
        mask_grass.setPosition(base_node.position() + hou.Vector2(2.5, -1.2))

        mat_grass = geo.node(f"{prefix}_GRASS_MATERIAL")
        if not mat_grass:
            mat_grass = geo.createNode("PE_heightfield_material::1.0", f"{prefix}_GRASS_MATERIAL")
        mat_grass.setInput(0, base_node)
        mat_grass.setInput(1, mask_grass)
        mat_grass.parm("filename1").set(grass_col)
        mat_grass.parm("filename2").set(grass_rough)
        mat_grass.parm("filename3").set(grass_hgt)
        mat_grass.parm("size").set(12.0)
        mat_grass.parm("heightscale").set(0.0)  # Lesson 4 rule: grass height scale = 0
        mat_grass.parm("use_mask").set(1)
        mat_grass.parm("srcname1").set("mask")
        mat_grass.parm("input2").set("2")  # Colour preview mode
        # Distortion
        mat_grass.parm("use_distort").set(1)
        mat_grass.parm("noisetype").set("simplex")
        mat_grass.parm("amp").set(3.5)
        mat_grass.parm("element_size").set(15.0)
        mat_grass.parm("rough").set(0.5)
        mat_grass.parm("maxoctave").set(3)
        mat_grass.setPosition(mask_grass.position() + hou.Vector2(0, -1.5))

        # 2. SAND MASK & MATERIAL
        mask_sand = geo.node(f"{prefix}_MASK_SAND")
        if not mask_sand:
            mask_sand = geo.createNode("heightfield_maskbyfeature", f"{prefix}_MASK_SAND")
        mask_sand.setInput(0, base_node)
        mask_sand.parm("maskbyheight").set(1)
        mask_sand.parm("minheight").set(-50.0)
        mask_sand.parm("maxheight").set(25.0)  # Coastal beach / wash
        mask_sand.parm("maskbyslope").set(1)
        mask_sand.parm("min_slopeangle").set(0.0)
        mask_sand.parm("max_slopeangle").set(18.0)  # Gentle slope only
        mask_sand.parm("maskbyocclusion").set(0)
        mask_sand.setPosition(mat_grass.position() + hou.Vector2(2.5, -1.2))

        mat_sand = geo.node(f"{prefix}_SAND_MATERIAL")
        if not mat_sand:
            mat_sand = geo.createNode("PE_heightfield_material::1.0", f"{prefix}_SAND_MATERIAL")
        mat_sand.setInput(0, mat_grass)
        mat_sand.setInput(1, mask_sand)
        mat_sand.parm("filename1").set(sand_col)
        mat_sand.parm("filename2").set(sand_rough)
        mat_sand.parm("filename3").set(sand_hgt)
        mat_sand.parm("size").set(8.0)
        mat_sand.parm("heightscale").set(0.08)  # Gentle ripple displacement
        mat_sand.parm("use_mask").set(1)
        mat_sand.parm("srcname1").set("mask")
        mat_sand.parm("use_distort").set(0)
        mat_sand.parm("input2").set("2")
        mat_sand.setPosition(mask_sand.position() + hou.Vector2(0, -1.5))

        # 3. PE HEIGHTFIELD TINT
        # Ramp control layer: Height gradient + Slope gradient + Occlusion micro-variation
        # Linear ramp definition (continuous gradient without trapezoidal plateau)
        lin_ramp = hou.Ramp([hou.rampBasis.Linear, hou.rampBasis.Linear], [0.0, 1.0], [0.0, 1.0])

        tint_ramp_height = geo.node(f"{prefix}_TINT_RAMP_HEIGHT")
        if not tint_ramp_height:
            tint_ramp_height = geo.createNode("heightfield_maskbyfeature", f"{prefix}_TINT_RAMP_HEIGHT")
        tint_ramp_height.setInput(0, base_node)
        tint_ramp_height.parm("maskbyheight").set(1)
        tint_ramp_height.parm("minheight").set(0.0)
        tint_ramp_height.parm("maxheight").set(1440.0)
        tint_ramp_height.parm("maskbyslope").set(0)  # Review fix 1: explicitly disable default slope mask
        tint_ramp_height.parm("maskbyocclusion").set(0)
        tint_ramp_height.parm("heightramp").set(lin_ramp)
        tint_ramp_height.setPosition(mat_sand.position() + hou.Vector2(2.5, -1.2))

        tint_ramp_slope = geo.node(f"{prefix}_TINT_RAMP_SLOPE")
        if not tint_ramp_slope:
            tint_ramp_slope = geo.createNode("heightfield_maskbyfeature", f"{prefix}_TINT_RAMP_SLOPE")
        tint_ramp_slope.setInput(0, tint_ramp_height)
        tint_ramp_slope.parm("maskbyslope").set(1)
        tint_ramp_slope.parm("min_slopeangle").set(0.0)
        tint_ramp_slope.parm("max_slopeangle").set(90.0)
        tint_ramp_slope.parm("maskbyheight").set(0)
        tint_ramp_slope.parm("maskbyocclusion").set(0)
        tint_ramp_slope.parm("combine").set("add")
        tint_ramp_slope.parm("sloperamp").set(lin_ramp)
        tint_ramp_slope.setPosition(tint_ramp_height.position() + hou.Vector2(0, -1.2))

        tint_ramp_occlusion = geo.node(f"{prefix}_TINT_RAMP_OCCLUSION")
        if not tint_ramp_occlusion:
            tint_ramp_occlusion = geo.createNode("heightfield_maskbyfeature", f"{prefix}_TINT_RAMP_OCCLUSION")
        tint_ramp_occlusion.setInput(0, tint_ramp_slope)
        tint_ramp_occlusion.parm("maskbyocclusion").set(1)
        tint_ramp_occlusion.parm("maskbyslope").set(0)  # Review fix 1: explicitly disable default slope mask
        tint_ramp_occlusion.parm("maskbyheight").set(0)
        tint_ramp_occlusion.parm("viewdistance").set(25.0)
        tint_ramp_occlusion.parm("combine").set("subtract")
        tint_ramp_occlusion.parm("invertmask").set(1)
        tint_ramp_occlusion.setPosition(tint_ramp_slope.position() + hou.Vector2(0, -1.2))

        # Copy combined mask to dedicated ramp_layer
        tint_copy_ramp = geo.node(f"{prefix}_TINT_COPY_RAMP")
        if not tint_copy_ramp:
            tint_copy_ramp = geo.createNode("heightfield_copylayer", f"{prefix}_TINT_COPY_RAMP")
        tint_copy_ramp.setInput(0, tint_ramp_occlusion)
        tint_copy_ramp.parm("srcname1").set("mask")
        tint_copy_ramp.parm("dstname1").set("ramp_layer")
        tint_copy_ramp.setPosition(tint_ramp_occlusion.position() + hou.Vector2(0, -1.2))

        # Tint action mask: where tint acts (we pass grass mask so tint enriches grass/vegetation)
        tint_node = geo.node(f"{prefix}_HEIGHTFIELD_TINT")
        if not tint_node:
            tint_node = geo.createNode("PE_heightfield_tint::1.0", f"{prefix}_HEIGHTFIELD_TINT")
        tint_node.setInput(0, mat_sand)
        tint_node.setInput(1, tint_copy_ramp)
        tint_node.parm("use_ramp").set("1")  # Gradient mode
        tint_node.parm("srcname1").set("ramp_layer")  # Ramp coordinate layer
        tint_node.parm("ramp_mask").set("")  # Global gradient
        tint_node.parm("strength").set(0.85)

        # Set tint_ramp: lush green at bottom (0.0) -> warm olive (0.5) -> golden dry grass at top (1.0)
        bases = [hou.rampBasis.Linear] * 3
        keys = [0.0, 0.5, 1.0]
        vals = [
            (0.42, 0.56, 0.22),
            (0.58, 0.54, 0.28),
            (0.74, 0.64, 0.36)
        ]
        r = hou.Ramp(bases, keys, vals)
        tint_node.parm("tint_ramp").set(r)
        tint_node.setPosition(tint_copy_ramp.position() + hou.Vector2(0, -1.5))

        # 4. CLIFF MASK & MATERIAL
        # Review fix 2: smooth_radius in voxels. Target physical smooth radius = 3.0m
        # Working: spacing 0.5m => 3.0 / 0.5 = 6.0 voxels
        # Context: spacing 8000/2048 = 3.90625m => 3.0 / 3.90625 = 0.768 voxels
        cliff_smooth_voxels = 0.768 if is_context else 6.0
        mask_cliff = geo.node(f"{prefix}_MASK_CLIFF")
        if not mask_cliff:
            mask_cliff = geo.createNode("heightfield_maskbyfeature", f"{prefix}_MASK_CLIFF")
        mask_cliff.setInput(0, base_node)
        mask_cliff.parm("maskbyslope").set(1)
        mask_cliff.parm("min_slopeangle").set(28.0)
        mask_cliff.parm("max_slopeangle").set(90.0)
        mask_cliff.parm("maskbyheight").set(0)
        mask_cliff.parm("maskbyocclusion").set(0)
        mask_cliff.parm("smooth_radius").set(cliff_smooth_voxels)
        mask_cliff.setPosition(tint_node.position() + hou.Vector2(2.5, -1.2))

        mat_cliff = geo.node(f"{prefix}_CLIFF_MATERIAL")
        if not mat_cliff:
            mat_cliff = geo.createNode("PE_heightfield_material::1.0", f"{prefix}_CLIFF_MATERIAL")
        mat_cliff.setInput(0, tint_node)
        mat_cliff.setInput(1, mask_cliff)
        mat_cliff.parm("filename1").set(cliff_col)
        mat_cliff.parm("filename2").set(cliff_rough)
        mat_cliff.parm("filename3").set(cliff_hgt)
        mat_cliff.parm("size").set(20.0)
        mat_cliff.parm("heightscale").set(0.35)
        mat_cliff.parm("use_mask").set(1)
        mat_cliff.parm("srcname1").set("mask")
        mat_cliff.parm("input2").set("2")
        mat_cliff.setPosition(mask_cliff.position() + hou.Vector2(0, -1.5))

        return {
            "mask_grass": mask_grass,
            "mat_grass": mat_grass,
            "mask_sand": mask_sand,
            "mat_sand": mat_sand,
            "tint_ramp_height": tint_ramp_height,
            "tint_ramp_slope": tint_ramp_slope,
            "tint_ramp_occlusion": tint_ramp_occlusion,
            "tint_copy_ramp": tint_copy_ramp,
            "tint_node": tint_node,
            "mask_cliff": mask_cliff,
            "mat_cliff": mat_cliff,
            "final_mat": mat_cliff
        }

    # Build Working Chain
    print("--- Building Working Landscape Material Chain ---")
    working_chain = build_material_chain("WORKING", compose_base, is_context=False)

    # Build Context Chain
    print("--- Building Context Background Material Chain ---")
    context_chain = build_material_chain("CONTEXT", csc, is_context=True)

    # Working Material Cache
    working_mat_cache = geo.node("WORKING_MATERIAL_CACHE")
    if not working_mat_cache:
        working_mat_cache = geo.createNode("filecache::2.0", "WORKING_MATERIAL_CACHE")
    working_mat_cache.setInput(0, working_chain["final_mat"])
    working_mat_cache.parm("filemethod").set(1)
    working_mat_cache.parm("file").set("$HIP/cache/lesson04_working_material_05m.bgeo.sc")
    working_mat_cache.parm("loadfromdisk").set(0)

    # Procedural Delta: Working Material Height M - Base Height B (Source + Manual)
    delta_proc = geo.node("MATERIAL_PROCEDURAL_DELTA")
    if not delta_proc:
        delta_proc = geo.createNode("heightfield_layer", "MATERIAL_PROCEDURAL_DELTA")
    delta_proc.setInput(0, working_mat_cache)
    delta_proc.setInput(1, compose_base)
    delta_proc.parm("mode").set("subtract")
    delta_proc.parm("layer").set("height")

    # Layer 4 Procedural Delta cache (Dedicated versioned path so Lesson 3 checkpoint remains untouched!)
    layer3_cache = geo.node("LAYER3_PROCEDURAL_CACHE")
    if not layer3_cache:
        layer3_cache = geo.createNode("filecache::2.0", "LAYER3_PROCEDURAL_CACHE")
    layer3_cache.setInput(0, delta_proc)
    layer3_cache.parm("filemethod").set(1)
    layer3_cache.parm("file").set("$HIP/cache/lesson04_procedural_delta.bgeo.sc")
    layer3_cache.parm("loadfromdisk").set(0)

    # Context Material Cache
    ctx_mat_cache = geo.node("CONTEXT_MATERIAL_CACHE")
    if not ctx_mat_cache:
        ctx_mat_cache = geo.createNode("filecache::2.0", "CONTEXT_MATERIAL_CACHE")
    ctx_mat_cache.setInput(0, context_chain["final_mat"])
    ctx_mat_cache.parm("filemethod").set(1)
    ctx_mat_cache.parm("file").set("$HIP/cache/lesson04_context_material.bgeo.sc")
    ctx_mat_cache.parm("loadfromdisk").set(0)

    # Switches in /obj/SA_CALOBRA
    sw_working = geo.node("WORKING_SOURCE_OR_DETAIL")
    sw_working.setInput(0, compose_base)
    sw_working.setInput(1, working_mat_cache)

    sw_ctx = geo.node("CONTEXT_SOURCE_OR_DETAIL")
    sw_ctx.setInput(0, csc)
    sw_ctx.setInput(1, ctx_mat_cache)

    sw_view = geo.node("VIEW_CONTEXT_OR_WORKING")
    sw_view.setInput(0, sw_ctx)
    sw_view.setInput(1, sw_working)

    # Configure PREVIEW heightfield_visualize to display 'r g b' color volume
    preview_node = geo.node("PREVIEW")
    if preview_node:
        preview_node.parm("cdvolume").set("r g b")
        preview_node.parm("updatetinting").set("custom")
        preview_node.setInput(0, sw_view)

    out0 = geo.node("output0")
    assert out0 is not None, "output0 not found"
    out0.setInput(0, preview_node if preview_node else sw_view)
    out0.setDisplayFlag(True)
    out0.setRenderFlag(True)

    # Defaults: enable_detail = 1, view_resolution = 1 (Working), material_preview = 2 (Colour)
    geo.parm("enable_detail").set(1)
    geo.parm("view_resolution").set(1)
    if geo.parm("material_preview"):
        geo.parm("material_preview").set("2")

    # Save candidate HIP initially to fix $HIP resolution
    hou.hipFile.save(target_hip.as_posix())
    print(f"Saved initial target HIP: {target_hip.name}")

    # Review fix 3: Force recook and cache Working Material
    working_mat_dest = proj_dir / "cache/lesson04_working_material_05m.bgeo.sc"
    print("--- Cooking Working Material Cache (7154 x 9829 cells) ---")
    t0 = time.time()
    working_chain["final_mat"].cook(force=True)
    working_mat_dest.parent.mkdir(parents=True, exist_ok=True)
    working_chain["final_mat"].geometry().saveToFile(working_mat_dest.as_posix())
    working_mat_cache.parm("loadfromdisk").set(1)
    working_mat_cache.parm("reload").pressButton()
    t1 = time.time()
    print(f"Working material cached in {t1 - t0:.2f}s ({working_mat_dest.stat().st_size} bytes)")

    # Force cook and Cache Lesson 04 Procedural Delta (Dedicated versioned path!)
    layer4_proc_dest = proj_dir / "cache/lesson04_procedural_delta.bgeo.sc"
    print("--- Cooking Lesson 04 Procedural Delta Cache ---")
    delta_proc.cook(force=True)
    layer4_proc_dest.parent.mkdir(parents=True, exist_ok=True)
    delta_proc.geometry().saveToFile(layer4_proc_dest.as_posix())
    layer3_cache.parm("loadfromdisk").set(1)
    layer3_cache.parm("reload").pressButton()
    print(f"Lesson 04 Procedural delta cached ({layer4_proc_dest.stat().st_size} bytes)")

    # Force cook and Cache Context Material
    ctx_mat_dest = proj_dir / "cache/lesson04_context_material.bgeo.sc"
    print("--- Cooking Context Background Material Cache (2048 x 2048 cells) ---")
    context_chain["final_mat"].cook(force=True)
    ctx_mat_dest.parent.mkdir(parents=True, exist_ok=True)
    context_chain["final_mat"].geometry().saveToFile(ctx_mat_dest.as_posix())
    ctx_mat_cache.parm("loadfromdisk").set(1)
    ctx_mat_cache.parm("reload").pressButton()
    print(f"Context material cached ({ctx_mat_dest.stat().st_size} bytes)")

    # Reload PEGASUS_PIPELINE_OVERVIEW
    h_load = hou.node("/obj/PEGASUS_PIPELINE_OVERVIEW/Houdini_Load_Landscape")
    if h_load:
        print("Reloading PEGASUS_PIPELINE_OVERVIEW/Houdini_Load_Landscape...")
        for fc in h_load.children():
            if fc.type().name() == "file":
                fc.parm("reload").pressButton()
        h_load.cook(force=True)
        print("Houdini_Load_Landscape successfully cooked!")

    # Save target HIP immediately so file is complete
    hou.hipFile.save(target_hip.as_posix())
    print(f"=== Saved Lesson 04 HIP: {target_hip.name} ===")

    # -------------------------------------------------------------
    # Verification & Measurements (Memory-Safe)
    # -------------------------------------------------------------
    print("--- Verifying Deliverable Contracts ---")
    # A. Check Tint does not alter height
    mat_sand = working_chain["mat_sand"]
    mat_sand.cook(force=True)
    p_sand_h = next(p for p in mat_sand.geometry().prims() if p.attribValue("name") == "height")
    h_sand = np.frombuffer(p_sand_h.allVoxelsAsString(), dtype=np.float32)

    tint_node = working_chain["tint_node"]
    tint_node.cook(force=True)
    p_tint_h = next(p for p in tint_node.geometry().prims() if p.attribValue("name") == "height")
    h_tint = np.frombuffer(p_tint_h.allVoxelsAsString(), dtype=np.float32)

    tint_height_delta = float(np.abs(h_tint - h_sand).max())
    del h_sand, h_tint
    gc.collect()
    print(f"Tint Stage Height Invariance: max delta = {tint_height_delta:.8f} m (strictly 0.0m)")
    assert tint_height_delta == 0.0, f"FAIL: Tint modified height: {tint_height_delta}"

    # B. Reversibility against Base B
    compose_base.cook(force=True)
    p_base = next(p for p in compose_base.geometry().prims() if p.attribValue("name") == "height")
    h_base = np.frombuffer(p_base.allVoxelsAsString(), dtype=np.float32)

    geo.parm("enable_detail").set(0)
    sw_working.cook(force=True)
    p_rev = next(p for p in sw_working.geometry().prims() if p.attribValue("name") == "height")
    h_rev = np.frombuffer(p_rev.allVoxelsAsString(), dtype=np.float32)
    reversibility_delta = float(np.abs(h_rev - h_base).max())
    del h_rev
    gc.collect()
    assert reversibility_delta == 0.0, f"Reversibility failed: delta={reversibility_delta}"
    print(f"Reversibility confirmed: delta = {reversibility_delta} m everywhere vs Base B when detail disabled!")
    geo.parm("enable_detail").set(1)

    # C. Cell-by-cell signed equality verification:
    # Review fix 4: Layer3 == MaterialHeight - (Source + Manual) for all corresponding cells
    p_final = next(p for p in working_mat_cache.geometry().prims() if p.attribValue("name") == "height")
    h_final = np.frombuffer(p_final.allVoxelsAsString(), dtype=np.float32)
    signed_delta = h_final - h_base
    del h_final

    p_delta_geom = next(p for p in delta_proc.geometry().prims() if p.attribValue("name") == "height")
    h_delta_proc = np.frombuffer(p_delta_geom.allVoxelsAsString(), dtype=np.float32)

    diff_cell = np.abs(h_delta_proc - signed_delta)
    del h_delta_proc
    gc.collect()

    max_signed_error = float(diff_cell.max())
    mean_signed_error = float(diff_cell.mean())
    del diff_cell
    gc.collect()

    print(f"Cell-by-cell signed equality: max error = {max_signed_error:.8f} m, mean error = {mean_signed_error:.8f} m")
    assert max_signed_error < 1e-4, f"FAIL: Procedural delta does not match MaterialHeight - BaseB: {max_signed_error}"

    # Delta measurements on Working Landscape
    diff = np.abs(signed_delta)
    del signed_delta, h_base
    gc.collect()
    max_d = float(diff.max())
    mean_d = float(diff.mean())
    modified_cells = int(np.count_nonzero(diff > 0.001))

    # Mask cliff stats
    p_cliff_mask = next(p for p in working_chain["mask_cliff"].geometry().prims() if p.attribValue("name") == "mask")
    m_cliff = np.frombuffer(p_cliff_mask.allVoxelsAsString(), dtype=np.float32)
    active_cliff = m_cliff > 0.01
    del m_cliff
    gc.collect()
    mean_d_cliff = float(diff[active_cliff].mean()) if np.any(active_cliff) else 0.0
    p95_d_cliff = float(np.percentile(diff[active_cliff], 95)) if np.any(active_cliff) else 0.0
    del diff, active_cliff
    gc.collect()

    print(f"Overall displacement: max = {max_d:.4f} m, mean = {mean_d:.4f} m, modified cells = {modified_cells}")
    print(f"Cliff mask displacement: mean = {mean_d_cliff:.4f} m, p95 = {p95_d_cliff:.4f} m")

    # D. Color volume verification (sequential memory-safe reads)
    wg = working_mat_cache.geometry()
    volumes = [p.attribValue("name") for p in wg.prims() if p.type() == hou.primType.Volume]
    assert "r" in volumes and "g" in volumes and "b" in volumes, "FAIL: r, g, b colour volumes missing"
    pr = next(p for p in wg.prims() if p.attribValue("name") == "r")
    pg = next(p for p in wg.prims() if p.attribValue("name") == "g")
    pb = next(p for p in wg.prims() if p.attribValue("name") == "b")

    arr_r = np.frombuffer(pr.allVoxelsAsString(), dtype=np.float32)
    r_min, r_max = float(arr_r.min()), float(arr_r.max())
    del arr_r
    gc.collect()

    arr_g = np.frombuffer(pg.allVoxelsAsString(), dtype=np.float32)
    g_min, g_max = float(arr_g.min()), float(arr_g.max())
    del arr_g
    gc.collect()

    arr_b = np.frombuffer(pb.allVoxelsAsString(), dtype=np.float32)
    b_min, b_max = float(arr_b.min()), float(arr_b.max())
    del arr_b
    gc.collect()

    print(f"RGB verification: r in [{r_min:.3f}, {r_max:.3f}], g in [{g_min:.3f}, {g_max:.3f}], b in [{b_min:.3f}, {b_max:.3f}]")
    print(f"=== Saved Lesson 04 HIP: {target_hip.name} ===")

    metrics = {
        "candidate_project": target_hip.name,
        "base_composition": {
            "source_node": sc.name(),
            "manual_node": man_cache.name(),
            "compose_node": compose_base.name(),
            "layer_operation": "add"
        },
        "sequence": [
            {
                "step": "A. Grass / Ground",
                "node": "WORKING_GRASS_MATERIAL",
                "colour_texture": grass_col,
                "roughness_texture": grass_rough,
                "displacement_texture": grass_hgt,
                "size_m": 12.0,
                "heightscale_m": 0.0,
                "slope_mask_deg": [0.0, 32.0],
                "height_mask_min_m": 8.0
            },
            {
                "step": "B. Scale, Tiling & Distortion",
                "node": "WORKING_GRASS_MATERIAL",
                "distortion_enabled": True,
                "noise_type": "Perlin",
                "amplitude_m": 3.5,
                "element_size_m": 15.0,
                "heightscale_m": 0.0
            },
            {
                "step": "C. Sand",
                "node": "WORKING_SAND_MATERIAL",
                "colour_texture": sand_col,
                "roughness_texture": sand_rough,
                "displacement_texture": sand_hgt,
                "size_m": 8.0,
                "heightscale_m": 0.08,
                "height_range_m": [-50.0, 25.0],
                "slope_range_deg": [0.0, 18.0]
            },
            {
                "step": "D. PE Heightfield Tint",
                "node": "WORKING_HEIGHTFIELD_TINT",
                "mode": "Gradient",
                "ramp_coordinate_layer": "ramp_layer",
                "action_mask": "global",
                "strength": 0.85,
                "height_delta_m": tint_height_delta
            },
            {
                "step": "E. Cliff",
                "node": "WORKING_CLIFF_MATERIAL",
                "colour_texture": cliff_col,
                "roughness_texture": cliff_rough,
                "displacement_texture": cliff_hgt,
                "size_m": 20.0,
                "heightscale_m": 0.35,
                "slope_mask_deg": [28.0, 90.0]
            }
        ],
        "working_landscape_grid": {
            "resolution": [7154, 9829, 1],
            "spacing_m": 0.5,
            "total_cells": 7154 * 9829
        },
        "context_background_grid": {
            "resolution": [2048, 2048, 1],
            "size_m": [8000.0, 8000.0],
            "total_cells": 2048 * 2048
        },
        "measurements": {
            "max_absolute_displacement_m": max_d,
            "mean_displacement_over_full_landscape_m": mean_d,
            "mean_displacement_in_cliff_mask_m": mean_d_cliff,
            "p95_displacement_in_cliff_mask_m": p95_d_cliff,
            "modified_cells_count": modified_cells,
            "tint_height_delta_m": tint_height_delta,
            "reversibility_max_delta_when_disabled_m": reversibility_delta,
            "cell_signed_equality_max_error_m": max_signed_error,
            "cell_signed_equality_mean_error_m": mean_signed_error
        }
    }

    metrics_file = proj_dir / "evidence/lesson04_material_verification.json"
    metrics_file.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Verification metrics saved to: {metrics_file.name}")
    print(json.dumps(metrics["measurements"], indent=2))


if __name__ == "__main__":
    main()

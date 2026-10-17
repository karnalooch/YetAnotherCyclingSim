"""Build and verify Sa Calobra Lesson 03 - Pegasus Heightfield Materials.

Applies original PE_heightfield_material::1.0 to the full Sa Calobra landscape
(7154 x 9829 cells at 0.5m spacing) and the 8000 x 8000m context background.
Uses verified slope mask (28 to 90 deg), real Colour and Height textures,
measures delta, caches Layer 3 Procedural delta, and saves SaCalobra_Pegasus_Lesson03.hiplc.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys
import time
import numpy as np
import hou


def main():
    proj_dir = pathlib.Path("D:/yacs/project/worldgen/houdini/sa_calobra").resolve()
    base_hip = proj_dir / "SaCalobra_Pegasus_Lesson02.hiplc"
    target_hip = proj_dir / "SaCalobra_Pegasus_Lesson03.hiplc"
    hda_path = proj_dir / "otls/sop_PE_heightfield_material.1.0.hda"

    print("=== START PEGASUS LESSON 03 BUILD ===")
    print(f"Loading base scene: {base_hip}")
    hou.setUpdateMode(hou.updateMode.Manual)
    hou.hipFile.load(base_hip.as_posix(), suppress_save_prompt=True, ignore_load_warnings=True)
    hou.setUpdateMode(hou.updateMode.AutoUpdate)

    # Install HDA and verify
    hou.hda.installFile(hda_path.as_posix())
    defs = hou.hda.definitionsInFile(hda_path.as_posix())
    assert defs, f"No definitions found in {hda_path}"
    print(f"Installed HDA: {defs[0].nodeTypeName()} from {hda_path.name}")

    geo = hou.node("/obj/SA_CALOBRA")
    assert geo is not None, "Node /obj/SA_CALOBRA not found"

    sc = geo.node("SOURCE_CACHE")
    assert sc is not None, "SOURCE_CACHE node not found"
    csc = geo.node("CONTEXT_SOURCE_CACHE")
    assert csc is not None, "CONTEXT_SOURCE_CACHE node not found"

    # Texture paths (using $HIP relative paths)
    tex_dir = proj_dir / "inputs/textures"
    col_path = "$HIP/inputs/textures/SaCalobra_PaleLimestone_BaseColor.png"
    rough_path = "$HIP/inputs/textures/SaCalobra_PaleLimestone_Roughness.png"
    hgt_path = "$HIP/inputs/textures/wepoeaw_4K_Displacement.exr"

    assert (tex_dir / "SaCalobra_PaleLimestone_BaseColor.png").exists(), "BaseColor texture missing"
    assert (tex_dir / "wepoeaw_4K_Displacement.exr").exists(), "Displacement texture missing"

    # 1. Slope mask for full working landscape (7154 x 9829 cells)
    mask_rock = geo.node("MASK_ROCK_SLOPE")
    if not mask_rock:
        mask_rock = geo.createNode("heightfield_maskbyfeature", "MASK_ROCK_SLOPE")
    mask_rock.setInput(0, sc)
    mask_rock.parm("maskbyslope").set(1)
    mask_rock.parm("min_slopeangle").set(28.0)
    mask_rock.parm("max_slopeangle").set(90.0)
    mask_rock.setPosition(sc.position() + hou.Vector2(3.0, -1.5))

    # 2. Material node for working landscape
    mat_rock = geo.node("ROCK_SLOPE_MATERIAL")
    if not mat_rock:
        mat_rock = geo.createNode("PE_heightfield_material::1.0", "ROCK_SLOPE_MATERIAL")
    mat_rock.setInput(0, sc)
    mat_rock.setInput(1, mask_rock)
    mat_rock.parm("filename1").set(col_path)
    mat_rock.parm("filename2").set(rough_path)
    mat_rock.parm("filename3").set(hgt_path)
    mat_rock.parm("size").set(20.0)
    mat_rock.parm("heightscale").set(0.35)
    mat_rock.parm("use_mask").set(1)
    mat_rock.parm("srcname1").set("mask")
    mat_rock.parm("input2").set("2") # Colour preview default
    mat_rock.setPosition(mask_rock.position() + hou.Vector2(0, -1.8))

    # 3. File cache for full working material
    working_mat_cache = geo.node("WORKING_MATERIAL_CACHE")
    if not working_mat_cache:
        working_mat_cache = geo.createNode("filecache::2.0", "WORKING_MATERIAL_CACHE")
    working_mat_cache.setInput(0, mat_rock)
    working_mat_cache.parm("filemethod").set(1)
    working_mat_cache.parm("file").set("$HIP/cache/lesson03_working_material_05m.bgeo.sc")
    working_mat_cache.parm("loadfromdisk").set(0)
    working_mat_cache.setPosition(mat_rock.position() + hou.Vector2(0, -1.5))

    # 4. Procedural Delta computation: Working Material Height - Source Base Height
    delta_proc = geo.node("MATERIAL_PROCEDURAL_DELTA")
    if not delta_proc:
        delta_proc = geo.createNode("heightfield_layer", "MATERIAL_PROCEDURAL_DELTA")
    delta_proc.setInput(0, working_mat_cache)
    delta_proc.setInput(1, sc)
    delta_proc.parm("mode").set("subtract")
    delta_proc.parm("layer").set("height")
    delta_proc.setPosition(working_mat_cache.position() + hou.Vector2(3.0, -1.5))

    # File cache for Layer 3 Procedural delta
    layer3_cache = geo.node("LAYER3_PROCEDURAL_CACHE")
    if not layer3_cache:
        layer3_cache = geo.createNode("filecache::2.0", "LAYER3_PROCEDURAL_CACHE")
    layer3_cache.setInput(0, delta_proc)
    layer3_cache.parm("filemethod").set(1)
    layer3_cache.parm("file").set("$HIP/Pegasus/Landscape/Landscape Heightfield Layers/Pegasus_Landscape_Layer_3_Procedural_Detail.bgeo.sc")
    layer3_cache.parm("loadfromdisk").set(0)
    layer3_cache.setPosition(delta_proc.position() + hou.Vector2(0, -1.5))

    # 5. Context background slope mask and material (2048 x 2048 cells)
    ctx_mask = geo.node("CONTEXT_MASK_ROCK_SLOPE")
    if not ctx_mask:
        ctx_mask = geo.createNode("heightfield_maskbyfeature", "CONTEXT_MASK_ROCK_SLOPE")
    ctx_mask.setInput(0, csc)
    ctx_mask.parm("maskbyslope").set(1)
    ctx_mask.parm("min_slopeangle").set(28.0)
    ctx_mask.parm("max_slopeangle").set(90.0)
    ctx_mask.setPosition(csc.position() + hou.Vector2(3.0, -1.5))

    ctx_mat = geo.node("CONTEXT_ROCK_MATERIAL")
    if not ctx_mat:
        ctx_mat = geo.createNode("PE_heightfield_material::1.0", "CONTEXT_ROCK_MATERIAL")
    ctx_mat.setInput(0, csc)
    ctx_mat.setInput(1, ctx_mask)
    ctx_mat.parm("filename1").set(col_path)
    ctx_mat.parm("filename2").set(rough_path)
    ctx_mat.parm("filename3").set(hgt_path)
    ctx_mat.parm("size").set(20.0)
    ctx_mat.parm("heightscale").set(0.35)
    ctx_mat.parm("use_mask").set(1)
    ctx_mat.parm("srcname1").set("mask")
    ctx_mat.parm("input2").set("2")
    ctx_mat.setPosition(ctx_mask.position() + hou.Vector2(0, -1.8))

    ctx_mat_cache = geo.node("CONTEXT_MATERIAL_CACHE")
    if not ctx_mat_cache:
        ctx_mat_cache = geo.createNode("filecache::2.0", "CONTEXT_MATERIAL_CACHE")
    ctx_mat_cache.setInput(0, ctx_mat)
    ctx_mat_cache.parm("filemethod").set(1)
    ctx_mat_cache.parm("file").set("$HIP/cache/lesson03_context_material.bgeo.sc")
    ctx_mat_cache.parm("loadfromdisk").set(0)
    ctx_mat_cache.setPosition(ctx_mat.position() + hou.Vector2(0, -1.5))

    # 6. Update existing switches in /obj/SA_CALOBRA
    sw_working = geo.node("WORKING_SOURCE_OR_DETAIL")
    sw_working.setInput(0, sc)
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

    # 7. Add Lesson 03 parameters to landscape_controls folder
    ptg = geo.parmTemplateGroup()
    lc = ptg.findFolder("Landscape controls")
    if lc:
        if not ptg.find("material_preview"):
            ptg.appendToFolder("Landscape controls", hou.MenuParmTemplate(
                "material_preview", "Material Preview Mode",
                menu_items=("0", "1", "2"),
                menu_labels=("None (Raw Geometry)", "Roughness", "Colour (Material Texture)"),
                default_value=2
            ))
        if not ptg.find("rock_scale"):
            ptg.appendToFolder("Landscape controls", hou.FloatParmTemplate(
                "rock_scale", "Rock Texture Scale (m)", 1, default_value=(20.0,)
            ))
        if not ptg.find("rock_height"):
            ptg.appendToFolder("Landscape controls", hou.FloatParmTemplate(
                "rock_height", "Rock Height Amplitude (m)", 1, default_value=(0.35,)
            ))
        geo.setParmTemplateGroup(ptg)

    # Link parameters to expressions
    mat_rock.parm("input2").setExpression('ch("../material_preview")')
    ctx_mat.parm("input2").setExpression('ch("../material_preview")')
    mat_rock.parm("size").setExpression('ch("../rock_scale")')
    ctx_mat.parm("size").setExpression('ch("../rock_scale")')
    mat_rock.parm("heightscale").setExpression('ch("../rock_height")')
    ctx_mat.parm("heightscale").setExpression('ch("../rock_height")')

    # Defaults: enable detail = 1, working landscape = 1, colour preview = 2
    geo.parm("enable_detail").set(1)
    geo.parm("view_resolution").set(1) # 1 = Working landscape
    if geo.parm("material_preview"):
        geo.parm("material_preview").set("2")

    # Initial save to establish $HIP
    hou.hipFile.save(target_hip.as_posix())
    print(f"Saved initial target HIP: {target_hip.name}")

    # 8. Cook and Cache
    print("--- Cooking Working Material Cache (7154 x 9829 cells) ---")
    t0 = time.time()
    mat_rock.cook(force=True)
    working_mat_dest = proj_dir / "cache/lesson03_working_material_05m.bgeo.sc"
    mat_rock.geometry().saveToFile(working_mat_dest.as_posix())
    working_mat_cache.parm("loadfromdisk").set(1)
    working_mat_cache.parm("reload").pressButton()
    t1 = time.time()
    print(f"Working material cached in {t1 - t0:.2f}s ({working_mat_dest.stat().st_size} bytes)")

    print("--- Cooking Layer 3 Procedural Delta Cache ---")
    delta_proc.cook(force=True)
    layer3_dest = proj_dir / "Pegasus/Landscape/Landscape Heightfield Layers/Pegasus_Landscape_Layer_3_Procedural_Detail.bgeo.sc"
    delta_proc.geometry().saveToFile(layer3_dest.as_posix())
    layer3_cache.parm("loadfromdisk").set(1)
    layer3_cache.parm("reload").pressButton()
    print(f"Layer 3 Procedural delta cached ({layer3_dest.stat().st_size} bytes)")

    print("--- Cooking Context Background Material Cache (2048 x 2048 cells) ---")
    ctx_mat.cook(force=True)
    ctx_mat_dest = proj_dir / "cache/lesson03_context_material.bgeo.sc"
    ctx_mat.geometry().saveToFile(ctx_mat_dest.as_posix())
    ctx_mat_cache.parm("loadfromdisk").set(1)
    ctx_mat_cache.parm("reload").pressButton()
    print(f"Context material cached ({ctx_mat_dest.stat().st_size} bytes)")

    # 9. Reload pipeline overview Houdini_Load_Landscape
    h_load = hou.node("/obj/PEGASUS_PIPELINE_OVERVIEW/Houdini_Load_Landscape")
    if h_load:
        print("Reloading PEGASUS_PIPELINE_OVERVIEW/Houdini_Load_Landscape...")
        # Force cook of files inside
        for fc in h_load.children():
            if fc.type().name() == "file":
                fc.parm("reload").pressButton()
        h_load.cook(force=True)
        print("Houdini_Load_Landscape successfully cooked with updated Layer 3!")

    # 10. Measure deltas and verify reversibility
    p_src = next(p for p in sc.geometry().prims() if p.attribValue("name") == "height")
    p_mat = next(p for p in working_mat_cache.geometry().prims() if p.attribValue("name") == "height")
    p_mask = next(p for p in mask_rock.geometry().prims() if p.attribValue("name") == "mask")

    h_src = np.frombuffer(p_src.allVoxelsAsString(), dtype=np.float32)
    h_mat = np.frombuffer(p_mat.allVoxelsAsString(), dtype=np.float32)
    m_arr = np.frombuffer(p_mask.allVoxelsAsString(), dtype=np.float32)

    diff = np.abs(h_mat - h_src)
    max_d = float(diff.max())
    mean_d = float(diff.mean())
    active_m = m_arr > 0.01
    inactive_m = m_arr < 0.0001
    mean_d_active = float(diff[active_m].mean())
    p95_d_active = float(np.percentile(diff[active_m], 95))
    max_d_outside = float(diff[inactive_m].max(initial=0.0))
    modified_cells = int(np.count_nonzero(diff > 0.001))

    # Verify reversibility: switch enable_detail = 0
    geo.parm("enable_detail").set(0)
    sw_working.cook(force=True)
    p_rev = next(p for p in sw_working.geometry().prims() if p.attribValue("name") == "height")
    h_rev = np.frombuffer(p_rev.allVoxelsAsString(), dtype=np.float32)
    reversibility_delta = float(np.abs(h_rev - h_src).max())
    assert reversibility_delta == 0.0, f"Reversibility failed: delta={reversibility_delta}"
    print(f"Reversibility confirmed: delta = {reversibility_delta} m everywhere when detail disabled!")

    # Restore enable_detail = 1
    geo.parm("enable_detail").set(1)

    # Save final target HIP
    hou.hipFile.save(target_hip.as_posix())
    print(f"=== Saved Lesson 03 HIP: {target_hip.name} ===")

    metrics = {
        "candidate_project": target_hip.name,
        "hda": {
            "type": defs[0].nodeTypeName(),
            "library_file": hda_path.as_posix(),
        },
        "textures": {
            "colour_map": col_path,
            "roughness_map": rough_path,
            "height_displacement_map": hgt_path,
            "rock_scale_m": 20.0,
            "height_scale_m": 0.35,
            "slope_mask_angle_deg": [28.0, 90.0]
        },
        "working_landscape_grid": {
            "resolution": [7154, 9829, 1],
            "spacing_m": 0.5,
            "total_cells": 7154 * 9829,
            "bounds_x_m": [-1771.25, 1805.25],
            "bounds_z_m": [-1769.75, 3144.25],
        },
        "context_background_grid": {
            "resolution": [2048, 2048, 1],
            "size_m": [8000.0, 8000.0],
            "total_cells": 2048 * 2048
        },
        "measurements": {
            "max_absolute_displacement_m": max_d,
            "mean_displacement_over_full_landscape_m": mean_d,
            "mean_displacement_in_slope_mask_m": mean_d_active,
            "p95_displacement_in_slope_mask_m": p95_d_active,
            "max_displacement_outside_slope_mask_m": max_d_outside,
            "modified_cells_count": modified_cells,
            "reversibility_max_delta_when_disabled_m": reversibility_delta
        }
    }

    metrics_file = proj_dir / "evidence/lesson03_material_verification.json"
    metrics_file.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Verification metrics saved to: {metrics_file.name}")
    print(json.dumps(metrics["measurements"], indent=2))


if __name__ == "__main__":
    main()

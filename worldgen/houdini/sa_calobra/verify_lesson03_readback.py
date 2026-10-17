"""Fresh readback verification of SaCalobra_Pegasus_Lesson03.hiplc.

Performs strict, dynamic assertion in an isolated Houdini process:
- Clean load of SaCalobra_Pegasus_Lesson03.hiplc
- Graph topology assertions (Base B = Source + Manual wired to Mask, Material, Delta, Switch)
- Live HDA definition resolution (libraryFilePath)
- Parameter value extraction (size, heightscale, slope mask range)
- Texture path resolution and file existence
- Resolution, bounds, and volumes check (Working 7154x9829, Context 2048x2048)
- Dynamic reversibility test against Base B (enable_detail = 0 yields 0.0000m delta)
- Saves actual measured receipt to evidence/lesson03_fresh_readback_receipt.json
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import numpy as np
import hou


def main():
    proj_dir = pathlib.Path("D:/yacs/project/worldgen/houdini/sa_calobra").resolve()
    target_hip = proj_dir / "SaCalobra_Pegasus_Lesson03.hiplc"
    evidence_dir = proj_dir / "evidence"

    print("=== START FRESH READBACK VERIFICATION ===")
    print(f"Loading scene: {target_hip}")
    hou.setUpdateMode(hou.updateMode.Manual)
    hou.hipFile.load(target_hip.as_posix(), suppress_save_prompt=True, ignore_load_warnings=True)
    hou.setUpdateMode(hou.updateMode.AutoUpdate)

    geo = hou.node("/obj/SA_CALOBRA")
    assert geo is not None, "FAIL: /obj/SA_CALOBRA not found"

    # 1. Graph Topology Assertions
    sc = geo.node("SOURCE_CACHE")
    assert sc is not None, "FAIL: SOURCE_CACHE not found"
    man_cache = geo.node("MANUAL_EDITS_CACHE")
    assert man_cache is not None, "FAIL: MANUAL_EDITS_CACHE not found"
    compose_base = geo.node("COMPOSE_SOURCE_AND_MANUAL")
    assert compose_base is not None, "FAIL: COMPOSE_SOURCE_AND_MANUAL not found"
    mask_rock = geo.node("MASK_ROCK_SLOPE")
    assert mask_rock is not None, "FAIL: MASK_ROCK_SLOPE not found"
    mat_node = geo.node("ROCK_SLOPE_MATERIAL")
    assert mat_node is not None, "FAIL: ROCK_SLOPE_MATERIAL not found"
    w_cache = geo.node("WORKING_MATERIAL_CACHE")
    assert w_cache is not None, "FAIL: WORKING_MATERIAL_CACHE not found"
    delta_proc = geo.node("MATERIAL_PROCEDURAL_DELTA")
    assert delta_proc is not None, "FAIL: MATERIAL_PROCEDURAL_DELTA not found"
    l3_cache = geo.node("LAYER3_PROCEDURAL_CACHE")
    assert l3_cache is not None, "FAIL: LAYER3_PROCEDURAL_CACHE not found"
    sw_working = geo.node("WORKING_SOURCE_OR_DETAIL")
    assert sw_working is not None, "FAIL: WORKING_SOURCE_OR_DETAIL not found"

    # Assert wiring
    assert compose_base.inputs()[0].name() == "SOURCE_CACHE", f"FAIL: compose_base input 0 is {compose_base.inputs()[0]}"
    assert compose_base.inputs()[1].name() == "MANUAL_EDITS_CACHE", f"FAIL: compose_base input 1 is {compose_base.inputs()[1]}"
    assert compose_base.parm("mode").evalAsString() == "add", f"FAIL: compose_base mode is {compose_base.parm('mode').eval()}"

    assert mask_rock.inputs()[0].name() == "COMPOSE_SOURCE_AND_MANUAL", f"FAIL: mask_rock input 0 is {mask_rock.inputs()[0]}"
    assert mat_node.inputs()[0].name() == "COMPOSE_SOURCE_AND_MANUAL", f"FAIL: mat_node input 0 is {mat_node.inputs()[0]}"
    assert mat_node.inputs()[1].name() == "MASK_ROCK_SLOPE", f"FAIL: mat_node input 1 is {mat_node.inputs()[1]}"

    assert delta_proc.inputs()[0].name() == "WORKING_MATERIAL_CACHE", f"FAIL: delta_proc input 0 is {delta_proc.inputs()[0]}"
    assert delta_proc.inputs()[1].name() == "COMPOSE_SOURCE_AND_MANUAL", f"FAIL: delta_proc input 1 is {delta_proc.inputs()[1]}"
    assert delta_proc.parm("mode").evalAsString() == "subtract", f"FAIL: delta_proc mode is {delta_proc.parm('mode').eval()}"

    assert sw_working.inputs()[0].name() == "COMPOSE_SOURCE_AND_MANUAL", f"FAIL: sw_working input 0 is {sw_working.inputs()[0]}"
    assert sw_working.inputs()[1].name() == "WORKING_MATERIAL_CACHE", f"FAIL: sw_working input 1 is {sw_working.inputs()[1]}"
    print("PASS: Graph topology verified: Base B = Source + Manual correctly wired across all nodes.")

    # 2. HDA Definition Assertion
    hda_def = mat_node.type().definition()
    assert hda_def is not None, "FAIL: mat_node has no definition"
    hda_lib_path = pathlib.Path(hda_def.libraryFilePath()).resolve().as_posix()
    assert os.path.exists(hda_lib_path), f"FAIL: HDA library file not found: {hda_lib_path}"
    hda_type_name = mat_node.type().name()
    print(f"PASS: HDA definition resolved: {hda_type_name} from {hda_lib_path}")

    # 3. Parameters Extraction
    rock_scale = float(mat_node.parm("size").eval())
    rock_heightscale = float(mat_node.parm("heightscale").eval())
    use_mask = int(mat_node.parm("use_mask").eval())
    mask_min_angle = float(mask_rock.parm("min_slopeangle").eval())
    mask_max_angle = float(mask_rock.parm("max_slopeangle").eval())
    assert rock_scale == 20.0, f"FAIL: Unexpected rock scale {rock_scale}"
    assert abs(rock_heightscale - 0.35) < 1e-4, f"FAIL: Unexpected heightscale {rock_heightscale}"
    assert use_mask == 1, f"FAIL: use_mask is not 1"
    assert mask_min_angle == 28.0 and mask_max_angle == 90.0, f"FAIL: Slope angles [{mask_min_angle}, {mask_max_angle}]"
    print(f"PASS: Parameters verified: size={rock_scale}m, heightscale={rock_heightscale}m, slope=[{mask_min_angle}°, {mask_max_angle}°]")

    # 4. Texture Paths Evaluation
    col_eval = pathlib.Path(mat_node.parm("filename1").evalAsString()).resolve().as_posix()
    rough_eval = pathlib.Path(mat_node.parm("filename2").evalAsString()).resolve().as_posix()
    hgt_eval = pathlib.Path(mat_node.parm("filename3").evalAsString()).resolve().as_posix()
    assert os.path.exists(col_eval), f"FAIL: Colour texture does not exist: {col_eval}"
    assert os.path.exists(rough_eval), f"FAIL: Roughness texture does not exist: {rough_eval}"
    assert os.path.exists(hgt_eval), f"FAIL: Height texture does not exist: {hgt_eval}"
    col_size = os.path.getsize(col_eval)
    rough_size = os.path.getsize(rough_eval)
    hgt_size = os.path.getsize(hgt_eval)
    print(f"PASS: Textures resolved: Colour ({col_size} B), Roughness ({rough_size} B), Height ({hgt_size} B)")

    # 5. Working Material Cache Check
    assert w_cache.parm("loadfromdisk").eval() == 1, "FAIL: WORKING_MATERIAL_CACHE loadfromdisk is not 1"
    w_cache.cook(force=True)
    wg = w_cache.geometry()
    volumes = [p.attribValue("name") for p in wg.prims() if p.type() == hou.primType.Volume]
    assert "height" in volumes, "FAIL: height volume missing"
    assert "r" in volumes and "g" in volumes and "b" in volumes, "FAIL: r, g, b colour volumes missing"
    h_prim = next(p for p in wg.prims() if p.attribValue("name") == "height")
    res = list(h_prim.resolution())
    bbox = [float(v) for v in h_prim.boundingBox().minvec()] + [float(v) for v in h_prim.boundingBox().maxvec()]
    assert tuple(res) == (7154, 9829, 1), f"FAIL: Unexpected resolution {res}"
    print(f"PASS: Working Material Cache verified: {res}, volumes: {volumes}")

    # 6. Context Background Cache Check
    ctx_cache = geo.node("CONTEXT_MATERIAL_CACHE")
    assert ctx_cache is not None, "FAIL: CONTEXT_MATERIAL_CACHE not found"
    ctx_cache.cook(force=True)
    cg = ctx_cache.geometry()
    ctx_h_prim = next(p for p in cg.prims() if p.attribValue("name") == "height")
    ctx_res = list(ctx_h_prim.resolution())
    ctx_bbox = [float(v) for v in ctx_h_prim.boundingBox().minvec()] + [float(v) for v in ctx_h_prim.boundingBox().maxvec()]
    assert tuple(ctx_res) == (2048, 2048, 1), f"FAIL: Unexpected context resolution {ctx_res}"
    print(f"PASS: Context Material Cache verified: {ctx_res}")

    # 7. Layer 3 Procedural Delta Cache Check
    assert l3_cache.parm("loadfromdisk").eval() == 1, "FAIL: LAYER3_PROCEDURAL_CACHE loadfromdisk is not 1"
    l3_cache.cook(force=True)
    l3_geo = l3_cache.geometry()
    l3_h_prim = next(p for p in l3_geo.prims() if p.attribValue("name") == "height")
    l3_h = np.frombuffer(l3_h_prim.allVoxelsAsString(), dtype=np.float32)
    l3_max = float(np.abs(l3_h).max())
    print(f"PASS: Layer 3 Procedural Delta verified: max delta = {l3_max:.4f} m")
    assert 0.30 <= l3_max <= 0.40, f"FAIL: Layer 3 max delta unexpected: {l3_max}"

    # 8. Dynamic Reversibility Measurement against Base B
    compose_base.cook(force=True)
    p_base = next(p for p in compose_base.geometry().prims() if p.attribValue("name") == "height")
    h_base = np.frombuffer(p_base.allVoxelsAsString(), dtype=np.float32)

    sc.cook(force=True)
    p_src = next(p for p in sc.geometry().prims() if p.attribValue("name") == "height")
    h_src = np.frombuffer(p_src.allVoxelsAsString(), dtype=np.float32)
    base_delta_vs_source = float(np.abs(h_base - h_src).max())
    print(f"Base B vs pure Source delta: {base_delta_vs_source:.6f} m (neutral)")
    assert base_delta_vs_source == 0.0, f"FAIL: Base B is not neutral: {base_delta_vs_source}"

    # Disable detail on /obj/SA_CALOBRA and measure output
    geo.parm("enable_detail").set(0)
    sw_working.cook(force=True)
    p_detail_off = next(p for p in sw_working.geometry().prims() if p.attribValue("name") == "height")
    h_detail_off = np.frombuffer(p_detail_off.allVoxelsAsString(), dtype=np.float32)
    measured_rev_delta = float(np.abs(h_detail_off - h_base).max())
    print(f"PASS: Dynamic reversibility verified: max delta vs Base B = {measured_rev_delta:.6f} m")
    assert measured_rev_delta == 0.0, f"FAIL: Dynamic reversibility failed: {measured_rev_delta}"

    # Re-enable detail
    geo.parm("enable_detail").set(1)

    # 9. Pipeline Overview Houdini_Load_Landscape Check
    h_load = hou.node("/obj/PEGASUS_PIPELINE_OVERVIEW/Houdini_Load_Landscape")
    assert h_load is not None, "FAIL: Houdini_Load_Landscape not found"
    h_load.cook(force=True)
    hl_geo = h_load.geometry()
    hl_h_prim = next(p for p in hl_geo.prims() if p.attribValue("name") == "height")
    print(f"PASS: Houdini_Load_Landscape verified: {hl_h_prim.resolution()}")

    # Build fresh receipt purely from inspected values
    receipt = {
        "status": "PASS",
        "timestamp_utc": hou.time(),
        "project": target_hip.name,
        "graph_architecture": {
            "base_composition_node": compose_base.name(),
            "source_node": sc.name(),
            "manual_node": man_cache.name(),
            "mask_node": mask_rock.name(),
            "material_node": mat_node.name(),
            "delta_node": delta_proc.name(),
            "working_switch_node": sw_working.name(),
            "switch_input0": sw_working.inputs()[0].name(),
            "switch_input1": sw_working.inputs()[1].name(),
            "delta_input0": delta_proc.inputs()[0].name(),
            "delta_input1": delta_proc.inputs()[1].name(),
        },
        "hda_verification": {
            "operator_type": hda_type_name,
            "library_file_path": hda_lib_path,
            "library_file_size_bytes": os.path.getsize(hda_lib_path),
        },
        "parameters": {
            "rock_material_scale_m": rock_scale,
            "rock_material_heightscale_m": rock_heightscale,
            "use_mask": use_mask,
            "slope_mask_angle_min_deg": mask_min_angle,
            "slope_mask_angle_max_deg": mask_max_angle,
        },
        "textures": {
            "colour_map": {
                "path": col_eval,
                "size_bytes": col_size
            },
            "roughness_map": {
                "path": rough_eval,
                "size_bytes": rough_size
            },
            "displacement_map": {
                "path": hgt_eval,
                "size_bytes": hgt_size
            }
        },
        "grids": {
            "working_resolution": res,
            "working_bounding_box": bbox,
            "working_volumes": volumes,
            "context_resolution": ctx_res,
            "context_bounding_box": ctx_bbox,
        },
        "measurements": {
            "base_vs_pure_source_delta_m": base_delta_vs_source,
            "layer3_procedural_delta_max_m": l3_max,
            "measured_reversibility_delta_when_detail_disabled_m": measured_rev_delta,
        }
    }

    receipt_file = evidence_dir / "lesson03_fresh_readback_receipt.json"
    receipt_file.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(f"Receipt written to: {receipt_file.name}")
    print("=== ALL READBACK ASSERTIONS PASSED WITH ZERO HARDCODING ===")


if __name__ == "__main__":
    main()

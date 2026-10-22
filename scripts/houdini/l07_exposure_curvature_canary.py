#!/usr/bin/env python3
"""Bounded actual native SideFX Exposure/Curvature branches after author Tint4.

Author graph: Tint4 -> heightfield_visualize4 -> mask12 -> mask13.
Main graph: Tint4 -> ExposureTint5(mask12) -> CurvatureTint6(mask13).
This is an isolated site-mechanism canary; exact final author ramp tuples are
UNKNOWN. The chosen ramp knots are marked YACS_ADAPTATION, not source claims.
Occlusion at View Distance 145m has insufficient halo on this 128m site.
Never touches canonical Sa Calobra caches, current UE packages, or user HIP.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

MATERIAL_RUN = "39808914161-1"
MATERIAL_ROOT = Path("D:/yacs/work/lesson07-cc0-real-material") / MATERIAL_RUN
SCRATCH = Path("D:/yacs/work/lesson07-exposure-curvature-native")
HDA = Path("D:/yacs/project/worldgen/houdini/sa_calobra/otls/sop_PE_heightfield_tint.1.0.hda")
HDA_SHA = "93cc47dd511bc3d5868835b5dd3b9082c13cab23355b688aaf2a947e8687a2ed"
EXPOSURE_MASK_PARMS = {
    "smooth_radius":1.0,
    "combine":0, # Native menu default=Replace; video verified
    "invertmask":0,
    "maskbyslope":0,
    "maskbyheight":0,
    "maskbycurvature":0,
    "maskbydir":0,
    "maskbyocclusion":1,
    "minexposure":0.0,
    "maxexposure":1.0,
    "viewdistance":145.0,
    "stepscale":1.0,
    "numsearches":16,
    "heightlayer":"height",
    "masklayer":"mask",
}
CURVATURE_MASK_PARMS = {
    "smooth_radius":1.0,
    "combine":0,
    "invertmask":0,
    "maskbyslope":0,
    "maskbyheight":0,
    "maskbycurvature":1,
    "maskbydir":0,
    "maskbyocclusion":0,
    "max_curvature":0.18,
    "heightlayer":"height",
    "masklayer":"mask",
}
EXPOSURE_TINT_PARMS = {
    "use_ramp":1,"strength":1.0,"ramp_mask":"","srcname1":"mask"
}
CURVATURE_TINT_PARMS = {
    "use_ramp":1,"strength":0.613,"ramp_mask":"","srcname1":"mask"
}

# These are source-compatible choices on the basis of final screen *shape*
# and directly readable middle/endpoints, NOT copied complete final author HIP.
EXPOSURE_CANDIDATE = (
    (0.0,(1.0,1.0,1.0)), # Earlier visible point1; final read UNKNOWN
    (0.93538,(0.651,0.651,0.651)), # Final visible author point2
    (1.0,(1.0,1.0,1.0)), # Right white endpoint present visually, numeric UNKNOWN
)
CURVATURE_CANDIDATE = (
    (0.0,(1.0,1.0,1.0)), # Initial white/brightness 1 narration, numeric UNKNOWN
    (1.0,(2.0,2.0,2.0)), # Author directly observed final point2
)


def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as source:
        for part in iter(lambda:source.read(1<<20),b""):
            h.update(part)
    return h.hexdigest()


def source_material()->tuple[Path,dict]:
    report=json.loads((MATERIAL_ROOT/"real-material-canary.json").read_text(encoding="utf-8"))
    if report.get("status")!="FIVE_PEGASUS_CC0_REAL_STAGE3_SOURCE_ORDERED_TINTS_BOUNDED_PASS":
        raise ValueError("Only source-ordered five-HDA/four-Tint receipt allowed")
    if report.get("stage3_upstream_lineage_accepted") is not False:
        raise ValueError("Historical Stage3 scree origin not fully proven")
    if report.get("complete_author_mask_and_tint_graph") is not False:
        raise ValueError("Input unexpectedly claims final whole-graph authority")
    tints=report.get("tint_stages",[])
    if [t["name"] for t in tints]!=["grass_gradient","grass_brightness","cliff","scree"]:
        raise ValueError("Different original source tinted-HDA node sequence")
    for t in tints:
        if t.get("height_and_semantic_masks_preserved") is not True:
            raise ValueError("Original tint output changed an accepted mask")
    target=Path(tints[-1]["bgeo"]).resolve()
    if not target.is_relative_to(MATERIAL_ROOT.resolve()) or not target.is_file():
        raise ValueError("Original bounded scree-tint BGEO missing/out of scope")
    if sha(target)!=tints[-1]["bgeo_sha256"]:
        raise ValueError("Source ordered last Tint HDA bytes changed")
    return target,report


def enum_by_label(parm,label:str)->str:
    template=parm.parmTemplate()
    pairs=list(zip(template.menuItems(),template.menuLabels()))
    matches=[value for value,caption in pairs if caption.strip().casefold()==label.casefold()]
    if len(matches)!=1:
        raise ValueError(f"Native enum value for {label!r} not unique in actual template: {pairs}")
    token=matches[0]
    try:
        parm.set(token)
    except (TypeError,ValueError):
        parm.set(int(token))
    return token


def numeric_ramp(hou,points):
    return hou.Ramp([hou.rampBasis.Linear]*len(points),[p for p,_ in points],
                    [c for _,c in points])


def mask_ramp(hou):
    return hou.Ramp([hou.rampBasis.Linear]*2,[0.0,1.0],[0.0,1.0])


def assert_protected_hashes(original_hashes,readback,hou,stage)->dict:
    from scripts.houdini.l07_real_material_canary import source_layer_hashes,PROTECTED
    actual=source_layer_hashes(readback,hou)
    for name in PROTECTED:
        if name=="mask":
            continue # MaskByFeature deliberately writes generic working mask.
        if actual.get(name)!=original_hashes.get(name):
            raise ValueError(f"Native {stage} changed original protected semantic volume {name}")
    if "mask" not in actual:
        raise ValueError("MaskByFeature removed generic working mask")
    return actual


def measure_mask(geo,hou,np)->dict:
    from scripts.houdini.l07_real_material_canary import volume_by_name
    by_name=volume_by_name(geo,hou)
    if "mask" not in by_name:
        raise ValueError("No native mask output")
    arr=np.frombuffer(by_name["mask"].allVoxelsAsString(),dtype="<f4").reshape((256,256))
    if not np.isfinite(arr).all():
        raise ValueError("Nonfinite native MaskByFeature output")
    return {
        "nonzero":int(np.count_nonzero(arr)),
        "min":float(arr.min()),"max":float(arr.max()),
        "mean":float(arr.mean()),
        "sha256_float32":hashlib.sha256(arr.astype("<f4").tobytes()).hexdigest(),
    }


def apply_feature(node,kind,hou):
    if kind=="exposure":
        parameters=EXPOSURE_MASK_PARMS
        ramp="ramp"
    elif kind=="curvature":
        parameters=CURVATURE_MASK_PARMS
        ramp="curvatureramp"
    else:
        raise ValueError("Only video-verified MaskByFeature branches")
    missing=[key for key in parameters if node.parm(key) is None]
    if missing:
        raise ValueError(f"Real Houdini MaskByFeature templates differ: {missing}")
    node.setParms(parameters)
    if node.parm(ramp) is None:
        raise ValueError(f"Native {ramp} parameter absent")
    node.parm(ramp).set(mask_ramp(hou))
    return {
        "parms":parameters,
        "ramp_knots_candidate":((0.0,0.0),(1.0,1.0)),
        "source_quality":"SOURCE_VERIFIED_PARAMETERS_RAMP_KNOTS_YACS_ADAPTATION",
    }


def apply_tint(tint,kind,hou)->dict:
    if kind=="exposure":
        params=EXPOSURE_TINT_PARMS
        points=EXPOSURE_CANDIDATE
    elif kind=="curvature":
        params=CURVATURE_TINT_PARMS
        points=CURVATURE_CANDIDATE
    else:
        raise ValueError(f"Unexpected original tint {kind}")
    tint.setParms(params)
    tint.parm("tint_ramp").set(numeric_ramp(hou,points))
    return {
        "parms":params,"points":[{"pos":a,"rgb":b} for a,b in points],
        "source_quality":"SOURCE_VERIFIED_STRENGTH_AND_MIDDLE_OR_END_KNOT_ONLY",
        "inferred_or_unknown_endpoint_adapted":True
    }


def render_tint(node,source_geometry,baseline,case,output,hou,np):
    from scripts.houdini.l07_original_tint_hda_canary import preserve_generic_working_mask_in_scratch
    from scripts.houdini.l07_real_material_canary import (
        restore_scratch_height,source_layer_hashes,volume_by_name,save_png
    )
    node.cook(force=True)
    if node.errors():
        raise ValueError(f"Native SideFX tint HDA error {case}: {node.errors()}")
    mask_restored,metrics=preserve_generic_working_mask_in_scratch(
        node.geometry(),source_geometry,hou,np,case)
    height=np.frombuffer(volume_by_name(source_geometry,hou)["height"].allVoxelsAsString(),
                         dtype="<f4").reshape((256,256)).copy()
    scratch,hashes,rounding=restore_scratch_height(
        mask_restored,{"height":height},baseline,hou,np,case)
    image=np.stack([
        np.frombuffer(volume_by_name(scratch,hou)[name].allVoxelsAsString(),
                      dtype="<f4").reshape((256,256))
        for name in ("r","g","b")
    ],axis=-1)
    if not np.isfinite(image).all():
        raise ValueError("Tint resulted in nonfinite RGB")
    image_path=output/f"native-{case}-color.png"
    save_png(image_path,image,np)
    bg=output/f"native-{case}.bgeo.sc"
    scratch.saveToFile(str(bg))
    if bg.stat().st_size>32*1024**2:
        raise ValueError("Native canary BGEO exceeds 32MiB")
    reopened=hou.Geometry()
    reopened.loadFromFile(str(bg))
    if source_layer_hashes(reopened,hou)!=hashes:
        raise ValueError("Tint source data lost voxel identity on BGEO reopen")
    return {
        "kind":case,"output":str(bg),"sha256":sha(bg),
        "preview":str(image_path),"preview_sha256":sha(image_path),
        "mean_rgb":list(map(float,image.mean(axis=(0,1)))),
        "black_rgb_pixels":int(np.count_nonzero(np.all(image<=1e-6,axis=2))),
        "generic_mask_restored_in_scratch":metrics,
        "protected_height_restored_in_scratch":rounding,
        "saved_reopened_voxel_hashes_equal":True,
        "original_semantic_volumes_unchanged":True,
    }


def run(hou,np,output:Path):
    if hou.isUIAvailable() or tuple(hou.applicationVersion())!=(22,0,466):
        raise ValueError("Requires single fresh headless Houdini 22.0.466")
    if hou.node("/obj").children():
        raise ValueError("Nonempty native scene is not owner-approved")
    if sha(HDA)!=HDA_SHA:
        raise ValueError("Original SideFX tint asset bytes have changed")
    data,prior_proof=source_material()
    hou.hda.installFile(str(HDA),force_use_assets=True)
    output.mkdir(parents=True,exist_ok=False)
    obj=hou.node("/obj").createNode("geo","L07_REAL_EXPOSURE_CURVATURE")
    try:
        for child in obj.children():
            child.destroy()
        src=obj.createNode("file","SOURCE_POST_SCREE_TINT4")
        src.parm("file").set(str(data))
        loaded=hou.Geometry()
        loaded.loadFromFile(str(data))
        from scripts.houdini.l07_real_material_canary import source_layer_hashes
        original=source_layer_hashes(loaded,hou)

        vis=obj.createNode("heightfield_visualize","VISUALIZE4")
        vis.setInput(0,src)
        tint_enum=enum_by_label(vis.parm("updatetinting"),"Default Tinting")
        material_enum=enum_by_label(vis.parm("updatematerial"),"No Change")
        exposure_mask=obj.createNode("heightfield_maskbyfeature","MASK12_EXPOSURE")
        exposure_mask.setInput(0,vis)
        exposure_parms=apply_feature(exposure_mask,"exposure",hou)
        exposure_mask.cook(force=True)
        if exposure_mask.errors():
            raise ValueError(f"Native source Mask12 errors: {exposure_mask.errors()}")
        mask12_h=assert_protected_hashes(original,exposure_mask.geometry(),hou,"mask12")
        exposure_stats=measure_mask(exposure_mask.geometry(),hou,np)

        tint5=obj.createNode("PE_heightfield_tint::1.0","TINT5_EXPOSURE")
        tint5.setInput(0,src)
        tint5.setInput(1,exposure_mask)
        exposure_tint_parms=apply_tint(tint5,"exposure",hou)
        exposure_result=render_tint(tint5,loaded,original,"exposure",output,hou,np)

        curvature_mask=obj.createNode("heightfield_maskbyfeature","MASK13_CURVATURE")
        curvature_mask.setInput(0,exposure_mask) # NOT tint5, per original SideFX video
        curvature_parms=apply_feature(curvature_mask,"curvature",hou)
        curvature_mask.cook(force=True)
        if curvature_mask.errors():
            raise ValueError(f"Native source Mask13 errors: {curvature_mask.errors()}")
        assert_protected_hashes(original,curvature_mask.geometry(),hou,"mask13")
        curvature_stats=measure_mask(curvature_mask.geometry(),hou,np)

        reopened=obj.createNode("file","SAFE_REOPEN_TINT5")
        reopened.parm("file").set(exposure_result["output"])
        tint6=obj.createNode("PE_heightfield_tint::1.0","TINT6_CURVATURE")
        tint6.setInput(0,reopened)
        tint6.setInput(1,curvature_mask)
        curvature_tint_parms=apply_tint(tint6,"curvature",hou)
        exposure_geo=hou.Geometry()
        exposure_geo.loadFromFile(exposure_result["output"])
        baseline=source_layer_hashes(exposure_geo,hou)
        curvature_result=render_tint(tint6,exposure_geo,baseline,"curvature",output,hou,np)
        return {
            "status":"ORIGINAL_PEGASUS_EXPOSURE_CURVATURE_NATIVE_REAL_SITE_ADAPTED_RAMP_CANARY_PASS",
            "source_material_sha256":sha(data),"original_tint_hda_sha256":HDA_SHA,
            "source_256x256_real_sacalobra":True,
            "actual_source_graph_edges":{
                "tint4_to_visualize4":"SOURCE_POST_SCREE_TINT4 -> VISUALIZE4",
                "visualize4_to_mask12":"VISUALIZE4 -> MASK12_EXPOSURE input 0",
                "mask12_to_mask13":"MASK12_EXPOSURE -> MASK13_CURVATURE input 0",
                "tint4_to_tint5":"SOURCE_POST_SCREE_TINT4 -> TINT5_EXPOSURE input 0",
                "mask12_to_tint5":"MASK12_EXPOSURE -> TINT5_EXPOSURE input 1",
                "tint5_to_tint6":"SAFE_REOPEN_TINT5 -> TINT6_CURVATURE input 0",
                "mask13_to_tint6":"MASK13_CURVATURE -> TINT6_CURVATURE input 1",
            },
            "visualize_options":{"update_tinting_default":tint_enum,"update_material_no_change":material_enum},
            "mask12":{"parms":exposure_parms,"stats":exposure_stats},
            "mask13":{"parms":curvature_parms,"stats":curvature_stats},
            "tint5":{"parms":exposure_tint_parms,"output":exposure_result},
            "tint6":{"parms":curvature_tint_parms,"output":curvature_result},
            "author_full_ramp_tuples_verified":False,
            "adaptation_note":"Endpoint positions missing from final source HIP are YACS candidate ramps, not author numeric settings",
            "boundary_halo_adequate_for_145m_occlusion":False,
            "canonical_height_and_alpha_changed":False,
            "semantic_stage2_masks_changed":False,
            "stage3_upstream_authority_accepted":False,
            "full_domain_cooked":False,
            "unreal_imported":False,"owner_visual_acceptance":False,
        }
    finally:
        obj.destroy()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token",required=True)
    args=parser.parse_args()
    if not re.fullmatch(r"[0-9]{9,13}-[1-9][0-9]*",args.token):
        raise ValueError("Expected exact workflow run-attempt token")
    import hou
    import numpy as np
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    result=run(hou,np,SCRATCH/args.token)
    file=SCRATCH/args.token/"exposure-curvature-proof.json"
    file.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],
        "masks":{"exposure":result["mask12"]["stats"]["nonzero"],
                 "curvature":result["mask13"]["stats"]["nonzero"]},
        "tints":{"exposure_rgb":result["tint5"]["output"]["mean_rgb"],
                 "curvature_rgb":result["tint6"]["output"]["mean_rgb"]},
        "evidence":str(file)}))


if __name__=="__main__":
    main()

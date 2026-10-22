#!/usr/bin/env python3
"""Real-Sa-Calobra, ORIGINAL SideFX Pegasus tint-HDA isolation proof.

Execute only on already verified 256x256 source-material snapshots. This smoke
tests native tint parameters and voxel invariants, NOT the complete author's
maskbyfeature6/7/8/12/13 network, original final HIP, full world, or UE Lit.
No canonical Stage1/2/3 data, UE assets, or accepted Landscape are modified.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

PROJECT = Path("D:/yacs/project")
MATERIAL_RUN = "39805083280-1"
MATERIAL_ROOT = Path("D:/yacs/work/lesson07-cc0-real-material") / MATERIAL_RUN
SCREE_CROP = Path("D:/yacs/work/lesson07-cc0-real-crops/39794174742-1")
BASE_CROP = Path("D:/yacs/work/lesson07-cc0-real-crops/39785285512-1")
SCRATCH_ROOT = Path("D:/yacs/work/lesson07-cc0-tint-proofs")
TINT_HDA = PROJECT / "worldgen/houdini/sa_calobra/otls/sop_PE_heightfield_tint.1.0.hda"
TINT_HDA_SHA256 = "93cc47dd511bc3d5868835b5dd3b9082c13cab23355b688aaf2a947e8687a2ed"

CASES = (
    # Stage after grass before sand; ramp is the accepted YACS Stage2
    # ramp_layer, which is NOT the missing original mask6/7/8 author graph.
    ("grass_gradient", "grass", "ramp_layer", "gradient"),
    ("grass_brightness", "grass_gradient", None, "brightness"),
    # The cliff stage is the input immediately before the author's cliff tint.
    ("cliff", "cliff", "cliff_mask", "solid_cliff"),
    # Original scree mask is from the historical georeferenced Stage3 proof,
    # not a fake cliff-mask proxy; its upstream lineage is NOT accepted.
    ("scree", "scree", "scree_mask", "solid_scree"),
)
MAX_BGEO_BYTES = 32 * 1024 * 1024
MAX_IMAGE_BYTES = 2 * 1024 * 1024


def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_material_source_report(path: Path) -> dict:
    proof=json.loads(path.read_text(encoding="utf-8"))
    if proof.get("status")!="FIVE_PEGASUS_CC0_REAL_STAGE3_DIAGNOSTIC_PASSED_NOT_PRODUCTION":
        raise ValueError("Source material proof was not the real Stage3 diagnostic run")
    if proof.get("stage3_upstream_lineage_accepted") is not False:
        raise ValueError("Historical scree source may not be upgraded to full source authority")
    if proof.get("ground_truth_height_and_stage2_masks_unchanged") is not True:
        raise ValueError("Source material changed accepted height or masks")
    stages=proof.get("stages",[])
    expected=["rock","grass","sand","cliff","scree"]
    if [s["role"] for s in stages]!=expected:
        raise ValueError("Not exactly the five original Pegasus material nodes")
    last=stages[-1]
    if last["mask_source"]!="HISTORICAL_STAGE3_GEOREGISTERED_UPSTREAM_UNVERIFIED" or last["mask_nonzero"]!=8619:
        raise ValueError("Real masked scree material input is not evidenced")
    for stage in stages:
        p=Path(stage["output_path"]).resolve()
        if not p.is_relative_to(MATERIAL_ROOT.resolve()) or not p.is_file():
            raise ValueError("Historical material output path outside pinned isolated run")
        if sha(p)!=stage["output_sha256"]:
            raise ValueError("Saved material BGEO differs from native five-HDA output")
    return proof


def source_for_case(case: str, report: dict, output: Path)->Path:
    if case=="grass_brightness":
        return output/"tint-grass_gradient.bgeo.sc"
    if case not in ("grass_gradient","cliff","scree"):
        raise ValueError("Unknown source material tint stage")
    role="grass" if case=="grass_gradient" else case
    return Path(next(s for s in report["stages"] if s["role"]==role)["output_path"])


def make_mask_source(geo, semantic_name: str | None, np, hou) -> tuple[object,int]:
    if semantic_name is None:
        # Brightness has Mask="" per author: its second port does not gate tint.
        return hou.Geometry(geo), 65536
    from scripts.houdini.l07_real_material_canary import volume_by_name
    original=volume_by_name(geo,hou)
    if semantic_name=="scree_mask":
        from scripts.houdini.verify_l07_scree_crop import verify as verify_scree
        report=verify_scree(SCREE_CROP,BASE_CROP,np)
        if report["scree_nonzero"]!=8619 or report["production_scree_mask_admitted"] is not False:
            raise ValueError("True scree source counts or diagnostic authority changed")
        with np.load(SCREE_CROP/"scree-real-crop.npz",allow_pickle=False) as bundle:
            samples=np.array(bundle["scree_mask"],dtype="<f4",copy=True)
    else:
        if semantic_name not in ("ramp_layer","cliff_mask"):
            raise ValueError("Refuse a synthetic mask branch")
        samples=np.frombuffer(original[semantic_name].allVoxelsAsString(),dtype="<f4").copy().reshape((256,256))
    if samples.shape!=(256,256) or not np.isfinite(samples).all():
        raise ValueError("Screener invalid scalar mask")
    cropped=hou.Geometry(geo)
    orig=volume_by_name(cropped,hou)
    cropped.deletePrims([p for name,p in orig.items() if name!="mask"],True)
    single=volume_by_name(cropped,hou)["mask"]
    single.setAllVoxelsFromString(samples.tobytes())
    return cropped,int(np.count_nonzero(samples))


def apply_parms(tint,kind,hou):
    parameters={"srcname1":"mask","strength":1.0,"ramp_mask":"","use_ramp":0}
    if kind=="gradient":
        parameters.update({"use_ramp":1,"strength":0.95})
    elif kind in ("solid_cliff","solid_scree"):
        parameters["ramp_mask"]="mask"
    tint.setParms(parameters)
    if kind=="gradient":
        ramp=hou.Ramp([hou.rampBasis.Linear]*2,[0.0,0.996694],
                      [(0.34,0.55,0.12705),(1.0,0.822741,0.538)])
        tint.parm("tint_ramp").set(ramp)
    elif kind=="brightness":
        tint.parmTuple("tint").set((2.0,2.0,2.0))
    elif kind=="solid_cliff":
        tint.parmTuple("tint").set((0.597,0.597,0.597))
    elif kind=="solid_scree":
        tint.parmTuple("tint").set((0.874,0.822347,0.701822))
    else:
        raise ValueError(f"Unapproved tint mode {kind}")
    return parameters


def native_case(obj,case,role,mask_name,kind,source_file,output,np,hou) -> dict:
    from scripts.houdini.l07_real_material_canary import (
        restore_scratch_height,source_layer_hashes,volume_by_name,save_png
    )
    loaded=hou.Geometry()
    loaded.loadFromFile(str(source_file))
    if not (0<len(loaded.prims())<=32):
        raise ValueError("Unexpected native source geometry")
    protected=source_layer_hashes(loaded,hou)
    original_height=np.frombuffer(volume_by_name(loaded,hou)["height"].allVoxelsAsString(),dtype="<f4").reshape((256,256)).copy()
    input_source=obj.createNode("file","IN_"+case.upper())
    input_source.parm("file").set(str(source_file))
    mask_geometry,count=make_mask_source(loaded,mask_name,np,hou)
    mask_path=output/("tint-"+case+"-mask.bgeo.sc")
    mask_geometry.saveToFile(str(mask_path))
    if mask_path.stat().st_size>MAX_BGEO_BYTES:
        raise ValueError("Oversized bounded source mask")
    mask_node=obj.createNode("file","MASK_"+case.upper())
    mask_node.parm("file").set(str(mask_path))
    tint=obj.createNode("PE_heightfield_tint::1.0","TINT_"+case.upper())
    definition=tint.type().definition()
    if not definition or Path(definition.libraryFilePath()).resolve()!=TINT_HDA.resolve():
        raise ValueError("Wrong original SideFX tint HDA")
    tint.setInput(0,input_source)
    tint.setInput(1,mask_node)
    parms=apply_parms(tint,kind,hou)
    tint.cook(force=True)
    if tint.errors():
        raise ValueError(f"Source tint HDA reported errors {case}: {tint.errors()}")
    raw=tint.geometry()
    repaired,hashes,roundoff=restore_scratch_height(
        raw,{"height":original_height},protected,hou,np,case)
    for key in ("r","g","b"):
        if key not in hashes:
            raise ValueError(f"Tint HDA omitted {key} colour layer")
    bg=output/("tint-"+case+".bgeo.sc")
    repaired.saveToFile(str(bg))
    if bg.stat().st_size>MAX_BGEO_BYTES:
        raise ValueError("Out-of-bounds native tint BGEO")
    reopen=hou.Geometry()
    reopen.loadFromFile(str(bg))
    if source_layer_hashes(reopen,hou)!=hashes:
        raise ValueError("Saved SideFX tint output not equal to fresh local reopen")
    colour=np.stack(
        [np.frombuffer(volume_by_name(repaired,hou)[key].allVoxelsAsString(),dtype="<f4").reshape((256,256))
         for key in ("r","g","b")],axis=-1)
    if not np.isfinite(colour).all():
        raise ValueError("NaN/Inf original HDA RGB output")
    p=output/("tint-"+case+".png")
    save_png(p,colour,np)
    if p.stat().st_size>MAX_IMAGE_BYTES:
        raise ValueError("Tint preview exceeds 2MiB evidence bound")
    return {
        "name":case,"kind":kind,"native_type":"PE_heightfield_tint::1.0",
        "source":str(source_file),"source_sha256":sha(source_file),
        "input2_mask":mask_name,"mask_nonzero":count,
        "author_source_status":"INFERRED_FINAL_GRASS_RAMP" if kind=="gradient" else "VIDEO_VERIFIED_UI_PARAMETERS",
        "yacs_adaptation":("STAGE2_RAMP_LAYER_INSTEAD_OF_AUTHOR_MASK6_7_8" if kind=="gradient"
                           else "HISTORICAL_STAGE3_UPSTREAM_NOT_FULLY_PROVEN" if kind=="solid_scree"
                           else None),
        "parms":parms,"height_and_semantic_masks_preserved":True,
        "raw_native_rounding":roundoff,"native_warnings":list(tint.warnings()),
        "min_rgb":float(colour.min()),"max_rgb":float(colour.max()),
        "mean_rgb":list(map(float,colour.mean(axis=(0,1)))),
        "black_all_three_rgb_count":int(np.count_nonzero(np.all(colour<=1e-6,axis=-1))),
        "bgeo":str(bg),"bgeo_sha256":sha(bg),
        "png":str(p),"png_sha256":sha(p),
        "native_reopen":True
    }


def run(hou,np,output):
    if hou.isUIAvailable() or tuple(hou.applicationVersion())!=(22,0,466):
        raise ValueError("Wrong Houdini native process/version")
    if hou.node("/obj").children():
        raise ValueError("Expected empty fresh hython scene")
    if sha(TINT_HDA)!=TINT_HDA_SHA256:
        raise ValueError("Original archived tint HDA checksum mismatch")
    report=check_material_source_report(MATERIAL_ROOT/"real-material-canary.json")
    output.mkdir(parents=True,exist_ok=False)
    hou.hda.installFile(str(TINT_HDA),force_use_assets=True)
    g=hou.node("/obj").createNode("geo","L07_ORIGINAL_TINT_ISOLATION")
    try:
        for n in g.children():
            n.destroy()
        results=[]
        for case,role,mask_name,kind in CASES:
            source=source_for_case(case,report,output)
            result=native_case(g,case,role,mask_name,kind,source,output,np,hou)
            results.append(result)
        return {
            "status":"ORIGINAL_PEGASUS_TINT_HDA_REAL_SITE_ISOLATED_PROOF_NOT_FULL_GRAPH",
            "source_run":MATERIAL_RUN,"original_tint_hda_sha256":TINT_HDA_SHA256,
            "stages":results,
            "full_graph":False,"whole_domain":False,"final_ue_lit":False,
            "no_original_mask_mutation":True,"no_original_height_mutation":True,
            "unknown_author_nodes":["exposure_mask12","curvature_mask13","endpoints of some native ramps"],
        }
    finally:
        g.destroy()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-token",required=True)
    args=parser.parse_args()
    if not re.fullmatch(r"[0-9]{9,13}-[1-9][0-9]*",args.run_token):
        raise ValueError("Unexpected GH run/attempt token")
    if os.name=="nt":
        if not str(SCRATCH_ROOT).lower().replace("/","\\").startswith("d:\\yacs\\work\\"):
            raise ValueError("Tint evidence must live in isolated D work folder")
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    import hou
    import numpy as np
    import scripts.houdini.l07_real_material_canary
    target=SCRATCH_ROOT/args.run_token
    result=run(hou,np,target)
    manifest=target/"tint-native-evidence.json"
    manifest.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"source":MATERIAL_RUN,
        "stages":[{"case":s["name"],"mask":s["mask_nonzero"],"rgb":s["mean_rgb"]}
                  for s in result["stages"]],"receipt":str(manifest)}))


if __name__=="__main__":
    main()

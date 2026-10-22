#!/usr/bin/env python3
"""Independently verify real-site Stage3 scree data from historical source cache.

This is a diagnostic only: the 96 MB Stage3 cache matches its own historical
producer receipt but upstream 4.3 GB cliff dependency has not been fully
fingerprinted. No geometry/material cook or approved terrain mutation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

CANONICAL_SOURCE_TOKEN = "39785285512-1"
ROOT = Path("D:/yacs/work/lesson07-cc0-real-crops")
EXPECTED_SHA = "2af8ce5b467db28613c2033677c444dba5a89af943b906b01258a0b44106edb7"
EXPECTED_WINDOW = [7961, 11560, 8217, 11816]


def sha256(path: Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda:stream.read(1<<20),b""):
            h.update(data)
    return h.hexdigest()


def validate_provenance(report:dict, baseline:dict)->dict:
    if report.get("status") != "HISTORICAL_STAGE3_SCREE_CROP_DIAGNOSTIC_NOT_ACCEPTED":
        raise ValueError("Stage3 was not prepared in diagnostic-only mode")
    if report.get("stage") != "scree":
        raise ValueError("Wrong actual Stage3 source")
    if report.get("source",{}).get("source_sha256") != EXPECTED_SHA:
        raise ValueError("Unexpected Stage3 historical source identity")
    if report.get("source",{}).get("source_size") != 96479665:
        raise ValueError("Stage3 size differs from native audit")
    if report.get("original_16000_grid") != [16000,16000,1]:
        raise ValueError("Unexpected full resolution")
    if report.get("crop_size") != 256 or report.get("crop_index_window") != EXPECTED_WINDOW:
        raise ValueError("Native sample differs from pinned Sa Calobra site")
    if report.get("historical_scree_authority_admitted") is not False:
        raise ValueError("Historical scree authority may not be promoted")
    if report.get("producer_upstream_lineage_verified") is not False:
        raise ValueError("Unverified upstream lineage may not be promoted")
    if report.get("heightfield_modified") is not False or report.get("source_masks_modified") is not False:
        raise ValueError("Source modification forbidden")
    scree=report.get("layer_metadata",{}).get("scree_mask")
    if not isinstance(scree,dict):
        raise ValueError("Missing native scree mask layer")
    if not re.fullmatch(r"[0-9a-f]{64}",str(scree.get("sha256_float32_le",""))):
        raise ValueError("Incomplete scree voxel receipt")
    if report["crop_index_window"] != EXPECTED_WINDOW:
        raise ValueError("Unexpected geographic window")
    if baseline.get("status") != "REAL_SOURCE_CROPS_VERIFIED_NO_MATERIAL_COOK":
        raise ValueError("Canonical Stage1/Stage2 source windows are not accepted")
    if baseline.get("crop_resolution") != [256,256,1] or baseline.get("raw_source_resolution") != [16000,16000,1]:
        raise ValueError("Stage1/2 not the same native lattice")
    original_coords=baseline.get("extent_world")
    current=[scree.get("first_voxel_world_xyz"),scree.get("last_voxel_world_xyz")]
    if not isinstance(original_coords,list) or len(original_coords)!=2:
        raise ValueError("Missing accepted 7-layer spatial proof")
    for a,b in zip(current,original_coords):
        if not (isinstance(a,list) and isinstance(b,list) and len(a)==3 and len(b)==3):
            raise ValueError("Invalid geographic metadata")
        if any(abs(float(x)-float(y))>0.005 for x,y in zip(a,b)):
            raise ValueError("Historical scree layer misregistered against accepted source")
    return scree


def verify(stage_dir:Path,base_dir:Path,np)->dict:
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    from scripts.houdini.verify_l07_real_crop import verify as verify_base
    source=verify_base(base_dir,CANONICAL_SOURCE_TOKEN,np)
    report_path=stage_dir/"scree-real-crop.json"
    crop_path=stage_dir/"scree-real-crop.npz"
    report=json.loads(report_path.read_text(encoding="utf-8"))
    scree=validate_provenance(report,source)
    if crop_path.stat().st_size>4*1024*1024 or sha256(crop_path)!=report["crop_sha256"]:
        raise ValueError("Stage3 extracted source file differs from native receipt")
    with np.load(crop_path,allow_pickle=False) as bundle:
        if bundle.files!=["scree_mask"]:
            raise ValueError("Expected exactly one scalar Stage3 scree mask")
        raw=bundle["scree_mask"]
        if raw.shape!=(256,256) or raw.dtype!=np.float32 or not np.isfinite(raw).all():
            raise ValueError("Invalid Stage3 source voxel dtype/resolution")
        if hashlib.sha256(raw.astype("<f4").tobytes()).hexdigest()!=scree["sha256_float32_le"]:
            raise ValueError("Scree voxels do not match native extraction")
        n=int(np.count_nonzero(raw))
        if n!=int(scree["nonzero"]):
            raise ValueError("Scree coverage counts differ from native proof")
        mn=float(raw.min());mx=float(raw.max())
        if mn<(-1e-5) or mx>1.0001:
            raise ValueError("Scree mask outside verified 0..1 bounds")
    return {"status":"HISTORICAL_STAGE3_SCREE_REAL_CROP_VERIFIED_DIAGNOSTIC_ONLY",
        "source_cache_sha256":EXPECTED_SHA,"crop_sha256":report["crop_sha256"],
        "scree_nonzero":n,"scree_min":mn,"scree_max":mx,
        "site_has_scree":n>0,
        "cropped_source_path":str(crop_path),"canonical_stage1_stage2_run":CANONICAL_SOURCE_TOKEN,
        "native_window":EXPECTED_WINDOW,
        "canonical_height_and_masks_untouched":True,
        "source_stage3_upstream_lineage_accepted":False,
        "production_scree_mask_admitted":False,
        "real_houdini_hda_cook":False,"unreal_modified":False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-token",required=True)
    args=parser.parse_args()
    if not re.fullmatch(r"[0-9]{9,13}-[1-9][0-9]*",args.run_token):
        raise ValueError("Expected immutable GitHub run-attempt ID")
    if os.name=="nt" and not str(ROOT).lower().replace("/","\\").startswith("d:\\yacs\\work\\"):
        raise ValueError("Wrong isolation directory")
    import numpy as np
    target=ROOT/args.run_token
    report=verify(target,ROOT/CANONICAL_SOURCE_TOKEN,np)
    output=target/"scree-diagnostic-verified.json"
    if output.exists():
        raise ValueError("Previous source proof exists; no overwriting")
    output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],"scree_nonzero":report["scree_nonzero"],
                      "site_has_scree":report["site_has_scree"],"receipt":str(output)}),flush=True)


if __name__=="__main__":
    main()

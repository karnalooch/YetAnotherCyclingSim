#!/usr/bin/env python3
"""Verify height and valid Alpha at real sand-positive Stage2 16K source indices.

Two source files are never loaded simultaneously: sand sites have already
been sampled from historical accepted Stage2; this fresh Houdini process reads
only original Stage1 height/Alpha to rank eight candidates, then extracts
one bounded 256x256 valid site. Geographic/coastline visual status remains open.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

STAGE1=Path("D:/yacs/work/lesson06-unified-20261019/stage1_base.bgeo.sc")
STAGE1_SIZE=519575557
STAGE1_SHA="08586f0e1aa6aa033cf7364a929d2c260c87c41d6dc11445c981e10ec6ba2952"
CANDIDATE=Path("D:/yacs/work/lesson07-sand-candidates/39813029959-1/real-sand-site-candidates.json")
OUTPUT=Path("D:/yacs/work/lesson07-valid-sand-sites")
PIN_MASK_SHA="203d46ea79a0a697d46256f631271135a0cd8766ba8768f7432ea315512c16a8"
GRID=(16000,16000,1)
SIZE=256


def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for piece in iter(lambda:f.read(1<<20),b""):
            h.update(piece)
    return h.hexdigest()


def load_sites()->tuple[list[dict],str]:
    evidence=json.loads(CANDIDATE.read_text(encoding="utf-8"))
    if evidence.get("status")!="SAND_POSITIVE_STAGE2_WORLD_COORDINATE_CANDIDATES_NOT_CROPPED":
        raise ValueError("Expected exact Stage2 native sand candidate status")
    if evidence.get("source",{}).get("source_sha256")!=PIN_MASK_SHA:
        raise ValueError("Candidate source is not accepted Stage2")
    if evidence.get("site_alpha_and_height_verified") is not False:
        raise ValueError("Stage2 scan cannot itself prove Stage1 height/Alpha")
    selected=evidence.get("chosen",[])
    if not isinstance(selected,list) or not 1<=len(selected)<=8:
        raise ValueError("Unexpected source discovery candidates")
    for item in selected:
        i,j=item["i"],item["j"]
        if not isinstance(i,int) or not isinstance(j,int) or not 128<=i<15872 or not 128<=j<15872:
            raise ValueError("Sand candidate indices outside fixed 256 crop")
        if not item.get("refined",{}).get("positive_samples",0)>0:
            raise ValueError("Candidate has no original sand-positive neighborhood")
        if item.get("window_indices")!=[i-128,j-128,i+128,j+128]:
            raise ValueError("Unapproved candidate sample window")
    return selected,sha(CANDIDATE)


def require_source()->tuple[int,int]:
    before=STAGE1.stat()
    if not STAGE1.is_file() or before.st_size!=STAGE1_SIZE:
        raise ValueError("Missing accepted full 16K height/Alpha baseline")
    if sha(STAGE1)!=STAGE1_SHA:
        raise ValueError("Accepted Stage1 height/Alpha SHA mismatch")
    after=STAGE1.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise ValueError("Stage1 changed while verifying source")
    return after.st_size,after.st_mtime_ns


def sample_region(height,alpha,site,step=16):
    i,j=site["i"],site["j"]
    import math
    valid=0
    plausible=0
    total=0
    invalid_alpha=0
    invalid_height_inside_valid_alpha=0
    skipped_height_outside_alpha=0
    positive_heights=[]
    for yy in range(j-128,j+128,step):
        for xx in range(i-128,i+128,step):
            h=float(height.voxel((xx,yy,0)))
            a=float(alpha.voxel((xx,yy,0)))
            total+=1
            if not math.isfinite(a) or not -0.00001<=a<=1.00001:
                invalid_alpha+=1
                continue
            if a<=0.5:
                # Stage1 has valid coastal sand mask searches beyond the
                # terrain-Alpha footprint. Never treat offshore NoData heights
                # or their source sentinels as admissible land heights.
                if not math.isfinite(h) or not -9999<h<9999:
                    skipped_height_outside_alpha+=1
                continue
            if not math.isfinite(h) or not -9999<h<9999:
                invalid_height_inside_valid_alpha+=1
                continue
            valid+=1
            positive_heights.append(h)
            if -50<=h<=35:
                plausible+=1
    return {
        "sample_step":step,"total":total,
        "alpha_valid":valid,
        "invalid_alpha":invalid_alpha,
        "invalid_height_inside_valid_alpha":invalid_height_inside_valid_alpha,
        "ignored_outside_alpha_nodata_heights":skipped_height_outside_alpha,
        "alpha_fraction":valid/total,
        "valid_low_elevation_count":plausible,
        "valid_low_elevation_fraction":plausible/total,
        "valid_height_min":min(positive_heights) if positive_heights else None,
        "valid_height_max":max(positive_heights) if positive_heights else None,
        "valid_height_mean":sum(positive_heights)/len(positive_heights) if positive_heights else None,
    }


def order_candidates(data:list[dict])->list[dict]:
    return sorted(data,key=lambda x:(
        -x["stage1"]["valid_low_elevation_fraction"],
        -x["stage1"]["alpha_fraction"],
        -x["stage2"]["refined"]["mean"],
        x["stage2"]["i"],x["stage2"]["j"]
    ))


def extract(vol,i,j,np):
    pixels=np.fromiter((vol.voxel((xx,yy,0))
                       for yy in range(j-128,j+128)
                       for xx in range(i-128,i+128)),dtype=np.float32,count=SIZE*SIZE)
    data=pixels.reshape((SIZE,SIZE))
    if not np.isfinite(data).all():
        raise ValueError("Native real-site source contains NaN/Inf")
    return data


def run(hou,np,token):
    if hou.isUIAvailable() or tuple(hou.applicationVersion())!=(22,0,466):
        raise ValueError("Fresh headless original Houdini required")
    if hou.node("/obj").children():
        raise ValueError("Refuse to operate on existing editor scene")
    sites,candidate_hash=load_sites()
    before=require_source()
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    from scripts.ue.lesson06_memory_guard import require_headroom
    memory=require_headroom(gib=30)
    if memory["available_physical_bytes"]<12*1024**3:
        raise ValueError("Source Stage1 RAM admission denied")
    source=hou.Geometry()
    source.loadFromFile(str(STAGE1))
    vols={x.attribValue("name"):x for x in source.prims() if isinstance(x,hou.Volume)}
    if set(vols)!={"height","mask","Alpha"}:
        raise ValueError("Unexpected source height/Alpha volume names")
    if any(tuple(v.resolution())!=GRID for v in vols.values()):
        raise ValueError("Not source-authority 16k lattice")
    if max(abs(float(a)-b) for a,b in zip(vols["height"].indexToPos((0,0,0)),(-3999.75,0,3999.75)))>1.0:
        raise ValueError("World space native Stage1 origin differs")
    observed=[]
    for entry in sites:
        h=vols["height"]
        coordinate=list(map(float,h.indexToPos((entry["i"],entry["j"],0))))
        if max(abs(a-b) for a,b in zip(coordinate,entry["center_world_xyz"]))>0.005:
            raise ValueError("Sand candidate Stage2 and original Stage1 spatial registration differ")
        summary=sample_region(h,vols["Alpha"],entry)
        observed.append({"stage2":entry,"stage1":summary,"geographic_center":coordinate})
    ordered=order_candidates(observed)
    selected=next((v for v in ordered if v["stage1"]["alpha_fraction"]>=0.95 and
                   v["stage1"]["valid_low_elevation_fraction"]>=0.80 and
                   v["stage1"]["invalid_alpha"]==0 and
                   v["stage1"]["invalid_height_inside_valid_alpha"]==0),None)
    if selected is None:
        return {
            "schema_version":1,
            "status":"NO_ACCEPTABLE_REAL_STAGE1_ALPHA_AND_LOW_HEIGHT_SAND_SITE",
            "source_stage1_sha256":STAGE1_SHA,"source_stage2_sha256":PIN_MASK_SHA,
            "candidate_report_sha256":candidate_hash,"candidates":ordered,
            "terrain_or_masks_changed":False,"native_source_cropped":False,
            "coastline_visual_proof":False
        }
    i,j=selected["stage2"]["i"],selected["stage2"]["j"]
    cropped={name:extract(vol,i,j,np) for name,vol in vols.items()}
    if int(np.count_nonzero(cropped["Alpha"]>0.5))<int(0.95*SIZE*SIZE):
        raise ValueError("Precise native Alpha does not match candidate's accepted coarse score")
    if require_source()!=before:
        raise ValueError("Original Stage1 changed during sand source extraction")
    out=OUTPUT/token
    if out.exists():
        raise ValueError("Native sand source output already exists")
    out.mkdir(parents=True,exist_ok=False)
    local=out/"selected-sand-stage1.npz"
    with local.open("xb") as stream:
        np.savez_compressed(stream,**cropped)
    with np.load(local,allow_pickle=False) as reopened:
        if set(reopened.files)!=set(cropped):
            raise ValueError("Native source NPZ readback lost Stage1 layers")
        for name in cropped:
            if not np.array_equal(cropped[name],reopened[name]):
                raise ValueError(f"Saved/reopened real Stage1 {name} changed")
    return {
        "schema_version":1,
        "status":"REAL_SAND_POSITIVE_SITE_STAGE1_HEIGHT_ALPHA_VERIFIED_STAGE2_CROP_PENDING",
        "source_stage1_sha256":STAGE1_SHA,"source_stage2_sha256":PIN_MASK_SHA,
        "candidate_report_sha256":candidate_hash,
        "selected_site":selected,
        "candidate_quality":ordered,
        "native_source_site":[i,j],
        "accepted_real_cropped_base_path":str(local),
        "accepted_real_cropped_base_sha256":sha(local),
        "precise_alpha_valid_count":int(np.count_nonzero(cropped["Alpha"]>0.5)),
        "precise_valid_height_min":float(cropped["height"][cropped["Alpha"]>0.5].min()),
        "precise_valid_height_max":float(cropped["height"][cropped["Alpha"]>0.5].max()),
        "world_extent":[list(map(float,vols["height"].indexToPos((i-128,j-128,0)))),
                        list(map(float,vols["height"].indexToPos((i+127,j+127,0))))],
        "original_stage1_height_alpha_unchanged":True,
        "source_stage2_mask_not_yet_cropped":True,
        "coastline_landmark_verified":False,
        "unreal_import":False,
        "full_domain_material_cooked":False,
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token",required=True)
    args=parser.parse_args()
    if not re.fullmatch(r"[0-9]{9,13}-[1-9][0-9]*",args.token):
        raise ValueError("Invalid exact GitHub run and attempt")
    import hou
    import numpy as np
    result=run(hou,np,args.token)
    out=OUTPUT/args.token
    if os.name=="nt" and not str(out).lower().replace("/","\\").startswith("d:\\yacs\\work\\"):
        raise ValueError("Wrong output work root")
    out.mkdir(parents=True,exist_ok=True)
    file=out/"sand-height-alpha-site.json"
    file.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],
                      "best_center":result.get("native_source_site"),
                      "valid_alpha":result.get("precise_alpha_valid_count"),
                      "range":[result.get("precise_valid_height_min"),result.get("precise_valid_height_max")],
                      "receipt":str(file)}))


if __name__=="__main__":
    main()

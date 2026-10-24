#!/usr/bin/env python3
"""Find actual sand-positive 256x256 site candidates from accepted 16K Stage2.

No full terrain cook or source mutation. Uses a deterministic bounded
coarse scan of the original full 16000x16000 sand_mask volume in one fresh
Houdini process. Geography is candidate-only until independently checked
against the accepted Stage1 height/Alpha in a SECOND native process.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time

ROOT=Path("D:/yacs/work/lesson06-unified-20261019")
SOURCE=ROOT/"stage2_masks.bgeo.sc"
OUT=Path("D:/yacs/work/lesson07-sand-candidates")
PIN_SHA="203d46ea79a0a697d46256f631271135a0cd8766ba8768f7432ea315512c16a8"
SIZE=1167222140
GRID=(16000,16000,1)
WINDOW=256
STEP=32
MAX_SCAN_SEC=180
MAX_BUCKETS=1200
MIN_SAND=0.01


def digest(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda:fh.read(1<<20),b""):
            h.update(chunk)
    return h.hexdigest()


def check_source()->dict:
    before=SOURCE.stat()
    if not SOURCE.is_file() or before.st_size!=SIZE:
        raise ValueError("Accepted Stage2 bytes/source size missing")
    sha=digest(SOURCE)
    after=SOURCE.stat()
    if sha!=PIN_SHA or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise ValueError("Accepted Stage2 changed during native sand scan")
    return {"source_sha256":PIN_SHA,"source_size":SIZE,"mtime_ns":after.st_mtime_ns}


def candidates_at_bucket_peaks(volume, clock=time.monotonic)->dict:
    started=clock()
    candidates={}
    band_peaks={}
    scanned=0
    positives=0
    for j in range(WINDOW//2,16000-WINDOW//2,STEP):
        for i in range(WINDOW//2,16000-WINDOW//2,STEP):
            value=float(volume.voxel((i,j,0)))
            scanned+=1
            if not math.isfinite(value) or not -1e-5<=value<=1.00001:
                raise ValueError("Invalid original native sand_mask value")
            if value>MIN_SAND:
                positives+=1
                key=(i//512,j//512)
                previous=candidates.get(key)
                if previous is None or (value,i,j)>(previous["max_sample"],previous["i"],previous["j"]):
                    candidates[key]={"i":i,"j":j,"max_sample":value}
                # The highest sand value in a bucket often lies in Alpha=0
                # offshore. Retain candidate peaks in *each* sand-intensity
                # band for a separate Alpha/height intersection on Stage1.
                band=min(3,int(value*4))
                band_key=(key[0],key[1],band)
                past=band_peaks.get(band_key)
                if past is None or (value,i,j)>(past["max_sample"],past["i"],past["j"]):
                    band_peaks[band_key]={"i":i,"j":j,"max_sample":value,
                                          "sand_value_band":band}
            if scanned%32768==0 and clock()-started>MAX_SCAN_SEC:
                raise ValueError("Native sand discovery exceeded bounded scan admission")
    if len(candidates)>MAX_BUCKETS or len(band_peaks)>4*MAX_BUCKETS:
        raise ValueError("Unexpected number of occupied tile buckets")
    return {"sampled":scanned,"positive_count":positives,
            "bucket_peaks":candidates,"band_peaks":band_peaks,
            "seconds":clock()-started}


def refine_neighborhood(volume,i:int,j:int)->dict:
    # 32^2 values per 256-wide candidate window: estimates semantic coverage
    # without claiming all 65536 native pixels were read yet.
    v=[]
    for y in range(j-128,j+128,8):
        for x in range(i-128,i+128,8):
            n=float(volume.voxel((x,y,0)))
            if not math.isfinite(n) or n<(-1e-5) or n>1.00001:
                raise ValueError("Invalid sampled native sand candidate")
            v.append(n)
    # Exactly the same 16x16 world-index lattice sampled in Stage1, in
    # the same row-major order. Stage2 and Stage1 must never be loaded
    # simultaneously just to intersect semantic sand with valid Alpha.
    grid16=[v[y*32+x] for y in range(0,32,2) for x in range(0,32,2)]
    return {"sample_count":len(v),"positive_samples":sum(x>MIN_SAND for x in v),
            "mean":sum(v)/len(v),"max":max(v),"sample_step":8,
            "alpha_joint_grid16":grid16}


def select_diverse(results:list[dict], count:int=8)->list[dict]:
    chosen=[]
    for item in sorted(results,key=lambda x:(-x["refined"]["mean"],-x["refined"]["positive_samples"],x["i"],x["j"])):
        if all((item["i"]-c["i"])**2+(item["j"]-c["j"])**2>=512**2 for c in chosen):
            chosen.append(item)
        if len(chosen)>=count:
            break
    return chosen


def run(hou,alpha_aware=False)->dict:
    if hou.isUIAvailable() or tuple(hou.applicationVersion())!=(22,0,466):
        raise ValueError("Requires fresh headless Houdini 22.0.466")
    if hou.node("/obj").children():
        raise ValueError("Cannot scan real source in a user scene")
    before=check_source()
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    from scripts.ue.lesson06_memory_guard import require_headroom
    memory=require_headroom(gib=30)
    if memory["available_physical_bytes"]<12*1024**3:
        raise ValueError("Insufficient physical headroom to load accepted 4-volume Stage2 cache")
    geo=hou.Geometry()
    geo.loadFromFile(str(SOURCE))
    values={p.attribValue("name"):p for p in geo.prims() if isinstance(p,hou.Volume)}
    if set(values)!={"grass_mask","sand_mask","cliff_mask","ramp_layer"}:
        raise ValueError("Source semantic Stage2 layer set differs from pinned")
    volume=values["sand_mask"]
    if tuple(volume.resolution())!=GRID:
        raise ValueError("Wrong accepted 16K source resolution")
    ref=tuple(map(float,volume.indexToPos((0,0,0))))
    if max(abs(x-y) for x,y in zip(ref,(-3999.75,0,3999.75)))>1.0:
        raise ValueError("Wrong 16K source geographic registration")
    original=candidates_at_bucket_peaks(volume)
    if original["positive_count"]==0:
        raise ValueError("Accepted producer states max=1 but native sand sampling found no positives")
    peaks=sorted(original["bucket_peaks"].values(),key=lambda x:(-x["max_sample"],x["i"],x["j"]))[:80]
    refined=[]
    for item in peaks:
        data=refine_neighborhood(volume,item["i"],item["j"])
        coords=list(map(float,volume.indexToPos((item["i"],item["j"],0))))
        refined.append({**item,"refined":data,"center_world_xyz":coords,
                        "window_indices":[item["i"]-128,item["j"]-128,item["i"]+128,item["j"]+128]})
    chosen=select_diverse(refined)
    alpha_pool=[]
    if alpha_aware:
        dedup_coords={}
        for item in sorted(original["band_peaks"].values(),
                           key=lambda x:(-x["max_sample"],x["i"],x["j"],-x["sand_value_band"])):
            coord_key=(item["i"],item["j"])
            if coord_key not in dedup_coords:
                dedup_coords[coord_key]=item
        candidates=sorted(dedup_coords.values(),
                          key=lambda x:(x["i"],x["j"],x["sand_value_band"]))
        if not 0<len(candidates)<=4*MAX_BUCKETS:
            raise ValueError("Unexpected candidate diversity count")
        for item in candidates:
            stats=refine_neighborhood(volume,item["i"],item["j"])
            coord=list(map(float,volume.indexToPos((item["i"],item["j"],0))))
            alpha_pool.append({**item,"refined":stats,
                               "center_world_xyz":coord,
                               "window_indices":[item["i"]-128,item["j"]-128,
                                                 item["i"]+128,item["j"]+128]})
        if len({(x["i"],x["j"]) for x in alpha_pool})!=len(alpha_pool):
            raise ValueError("Duplicate Stage2 Alpha-aware candidate coordinates")
    if len(chosen)<1 or chosen[0]["refined"]["positive_samples"]<1:
        raise ValueError("No verified sand-positive representative site was found")
    if check_source()!=before:
        raise ValueError("Source cache changed during geographic site selection")
    return {
        "schema_version":1,"status":"SAND_POSITIVE_STAGE2_WORLD_COORDINATE_CANDIDATES_NOT_CROPPED",
        "source":before,"full_lattice":list(GRID),"source_origin_xyz":list(ref),
        "source_mean_recorded_in_producer":0.07240492912124141,
        "scan_stride":STEP,"positive_coarse_samples":original["positive_count"],
        "scanned_sample_count":original["sampled"],"candidate_bucket_count":len(original["bucket_peaks"]),
        "initial_peak_candidates_refined":len(refined),"chosen":chosen,
        "alpha_aware_candidate_pool":alpha_pool,
        "alpha_aware_grid_step":16 if alpha_aware else None,
        "alpha_aware_pool_count":len(alpha_pool),
        "site_alpha_and_height_verified":False,"coastline_landmark_verified":False,
        "canonical_height_or_masks_changed":False,"native_material_cook":False,"unreal_import":False,
        "memory_admission":memory,
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token",required=True)
    parser.add_argument("--alpha-aware",action="store_true",
                        help="Retain bounded per-sand-band full-domain candidate pool for Stage1 land intersection")
    args=parser.parse_args()
    if not re.fullmatch(r"[0-9]{9,13}-[1-9][0-9]*",args.token):
        raise ValueError("Invalid workflow run and attempt")
    import hou
    result=run(hou,alpha_aware=args.alpha_aware)
    folder=OUT/args.token
    if os.name=="nt" and not str(folder).lower().replace("/","\\").startswith("d:\\yacs\\work\\"):
        raise ValueError("Cannot write outside isolated source diagnostics")
    if folder.exists():
        raise ValueError("No overwrite of existing site proof")
    folder.mkdir(parents=True,exist_ok=False)
    out=folder/"real-sand-site-candidates.json"
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"samples":result["scanned_sample_count"],
                      "positive_samples":result["positive_coarse_samples"],
                      "top_sites":result["chosen"][:3],
                      "receipt":str(out)}))


if __name__=="__main__":
    main()

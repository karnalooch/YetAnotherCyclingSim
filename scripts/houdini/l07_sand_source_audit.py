#!/usr/bin/env python3
"""Audit accepted full-16k Stage2 sand mask producer without native geometry cook.

Read-only: confirms entire *producer* sand range and reports whether a coastal
material canary with sand_mask>0 can be found from current Stage2 or whether
the SOURCE producer is empty. Does not infer actual coastline from min/max.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

ROOT=Path("D:/yacs/work/lesson06-unified-20261019")
SOURCE=ROOT/"stage2_masks.bgeo.sc"
RECEIPT=ROOT/"stage2_masks.json"
OUTPUT=Path("D:/yacs/work/lesson07-sand-mask-audit")
PIN_SHA256="203d46ea79a0a697d46256f631271135a0cd8766ba8768f7432ea315512c16a8"
PIN_SIZE=1167222140


def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda:source.read(1<<20),b""):
            h.update(chunk)
    return h.hexdigest()


def validate_producer_report(producer:dict)->dict:
    if producer.get("stage")!="stage2_masks":
        raise ValueError("Input is not the accepted source Stage2 producer")
    if str(producer.get("output_file","")).lower().replace("/","\\")!=str(SOURCE).lower().replace("/","\\"):
        raise ValueError("Stage2 producer claims a different cache")
    if producer.get("sha256")!=PIN_SHA256:
        raise ValueError("Producer mask hash differs from the independently accepted source")
    keys={"grass_mask","sand_mask","cliff_mask","ramp_layer"}
    if not keys.issubset(producer):
        raise ValueError("Required four Stage2 mask statistics missing")
    metrics={}
    for kind in sorted(keys):
        entry=producer[kind]
        if not isinstance(entry,dict) or int(entry.get("count",-1))!=256000000:
            raise ValueError(f"Wrong statistical cell count for {kind}")
        lo,hi,mean=(float(entry[k]) for k in ("min","max","mean"))
        if not 0<=lo<=mean<=hi<=1.00001:
            raise ValueError(f"Invalid original Stage2 {kind} range")
        metrics[kind]={"min":lo,"max":hi,"mean":mean,"count":int(entry["count"])}
    return metrics


def run()->dict:
    before=SOURCE.stat()
    if not SOURCE.is_file() or before.st_size!=PIN_SIZE:
        raise ValueError("Canonical Stage2 source cache absent or wrong file size")
    if sha(SOURCE)!=PIN_SHA256:
        raise ValueError("Native accepted Stage2 source bytes differ")
    after=SOURCE.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise ValueError("Original source changed during sand audit")
    original=validate_producer_report(json.loads(RECEIPT.read_text(encoding="utf-8")))
    stats=original["sand_mask"]
    return {
        "schema_version":1,
        "status":("STAGE2_SAND_POSITIVE_VALUES_SOMEWHERE_NATIVE_SITE_PENDING"
                  if stats["max"]>0 else "STAGE2_SAND_ENTIRE_16K_PRODUCER_ZERO"),
        "source_path":str(SOURCE),
        "source_sha256":PIN_SHA256,"source_bytes":PIN_SIZE,
        "producer_sha256":sha(RECEIPT),
        "producer_statistics":original,
        "sand_positive_exists_in_full_16k":stats["max"]>0,
        "sand_coastline_location_verified":False,
        "source_geometry_loaded":False,"native_cook":False,
        "full_16k_height_or_masks_mutated":False,"unreal_modified":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--token",required=True)
    args=p.parse_args()
    if not re.fullmatch(r"[0-9]{9,13}-[1-9][0-9]*",args.token):
        raise ValueError("Invalid immutable source-run token")
    proof=run()
    target=OUTPUT/args.token
    if os.name=="nt" and not str(target).lower().replace("/","\\").startswith("d:\\yacs\\work\\"):
        raise ValueError("Wrong bounded output")
    if target.exists():
        raise ValueError("Do not overwrite previous sand source proof")
    target.mkdir(parents=True,exist_ok=False)
    file=target/"sand-source-audit.json"
    file.write_text(json.dumps(proof,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":proof["status"],
                      "sand_statistics":proof["producer_statistics"]["sand_mask"],
                      "output":str(file)}))


if __name__=="__main__":
    main()

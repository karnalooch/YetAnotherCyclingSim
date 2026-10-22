#!/usr/bin/env python3
"""Read-only inventory of preexisting Pegasus Stage3 scree-mask source cache.

Checks producer self-identity, selected upstream Stage4C metadata, and native
ginfo header. Does not assume source Stage3 scree cache is production-approved.
Never starts hou/UE, recooks cache, overwrites a file, or changes producer files.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT=Path("D:/yacs/work/lesson06-unified-20261019")
OUT=Path("D:/yacs/work/lesson07-cc0-scree-audit")
GINFO=Path("D:/yacs/tools/houdini-22.0.466/bin/ginfo.exe")
GINFO_SHA="be4c5d9d9753483596d7eb9664dab27fc816d0ba912597d78a6ce9061689d31d"
MAX_SIZE=2*1024**3


def signature(path,limit):
    if not path.is_file():
        return {"exists":False}
    before=path.stat()
    if not 0<before.st_size<=limit:
        # Historical 4.3-GB cliff output is not needed to inspect the separate
        # Stage3 scree mask. Retain its metadata, but NEVER mark it hash-pinned.
        return {"exists":True,"bytes":before.st_size,"sha256":None,
                "modified_ns":before.st_mtime_ns,"hash_skipped_size_limit":limit}
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):
            h.update(chunk)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise ValueError("Existing source changed during diagnostic read")
    return {"exists":True,"bytes":before.st_size,"sha256":h.hexdigest(),
            "modified_ns":before.st_mtime_ns}


def inventory():
    data={}
    for label in ("stage3_scree","stage4c_cliff"):
        cache=ROOT/(label+".bgeo.sc")
        receipt=ROOT/(label+".json")
        meta=signature(cache,MAX_SIZE)
        receipt_state=signature(receipt,16*1024)
        if not receipt_state["exists"]:
            data[label]={"cache":meta,"receipt":receipt_state,"producer_claim_matches_bytes":False}
            continue
        desc=json.loads(receipt.read_text(encoding="utf-8"))
        source=str(cache).lower().replace("/","\\")
        claimed=str(desc.get("output_file","")).lower().replace("/","\\")
        claimed_sha=desc.get("sha256")
        validated=bool(meta["exists"] and source==claimed
                       and isinstance(claimed_sha,str) and re.fullmatch(r"[0-9a-f]{64}",claimed_sha)
                       and meta["sha256"]==claimed_sha)
        data[label]={"cache":meta,"receipt":receipt_state,
                     "producer_claim_matches_bytes":validated,
                     "reported_stage":desc.get("stage"),
                     "claimed_cache_sha256":claimed_sha,
                     "reported_scree_stats":desc.get("scree_mask")}
    if not data["stage3_scree"]["cache"]["exists"]:
        status="NATIVE_STAGE3_SCREE_CACHE_ABSENT"
    elif not data["stage3_scree"]["producer_claim_matches_bytes"]:
        status="NATIVE_STAGE3_SCREE_CACHE_PRESENT_PRODUCER_MISMATCH"
    else:
        status="NATIVE_STAGE3_SCREE_CACHE_MATCHES_CURRENT_RECEIPT_NOT_ACCEPTED"
    native=None
    if data["stage3_scree"]["cache"]["exists"]:
        binary=signature(GINFO,6*1024**2)
        if not binary["exists"] or binary["sha256"]!=GINFO_SHA:
            raise ValueError("Native ginfo executable differs from pinned Houdini binary")
        run=subprocess.run([str(GINFO),"-S","-u",str(ROOT/"stage3_scree.bgeo.sc")],
            capture_output=True,text=True,timeout=40,check=False,encoding="utf-8",errors="replace")
        header=run.stdout
        # Houdini prints singular "Volume" when there is just one; capture
        # only shape/name technical lines to resolve this without guessing.
        one_volume=bool(re.search(r"\\b1 Volume(?:s)?\\b",header))
        right_name=bool(re.search(r"\\(scree_mask\\)",header))
        right_lattice=("[16000, 16000, 1]" in header)
        expected=(one_volume and right_name and right_lattice)
        technical_lines=[
            line.strip() for line in header.splitlines()
            if ("Volume" in line or "scree" in line or "Voxel Count" in line
                or "(mask)" in line)
        ][:30]
        native={"exit_code":run.returncode,
                "geometry_header_has_correct_scree_layer":expected,
                "one_volume":one_volume,
                "scree_mask_named_layer":right_name,
                "stage3_bounds_matches_16k":right_lattice,
                "technical_header_lines":technical_lines,
                "header_sha256":hashlib.sha256(header.encode()).hexdigest(),
                "stderr_empty":not bool(run.stderr.strip())}
        if run.returncode!=0 or not expected or run.stderr.strip():
            status="NATIVE_STAGE3_SCREE_HEADER_NOT_ACCEPTED"
    return {"schema_version":1,"status":status,"files":data,"native_header":native,
            "producer_isolation":"READ_ONLY_EXISTING_BYTES",
            "stage3_authority_acceptance":False,
            "full_source_lineage_verified":False,
            "real_source_masks_modified":False,
            "base_height_changed":False,
            "unreal_mutated":False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--token",required=True)
    args=p.parse_args()
    if not re.fullmatch(r"[0-9]{9,13}-[1-9][0-9]*",args.token):
        raise ValueError("Expected immutable workflow run/attempt token")
    output=OUT/args.token
    if os.name=="nt" and not str(output).lower().replace("/","\\").startswith("d:\\yacs\\work\\"):
        raise ValueError("Forbidden audit output root")
    if output.exists():
        raise ValueError("Preserve existing audit outputs")
    result=inventory()
    output.mkdir(parents=True,exist_ok=False)
    (output/"native-scree-audit.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],
                      "stage3":result["files"]["stage3_scree"],
                      "stage4c":result["files"]["stage4c_cliff"],
                      "native":result["native_header"]}),flush=True)


if __name__=="__main__":
    main()

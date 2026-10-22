#!/usr/bin/env python3
"""Read-only audit when current Sa Calobra stage2 masks differ from accepted pin.

This diagnostic NEVER admits changed source masks and cannot alter the
accepted L06 base/masks or the already live UE Landscape.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import os

CACHE=Path("D:/yacs/work/lesson06-unified-20261019")
PREVIOUS_PIN="203d46ea79a0a697d46256f631271135a0cd8768f7432ea315512c16a8"


def fingerprint(path:Path)->dict:
    before=path.stat()
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for piece in iter(lambda:stream.read(1024*1024),b""):
            digest.update(piece)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise ValueError("Cache file changed during read-only audit")
    return {"bytes":after.st_size,"mtime_ns":after.st_mtime_ns,
            "sha256":digest.hexdigest()}


def audit(cache:Path)->dict:
    file=cache/"stage2_masks.bgeo.sc"
    receipt=cache/"stage2_masks.json"
    data=fingerprint(file)
    info=json.loads(receipt.read_text(encoding="utf-8"))
    if info.get("stage")!="stage2_masks":
        raise ValueError("Wrong stage2 mask producer receipt")
    producer_sha=info.get("sha256")
    if not isinstance(producer_sha,str) or not re.fullmatch(r"[0-9a-f]{64}",producer_sha):
        raise ValueError("Invalid producer reported digest")
    if info.get("output_file","").lower().replace("/","\\")!=str(file).lower().replace("/","\\"):
        raise ValueError("Source producer receipt points at another output")
    return {
        "status":"READ_ONLY_MASK_LINEAGE_AUDIT_NOT_SOURCE_ADMISSION",
        "bytes":data["bytes"],"sha256":data["sha256"],
        "source_file_mtime_ns":data["mtime_ns"],
        "prior_independently_observed_sha256":PREVIOUS_PIN,
        "same_as_prior_independent_pin":data["sha256"]==PREVIOUS_PIN,
        "current_producer_claim_sha256":producer_sha,
        "current_matches_producer_receipt":data["sha256"]==producer_sha,
        "producer_receipt_sha256":fingerprint(receipt)["sha256"],
        "material_source_admitted":False, "stage2_mask_source_accepted":False,
        "native_geographic_crop_cooked":False,
        "canonical_source_modified":False, "unreal_modified":False,
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token",required=True)
    args=parser.parse_args()
    if not re.fullmatch(r"[0-9]{9,13}-[1-9][0-9]*",args.token):
        raise ValueError("Invalid run attempt")
    report=audit(CACHE)
    root=Path("D:/yacs/work/lesson07-cc0-mask-audits") / args.token
    if os.name=="nt" and not str(root).lower().replace("/","\\").startswith("d:\\yacs\\work\\"):
        raise ValueError("Audit output must stay in isolated D work")
    if root.exists():
        raise ValueError("Refusing overwrite of prior diagnostic")
    root.mkdir(parents=True)
    (root/"mask-source-audit.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],
        "prior_pin_equal":report["same_as_prior_independent_pin"],
        "producer_claim_equal":report["current_matches_producer_receipt"],
        "current_source_sha256":report["sha256"],
        "producer_sha256":report["current_producer_claim_sha256"],
        "bytes":report["bytes"]}),flush=True)


if __name__=="__main__":
    main()

#!/usr/bin/env python3
"""Independent bounded readback of actual Sa Calobra L06 source crop arrays.

No Houdini creation/cook, world mutation, geographic reorientation or source
cache reuse as a material proof.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import os
import re


PINNED = {
    "base": ("height","mask","Alpha"),
    "masks": ("grass_mask","sand_mask","cliff_mask","ramp_layer"),
}
SHA_PINS = {
    "base": "08586f0e1aa6aa033cf7364a929d2c260c87c41d6dc11445c981e10ec6ba2952",
    "masks": "203d46ea79a0a697d46256f631271135a0cd8766ba8768f7432ea315512c16a8",
}

def file_sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as inp:
        for block in iter(lambda:inp.read(1<<20),b''):
            h.update(block)
    return h.hexdigest()


def verify(root: Path, token: str, np, expected_window: list[int] | None = None) -> dict:
    identity, arrays = {}, {}
    observed_window = None
    for stage, keys in PINNED.items():
        p=root/f"{stage}-real-crop.json"
        d=root/f"{stage}-real-crop.npz"
        receipt=json.loads(p.read_text(encoding='utf-8'))
        if receipt.get("status") != "REAL_ACCEPTED_L06_SOURCE_CROP_REOPEN_REQUIRED":
            raise ValueError("Missing unadmitted source extraction receipt")
        if receipt.get("run_token") != token or receipt.get("stage") != stage:
            raise ValueError("Source crop run token/stage mismatch")
        if receipt.get("original_16000_grid") != [16000,16000,1]:
            raise ValueError("Wrong source grid")
        if receipt["source"]["source_sha256"] != SHA_PINS[stage]:
            raise ValueError("Unexpected baseline L06 cache source identity")
        win = receipt.get("crop_index_window")
        if receipt.get("crop_size") != 256 or not isinstance(win, list) or len(win) != 4 or win[2]-win[0] != 256 or win[3]-win[1] != 256:
            raise ValueError("Wrong accepted real source site/index window")
        if expected_window is not None and win != expected_window:
            raise ValueError("Wrong accepted real source site/index window")
        if observed_window is None:
            observed_window = win
        elif win != observed_window:
            raise ValueError("Base and mask crop index windows do not match")
        if d.stat().st_size > 10 * 1024**2 or file_sha(d) != receipt["crop_sha256"]:
            raise ValueError("Source crop archive changed")
        with np.load(d,allow_pickle=False) as archive:
            if set(archive.files) != set(keys) or set(receipt["layer_metadata"]) != set(keys):
                raise ValueError("Different layer list from accepted L06 source")
            for key in keys:
                arr=archive[key]
                if arr.shape != (256,256) or arr.dtype != np.float32 or not np.isfinite(arr).all():
                    raise ValueError(f"Invalid cropped native data for {key}")
                raw=arr.astype("<f4").tobytes()
                metadata=receipt["layer_metadata"][key]
                if hashlib.sha256(raw).hexdigest() != metadata["sha256_float32_le"]:
                    raise ValueError(f"Crop voxel identity mismatch: {key}")
                if int(np.count_nonzero(arr)) != metadata["nonzero"]:
                    raise ValueError(f"Crop nonzero distribution mismatch: {key}")
                arrays[key]=metadata
        identity[stage]={"sha256":file_sha(p),"source":receipt["source"],
                         "npz_sha256":receipt["crop_sha256"]}
    # Every layer must share the same Houdini source-world spatial mapping.
    a=arrays["height"]
    for name,b in arrays.items():
        for k in ("first_voxel_world_xyz","last_voxel_world_xyz"):
            if len(b[k]) != 3 or len(a[k]) != 3:
                raise ValueError("Missing spatial origin/extent")
            if max(abs(float(x)-float(y)) for x,y in zip(a[k],b[k])) > 0.005:
                raise ValueError(f"Layer {name} has mismatched native geographic coordinates")
    if arrays["Alpha"]["nonzero"] <= 0:
        raise ValueError("No valid terrain in selected real source site")
    return {"status":"REAL_SOURCE_CROPS_VERIFIED_NO_MATERIAL_COOK","run_token":token,
            "sources":identity,"seven_layer_names":sorted(arrays),
            "extent_world":[a["first_voxel_world_xyz"],a["last_voxel_world_xyz"]],
            "raw_source_resolution":[16000,16000,1],"crop_resolution":[256,256,1],
            "original_geometry_source":True,"source_stage2_masks_preserved":True,
            "geometry_modified":False,"full_landscape_cooked":False,
            "unreal_import":False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--run-token",required=True)
    x=p.parse_args()
    if not re.fullmatch(r"[0-9]{9,13}-[1-9][0-9]*",x.run_token):
        raise ValueError("Invalid exact run/attempt")
    root=x.root.resolve()
    if os.name=="nt" and not str(root).lower().replace("/","\\").startswith("d:\\yacs\\work\\lesson07-cc0-real-crops\\"):
        raise ValueError("Wrong isolated work folder")
    import numpy as np
    receipt=verify(root,x.run_token,np)
    out=root/"real-source-verified.json"
    if out.exists():
        raise ValueError("Do not overwrite immutable native source readback")
    out.write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":receipt["status"],"receipt":str(out),
                      "seven_layers":len(receipt["seven_layer_names"]),
                      "extent":receipt["extent_world"]}),flush=True)


if __name__=="__main__":
    main()

#!/usr/bin/env python3
"""Read-only native SideFX MaskByFeature/Visualize/Tint parameter contract.

No protected Sa Calobra source is opened and NO full-domain cook occurs. The
script queries actual Houdini 22.0.466 live parameter templates, so no
guessed legacy names/ports enter the source-grade recipe.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

TINT_HDA=Path("D:/yacs/project/worldgen/houdini/sa_calobra/otls/sop_PE_heightfield_tint.1.0.hda")
SHA="93cc47dd511bc3d5868835b5dd3b9082c13cab23355b688aaf2a947e8687a2ed"
OUTPUT=Path("D:/yacs/work/lesson07-feature-native-contract")
TYPES=("heightfield_maskbyfeature","heightfield_visualize","PE_heightfield_tint::1.0")
KEYWORDS=("occlu","curv","slope","height","search","step","view","ramp","smooth",
          "mask","invert","combine","direction","range","max","min","source",
          "update","tint","material","quality","distance","angle","scale")


def digest(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda:source.read(1<<20),b""):
            h.update(chunk)
    return h.hexdigest()


def selected(visible_name:str)->bool:
    return any(token in visible_name.lower() for token in KEYWORDS)


def describe(node)->dict:
    output=[]
    for parm in node.parms():
        name=parm.name()
        label=parm.parmTemplate().label()
        if not selected(name+" "+label):
            continue
        try:
            val=parm.eval()
        except Exception:
            val=None
        if isinstance(val,(int,float,str)) and len(str(val))<180:
            value=val
        else:
            value=None
        output.append({
            "name":name,"label":label,
            "type":str(parm.parmTemplate().type()),
            "default_evaluation":value,
            "expression":str(parm.expression())[:140] if parm.isTimeDependent() else None,
        })
    native_labels=getattr(node,"inputLabels",None)
    labels=list(native_labels()) if callable(native_labels) else []
    result={
        "node_type":node.type().name(),
        "input_labels":labels,
        "min_inputs":node.type().minNumInputs(),
        "max_inputs":node.type().maxNumInputs(),
        "parameters":output,
    }
    if not output:
        raise ValueError("Native node contains no relevant parameter templates")
    return result


def run(hou,token:str)->dict:
    if hou.isUIAvailable() or tuple(hou.applicationVersion())!=(22,0,466):
        raise ValueError("Requires fresh headless Houdini 22.0.466")
    if hou.node("/obj").children():
        raise ValueError("Cannot introspect existing user Houdini scene")
    if digest(TINT_HDA)!=SHA:
        raise ValueError("Original SideFX Tint HDA bytes changed")
    hou.hda.installFile(str(TINT_HDA),force_use_assets=True)
    parent=hou.node("/obj").createNode("geo","L07_READ_ONLY_NATIVE_PARMS")
    try:
        for child in parent.children():
            child.destroy()
        nodes={}
        for kind in TYPES:
            node=parent.createNode(kind,"INTROSPECT_"+re.sub(r"[^a-zA-Z0-9_]+","_",kind).upper())
            output=describe(node)
            nodes[kind]=output
        if "heightfield_maskbyfeature" not in nodes or "PE_heightfield_tint::1.0" not in nodes:
            raise ValueError("Native SideFX node definition is missing")
        return {
            "status":"SIDEFX_NATIVE_FEATURE_TINT_PARM_CONTRACT_READ_ONLY",
            "houdini":hou.applicationVersionString(),
            "source_tint_hda_sha256":SHA,"source_stage3_authority_accepted":False,
            "nodes":nodes,"houdini_scene_saved":False,"native_cook":False,
            "original_height_and_masks_modified":False,"unreal_modified":False
        }
    finally:
        parent.destroy()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token",required=True)
    args=parser.parse_args()
    if not re.fullmatch(r"[0-9]{9,13}-[1-9][0-9]*",args.token):
        raise ValueError("Expected run ID and attempt")
    import hou
    proof=run(hou,args.token)
    target=OUTPUT/args.token
    if os.name=="nt" and not str(target).lower().replace("/","\\").startswith("d:\\yacs\\work\\"):
        raise ValueError("Output path escaped D scratch")
    if target.exists():
        raise ValueError("Refusing to overwrite previous source-contract proof")
    target.mkdir(parents=True,exist_ok=False)
    out=target/"native-feature-tint-parameter-contract.json"
    out.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "status":proof["status"],
        "node_types":list(proof["nodes"]),
        "fields_per_node":{n:len(v["parameters"]) for n,v in proof["nodes"].items()},
        "artifact":str(out)
    }))


if __name__=="__main__":
    main()

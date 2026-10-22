#!/usr/bin/env python3
"""Five ORIGINAL Pegasus material HDAs over real, pinned Sa Calobra source voxels.

This is an isolated 256x256 native material proof, not the author's full final
material/tint/erosion graph and NOT a whole-8-km Landscape bake. Sand has zero
coverage at the selected scree site; scree uses a diagnostic cliff-mask proxy
until the original Stage3 scree mask is independently accepted.

Height Scale=0 on all HDAs is an intentional, explicit test adaptation so
unchanged accepted height voxels can be established before any displacement.
No canonical caches, Editor, LFS assets, or user maps are written.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import zlib

SIZE = 256
PIN_HDA = "e7d41ca64757699aa65b69520aca96b11f7325365506ddc675f8ea2b23a45023"
HDA = Path("D:/yacs/project/worldgen/houdini/sa_calobra/otls/sop_PE_heightfield_material.1.0.hda")
SOURCE_ROOT = Path("D:/yacs/work/lesson07-polyhaven-cc0-v1")
CROP_ROOT = Path("D:/yacs/work/lesson07-cc0-real-crops")
OUTPUT_ROOT = Path("D:/yacs/work/lesson07-cc0-real-material")

# Original source-observed texture tile scales; all heightscales pinned to ZERO
# only for this preservation canary. Scree mask is a test proxy (NOT final).
ROLES = (
    ("rock", "dark_rock", None, 1000.0, False),
    ("grass", "sparse_grass", "grass_mask", 100.0, True),
    ("sand", "dense_sand", "sand_mask", 500.0, True),
    ("cliff", "dark_rock_02", "cliff_mask", 100.0, True),
    ("scree", "gray_rocks", "cliff_mask", 100.0, True),
)
PROTECTED = ("height", "mask", "Alpha", "grass_mask", "sand_mask", "cliff_mask", "ramp_layer")
BINARY_LIMIT = 32 * 1024**2


def digest(path: Path)->str:
    obj=hashlib.sha256()
    with path.open("rb") as h:
        for chunk in iter(lambda:h.read(1<<20),b""):
            obj.update(chunk)
    return obj.hexdigest()


def accepted_inputs(crop_folder:Path,source_token:str,material_folder:Path,np)->tuple[dict,dict,dict]:
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    from scripts.houdini.verify_l07_real_crop import verify
    original=verify(crop_folder,source_token,np)
    if original["status"]!="REAL_SOURCE_CROPS_VERIFIED_NO_MATERIAL_COOK":
        raise ValueError("Only verified exact-L06 Sa Calobra source windows are allowed")
    if original.get("crop_resolution")!=[256,256,1]:
        raise ValueError("Not the approved 256x256 real source")
    binding=json.loads((material_folder/"bindings-v1.json").read_text(encoding="utf-8"))
    if binding.get("status")!="SOURCE_BINDINGS_VERIFIED_NO_MATERIAL_IMPORT":
        raise ValueError("Source textures lack independent provider verification")
    inputs={}
    actual_roles={x["role"]:x for x in binding["houdini"]}
    if len(actual_roles)!=5:
        raise ValueError("Expected precisely five pinned Houdini material roles")
    for role,slug,*_ in ROLES:
        selected=actual_roles[role]
        if selected["slug"]!=slug or set(selected["files"])!={"diff","rough","nor_gl","disp"}:
            raise ValueError(f"Material identity drift: {role}")
        output={}
        for kind,parameter in (("diff","filename1"),("rough","filename2"),("disp","filename3")):
            rec=selected["files"][kind]
            file=Path(rec["path"]).resolve()
            if not file.is_relative_to(material_folder.resolve()) or not file.is_file():
                raise ValueError("Source image left the approved CC0 cache")
            if digest(file)!=rec["sha256"]:
                raise ValueError(f"Publisher-verified {role}/{kind} source changed")
            output[parameter]=str(file)
        inputs[role]=output
    return original, inputs, binding


def read_crops(folder:Path,np)->tuple[dict,dict]:
    meta={}
    for stage in ("base","masks"):
        meta[stage]=json.loads((folder/f"{stage}-real-crop.json").read_text(encoding="utf-8"))
    arrays={}
    for stage in ("base","masks"):
        with np.load(folder/f"{stage}-real-crop.npz",allow_pickle=False) as archive:
            for name in archive.files:
                if name in arrays:
                    raise ValueError("Duplicate source crop layer")
                arrays[name]=np.array(archive[name],dtype="<f4",copy=True)
    if set(arrays)!=set(PROTECTED):
        raise ValueError(f"Unexpected canonical source crop names: {sorted(arrays)}")
    for name,a in arrays.items():
        if a.shape!=(SIZE,SIZE) or not np.isfinite(a).all():
            raise ValueError(f"Invalid pinned source voxels: {name}")
    return arrays,meta


def read_historical_scree_source(source_token: str, scree_token: str, np):
    """Reverify exact Stage3 diagnostic bytes; do not grant upstream authority."""
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    from scripts.houdini.verify_l07_scree_crop import verify as verify_scree
    diagnostic=verify_scree(CROP_ROOT/scree_token,CROP_ROOT/source_token,np)
    if not diagnostic.get("site_has_scree") or diagnostic.get("scree_nonzero",0)<=0:
        raise ValueError("Source scree mask is empty at the chosen real Sa Calobra site")
    if diagnostic.get("source_stage3_upstream_lineage_accepted") is not False:
        raise ValueError("Historical scree lineage cannot be silently promoted")
    with np.load(CROP_ROOT/scree_token/"scree-real-crop.npz",allow_pickle=False) as source:
        if source.files!=["scree_mask"]:
            raise ValueError("Stage3 source must contain exactly one scree mask")
        mask=np.array(source["scree_mask"],dtype="<f4",copy=True)
    if mask.shape!=(SIZE,SIZE) or not np.isfinite(mask).all():
        raise ValueError("Historical scree diagnostic crop has invalid voxels")
    return mask, diagnostic


def selected_mask(role: str, original: str | None, scree_token: str | None) -> str | None:
    """Explicitly switch only the scree test to real historical Stage3 mask."""
    if role=="scree" and scree_token is not None:
        return "scree_mask"
    return original


def volume_by_name(geo,hou)->dict:
    items={v.attribValue("name"):v for v in geo.prims() if isinstance(v,hou.Volume)}
    if len(items)!=len(geo.prims()):
        raise ValueError("Non-volume primitive in native material field")
    return items


def source_layer_hashes(geo,hou)->dict:
    result={}
    for name,volume in volume_by_name(geo,hou).items():
        if tuple(volume.resolution())!=(SIZE,SIZE,1):
            raise ValueError(f"Not a 256x256 native heightfield layer: {name}")
        raw=volume.allVoxelsAsString()
        if len(raw)!=SIZE*SIZE*4:
            raise ValueError("Wrong native float32 voxel format")
        result[name]=hashlib.sha256(raw).hexdigest()
    return result


def align_to_original(vol,original,hou)->None:
    first=vol.indexToPos((0,0,0))
    target=original["first_voxel_world_xyz"]
    # Accepted L06 j-index heads toward negative Z. A newly created Houdini
    # heightfield SOP heads toward positive Z; keep X and up unchanged.
    # Mirror ONLY scratch volume transforms, NEVER accepted source arrays.
    local=hou.Matrix4(vol.transform()) * hou.hmath.buildTranslate(vol.vertex(0).point().position())
    vol.setTransform(local * hou.hmath.buildScale((1.0,1.0,-1.0)))
    reflected_first=vol.indexToPos((0,0,0))
    center=vol.vertex(0).point()
    center.setPosition(center.position()+hou.Vector3(tuple(float(t)-float(f) for t,f in zip(target,reflected_first))))
    after_first=vol.indexToPos((0,0,0))
    after_last=vol.indexToPos((SIZE-1,SIZE-1,0))
    if (max(abs(float(a)-float(b)) for a,b in zip(after_first,target))>0.008
            or max(abs(float(a)-float(b)) for a,b in zip(after_last,original["last_voxel_world_xyz"]))>0.02):
        raise ValueError(f"Native cropped lattice mismatch: first={list(after_first)}, last={list(after_last)}, expected_first={target}, expected_last={original['last_voxel_world_xyz']}, initial_first={list(first)}, original_transform={list(vol.transform().asTuple())}")


def make_original_geometry(obj,hou,np,arrays,metadata):
    hf=obj.createNode("heightfield","REAL_SA_CALOBRA_LATTICE")
    hf.parmTuple("size").set((128.0,128.0))
    hf.parm("gridspacing").set(0.5)
    hf.cook(force=True)
    seed=hf.geometry()
    if set(volume_by_name(seed,hou))!={"height","mask"}:
        raise ValueError("Unexpected new Houdini heightfield layer structure")
    if any(tuple(v.resolution())!=(SIZE,SIZE,1) for v in volume_by_name(seed,hou).values()):
        raise ValueError("Houdini native 0.5-m field does not have 256x256 resolution")
    base=hou.Geometry(seed)
    for name in ("height","mask"):
        v=volume_by_name(base,hou)[name]
        v.setAllVoxelsFromString(arrays[name].tobytes())
        align_to_original(v,metadata["base"]["layer_metadata"][name],hou)

    for name in ("Alpha","grass_mask","sand_mask","cliff_mask","ramp_layer"):
        single=hou.Geometry(seed)
        original=volume_by_name(single,hou)
        single.deletePrims([original["height"]],True)
        v=volume_by_name(single,hou)["mask"]
        v.setAttribValue("name",name)
        v.setAllVoxelsFromString(arrays[name].tobytes())
        key="base" if name=="Alpha" else "masks"
        align_to_original(v,metadata[key]["layer_metadata"][name],hou)
        base.merge(single)
    if set(volume_by_name(base,hou))!=set(PROTECTED):
        raise ValueError("Cropped source layers missing after native assembly")
    for name in PROTECTED:
        actual=source_layer_hashes(base,hou)[name]
        expected=hashlib.sha256(arrays[name].tobytes()).hexdigest()
        if actual!=expected:
            raise ValueError(f"Actual native Houdini source field differs: {name}")
    return base


def make_mask_source(base,hou,np,arrays,name):
    geo=hou.Geometry(base)
    vols=volume_by_name(geo,hou)
    geo.deletePrims([v for k,v in vols.items() if k!="mask"],True)
    mask=volume_by_name(geo,hou)["mask"]
    mask.setAllVoxelsFromString(arrays[name].tobytes())
    return geo


def png_chunk(tag,body):
    crc=zlib.crc32(tag+body)&0xFFFFFFFF
    return struct.pack(">I",len(body))+tag+body+struct.pack(">I",crc)


def save_png(path:Path,rgb,np):
    if rgb.shape!=(SIZE,SIZE,3) or not np.isfinite(rgb).all():
        raise ValueError("Invalid native RGB preview")
    # Source texture RGB can exceed 1 after tint; render is display-clipped only.
    pixels=np.clip(rgb,0.0,1.0)
    pixels=(pixels*255.0+0.5).astype(np.uint8)
    scanlines=b"".join(b"\0"+pixels[y].tobytes() for y in range(SIZE))
    png=b"\x89PNG\r\n\x1a\n"
    png+=png_chunk(b"IHDR",struct.pack(">IIBBBBB",SIZE,SIZE,8,2,0,0,0))
    png+=png_chunk(b"IDAT",zlib.compress(scanlines,6))
    png+=png_chunk(b"IEND",b"")
    path.write_bytes(png)


def compare_protected(before,after,role):
    missing=[name for name in PROTECTED if name not in after]
    changed=[name for name in PROTECTED if name in after and before[name]!=after[name]]
    if missing or changed:
        raise ValueError(f"Original HDA modified protected geometry/masks at {role}: missing={missing}, changed={changed}")


def is_bounded_float_rounding(max_delta_m,changed_count,total=SIZE*SIZE):
    # A guard only for native COLOR-preview scratch: <=0.1 mm and <=5% cells.
    # Authoritative height MUST be restored byte-for-byte, not approximated.
    import math
    return (isinstance(changed_count,int) and isinstance(total,int)
            and 0<=changed_count<=int(total*0.05)
            and isinstance(max_delta_m,(float,int)) and math.isfinite(max_delta_m)
            and 0<=max_delta_m<=0.0001)


def restore_scratch_height(cooked,source_arrays,protected,hou,np,role):
    original=source_arrays["height"]
    raw_volume=volume_by_name(cooked,hou).get("height")
    if raw_volume is None:
        raise ValueError(f"Original HDA removed height at {role}")
    raw=np.frombuffer(raw_volume.allVoxelsAsString(),dtype="<f4").reshape((SIZE,SIZE))
    if not np.isfinite(raw).all():
        raise ValueError(f"Original HDA made nonfinite heights at {role}")
    delta=np.abs(raw.astype(np.float64)-original.astype(np.float64))
    metrics={"changed_count":int(np.count_nonzero(delta)),
             "max_delta_m":float(delta.max()),
             "mean_delta_m":float(delta.mean()),
             "p99_delta_m":float(np.percentile(delta,99)),
             "height_raw_min_m":float(raw.min()),
             "height_raw_max_m":float(raw.max())}
    # Do not hide ANY change of original masks or Alpha behind the height fix.
    raw_hashes=source_layer_hashes(cooked,hou)
    for name in PROTECTED:
        if name!="height" and raw_hashes.get(name)!=protected[name]:
            raise ValueError(f"Native HDA changed protected {name} at {role}; refuse adjustment")
    if not is_bounded_float_rounding(metrics["max_delta_m"],metrics["changed_count"]):
        raise ValueError(f"Native HDA non-rounding height change at {role}: {json.dumps(metrics)}")
    # Houdini's material-HDA interpolation may introduce 1-ulp drift. We only
    # repair scratch geometry so the next layer receives EXACT source bytes.
    repaired=hou.Geometry(cooked)
    target=volume_by_name(repaired,hou).get("height")
    if target is None:
        raise ValueError("Cloned scratch output lost height")
    target.setAllVoxelsFromString(original.tobytes())
    hashes=source_layer_hashes(repaired,hou)
    compare_protected(protected,hashes,role)
    return repaired,hashes,{**metrics,
             "scratch_height_restored_exactly":True,
             "restoration_scope":"DISPOSABLE_REAL_256_CROP_ONLY",
             "canonical_16k_terrain_changed":False}


def run(hou,np,crop_path:Path,asset_root:Path,output:Path,token:str,scree_token:str|None=None)->dict:
    if hou.isUIAvailable() or tuple(hou.applicationVersion())!=(22,0,466):
        raise ValueError("Only fresh headless Houdini 22.0.466 is supported")
    if hou.node("/obj").children():
        raise ValueError("Unexpected user HIP or prior Houdini scene")
    if digest(HDA)!=PIN_HDA:
        raise ValueError("Original archived SideFX Pegasus HDA identity mismatch")
    provenance, material_files, binding=accepted_inputs(crop_path,token,asset_root,np)
    arrays,metadata=read_crops(crop_path,np)
    real_scree_diagnostic=None
    if scree_token is not None:
        mask,real_scree_diagnostic=read_historical_scree_source(token,scree_token,np)
        arrays["scree_mask"]=mask  # scratch mask only, never insert into canonical source BGEO
    # Never use newly computed/estimated masks in place of Stage2 accepted masks.
    count={name:int(np.count_nonzero(arrays[name])) for name in arrays}
    if count["Alpha"]!=SIZE*SIZE or count["grass_mask"]==0 or count["cliff_mask"]==0:
        raise ValueError("Pinned real-world sample not valid for both grass and cliff")
    output.mkdir(parents=True,exist_ok=False)
    hou.hda.installFile(str(HDA),force_use_assets=True)
    geo_obj=hou.node("/obj").createNode("geo","PEGASUS_REAL_CC0_CANARY")
    try:
        for child in geo_obj.children():
            child.destroy()
        geo=make_original_geometry(geo_obj,hou,np,arrays,metadata)
        input_source=output/"real_source.bgeo.sc"
        geo.saveToFile(str(input_source))
        if input_source.stat().st_size>BINARY_LIMIT:
            raise ValueError("Oversized isolated native crop")
        reloaded=hou.Geometry()
        reloaded.loadFromFile(str(input_source))
        protected=source_layer_hashes(reloaded,hou)
        if protected!=source_layer_hashes(geo,hou):
            raise ValueError("Isolated native source failed same-process reopen")
        source=geo_obj.createNode("file","LOAD_EXACT_REAL_CROP")
        source.parm("file").set(str(input_source))
        previous=source
        results=[]
        for role,slug,default_mask,size,use_mask in ROLES:
            mask_name=selected_mask(role,default_mask,scree_token)
            if mask_name is None:
                mask_node=source
            else:
                mask_data=make_mask_source(geo,hou,np,arrays,mask_name)
                mask_path=output/f"{role}_mask_input.bgeo.sc"
                mask_data.saveToFile(str(mask_path))
                mask_node=geo_obj.createNode("file","LOAD_MASK_"+role.upper())
                mask_node.parm("file").set(str(mask_path))
            material=geo_obj.createNode("PE_heightfield_material::1.0","MAT_"+role.upper())
            hda_definition=material.type().definition()
            if not hda_definition or Path(hda_definition.libraryFilePath()).resolve()!=HDA.resolve():
                raise ValueError("Not the pinned original SideFX HDA")
            material.setInput(0,previous)
            material.setInput(1,mask_node)
            params={
                **material_files[role],
                "size":size,"heightscale":0.0,"use_mask":int(use_mask),
                "srcname1":"mask","input2":"2",
                "use_distort":0,  # Diagnostic only; Grass author's Curl is not recreated here
            }
            material.setParms(params)
            material.cook(force=True)
            if material.errors():
                raise ValueError(f"Original SideFX HDA cook errors at {role}: {material.errors()}")
            cooked=material.geometry()
            # Clamp only measured native float32 interpolation in scratch;
            # preserve all stage2 source masks and original height bytes.
            repaired,hashes,height_rounding=restore_scratch_height(
                cooked,arrays,protected,hou,np,role)
            for channel in ("r","g","b"):
                if channel not in hashes:
                    raise ValueError(f"Original HDA missing RGB output at {role}")
            volumes=volume_by_name(repaired,hou)
            channels=[np.frombuffer(volumes[c].allVoxelsAsString(),dtype="<f4").reshape((SIZE,SIZE))
                      for c in ("r","g","b")]
            rgb=np.stack(channels,axis=-1)
            if not np.isfinite(rgb).all():
                raise ValueError(f"Invalid native material RGB at {role}")
            image=output/f"real-{role}-colour.png"
            save_png(image,rgb,np)
            cache=output/f"real-after-{role}.bgeo.sc"
            repaired.saveToFile(str(cache))
            if cache.stat().st_size>BINARY_LIMIT:
                raise ValueError("Native HDA emitted oversized real source fragment")
            opened=hou.Geometry()
            opened.loadFromFile(str(cache))
            if source_layer_hashes(opened,hou)!=hashes:
                raise ValueError(f"Reopened real material differs from cooked geometry at {role}")
            results.append({
                "role":role,"material":slug,
                "source_texture_hashes":{k:binding['houdini'][[t['role'] for t in binding['houdini']].index(role)]['files'][k]['sha256'] for k in ("diff","rough","disp")},
                "mask":mask_name,"mask_nonzero":count.get(mask_name,0) if mask_name else SIZE*SIZE,
                "mask_source":("HISTORICAL_STAGE3_GEOREGISTERED_UPSTREAM_UNVERIFIED" if role=="scree" and scree_token
                    else "STAGE2_ACCEPTED" if role not in ("rock","scree")
                    else "UNMASKED" if role=="rock" else "DIAGNOSTIC_CLIFF_PROXY_NOT_SCREE_STAGE3"),
                "heightscale_canary_override":0,"distortion_disabled_in_canary":True,
                "native_height_rounding":height_rounding,
                "size":size,"material_warnings":list(material.warnings()),
                "rgb_min":float(rgb.min()),"rgb_max":float(rgb.max()),
                "black_rgb_pixels":int(np.count_nonzero(np.all(rgb<=1e-6,axis=2))),
                "rgb_sha256_float32":hashlib.sha256(rgb.astype("<f4").tobytes()).hexdigest(),
                "preview_path":str(image),"preview_sha256":digest(image),
                "output_path":str(cache),"output_sha256":digest(cache),
                "native_reopen_equal":True,
                "base_height_alpha_masks_unchanged":True,
            })
            # Feed the REOPENED repaired scratch output, not the raw HDA
            # output, to guarantee immutable input heights for next stage.
            previous=geo_obj.createNode("file","LOAD_SAFE_"+role.upper())
            previous.parm("file").set(str(cache))
        return {
            "status":("FIVE_PEGASUS_CC0_REAL_STAGE3_DIAGNOSTIC_PASSED_NOT_PRODUCTION"
                if scree_token else "FIVE_PEGASUS_CC0_HDA_REAL_SITE_MECHANISM_PASSED_NOT_PRODUCTION"),
            "historical_real_stage3_diagnostic":real_scree_diagnostic,
            "stage3_upstream_lineage_accepted":False,
            "source_token":token,
            "real_source_provenance":provenance,
            "original_hda_sha256":PIN_HDA,
            "source_voxel_count":SIZE*SIZE,
            "source_layer_nonzero":count,
            "stages":results,
            "unsupported_in_this_canary":[
                ("Original Stage3 scree source is diagnostic with upstream lineage UNVERIFIED"
                    if scree_token else "Original Stage3 scree mask not connected"),
                "grass Curl distortion",
                "grass ramp and brightness tints", "cliff/scree/exposure/curvature final tint network",
                "HDA nonzero height displacement", "whole-area source material cook",
                "UE imported arrays, packed ORD(p), shader/render acceptance"],
            "ground_truth_height_and_stage2_masks_unchanged":True,
            "original_HDA_float32_rounding_corrected_only_in_disposable_crops":True,
            "native_original_height_restored_byte_exact_after_each_stage":True,
            "real_source_256x256":True,
            "whole_landscape_material_pass":False,
            "unreal_import":False,
            "production_entry_guards_bypassed":False,
        }
    finally:
        geo_obj.destroy()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-token",required=True)
    p.add_argument("--run-token",required=True)
    p.add_argument("--scree-token",default=None,help="Read-only verified historical Stage3 crop token; not production authority")
    args=p.parse_args()
    for t in (args.source_token,args.run_token,*([args.scree_token] if args.scree_token else [])):
        if not re.fullmatch(r"[0-9]{9,13}-[1-9][0-9]*",t):
            raise ValueError("Expected immutable numeric GitHub run/attempt token")
    if os.name=="nt":
        for path in (SOURCE_ROOT,CROP_ROOT,OUTPUT_ROOT):
            if not str(path).lower().replace("/","\\").startswith("d:\\yacs\\work\\"):
                raise ValueError("Material evidence must remain in external D work")
    import hou
    import numpy as np
    output=OUTPUT_ROOT/args.run_token
    result=run(hou,np,CROP_ROOT/args.source_token,SOURCE_ROOT,output,args.source_token,args.scree_token)
    report=output/"real-material-canary.json"
    report.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"source":result["source_token"],
        "stages":[{"role":s["role"],"coverage":s["mask_nonzero"],"black":s["black_rgb_pixels"]}
                  for s in result["stages"]],
        "receipt":str(report)}),flush=True)


if __name__=="__main__":
    main()

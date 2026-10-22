#!/usr/bin/env python3
"""Bounded material mechanism canary with ORIGINAL Pegasus HDA and approved CC0 maps.

A synthetic 256m heightfield only; no real world data, cache, or UE change.
This is not a production terrain cook or final video asset-identical replay.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

HDA_SHA256 = "e7d41ca64757699aa65b69520aca96b11f7325365506ddc675f8ea2b23a45023"
HDA_RELATIVE = "worldgen/houdini/sa_calobra/otls/sop_PE_heightfield_material.1.0.hda"
MAX_OUTPUT_BYTES = 64 * 1024**2


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_geometry(geometry, hou) -> dict:
    values = {}
    for primitive in geometry.prims():
        if not isinstance(primitive, hou.Volume):
            raise ValueError("Non-volume in Houdini canary output")
        name = primitive.attribValue("name")
        if name in values or not isinstance(name, str):
            raise ValueError("Duplicate or missing heightfield layer")
        x, y, z = primitive.resolution()
        if not 64 <= x <= 512 or not 64 <= y <= 512 or z != 1:
            raise ValueError(f"Canary exceeds safe volume resolution: {name}: {x}x{y}x{z}")
        raw = primitive.allVoxelsAsString()
        if len(raw) != x * y * 4:
            raise ValueError("Unexpected non-float32 canary voxels")
        values[name] = {
            "resolution": [x, y, z],
            "voxel_sha256": hashlib.sha256(raw).hexdigest(),
            "transform": list(primitive.transform().asTuple()),
            "position": list(primitive.vertex(0).point().position()),
            "raw_bytes": len(raw),
        }
    return values


def verify_canary_volumes(before: dict, after: dict) -> dict:
    if not {"height", "mask"}.issubset(before):
        raise ValueError("Synthetic source is not an expected heightfield")
    if not {"height", "mask", "r", "g", "b"}.issubset(after):
        raise ValueError("Pegasus material HDA did not generate RGB")
    for name, record in before.items():
        if after.get(name) != record:
            raise ValueError(f"Original HDA changed protected {name} layer")
    height_resolution = before["height"]["resolution"]
    if any(after[k]["resolution"] != height_resolution for k in ("r", "g", "b")):
        raise ValueError("HDA RGB resolution does not match the source")
    return {
        "protected_volume_names": sorted(before),
        "rgb_output_names": ["r", "g", "b"],
        "source_volume_identity_unchanged": True,
        "rgb_volume_voxel_sha256": {k: after[k]["voxel_sha256"] for k in ("r", "g", "b")},
    }


def approved_paths(binding: dict, root: Path) -> dict:
    if binding.get("status") != "SOURCE_BINDINGS_VERIFIED_NO_MATERIAL_IMPORT":
        raise ValueError("Only independently verified Poly Haven bindings are allowed")
    if binding.get("houdini_cook") is not False:
        raise ValueError("Source evidence must precede native material cook")
    rock = next((r for r in binding.get("houdini", []) if r["role"] == "rock"), None)
    if rock is None or rock["slug"] != "dark_rock":
        raise ValueError("Unexpected native canary material selection")
    files = rock["files"]
    output = {}
    for kind, parm in [("diff", "filename1"), ("rough", "filename2"), ("disp", "filename3")]:
        rec = files[kind]
        path = Path(rec["path"]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Material source outside authorized D work root")
        if not path.is_file() or digest(path) != rec["sha256"]:
            raise ValueError(f"Material source changed: {kind}")
        output[parm] = str(path)
    return output


def run_canary(hou, paths: dict, hda: Path, out: Path) -> dict:
    if hou.isUIAvailable():
        raise ValueError("Headless hython required; do not operate inside user Editor")
    if tuple(hou.applicationVersion()) != (22, 0, 466):
        raise ValueError("Exact Houdini 22.0.466 required")
    if hou.node("/obj").children():
        raise ValueError("Unexpected existing nodes in fresh headless Houdini")
    hou.hda.installFile(str(hda), force_use_assets=True)
    obj = hou.node("/obj").createNode("geo", "L07_CC0_CANARY")
    try:
        for child in obj.children():
            child.destroy()
        hf = obj.createNode("heightfield", "SYNTHETIC_HEIGHT")
        size = hf.parmTuple("size")
        if size is not None and len(size) == 2:
            size.set((256.0, 256.0))
        else:
            for name in ("sizex", "sizey"):
                if hf.parm(name) is not None:
                    hf.parm(name).set(256.0)
        spacing = hf.parm("gridspacing")
        if spacing is not None:
            spacing.set(1.0)
        hf.cook(force=True)
        before = inspect_geometry(hf.geometry(), hou)
        material = obj.createNode("PE_heightfield_material::1.0", "ORIGINAL_PEGASUS_MATERIAL")
        definition = material.type().definition()
        if definition is None or Path(definition.libraryFilePath()).resolve() != hda.resolve():
            raise ValueError("Wrong source HDA definition")
        material.setInput(0, hf)
        material.setInput(1, hf)
        # Mechanism test: zero displacement to protect synthetic height.
        # This is NOT the author's final Height Scale 10.
        parameters = {**paths, "size": 1000.0, "heightscale": 0.0,
                      "use_mask": 0, "srcname1": "mask", "input2": "2",
                      "use_distort": 0}
        material.setParms(parameters)
        if any(material.parm(k).evalAsString() != p for k, p in paths.items()):
            raise ValueError("HDA did not retain absolute texture paths")
        material.cook(force=True)
        if material.errors():
            raise ValueError(f"HDA cook errors: {material.errors()}")
        after = inspect_geometry(material.geometry(), hou)
        invariant = verify_canary_volumes(before, after)
        output = out / "original-hda-dark-rock-synthetic.bgeo.sc"
        material.geometry().saveToFile(str(output))
        if output.stat().st_size > MAX_OUTPUT_BYTES:
            output.unlink()
            raise ValueError("Oversized canary output")
        reopened = hou.Geometry()
        reopened.loadFromFile(str(output))
        if inspect_geometry(reopened, hou) != after:
            output.unlink()
            raise ValueError("Geometry changed during same-process native reopen")
        return {
            "status": "PEGASUS_ORIGINAL_HDA_CC0_CANARY_PASSED_NOT_PRODUCTION",
            "material": "dark_rock",
            "original_hda_sha256": digest(hda),
            "parameters": parameters,
            "scene": "SYNTHETIC_HEIGHTFIELD_ONLY",
            "source_lattice": before["height"]["resolution"],
            "output_bgeo": str(output),
            "output_size": output.stat().st_size,
            "output_sha256": digest(output),
            "heightfield_modified": False, "masks_modified": False,
            "canonical_world_touched": False, "unreal_import": False,
            "source_volume_invariants": invariant,
            "material_warnings": list(material.warnings()),
        }
    finally:
        obj.destroy()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-root", type=Path, required=True)
    ap.add_argument("--project-root", type=Path, required=True)
    ap.add_argument("--out-root", type=Path, required=True)
    ap.add_argument("--run-token", required=True)
    args = ap.parse_args()
    if not re.fullmatch(r"[0-9]{9,13}-[1-9][0-9]*", args.run_token):
        raise ValueError("Expected exact GitHub run-attempt token")
    root, project, out_root = (args.source_root.resolve(), args.project_root.resolve(), args.out_root.resolve())
    if os.name == "nt":
        if not str(root).lower().replace("/", "\\").startswith("d:\\yacs\\work\\"):
            raise ValueError("Wrong source root")
        if not str(out_root).lower().replace("/", "\\").startswith("d:\\yacs\\work\\"):
            raise ValueError("Wrong output root")
        if project != Path("D:/yacs/project").resolve():
            raise ValueError("Wrong canonical project root")
    import hou
    binding = json.loads((root / "bindings-v1.json").read_text(encoding="utf-8"))
    paths = approved_paths(binding, root)
    hda = project / HDA_RELATIVE
    if digest(hda) != HDA_SHA256:
        raise ValueError("Original Pegasus HDA hash mismatch")
    out = out_root / ("l07-cc0-hda-" + args.run_token)
    if out.exists():
        raise ValueError("Refuse overwrite of previous canary")
    out.mkdir(parents=True, exist_ok=False)
    receipt = run_canary(hou, paths, hda, out)
    (out / "canary.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "output": receipt["output_bgeo"],
                      "size": receipt["output_size"], "receipt": str(out / "canary.json")}))


if __name__ == "__main__":
    main()

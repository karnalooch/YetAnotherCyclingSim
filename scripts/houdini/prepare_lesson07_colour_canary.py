"""Bounded mechanism A/B test of the original Pegasus HDA mask switch.

Run with Houdini 22.0.466 hython in a fresh headless process, for example:
    $env:HOUDINI_OCL_DEVICETYPE = "CPU"
    $env:HOUDINI_COP_MAXRES = "32768"
    hython prepare_lesson07_colour_canary.py --run-token colour-20261022-a

This retained diagnostic uses YACS substitute colour and roughness inputs. It
does not reproduce the author's original material inputs or layer sequence
and is not the exact-Pegasus acceptance recipe.

This uses a retained 257x257 diagnostic crop, not the full terrain cache. It
simulates stage4a's colour-free input with the crop's final Grass layer and
existing geometry. It is a mechanism test, not a replay of all material stages
or a production global-colour replacement. Both outputs retain every original
non-RGB volume, including roughness, masks, height, Alpha and ID. No existing
HIP, cache, texture, Unreal asset or editor session is written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys


PROJECT = Path("D:/yacs/project")
WORLD = PROJECT / "worldgen/houdini/sa_calobra"
PREVIEW_ROOT = Path(
    "D:/yacs/work/lesson07-unified-20261019/preview_cache/"
    "340c7f8aa20e0d3e34b7a8416981eaa115eae4e4de025337c5e229e00d5ae775"
)
OUTPUT_ROOT = Path("D:/yacs/work/lesson07-colour-canary")
SOURCE_RECEIPT = (
    "docs/tooling/sidefx/lesson07-material-setup-verification-receipt.json"
    "#houdini_preview_verification.repair"
)
# These are two outputs of the *same* native 128 m crop. The alternate adds
# the original ID-to-layer decoder's generic mask; there is no auto-fallback.
CROP_PINS = {
    "SCREE_SITE_GLOBAL_COLOR": "058a52fdf717bc8ff5eb770101594c54f3f12e12a928efd67720205da50f59ac",
    "SCREE_FULLRES_PREVIEW": "5578cec56f5d215c7fa2e563ddc119a4412c927f251ba5ccae8b9b2d545a0f2b",
}
ASSET_PINS = {
    "hda": ("otls/sop_PE_heightfield_material.1.0.hda", 45649,
            "e7d41ca64757699aa65b69520aca96b11f7325365506ddc675f8ea2b23a45023"),
    "filename1": ("inputs/textures/SaCalobra_Grass_BaseColor.png", 98214149,
                  "719cffbc6f7cfec846cc2ba9610228dce5475cd2677f19f462bec6edc3e30ad9"),
    "filename2": ("inputs/textures/SaCalobra_Grass_Roughness.png", 74669799,
                  "5423503ba94f8e16ced4615cfa05893ec76b3df65cf85be9c8c07201efd5be90"),
    "filename3": ("inputs/textures/tlonbisya_4K_Displacement.exr", 49398483,
                  "e0e7c2ddcf6e3d98d91ffa3747a9234791ebf8aae52009bddc8ab9d740279b30"),
}
RECIPE_SHA256 = "d8026332c1abe42a3ab2e7428ce4335f9f69c2403bb1e2105164671a65202c37"
# Exact stage4a_grass values in the fingerprinted recipe; only use_mask varies.
MATERIAL_PARMS = {
    "size": 12.0, "heightscale": 0.0, "srcname1": "mask", "input2": "2",
    "use_distort": 1, "noisetype": "simplex", "amp": 3.5,
    "element_size": 15.0, "rough": 0.5, "maxoctave": 3,
}
RGB = frozenset(("r", "g", "b"))
REQUIRED = frozenset(("height", "Alpha", "id", "grass", "grass 2", "sand", "cliffs", "scree")) | RGB
RESOLUTION = (257, 257, 1)
MAX_CROP_BYTES = 64 * 1024**2


def reject_links(path: Path) -> None:
    """Do not follow links/junctions when selecting input or output files."""
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError(f"Linked path is not permitted: {item}")
        if item.exists():
            attributes = getattr(item.lstat(), "st_file_attributes", 0)
            if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                raise ValueError(f"Reparse path is not permitted: {item}")


def identity(path: Path, expected_sha: str | None = None,
             size: int | None = None, maximum: int | None = None) -> dict:
    reject_links(path)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size <= 0:
        raise ValueError(f"Expected a nonempty regular file: {path}")
    if size is not None and before.st_size != size:
        raise ValueError(f"Wrong pinned size: {path}")
    if maximum is not None and before.st_size > maximum:
        raise ValueError(f"File exceeds the bounded input size: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024**2), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(f"File changed while hashing: {path}")
    actual = digest.hexdigest()
    if expected_sha is not None and actual != expected_sha:
        raise ValueError(f"Pinned SHA256 mismatch: {path}")
    return {"path": str(path), "size_bytes": after.st_size, "sha256": actual}


def preflight(crop_name: str) -> dict:
    if crop_name not in CROP_PINS:
        raise ValueError("Only the two explicitly pinned 257x257 crops are supported")
    # Check the crop first. A missing crop cannot initiate a native cook or a
    # full-cache read, and does not silently select the other source.
    result = {"crop": identity(PREVIEW_ROOT / f"{crop_name}.bgeo.sc",
                               CROP_PINS[crop_name], maximum=MAX_CROP_BYTES)}
    for name, (relative, size, digest) in ASSET_PINS.items():
        result[name] = identity(WORLD / relative, digest, size=size)
    result["recipe"] = identity(Path(__file__).with_name("lesson06_unified_pipeline.py"),
                                 RECIPE_SHA256, maximum=256 * 1024)
    return result


def output_directory(run_token: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", run_token):
        raise ValueError("run-token must be 1-64 letters, digits, underscores or hyphens")
    target = OUTPUT_ROOT / run_token
    reject_links(target)
    if target.exists():
        raise ValueError(f"Refusing to overwrite an existing canary run: {target}")
    return target


def require_native_environment() -> None:
    # Hython can preload hou before executing this file. Assigning these inside
    # Python would therefore not establish the device selected at startup.
    required = {"HOUDINI_OCL_DEVICETYPE": "CPU", "HOUDINI_COP_MAXRES": "32768"}
    if any(os.environ.get(name) != value for name, value in required.items()):
        raise ValueError("Set HOUDINI_OCL_DEVICETYPE=CPU and HOUDINI_COP_MAXRES=32768 before launching hython")


def require_equal_layers(before: dict, after: dict, allowed: frozenset = RGB,
                         exact_names: bool = True) -> None:
    if exact_names and before.keys() != after.keys():
        raise ValueError("Volume layer names changed")
    for name, layer in before.items():
        if name in allowed and name in after and lattice(after[name]) != lattice(layer):
            raise ValueError(f"Volume lattice changed: {name}")
        if name not in allowed and after.get(name) != layer:
            raise ValueError(f"Protected volume changed: {name}")


def coverage_counts(alpha, masked, unmasked, np) -> dict:
    if masked.shape != unmasked.shape or masked.shape != (alpha.size, 3):
        raise ValueError("Coverage arrays have different voxel shapes")
    if not all(np.isfinite(a).all() for a in (alpha, masked, unmasked)):
        raise ValueError("Coverage contains nonfinite voxels")
    valid = alpha > 0
    old_black = np.all(masked == 0, axis=1)
    new_black = np.all(unmasked == 0, axis=1)
    return {
        "valid_voxels": int(np.count_nonzero(valid)),
        "masked_black_valid_voxels": int(np.count_nonzero(valid & old_black)),
        "unmasked_black_valid_voxels": int(np.count_nonzero(valid & new_black)),
        "black_valid_voxels_filled": int(np.count_nonzero(valid & old_black & ~new_black)),
        "new_black_valid_voxels": int(np.count_nonzero(valid & ~old_black & new_black)),
        "different_valid_rgb_voxels": int(np.count_nonzero(valid & np.any(masked != unmasked, axis=1))),
    }


def volume_state(geometry, hou, np):
    prims = geometry.prims()
    if not 1 <= len(prims) <= 32 or any(not isinstance(p, hou.Volume) for p in prims):
        raise ValueError("Expected at most 32 native scalar volumes in the pinned crop")
    states, arrays, volumes = {}, {}, {}
    for prim in prims:
        name = prim.attribValue("name")
        if not isinstance(name, str) or not name or name in states:
            raise ValueError("Expected unique named volume layers")
        if tuple(prim.resolution()) != RESOLUTION:
            raise ValueError(f"Unexpected crop resolution for {name}")
        data = prim.allVoxelsAsString()
        if len(data) != 257 * 257 * 4:
            raise ValueError(f"Expected scalar float32 voxels for {name}")
        array = np.frombuffer(data, dtype=np.float32)
        if not np.isfinite(array).all():
            raise ValueError(f"Nonfinite source/cooked voxels in {name}")
        states[name] = {
            "resolution": list(prim.resolution()),
            "transform": list(prim.transform().asTuple()),
            "position": list(prim.vertex(0).point().position()),
            "voxels_sha256": hashlib.sha256(data).hexdigest(),
        }
        arrays[name], volumes[name] = array, prim
    return states, arrays, volumes


def lattice(state: dict) -> dict:
    return {key: value for key, value in state.items() if key != "voxels_sha256"}


def cook_canary(inputs: dict, target: Path, report: dict) -> None:
    # Deliberately delayed until all pinned files and the output boundary pass.
    require_native_environment()
    import hou
    import numpy as np

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.ue.lesson06_memory_guard import require_headroom

    if hou.isUIAvailable() or tuple(hou.applicationVersion()) != (22, 0, 466):
        raise ValueError("Use a fresh headless Houdini 22.0.466 hython process")
    if hou.node("/obj").children():
        raise ValueError("Expected an empty fresh hython scene; existing HIPs are not loaded")
    report["memory_before"] = require_headroom()
    report["houdini_version"] = hou.applicationVersionString()
    hou.hda.installFile(inputs["hda"]["path"], force_use_assets=True)
    network = hou.node("/obj").createNode("geo", "LESSON07_COLOUR_CANARY")
    try:
        source = network.createNode("file", "PINNED_CROP")
        source.parm("file").set(inputs["crop"]["path"])
        source.cook(force=True)
        source_geo = source.geometry().freeze(read_only=True)
        before, original, _ = volume_state(source_geo, hou, np)
        if not REQUIRED.issubset(before):
            raise ValueError(f"Missing required source layers: {sorted(REQUIRED - before.keys())}")
        if any(lattice(layer) != lattice(before["height"]) for layer in before.values()):
            raise ValueError("Source layers do not share the exact height lattice")
        scree_count = int(np.count_nonzero(np.isclose(original["id"], 1.0, atol=1e-6, rtol=0)))
        if scree_count != 34 or not np.any(original["Alpha"] > 0):
            raise ValueError("Pinned crop does not reproduce its native class/validity receipt")
        report["source_layers"] = before
        report["source_scree_id_voxels"] = scree_count

        colour_free = network.createNode("blast", "REMOVE_COPIED_COLOUR")
        colour_free.setInput(0, source)
        colour_free.setParms({"group": "@name=r @name=g @name=b @name=roughness", "negate": 0})
        grass = network.createNode("blast", "RETAIN_COPIED_GRASS")
        grass.setInput(0, source)
        grass.setParms({"group": "@name=grass", "negate": 1})
        mask = network.createNode("heightfield_copylayer", "COPY_GRASS_TO_MASK")
        mask.setInput(0, grass)
        mask.setParms({"srcname1": "grass", "dstname1": "mask"})
        base_state, _, _ = volume_state(colour_free.geometry(), hou, np)
        if RGB.intersection(base_state) or "roughness" in base_state:
            raise ValueError("Base-stage colour-free input still contains RGB/roughness")
        require_equal_layers(before, base_state, RGB | {"roughness"}, exact_names=False)

        rgb_outputs = {}
        for use_mask, label in ((1, "masked"), (0, "unmasked")):
            report[f"memory_before_{label}"] = require_headroom()
            material = network.createNode("PE_heightfield_material::1.0", f"MAT_GRASS_{label.upper()}")
            definition = material.type().definition()
            if (material.type().name() != "PE_heightfield_material::1.0" or definition is None
                    or Path(definition.libraryFilePath()).resolve() != Path(inputs["hda"]["path"]).resolve()):
                raise ValueError("Material node did not select the pinned original HDA")
            material.setInput(0, colour_free)
            material.setInput(1, mask)
            parms = {**MATERIAL_PARMS, "use_mask": use_mask}
            parms.update({key: inputs[key]["path"] for key in ("filename1", "filename2", "filename3")})
            material.setParms(parms)
            material.cook(force=True)
            if material.errors():
                raise ValueError(f"Original material HDA failed: {material.errors()}")
            cooked, arrays, volumes = volume_state(material.geometry(), hou, np)
            if not RGB.issubset(cooked):
                raise ValueError("Original material HDA did not produce RGB")
            # HDA-local generic mask and roughness may change. Every retained
            # source mask and all spatial authority must survive even this cook.
            require_equal_layers(before, cooked, RGB | {"roughness", "mask"}, exact_names=False)
            if any(lattice(cooked[name]) != lattice(before[name]) for name in RGB):
                raise ValueError("Cooked RGB does not match the source lattice")
            rgb_outputs[label] = np.column_stack([arrays[name] for name in ("r", "g", "b")])

            # Copy only the native HDA's RGB voxel bytes into a deep copy of
            # the original crop. Do not publish its temporary mask/roughness.
            candidate = hou.Geometry(source_geo)
            _, _, copied_volumes = volume_state(candidate, hou, np)
            for name in RGB:
                copied_volumes[name].setAllVoxelsFromString(volumes[name].allVoxelsAsString())
            candidate.incrementAllDataIds()
            candidate_state, _, _ = volume_state(candidate, hou, np)
            require_equal_layers(before, candidate_state)
            destination = target / f"grass_base_{label}_rgb_only.bgeo.sc"
            candidate.saveToFile(str(destination))
            reopened = hou.Geometry()
            reopened.loadFromFile(str(destination))
            reopened_state, _, _ = volume_state(reopened, hou, np)
            if reopened_state != candidate_state:
                raise ValueError("Saved candidate changed during same-process BGEO reopen")
            require_equal_layers(before, reopened_state)
            report["outputs"][label] = {
                **identity(destination, maximum=MAX_CROP_BYTES),
                "use_mask": use_mask, "heightscale": 0.0,
                "non_rgb_layers_unchanged": True, "raw_hda_authority_layers_unchanged": True,
                "same_process_reopen_equal": True, "layers": reopened_state,
                "hda_warnings": list(material.warnings()),
            }
            material.destroy()
        report["coverage"] = coverage_counts(original["Alpha"], rgb_outputs["masked"],
                                              rgb_outputs["unmasked"], np)
        counts = report["coverage"]
        report["coverage_mechanism_demonstrated"] = (
            counts["black_valid_voxels_filled"] > 0 and counts["new_black_valid_voxels"] == 0
        )
    finally:
        network.destroy()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-token", required=True)
    parser.add_argument("--source-crop", choices=tuple(CROP_PINS), default="SCREE_SITE_GLOBAL_COLOR",
                        help="Explicit pinned crop selection; never falls back if it is missing")
    args = parser.parse_args(argv)
    target = output_directory(args.run_token)
    inputs = preflight(args.source_crop)
    require_native_environment()
    target.mkdir(parents=True, exist_ok=False)
    report = {
        "kind": "original_pegasus_base_colour_mask_ab_canary", "status": "FAILED",
        "source_receipt": SOURCE_RECEIPT, "source_crop_name": args.source_crop,
        "inputs": inputs, "outputs": {},
        "scope": "base-stage simulation on retained final crop; not full recipe replay",
        "production_colour_repaired": False, "fresh_process_output_reopen_verified": False,
    }
    error = None
    try:
        cook_canary(inputs, target, report)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    try:
        after = preflight(args.source_crop)
        if after != inputs:
            raise ValueError("Pinned source fingerprint changed during the canary")
        report["source_fingerprints_unchanged"] = True
    except Exception as exc:
        report["source_fingerprints_unchanged"] = False
        error = f"{error + '; ' if error else ''}{type(exc).__name__}: {exc}"
    if error:
        report["error"] = error
        code = 1
    else:
        demonstrated = report["coverage_mechanism_demonstrated"]
        report["status"] = "COVERAGE_MECHANISM_DEMONSTRATED" if demonstrated else "NO_COVERAGE_WITNESS"
        code = 0 if demonstrated else 2
    receipt = target / "canary.json"
    receipt.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "receipt": str(receipt),
                      "coverage": report.get("coverage"), "error": error}), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

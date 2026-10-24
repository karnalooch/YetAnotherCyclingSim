"""Derive bounded L07 Update Existing transport from the four saved native tiles.

No HIP load, SOP cook, resampling, terrain generation or UE operation occurs.
The default output contains visibility alone for the first owned native canary.
height-and-visibility retains every height float and volume transform, and asks
the UE caller to use the maximum observed actor Scale.Z on all four actors.

The original PE_Load_Landscape::2 uses Update Existing but keeps height only.
The already installed SaCalobra_Terrain_Transfer_v2 file->output adapter can
carry this visibility-only output through the same native Houdini translator.
References: https://www.sidefx.com/docs/houdini/unreal/landscape/basics.html
            https://www.sidefx.com/docs/houdini/hom/hou/Geometry.html
"""

import argparse
import hashlib
import json
from pathlib import Path

from compare_lesson07_consumer import (
    ACTORS, DEFAULT_MANIFEST, MANIFEST_SHA256, SOURCE_SHA256,
    sha256, validate_inputs,
)


EDIT_LAYER = "Houdini_Unified_Final"
HDA_ASSET = (
    "/Game/Worlds/SaCalobra_Houdini_20261016/Houdini/"
    "SaCalobra_Terrain_Transfer_v2.SaCalobra_Terrain_Transfer_v2"
)


def invert_validity(raw, expected_valid, expected_invalid):
    """Convert the pinned binary source validity to the UE hole-mask convention."""
    import numpy as np

    values = np.frombuffer(raw, dtype=np.float32)
    if not np.all((values == 0.0) | (values == 1.0)):
        raise ValueError("Source validity is not binary; no implicit normalization")
    valid = int(np.count_nonzero(values))
    invalid = int(values.size - valid)
    if (valid, invalid) != (expected_valid, expected_invalid):
        raise ValueError("Validity counts differ from the pinned native manifest")
    holes = np.subtract(np.float32(1.0), values, dtype=np.float32)
    return holes.tobytes(), {"visible_samples": valid, "hole_samples": invalid}


def volume_identity(volume):
    resolution = tuple(volume.resolution())
    return {
        "resolution": list(resolution),
        "transform": list(volume.transform().asTuple()),
        "position": list(volume.vertex(0).point().position()),
        "pos0": list(volume.indexToPos((0, 0, 0))),
        "pos_max": list(volume.indexToPos(tuple(n - 1 for n in resolution))),
        "float32_voxels_sha256": hashlib.sha256(volume.allVoxelsAsString()).hexdigest(),
    }


def named_volumes(geometry, hou, expected):
    volumes = {
        p.attribValue("name"): p for p in geometry.prims() if isinstance(p, hou.Volume)
    }
    if set(volumes) != expected or len(geometry.prims()) != len(expected):
        raise ValueError(f"Expected only {sorted(expected)}, got {sorted(volumes)}")
    return volumes


def apply_attributes(geometry, hou, actor):
    # Eliminate stale material, bake, scaling and other import side effects.
    removed = []
    for attributes in (
        geometry.globalAttribs(), geometry.primAttribs(),
        geometry.pointAttribs(), geometry.vertexAttribs(),
    ):
        for attribute in attributes:
            if attribute.name().startswith("unreal_") or attribute.name() in (
                "shop_materialpath", "material_override"
            ):
                removed.append(attribute.name())
                attribute.destroy()
    values = {
        "unreal_output_name": actor,
        "unreal_landscape_output_mode": 1,
        "unreal_landscape_editlayer_name": EDIT_LAYER,
        # Visibility + clear=1 clears HEIGHT in the installed translator!
        "unreal_landscape_editlayer_clear": 0,
        "unreal_landscape_section_size": 127,
        "unreal_landscape_sections_per_component": 2,
        "unreal_landscape_layer_normalize": 0,
    }
    for name, value in values.items():
        attr = geometry.addAttrib(hou.attribType.Prim, name, value)
        for primitive in geometry.prims():
            primitive.setAttribValue(attr, value)
    # The primitive attribute schema is shared by height and visibility.
    # Keep the old declared height range; only visibility receives 0..1.
    # Modify Existing actually quantizes height with the actor's Scale.Z.
    minimum = geometry.addAttrib(hou.attribType.Prim, "unreal_landscape_layer_min", 0.0)
    maximum = geometry.addAttrib(hou.attribType.Prim, "unreal_landscape_layer_max", 1.0)
    for primitive in geometry.prims():
        if primitive.attribValue("name") == "height":
            # Preserve the retained declared height range without claiming that
            # it controls Modify Existing scaling.
            primitive.setAttribValue(minimum, -5.0)
            primitive.setAttribValue(maximum, 1500.0)
        else:
            primitive.setAttribValue(minimum, 0.0)
            primitive.setAttribValue(maximum, 1.0)
    return sorted(set(removed)), values


def prepare(manifest_path, native_path, output_dir, mode, selected):
    manifest, native, actors = validate_inputs(manifest_path, native_path)
    if mode not in ("visibility-only", "height-and-visibility"):
        raise ValueError("Unsupported update mode")
    if not selected or not set(selected) <= ACTORS or len(set(selected)) != len(selected):
        raise ValueError("Select distinct existing L07 actors")
    if mode == "height-and-visibility" and set(selected) != ACTORS:
        raise ValueError("Common-Z height repair requires all four actors as one update")
    if native["native_seams"]["value"].get("height_samples_complete") is not True:
        raise ValueError("Complete native before-state required before preparing repair")
    common_scale_z = max(float(a["scale"][2]) for a in actors.values())
    if common_scale_z <= 0:
        raise ValueError("Invalid native Scale.Z")
    output_dir.mkdir(parents=False, exist_ok=False)
    result = {
        "schema_version": 1,
        "status": "DERIVED_TRANSPORT_READY_NATIVE_UPDATE_NOT_RUN",
        "mode": mode,
        "selected_actors": sorted(selected),
        "source_manifest": {"path": str(manifest_path), "sha256": MANIFEST_SHA256},
        "accepted_l06_sha256": SOURCE_SHA256,
        "native_before": {"path": str(native_path), "sha256": sha256(native_path)},
        "source_head": native["source_head"],
        "source_map": native["level"],
        "source_map_identity": native["map_before"],
        "hda_asset": HDA_ASSET,
        "hda_parameter": "terrain_cache",
        "hda_runtime_identity_verified": False,
        "target_edit_layer": EDIT_LAYER,
        "required_common_scale_z": common_scale_z if mode == "height-and-visibility" else None,
        "common_scale_basis": (
            "Maximum Scale.Z measured on the four original actors; same native "
            "16-bit conversion for matching source heights. Not a terrain amplitude standard."
        ),
        "native_actor_transforms_before": {
            name: {key: actor[key] for key in (
                "location_cm", "rotation_deg_pitch_yaw_roll", "scale"
            )} for name, actor in actors.items()
        },
        "required_native_update_contract": {
            "modify_existing_only": True,
            "landscape_use_temp_layers": False,
            "clear_edit_layer": False,
            "do_not_bake_all_outputs": True,
            "no_save_between_scale_change_and_all_height_updates": True,
            "material_assignment_unchanged": True,
            "preserve_actor_identity_layout_xy_and_source_caches": True,
        },
        "source_method": (
            "PEG-02-07 12:38-12:58 Update Existing; bounded YACS adaptation: "
            "cached native file->output transport, no new terrain or detail calculation."
        ),
        "geometry_accepted": False,
        "visibility_layer_proved_in_ue": False,
        "tiles": [],
    }
    import hou

    if tuple(hou.applicationVersion()) != (22, 0, 466):
        raise ValueError("Expected the reviewed Houdini 22.0.466")
    for tile in manifest["tiles"]:
        if tile["name"] not in selected:
            continue
        source = (manifest_path.parent / tile["file"]).resolve()
        if source.parent != manifest_path.parent.resolve() or sha256(source) != tile["sha256"]:
            raise ValueError(f"Source tile changed or escaped its directory: {source}")
        geometry = hou.Geometry()
        geometry.loadFromFile(str(source))
        try:
            layers = named_volumes(geometry, hou, {"height", "visibility"})
            height_before = volume_identity(layers["height"])
            visibility_before = volume_identity(layers["visibility"])
            if height_before["resolution"] != tile["resolution"]:
                raise ValueError("Height resolution differs from source manifest")
            if any(height_before[k] != visibility_before[k] for k in (
                "resolution", "transform", "position", "pos0", "pos_max"
            )):
                raise ValueError("Source height and validity have different registration")
            raw_holes, counts = invert_validity(
                layers["visibility"].allVoxelsAsString(),
                tile["visibility"]["valid_samples"], tile["visibility"]["invalid_samples"],
            )
            layers["visibility"].setAllVoxelsFromString(raw_holes)
            expected_hole_digest = hashlib.sha256(raw_holes).hexdigest()
            del raw_holes
            if mode == "visibility-only":
                geometry.deletePrims([layers["height"]])
            removed, attributes = apply_attributes(geometry, hou, tile["name"])
            if mode == "height-and-visibility":
                if volume_identity(layers["height"]) != height_before:
                    raise ValueError("Preparing visibility changed height or its transform")
            output = output_dir / (tile["name"] + ".bgeo.sc")
            geometry.saveToFile(str(output))
        finally:
            geometry.clear()

        # Authenticate the actual reopened transport, not just the in-memory edit.
        reopened = hou.Geometry()
        reopened.loadFromFile(str(output))
        try:
            expected = {"visibility"} | ({"height"} if mode == "height-and-visibility" else set())
            saved = named_volumes(reopened, hou, expected)
            visibility_after = volume_identity(saved["visibility"])
            if visibility_after["float32_voxels_sha256"] != expected_hole_digest:
                raise ValueError("Saved visibility differs from the prepared hole mask")
            if any(visibility_after[k] != visibility_before[k] for k in (
                "resolution", "transform", "position", "pos0", "pos_max"
            )):
                raise ValueError("Saved visibility registration changed")
            height_after = volume_identity(saved["height"]) if "height" in saved else None
            if height_after is not None and height_after != height_before:
                raise ValueError("Saved height floats or registration changed")
            for primitive in reopened.prims():
                for key, value in attributes.items():
                    if primitive.attribValue(key) != value:
                        raise ValueError(f"Saved update attribute changed: {key}")
            if any("material" in a.name() for a in reopened.primAttribs()):
                raise ValueError("Unexpected material assignment survived")
        finally:
            reopened.clear()
        if sha256(source) != tile["sha256"]:
            raise ValueError("Original tile changed during derivation")
        result["tiles"].append({
            "name": tile["name"], "file": output.name, "sha256": sha256(output),
            "bytes": output.stat().st_size,
            "source_file": str(source), "source_sha256": tile["sha256"],
            "source_unchanged": True,
            "height_source": height_before, "height_output": height_after,
            "height_float32_and_transform_unchanged": height_after == height_before if height_after else None,
            "visibility_source": visibility_before, "visibility_output": visibility_after,
            "visibility_polarity": "UE hole=1-source validity; visible=0, hole=1",
            **counts, "removed_unreal_attributes": removed,
            "update_attributes": attributes,
            "saved_reopen_verified": True,
        })
        print(f"Prepared and reopened {tile['name']}: {mode}", flush=True)
    with (output_dir / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--native-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("visibility-only", "height-and-visibility"),
                        default="visibility-only")
    parser.add_argument("--actor", action="append", choices=sorted(ACTORS))
    args = parser.parse_args()
    prepare(args.manifest.resolve(), args.native_report.resolve(),
            args.output_dir.resolve(), args.mode, args.actor or sorted(ACTORS))


if __name__ == "__main__":
    main()

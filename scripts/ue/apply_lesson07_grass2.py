"""Apply the validated Grass2 package to slot 1 of existing L07 arrays.

Run with UE's existing Python console. Does not load/save a level, launch an
editor, enable a listener, cook Houdini, or alter class masks/material graphs.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROOF = ROOT / "Saved/RuntimeProof/Lesson07Grass2-20261020-1"
PACKAGE = PROOF / "package"
BASE = "/Game/Generated/YACS/Lesson07_Unified"
LEVEL = BASE + "/L_SaCalobra_Lesson07.L_SaCalobra_Lesson07"
DESTINATION = BASE + "/Textures/Grass2_Limestone_V1"
CHANNELS = {"Colour": "Colour", "Normal": "Normal", "Masks": "Masks"}


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_package(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "grass2-package.json").read_text(encoding="utf-8"))
    if (manifest.get("family"), manifest.get("variant"), manifest.get("slot"), manifest.get("id_code")) != ("mediterranean_soil", "limestone_grass2_v1", 1, 64):
        raise ValueError("Package must target the existing Grass2 class and slot")
    if set(manifest["maps"]) != set(CHANNELS):
        raise ValueError("Exactly Colour, Normal and Masks are required")
    for channel, record in manifest["maps"].items():
        filename = record["file"]
        if filename != f"T_Grass2_{channel}.png":
            raise ValueError("Unexpected Grass2 file name")
        path = directory / filename
        if sha(path) != record["sha256"]:
            raise ValueError("Grass2 package file hash mismatch")
        with path.open("rb") as stream:
            header = stream.read(24)
        if header[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", header[16:24]) != (2048, 2048):
            raise ValueError("Grass2 textures must be 2048-square PNGs")
    return manifest


def landscape_snapshot(unreal, actors):
    def xyz(value):
        return [value.x, value.y, value.z]

    result = {}
    for actor in actors:
        if isinstance(actor, unreal.LandscapeProxy):
            rotation = actor.get_actor_rotation()
            result[actor.get_path_name()] = {
                "location": xyz(actor.get_actor_location()),
                "rotation": [rotation.pitch, rotation.yaw, rotation.roll],
                "scale": xyz(actor.get_actor_scale3d()),
                "material": actor.get_editor_property("landscape_material").get_path_name(),
            }
    return result


def main():
    import unreal

    project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
    if project != ROOT:
        raise RuntimeError("Active Unreal project differs from this script checkout; no writes performed")
    manifest = validate_package(PACKAGE)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name() != LEVEL:
        raise RuntimeError("Open the existing L_SaCalobra_Lesson07 map first; no map switch performed")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    before = landscape_snapshot(unreal, subsystem.get_all_level_actors())
    expected_names = {f"SaCalobra_Unified_{x}_{y}" for x in (0, 1) for y in (0, 1)}
    if {path.rsplit(".", 1)[-1] for path in before} != expected_names:
        raise RuntimeError("Unexpected Landscape inventory")
    if any(actor.get_editor_property("enable_nanite") for actor in subsystem.get_all_level_actors() if isinstance(actor, unreal.LandscapeProxy)):
        raise RuntimeError("Nanite Landscape requires separate displacement review; no writes performed")
    mi_path = BASE + "/Materials/MI_Landscape_Instance_YACS"
    if any(value["material"] != mi_path + ".MI_Landscape_Instance_YACS" for value in before.values()):
        raise RuntimeError("Landscape binding differs; no writes performed")
    arrays, originals, original_srgb = {}, {}, {}
    dirty = {package.get_path_name() for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
    instance = unreal.load_asset(mi_path)
    parent = instance.get_editor_property("parent")
    if parent.get_path_name() != BASE + "/Materials/M_Landscape_YACS.M_Landscape_YACS" or parent.get_editor_property("enable_tessellation"):
        raise RuntimeError("Unexpected or tessellated parent material; no writes performed")
    binding_names = {"Colour": "Colour Atlas", "Normal": "Normal Atlas", "Masks": "Masks Atlas"}
    classes = ["Grass", "Grass2", "Sand", "Cliffs", "Scree"]
    for channel in CHANNELS:
        asset = unreal.load_asset(BASE + f"/Materials/TA_{channel}_Unified")
        if not isinstance(asset, unreal.Texture2DArray):
            raise RuntimeError("Expected existing Texture2DArray")
        if asset.get_path_name().split(".", 1)[0] in dirty:
            raise RuntimeError("Existing array has unsaved edits; no writes performed")
        sources = list(asset.get_editor_property("source_textures"))
        if len(sources) != 5 or [value.get_name() for value in sources] != [f"T_{name}_{channel}" for name in classes]:
            raise RuntimeError("Unexpected five-class array source order")
        if unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(instance, binding_names[channel]) != asset:
            raise RuntimeError("Instance texture binding differs")
        arrays[channel], originals[channel] = asset, sources
        original_srgb[channel] = bool(asset.get_editor_property("srgb"))
    if unreal.EditorAssetLibrary.does_directory_exist(DESTINATION):
        raise RuntimeError("Grass2 candidate destination already exists; inspect previous receipt before retrying")
    backup = PROOF / "before-arrays"
    backup.mkdir(parents=True, exist_ok=False)
    backup_identities = {}
    for channel in CHANNELS:
        path = ROOT / f"Content/Generated/YACS/Lesson07_Unified/Materials/TA_{channel}_Unified.uasset"
        digest = sha(path)
        target = backup / path.name
        shutil.copy2(path, target)
        if sha(target) != digest:
            raise RuntimeError("Array disk backup failed")
        backup_identities[channel] = {"path": str(target), "sha256": digest}
    imported = {}
    touched = set()
    report = {"status": "IMPORT_STARTED", "world": LEVEL, "package": manifest,
              "map_saved": False, "terrain_rebuilt": False, "classification_changed": False,
              "editor_closed": False, "before": before, "array_backups": backup_identities,
              "render_verified": False, "fresh_reopen_verified": False}
    try:
        for channel in CHANNELS:
            task = unreal.AssetImportTask()
            task.filename = str(PACKAGE / manifest["maps"][channel]["file"])
            task.destination_path = DESTINATION
            task.destination_name = "T_Grass2_" + channel
            task.automated, task.replace_existing, task.save = True, False, False
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
            paths = list(task.get_editor_property("imported_object_paths"))
            if len(paths) != 1:
                raise RuntimeError("Grass2 texture import failed")
            texture = unreal.load_asset(paths[0])
            texture.set_editor_property("srgb", channel == "Colour")
            texture.set_editor_property("compression_settings", {
                "Colour": unreal.TextureCompressionSettings.TC_DEFAULT,
                "Normal": unreal.TextureCompressionSettings.TC_NORMALMAP,
                "Masks": unreal.TextureCompressionSettings.TC_MASKS,
            }[channel])
            for axis in ("address_x", "address_y"):
                texture.set_editor_property(axis, unreal.TextureAddress.TA_WRAP)
            if channel == "Normal":
                texture.set_editor_property("flip_green_channel", False)
            imported[channel] = texture
        with unreal.ScopedEditorTransaction("YACS L07 Grass2 olive limestone appearance"):
            for channel, asset in arrays.items():
                asset.modify()
                sources = list(originals[channel])
                sources[1] = imported[channel]
                touched.add(channel)
                asset.set_editor_property("source_textures", sources)
                asset.set_editor_property("srgb", channel == "Colour")
                actual = list(asset.get_editor_property("source_textures"))
                if actual != sources or any(actual[index] != originals[channel][index] for index in (0, 2, 3, 4)):
                    raise RuntimeError("Array source readback mismatch")
        after = landscape_snapshot(unreal, subsystem.get_all_level_actors())
        if after != before:
            raise RuntimeError("Landscape state unexpectedly changed")
        for asset in [*imported.values(), *arrays.values()]:
            if not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
                raise RuntimeError("Scoped material asset save failed")
        report.update(status="GRASS2_SLOT_REPLACED_SAVED_RENDER_REVIEW_PENDING", after=after,
                      changed_slot=1, other_four_slots_unchanged=True,
                      imported={key: value.get_path_name() for key, value in imported.items()},
                      array_sources={key: [value.get_path_name() for value in asset.get_editor_property("source_textures")]
                                     for key, asset in arrays.items()})
    except Exception as error:
        report.update(status="FAILED", error=str(error), rollback_errors=[])
        for channel in touched:
            asset = arrays[channel]
            try:
                asset.set_editor_property("source_textures", originals[channel])
                asset.set_editor_property("srgb", original_srgb[channel])
                if not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
                    raise RuntimeError("Original array rollback save failed")
            except Exception as rollback_error:
                report["rollback_errors"].append(str(rollback_error))
        raise
    finally:
        (PROOF / "live-import.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    unreal.log("YACS Grass2 replaced in shared arrays for all four existing Landscapes. Level not saved.")


if __name__ == "__main__":
    main()

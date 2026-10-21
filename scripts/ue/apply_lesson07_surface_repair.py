"""Import one pinned five-texture surface repair into the existing L07 arrays.

Execute this file once through the existing authenticated editor tool and its
normal safety review. It is a distinct material import, not the frozen observer.
The file must be staged in the canonical project's named runtime-proof folder.
No level, material instance, material graph, terrain or classification is saved.

API: Epic UE 5.8 UAssetImportTask; Texture2DArray.source_textures;
EditorAssetLibrary.save_loaded_asset. Native pattern: apply_lesson07_grass2.py.
"""
import hashlib
import json
import re
import shutil
import stat
import struct
from pathlib import Path


ROOT = Path("D:/yacs/project")
STAGING_ROOT = ROOT / "Saved/RuntimeProof/Lesson07SurfaceRepair-20261021"
EXPECTED_MANIFEST_SHA256 = "e8e0ae6cbd752b6b564a67b830aa16a5c4dbb01db3af9792963e8c6121bc88a6"
PACKAGE_ID = "lesson07-surface-repair-20261021"
BASE = "/Game/Generated/YACS/Lesson07_Unified"
LEVEL = BASE + "/L_SaCalobra_Lesson07.L_SaCalobra_Lesson07"
MI = BASE + "/Materials/MI_Landscape_Instance_YACS"
PARENT = BASE + "/Materials/M_Landscape_YACS.M_Landscape_YACS"
DESTINATION = BASE + "/Textures/SurfaceRepair_20261021"
CHANNELS = ("Colour", "Normal", "Masks")
CLASSES = ("Grass", "Grass2", "Sand", "Cliffs", "Scree")
MAPS = {
    "Grass_Normal": (0, "Normal", "slice_0_grass_normal.png"),
    "Grass_Masks": (0, "Masks", "slice_0_grass_masks.png"),
    "Cliffs_Colour": (3, "Colour", "slice_3_cliffs_colour.png"),
    "Cliffs_Normal": (3, "Normal", "slice_3_cliffs_normal.png"),
    "Cliffs_Masks": (3, "Masks", "slice_3_cliffs_masks.png"),
}
GRASS_HASHES = {
    "Grass_Normal": "6cfe99fee469d538d07f6770bcd10714bac5f59db904cb665f26f3fddcdfb239",
    "Grass_Masks": "bc9131bb40a06e00c14544785b873bce6430797c59eb3c7369b34fbaff318d1c",
}
ARRAY_PINS = {
    "Colour": (24178947, "9efed079b6fba9f1c900c4348b9dceabab785a6eadcaf0ea21a6fe8b775568cf"),
    "Normal": (40441798, "838a513e1c725e4e69da26715e6dff3734bfa2e98ef7d91a31278c2a0dbaf0f1"),
    "Masks": (12124066, "e34fb9b1a51d4251058b6cf3da66951f3abc26ac4a6ab1c25f9d348c6923c9e8"),
}
ARRAY_PROPERTIES = (
    "srgb", "compression_settings", "filter", "address_x", "address_y", "address_z",
    "flip_green_channel", "mip_gen_settings", "adjust_brightness",
    "adjust_brightness_curve", "adjust_saturation", "adjust_hue", "adjust_rgb_curve",
)
SUCCESS = "SURFACE_REPAIR_SAVED_NATIVE_READBACK_PENDING_VISUAL"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def plain_path(path, boundary):
    """Reject links and Windows reparse points, including parent directories."""
    path, boundary = Path(path).absolute(), Path(boundary).absolute()
    path.relative_to(boundary)
    for cursor in (path, *path.parents):
        info = cursor.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Redirected path is not admitted")
        if cursor == boundary:
            return path
    raise ValueError("Path boundary not reached")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate manifest key")
        result[key] = value
    return result


def validate_package(directory, expected_sha256):
    directory = Path(directory)
    manifest_path = plain_path(directory / "surface-repair-package.json", directory)
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("Manifest hash must be pinned before execution")
    if not 0 < manifest_path.stat().st_size <= 65536 or sha(manifest_path) != expected_sha256:
        raise ValueError("Surface manifest hash or size differs")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    if (manifest.get("schema_version"), manifest.get("package_id"), manifest.get("size"),
            manifest.get("normal_convention"), manifest.get("masks_channels")) != (
                1, PACKAGE_ID, [2048, 2048], "DirectX", {"R": "AO", "G": "Roughness", "B": "Height"}):
        raise ValueError("Surface package contract differs")
    if manifest.get("classification_changed") is not False or manifest.get("terrain_changed") is not False:
        raise ValueError("Surface import must preserve terrain and classification")
    if not isinstance(manifest.get("provenance"), dict) or not manifest["provenance"]:
        raise ValueError("Pinned source provenance is required")
    if set(manifest.get("maps", {})) != set(MAPS):
        raise ValueError("Exactly the five admitted maps are required")
    for name, (_, _, filename) in MAPS.items():
        record = manifest["maps"][name]
        if record.get("file") != filename:
            raise ValueError("Surface map filename differs")
        path = plain_path(directory / filename, directory)
        size = record.get("size_bytes")
        digest = record.get("sha256", "")
        if type(size) is not int or not 33 <= size <= 40 * 1024 * 1024:
            raise ValueError("Surface image size is not admitted")
        if path.stat().st_size != size or not re.fullmatch(r"[0-9a-f]{64}", digest) or sha(path) != digest:
            raise ValueError("Surface image hash or byte count differs")
        if name in GRASS_HASHES and digest != GRASS_HASHES[name]:
            raise ValueError("Grass source differs from the retained correction")
        with path.open("rb") as stream:
            header = stream.read(33)
        if (header[:8] != b"\x89PNG\r\n\x1a\n" or header[8:16] != b"\x00\x00\x00\rIHDR"
                or struct.unpack(">II", header[16:24]) != (2048, 2048)
                or header[24] != 8 or header[25] not in (2, 6) or header[26:29] != b"\0\0\0"):
            raise ValueError("Surface image must be noninterlaced RGB/RGBA 2K 8-bit PNG")
    return manifest


def stage_import_inputs(package, manifest):
    """Keep source bytes; give legacy and Interchange the same fixed asset names."""
    package = Path(package)
    if package.name != "package" or set(manifest.get("maps", {})) != set(MAPS):
        raise ValueError("Exactly the five staged package inputs are required")
    plain_path(package, package.parent)
    directory = package.parent / "import-inputs"
    if directory.exists() or directory.is_symlink():
        raise RuntimeError("Import input staging already exists; inspect the prior attempt")
    sources = {}
    for name, (_, _, filename) in MAPS.items():
        record = manifest["maps"][name]
        source = plain_path(package / filename, package)
        if record.get("file") != filename or (source.stat().st_size, sha(source)) != (
                record.get("size_bytes"), record.get("sha256")):
            raise ValueError("Import source hash, size or filename changed")
        sources[name] = source
    directory.mkdir(exist_ok=False)
    plain_path(directory, package.parent)
    result = {}
    for name, source in sources.items():
        target = directory / ("T_" + name + ".png")
        with source.open("rb") as incoming, target.open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
        record = manifest["maps"][name]
        expected = (record["size_bytes"], record["sha256"])
        if any((path.stat().st_size, sha(path)) != expected for path in (source, target)):
            raise RuntimeError("Import input copy differs from its pinned source")
        result[name] = target
    return result


def landscape_snapshot(unreal):
    def xyz(value):
        return [float(value.x), float(value.y), float(value.z)]

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    result = {}
    for actor in actors:
        if not isinstance(actor, unreal.LandscapeProxy):
            continue
        rotation = actor.get_actor_rotation()
        material = actor.get_editor_property("landscape_material")
        result[actor.get_path_name()] = {
            "location": xyz(actor.get_actor_location()), "scale": xyz(actor.get_actor_scale3d()),
            "rotation": [float(rotation.pitch), float(rotation.yaw), float(rotation.roll)],
            "material": material.get_path_name() if material else None,
            "nanite": bool(actor.get_editor_property("enable_nanite")),
            "components": len(actor.get_components_by_class(unreal.LandscapeComponent)),
        }
    return result


def expected_sources(channel):
    return [BASE + "/Textures/" + ("Grass2_Limestone_V1" if name == "Grass2" else "Slices")
            + f"/T_{name}_{channel}.T_{name}_{channel}" for name in CLASSES]


def array_path(channel):
    return BASE + f"/Materials/TA_{channel}_Unified"


def restore_properties(asset, settings):
    for name, value in settings.items():
        if asset.get_editor_property(name) != value:
            asset.set_editor_property(name, value)
    if any(asset.get_editor_property(name) != value for name, value in settings.items()):
        raise RuntimeError("Array setting readback differs")


def rollback_arrays(unreal, arrays, originals, settings, touched):
    errors = []
    for channel in reversed(touched):
        try:
            asset = arrays[channel]
            asset.set_editor_property("source_textures", originals[channel])
            restore_properties(asset, settings[channel])
            if list(asset.get_editor_property("source_textures")) != originals[channel]:
                raise RuntimeError("Rollback array source readback differs")
            if not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
                raise RuntimeError("Rollback scoped save failed")
        except Exception as error:
            errors.append({"channel": channel, "error": str(error)})
    return errors


def main():
    import unreal

    script = Path(__file__).absolute()
    staging = script.parent
    if staging.parent != STAGING_ROOT or not re.fullmatch(r"[1-9][0-9]{0,19}-[1-9][0-9]{0,4}", staging.name):
        raise RuntimeError("Importer must run from its named canonical proof staging")
    if script.name != "apply_lesson07_surface_repair.py":
        raise RuntimeError("Unexpected importer filename")
    plain_path(script, ROOT.parent.parent)
    package = plain_path(staging / "package", ROOT)
    manifest = validate_package(package, EXPECTED_MANIFEST_SHA256)
    report_path = staging / "live-import.json"
    if report_path.exists() or (staging / "before-arrays").exists():
        raise RuntimeError("This staged operation was already attempted; inspect its receipt")
    project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
    if project != ROOT or unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor():
        raise RuntimeError("Canonical idle editor project is required")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None or world.get_path_name() != LEVEL:
        raise RuntimeError("Exact existing Lesson07 world is required")
    before = landscape_snapshot(unreal)
    names = {f"SaCalobra_Unified_{x}_{y}" for x in (0, 1) for y in (0, 1)}
    if {path.rsplit(".", 1)[-1] for path in before} != names or len(before) != 4:
        raise RuntimeError("Exact four-Landscape inventory is required")
    if any(row["material"] != MI + ".MI_Landscape_Instance_YACS" or row["nanite"]
           or row["components"] != 1024 for row in before.values()):
        raise RuntimeError("Landscape binding, component count or Nanite state differs")
    dirty = {p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
    dirty_maps = {p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()}
    instance = unreal.load_asset(MI)
    if instance is None or instance.get_editor_property("parent").get_path_name() != PARENT:
        raise RuntimeError("Expected material parent is required")
    if instance.get_editor_property("parent").get_editor_property("enable_tessellation"):
        raise RuntimeError("Tessellated material is outside surface-import scope")
    scalar_names = ("Global Normal Flatten", "Macro Tiling")
    scalars = {name: unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(instance, name)
               for name in scalar_names}
    if abs(scalars["Global Normal Flatten"] - 1.0) > 1e-6 or abs(scalars["Macro Tiling"] - 0.05) > 1e-6:
        raise RuntimeError("Retained flatten and Macro checkpoint differs")
    arrays, originals, settings, disk_paths = {}, {}, {}, {}
    protected_packages = {MI, PARENT.split(".", 1)[0]}
    for channel in CHANNELS:
        asset = unreal.load_asset(array_path(channel))
        if not isinstance(asset, unreal.Texture2DArray):
            raise RuntimeError("Expected existing Texture2DArray")
        sources = list(asset.get_editor_property("source_textures"))
        if [value.get_path_name() if value else None for value in sources] != expected_sources(channel):
            raise RuntimeError("Existing five-class array order or source identity differs")
        if unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(instance, channel + " Atlas") != asset:
            raise RuntimeError("Expected atlas binding differs")
        arrays[channel], originals[channel] = asset, sources
        settings[channel] = {name: asset.get_editor_property(name) for name in ARRAY_PROPERTIES}
        if bool(settings[channel]["srgb"]) != (channel == "Colour"):
            raise RuntimeError("Existing array colour-space checkpoint differs")
        protected_packages.add(array_path(channel))
        protected_packages.update(value.get_path_name().split(".", 1)[0] for value in sources)
        disk = ROOT / f"Content/Generated/YACS/Lesson07_Unified/Materials/TA_{channel}_Unified.uasset"
        plain_path(disk, ROOT)
        if (disk.stat().st_size, sha(disk)) != ARRAY_PINS[channel]:
            raise RuntimeError("Existing array disk pin differs")
        disk_paths[channel] = disk
    if protected_packages & dirty:
        raise RuntimeError("An affected or source material package has unsaved edits")
    destination_disk = ROOT / "Content/Generated/YACS/Lesson07_Unified/Textures/SurfaceRepair_20261021"
    plain_path(destination_disk.parent, ROOT)
    if destination_disk.exists() or unreal.EditorAssetLibrary.does_directory_exist(DESTINATION):
        raise RuntimeError("Surface candidate destination already exists; inspect prior attempt")
    backup = staging / "before-arrays"
    backup.mkdir(exist_ok=False)
    backups = {}
    for channel, path in disk_paths.items():
        copied = backup / path.name
        shutil.copy2(path, copied)
        if (copied.stat().st_size, sha(copied)) != ARRAY_PINS[channel]:
            raise RuntimeError("Array disk backup differs")
        backups[channel] = {"file": copied.name, "size_bytes": copied.stat().st_size, "sha256": sha(copied)}
    report = {
        "status": "IMPORT_STARTED", "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "world": LEVEL, "before": before, "array_backups": backups, "saved": False,
        "classification_changed": False, "terrain_changed": False, "map_saved": False,
        "material_instance_changed": False, "normal_flatten_preserved": False,
        "visual_acceptance": False, "fresh_reopen_verified": False, "failure_count": 0,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    imported, touched = {}, []
    try:
        import_inputs = stage_import_inputs(package, manifest)
        report["import_inputs"] = {name: path.name for name, path in import_inputs.items()}
        for name, (_, channel, _) in MAPS.items():
            task = unreal.AssetImportTask()
            task.filename, task.destination_path = str(import_inputs[name]), DESTINATION
            task.destination_name = "T_" + name
            task.automated, task.replace_existing, task.save = True, False, False
            task.set_editor_property("async_", False)
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
            paths = list(task.get_editor_property("imported_object_paths"))
            expected = DESTINATION + "/T_" + name
            if len(paths) != 1 or paths[0] not in (expected, expected + ".T_" + name):
                raise RuntimeError("Imported object path differs from the admitted destination")
            texture = unreal.load_asset(paths[0])
            if not isinstance(texture, unreal.Texture2D):
                raise RuntimeError("Imported object is not Texture2D")
            properties = {
                "srgb": channel == "Colour", "address_x": unreal.TextureAddress.TA_WRAP,
                "address_y": unreal.TextureAddress.TA_WRAP,
                "compression_settings": {"Colour": unreal.TextureCompressionSettings.TC_DEFAULT,
                    "Normal": unreal.TextureCompressionSettings.TC_NORMALMAP,
                    "Masks": unreal.TextureCompressionSettings.TC_MASKS}[channel],
            }
            if channel == "Normal":
                properties["flip_green_channel"] = False
            for key, value in properties.items():
                texture.set_editor_property(key, value)
            if any(texture.get_editor_property(key) != value for key, value in properties.items()):
                raise RuntimeError("Imported texture settings did not persist")
            imported[name] = texture
        # Persist only the five new textures before creating references to them.
        for texture in imported.values():
            if not unreal.EditorAssetLibrary.save_loaded_asset(texture, only_if_is_dirty=False):
                raise RuntimeError("Scoped candidate texture save failed")
        with unreal.ScopedEditorTransaction("YACS L07 pinned Grass and Cliffs surface repair"):
            for channel, asset in arrays.items():
                sources = list(originals[channel])
                for name, (slot, selected_channel, _) in MAPS.items():
                    if selected_channel == channel:
                        sources[slot] = imported[name]
                asset.modify()
                touched.append(channel)
                asset.set_editor_property("source_textures", sources)
                restore_properties(asset, settings[channel])
                if list(asset.get_editor_property("source_textures")) != sources:
                    raise RuntimeError("Array source readback differs")
        after = landscape_snapshot(unreal)
        actual_scalars = {name: unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(instance, name)
                          for name in scalar_names}
        if after != before or actual_scalars != scalars:
            raise RuntimeError("Unrelated Landscape or material scalar state changed")
        if {p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()} != dirty_maps:
            raise RuntimeError("Map dirty state changed during material import")
        for asset in arrays.values():
            if not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
                raise RuntimeError("Scoped array save failed")
        report.update(status=SUCCESS, saved=True, after=after, changed_slots=[0, 3],
                      grass_colour_preserved=True, other_slots_preserved=[1, 2, 4],
                      normal_flatten_preserved=True, scalar_readback=actual_scalars,
                      imported={key: value.get_path_name() for key, value in imported.items()},
                      array_sources={key: [value.get_path_name() for value in asset.get_editor_property("source_textures")]
                                     for key, asset in arrays.items()},
                      saved_array_hashes={channel: sha(path) for channel, path in disk_paths.items()})
    except Exception as error:
        report.update(status="SURFACE_REPAIR_FAILED", failure_count=1, error=str(error),
                      rollback_errors=rollback_arrays(unreal, arrays, originals, settings, touched))
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("YACS_L07_SURFACE_IMPORT=" + json.dumps({key: report[key] for key in (
        "status", "saved", "changed_slots", "classification_changed", "terrain_changed",
        "normal_flatten_preserved", "failure_count", "manifest_sha256")}, separators=(",", ":")))


if __name__ == "__main__":
    main()

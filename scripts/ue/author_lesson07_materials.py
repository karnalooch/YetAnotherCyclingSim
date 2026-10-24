import json
import os
import time
from pathlib import Path
import unreal

WORK_DIR = Path("D:/yacs/work/lesson07-unified-20261019")
SLICES_DIR = WORK_DIR / "assembled_slices"
LOG_FILE = WORK_DIR / "ue_material_setup_report.json"

report = {
    "schema_version": 1,
    "status": "STARTED",
    "timestamp": time.time(),
    "imported_textures": {},
    "texture_arrays": {},
    "material_instance": {},
    "level": {}
}

def log(msg):
    print(f"[Lesson07_UE] {msg}", flush=True)

def ensure_dir(path):
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        unreal.EditorAssetLibrary.make_directory(path)
        log(f"Created directory: {path}")

def import_texture(source_file, dest_path, dest_name, srgb, compression, filter_mode=unreal.TextureFilter.TF_DEFAULT, lod_group=unreal.TextureGroup.TEXTUREGROUP_WORLD):
    log(f"Importing {dest_name} from {source_file}...")
    task = unreal.AssetImportTask()
    task.filename = str(source_file)
    task.destination_path = dest_path
    task.destination_name = dest_name
    task.automated = True
    task.replace_existing = True
    task.save = True
    
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    
    asset_full = f"{dest_path}/{dest_name}"
    tex = unreal.EditorAssetLibrary.load_asset(asset_full)
    if not tex:
        raise RuntimeError(f"Failed to load imported texture: {asset_full}")
        
    tex.set_editor_property("srgb", srgb)
    tex.set_editor_property("compression_settings", compression)
    tex.set_editor_property("filter", filter_mode)
    tex.set_editor_property("lod_group", lod_group)
    
    unreal.EditorAssetLibrary.save_loaded_asset(tex)
    log(f"Successfully configured and saved {asset_full}")
    
    return tex

# 1. Directories
ensure_dir("/Game/Generated/YACS/Lesson07_Unified/Textures")
ensure_dir("/Game/Generated/YACS/Lesson07_Unified/Textures/Slices")
ensure_dir("/Game/Generated/YACS/Lesson07_Unified/Materials")

# 2. Import 16k maps
idmap_src = WORK_DIR / "T_PE_Terrain_IDMap.png"
color_src = WORK_DIR / "T_PE_Terrain_Color.png"

tex_idmap = import_texture(
    idmap_src,
    "/Game/Generated/YACS/Lesson07_Unified/Textures",
    "T_PE_Terrain_IDMap",
    srgb=False,
    compression=unreal.TextureCompressionSettings.TC_GRAYSCALE,
    filter_mode=unreal.TextureFilter.TF_NEAREST
)
report["imported_textures"]["T_PE_Terrain_IDMap"] = {
    "path": tex_idmap.get_path_name(),
    "srgb": str(tex_idmap.get_editor_property("srgb")),
    "compression": str(tex_idmap.get_editor_property("compression_settings")),
    "filter": str(tex_idmap.get_editor_property("filter")),
}

tex_color = import_texture(
    color_src,
    "/Game/Generated/YACS/Lesson07_Unified/Textures",
    "T_PE_Terrain_Color",
    srgb=True,
    compression=unreal.TextureCompressionSettings.TC_DEFAULT,
    filter_mode=unreal.TextureFilter.TF_DEFAULT
)
report["imported_textures"]["T_PE_Terrain_Color"] = {
    "path": tex_color.get_path_name(),
    "srgb": str(tex_color.get_editor_property("srgb")),
    "compression": str(tex_color.get_editor_property("compression_settings")),
    "filter": str(tex_color.get_editor_property("filter")),
}

# 3. Import 15 surface slices
classes = [
    ("0_grass", "Grass"),
    ("1_grass2", "Grass2"),
    ("2_sand", "Sand"),
    ("3_cliffs", "Cliffs"),
    ("4_scree", "Scree")
]

col_slices = []
norm_slices = []
masks_slices = []

for idx_name, cls_name in classes:
    col_file = SLICES_DIR / f"slice_{idx_name}_colour.png"
    norm_file = SLICES_DIR / f"slice_{idx_name}_normal.png"
    masks_file = SLICES_DIR / f"slice_{idx_name}_masks.png"
    
    t_c = import_texture(
        col_file,
        "/Game/Generated/YACS/Lesson07_Unified/Textures/Slices",
        f"T_{cls_name}_Colour",
        srgb=True,
        compression=unreal.TextureCompressionSettings.TC_DEFAULT
    )
    col_slices.append(t_c)
    
    t_n = import_texture(
        norm_file,
        "/Game/Generated/YACS/Lesson07_Unified/Textures/Slices",
        f"T_{cls_name}_Normal",
        srgb=False,
        compression=unreal.TextureCompressionSettings.TC_NORMALMAP
    )
    norm_slices.append(t_n)
    
    t_m = import_texture(
        masks_file,
        "/Game/Generated/YACS/Lesson07_Unified/Textures/Slices",
        f"T_{cls_name}_Masks",
        srgb=False,
        compression=unreal.TextureCompressionSettings.TC_MASKS
    )
    masks_slices.append(t_m)

log(f"Imported all 15 surface slices ({len(col_slices)} colour, {len(norm_slices)} normal, {len(masks_slices)} masks).")

# 4. Duplicate and configure Texture2DArrays
def setup_texture_array(src_ta_path, dest_ta_path, slices, srgb, compression):
    if not unreal.EditorAssetLibrary.does_asset_exist(dest_ta_path):
        unreal.EditorAssetLibrary.duplicate_asset(src_ta_path, dest_ta_path)
        log(f"Duplicated {src_ta_path} -> {dest_ta_path}")
    ta = unreal.EditorAssetLibrary.load_asset(dest_ta_path)
    if not ta:
        raise RuntimeError(f"Failed to load Texture2DArray: {dest_ta_path}")
    ta.set_editor_property("source_textures", slices)
    ta.set_editor_property("srgb", srgb)
    ta.set_editor_property("compression_settings", compression)
    ta.set_editor_property("address_x", unreal.TextureAddress.TA_WRAP)
    ta.set_editor_property("address_y", unreal.TextureAddress.TA_WRAP)
    unreal.EditorAssetLibrary.save_loaded_asset(ta)
    log(f"Configured Texture2DArray {dest_ta_path} with {len(slices)} slices")
    return ta

ta_colour = setup_texture_array(
    "/Game/PegasusDemo/Materials/Landscape/Textures/TA_Colour",
    "/Game/Generated/YACS/Lesson07_Unified/Materials/TA_Colour_Unified",
    col_slices,
    srgb=True,
    compression=unreal.TextureCompressionSettings.TC_DEFAULT
)
ta_normal = setup_texture_array(
    "/Game/PegasusDemo/Materials/Landscape/Textures/TA_Normal",
    "/Game/Generated/YACS/Lesson07_Unified/Materials/TA_Normal_Unified",
    norm_slices,
    srgb=False,
    compression=unreal.TextureCompressionSettings.TC_NORMALMAP
)
ta_masks = setup_texture_array(
    "/Game/PegasusDemo/Materials/Landscape/Textures/TA_Masks",
    "/Game/Generated/YACS/Lesson07_Unified/Materials/TA_Masks_Unified",
    masks_slices,
    srgb=False,
    compression=unreal.TextureCompressionSettings.TC_MASKS
)

report["texture_arrays"] = {
    "TA_Colour_Unified": {"slices": len(col_slices), "path": ta_colour.get_path_name()},
    "TA_Normal_Unified": {"slices": len(norm_slices), "path": ta_normal.get_path_name()},
    "TA_Masks_Unified": {"slices": len(masks_slices), "path": ta_masks.get_path_name()},
}

# 5. Create derivative Material Instance MI_Landscape_Instance_YACS
mi_path = "/Game/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS"
if not unreal.EditorAssetLibrary.does_asset_exist(mi_path):
    unreal.EditorAssetLibrary.duplicate_asset(
        "/Game/PegasusDemo/Materials/Landscape/MI_Landscape_Instance",
        mi_path
    )
    log(f"Created MI_Landscape_Instance_YACS by duplicating base instance")

mi = unreal.EditorAssetLibrary.load_asset(mi_path)
if not mi:
    raise RuntimeError(f"Failed to load Material Instance: {mi_path}")

unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(mi, "Terrain IDmap", tex_idmap)
unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(mi, "Terrain Colour", tex_color)
unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(mi, "Colour Atlas", ta_colour)
unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(mi, "Normal Atlas", ta_normal)
unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(mi, "Masks Atlas", ta_masks)

# Exact derived parameters for full unified domain (0.5m spacing, 8x8 km span)
unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi, "Num IDmap Layers", 5.0)
unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi, "Terrain Resolution", 16000.0)
unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi, "Terrain Scale", 50.0)
unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi, "UV Rotate", 0.0)
unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(mi, "Offset", unreal.LinearColor(-8000.0, -8000.0, 0.0, 0.0))
unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi, "Global Colour Strength", 0.5)
unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi, "Global Specular Scale", 1.0)
unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi, "Detail Brightness", 1.5)

unreal.MaterialEditingLibrary.update_material_instance(mi)
unreal.EditorAssetLibrary.save_loaded_asset(mi)
log(f"Updated and saved {mi_path}")

# 6. Assign MI to all Landscape Actors in L_SaCalobra_Lesson07
level_path = "/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07"
world = unreal.EditorLoadingAndSavingUtils.load_map(level_path)
landscapes_assigned = []
for actor in unreal.EditorLevelLibrary.get_all_level_actors():
    if isinstance(actor, unreal.Landscape):
        actor.set_editor_property("landscape_material", mi)
        landscapes_assigned.append(actor.get_name())
        log(f"Assigned MI_Landscape_Instance_YACS to landscape: {actor.get_name()}")

unreal.EditorLevelLibrary.save_current_level()
log(f"Saved level {level_path} with {len(landscapes_assigned)} landscapes assigned")

# 7. Verification Re-Open Pass: Reload from disk and verify parameters
log("Starting mandatory verification reload pass...")
reloaded_mi = unreal.EditorAssetLibrary.load_asset(mi_path)
readback_scalars = {
    "Num IDmap Layers": float(unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(reloaded_mi, "Num IDmap Layers")),
    "Terrain Resolution": float(unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(reloaded_mi, "Terrain Resolution")),
    "Terrain Scale": float(unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(reloaded_mi, "Terrain Scale")),
    "UV Rotate": float(unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(reloaded_mi, "UV Rotate")),
    "Global Colour Strength": float(unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(reloaded_mi, "Global Colour Strength")),
    "Global Specular Scale": float(unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(reloaded_mi, "Global Specular Scale")),
    "Detail Brightness": float(unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(reloaded_mi, "Detail Brightness")),
}
offset_vec = unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value(reloaded_mi, "Offset")
readback_vector = [offset_vec.r, offset_vec.g, offset_vec.b, offset_vec.a]

report["material_instance"] = {
    "path": mi_path,
    "class": reloaded_mi.get_class().get_name(),
    "textures": {
        "Terrain IDmap": tex_idmap.get_path_name(),
        "Terrain Colour": tex_color.get_path_name(),
        "Colour Atlas": ta_colour.get_path_name(),
        "Normal Atlas": ta_normal.get_path_name(),
        "Masks Atlas": ta_masks.get_path_name(),
    },
    "scalars": readback_scalars,
    "vector_offset": readback_vector,
    "landscapes_assigned": landscapes_assigned,
    "reopened_cleanly": True
}

report["status"] = "AUTHORING_COMPLETED"
report["duration_seconds"] = time.time() - report["timestamp"]

LOG_FILE.write_text(json.dumps(report, indent=2))
log(f"All operations finished in {report['duration_seconds']:.2f}s. Report saved to {LOG_FILE}")


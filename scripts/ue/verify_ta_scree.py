import json
import unreal

report = {}

t_scree = unreal.EditorAssetLibrary.load_asset("/Game/Generated/YACS/Lesson07_Unified/Textures/Slices/T_Scree_Masks")
if not t_scree:
    raise RuntimeError("Failed to load T_Scree_Masks")

report["T_Scree_Masks"] = {
    "class": t_scree.get_class().get_name(),
    "srgb": bool(t_scree.get_editor_property("srgb")),
    "compression_settings": str(t_scree.get_editor_property("compression_settings")),
    "lod_group": str(t_scree.get_editor_property("lod_group")),
    "path": t_scree.get_path_name(),
}

ta_masks = unreal.EditorAssetLibrary.load_asset("/Game/Generated/YACS/Lesson07_Unified/Materials/TA_Masks_Unified")
if not ta_masks:
    raise RuntimeError("Failed to load TA_Masks_Unified")

sources = ta_masks.get_editor_property("source_textures")
report["TA_Masks_Unified"] = {
    "slice_count": len(sources),
    "slices": [s.get_path_name() if s else None for s in sources],
    "slice_4": sources[4].get_path_name() if len(sources) > 4 and sources[4] else None,
    "srgb": bool(ta_masks.get_editor_property("srgb")),
    "compression_settings": str(ta_masks.get_editor_property("compression_settings")),
}

# Ensure all 3 TAs are fully updated and saved
for name, is_srgb, comp in [
    ("TA_Masks_Unified", False, unreal.TextureCompressionSettings.TC_MASKS),
    ("TA_Colour_Unified", True, unreal.TextureCompressionSettings.TC_DEFAULT),
    ("TA_Normal_Unified", False, unreal.TextureCompressionSettings.TC_NORMALMAP),
]:
    ta = unreal.EditorAssetLibrary.load_asset(f"/Game/Generated/YACS/Lesson07_Unified/Materials/{name}")
    ta.set_editor_property("srgb", is_srgb)
    ta.set_editor_property("compression_settings", comp)
    ta.set_editor_property("address_x", unreal.TextureAddress.TA_WRAP)
    ta.set_editor_property("address_y", unreal.TextureAddress.TA_WRAP)
    unreal.EditorAssetLibrary.save_loaded_asset(ta)
    unreal.EditorLoadingAndSavingUtils.save_packages([ta.get_package()], only_dirty=False)

out_json = "D:/yacs/work/lesson07-unified-20261019/ta_scree_verification.json"
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)
print("Saved report to", out_json)

unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")

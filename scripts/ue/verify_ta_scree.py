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

# A verifier must never mutate or save native UE assets.
# Correct SourceTextures references are a necessary, but not sufficient,
# proof that the GPU/platform pixels were updated.
expected_scree = (
    "/Game/Generated/YACS/Lesson07_Unified/Textures/Slices/"
    "T_Scree_Masks.T_Scree_Masks"
)
if len(sources) != 5 or report["TA_Masks_Unified"]["slice_4"] != expected_scree:
    raise RuntimeError("Scree is not source texture 4 in the Masks atlas")
if report["TA_Masks_Unified"]["srgb"]:
    raise RuntimeError("Masks Texture2DArray must have sRGB disabled")
report["status"] = "SOURCE_REFERENCE_PASS_NATIVE_PIXEL_PROOF_PENDING"
report["platform_pixel_content_verified"] = False

out_json = "D:/yacs/work/lesson07-unified-20261019/ta_scree_verification.json"
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)
print("Saved report to", out_json)

unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")

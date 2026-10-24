"""Make the separate L07 Landscape hole material, only in an isolated UE project.

AUDIT is default. APPLY creates a new (never overwritten) BLEND_MASKED material
whose Opacity Mask input receives a LandscapeVisibilityMask expression.
This script must run through Unreal's embedded Python, never plain Python.
"""
import hashlib
import json
import os
from pathlib import Path

import unreal

ASSET_PATH = "/Game/Generated/YACS/Lesson07_Unified/Materials/M_L07_Visibility_Holes"
MODE = os.environ.get("YACS_L07_VISIBILITY_MATERIAL_MODE", "AUDIT")
OUT = Path(os.environ.get(
    "YACS_L07_VISIBILITY_MATERIAL_REPORT",
    "D:/yacs/work/l07-visibility-material-audit.json",
))
MAP_FILE = Path(os.environ.get(
    "YACS_L07_ISOLATED_UMAP_FILE",
    "D:/yacs/project/Content/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap",
))


def checksum(path):
    if not path.is_file():
        return None
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def validate(material):
    if not isinstance(material, unreal.Material):
        raise RuntimeError("Visibility holes must be a real Material, not a material instance")
    blend = material.get_editor_property("blend_mode")
    if blend != unreal.BlendMode.BLEND_MASKED:
        raise RuntimeError("Visibility holes Material is not BLEND_MASKED")
    linked = unreal.MaterialEditingLibrary.get_material_property_input_node(
        material, unreal.MaterialProperty.MP_OPACITY_MASK
    )
    if linked is None or linked.get_class().get_name() != "MaterialExpressionLandscapeVisibilityMask":
        raise RuntimeError("Missing direct LandscapeVisibilityMask to Opacity Mask link")
    return True


def main():
    if MODE not in ("AUDIT", "APPLY"):
        raise RuntimeError("Allowed modes: AUDIT or APPLY only")
    project_file = Path(unreal.Paths.get_project_file_path()).resolve()
    if MODE == "APPLY" and Path("D:/yacs/work").resolve() not in project_file.parents:
        raise RuntimeError("APPLY prohibited in canonical author project; stage isolated UE project")
    map_before = checksum(MAP_FILE)
    try:
        material = unreal.load_asset(ASSET_PATH)
        if material is not None:
            validate(material)
            status = "ALREADY_VALIDATED_MASKED_MATERIAL"
        elif MODE == "AUDIT":
            status = "MISSING_HOLE_MATERIAL_REQUIRES_ISOLATED_APPLY"
        else:
            package, name = ASSET_PATH.rsplit("/", 1)
            tools = unreal.AssetToolsHelpers.get_asset_tools()
            material = tools.create_asset(
                name, package, unreal.Material, unreal.MaterialFactoryNew()
            )
            if material is None:
                raise RuntimeError("Unreal AssetTools did not create Material")
            material.set_editor_property(
                "blend_mode", unreal.BlendMode.BLEND_MASKED
            )
            visibility = unreal.MaterialEditingLibrary.create_material_expression(
                material, unreal.MaterialExpressionLandscapeVisibilityMask, -450, 0
            )
            if visibility is None:
                raise RuntimeError("LandscapeVisibilityMask expression creation failed")
            connected = unreal.MaterialEditingLibrary.connect_material_property(
                visibility, "", unreal.MaterialProperty.MP_OPACITY_MASK
            )
            if not connected:
                raise RuntimeError("Could not link visibility node into Opacity Mask")
            unreal.MaterialEditingLibrary.recompile_material(material)
            validate(material)
            if not unreal.EditorAssetLibrary.save_loaded_asset(
                material, only_if_is_dirty=False
            ):
                raise RuntimeError("Failed to save isolated visibility-hole asset")
            status = "MASKED_HOLE_MATERIAL_CREATED_ISOLATED"
        result = {
            "status": status,
            "project": str(project_file),
            "asset": ASSET_PATH,
            "mode": MODE,
            "saved_world_before_sha256": map_before,
            "saved_world_after_sha256": checksum(MAP_FILE),
            "geometry_accepted": False,
            "landscape_visibility_validated_after_bake": False,
        }
        if result["saved_world_before_sha256"] != result["saved_world_after_sha256"]:
            raise RuntimeError("Existing L07 .umap changed during hole Material operation")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        unreal.log(f"[L07 hole material] {status}, world unchanged")
    finally:
        unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


if __name__ == "__main__":
    main()

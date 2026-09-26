"""
Stage 3G reference-environment material authoring. Idempotent.

Creates low-cost opaque materials under:
/Game/Prototype/Environment/Stage3G/Materials

The source actor falls back to the Stage 3F terrain material when these assets
have not been authored yet, so the C++ branch can build before this script is
run. The generated .uasset files must be committed through Git LFS after the
home-PC proof.
"""

import sys
import traceback
import unreal

PACKAGE = "/Game/Prototype/Environment/Stage3G/Materials"

MATERIALS = [
    ("Grass", (0.22, 0.36, 0.17), 0.95),
    ("Forest", (0.055, 0.16, 0.07), 0.96),
    ("Rock", (0.30, 0.31, 0.30), 0.92),
    ("DistantRock", (0.32, 0.39, 0.43), 0.96),
    ("Water", (0.035, 0.22, 0.30), 0.28),
]


def log(message):
    unreal.log("[Stage3G] {}".format(message))


def ensure_dir():
    if not unreal.EditorAssetLibrary.does_directory_exist(PACKAGE):
        unreal.EditorAssetLibrary.make_directory(PACKAGE)


def delete_if_exists(path):
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)


def save(asset):
    path = asset.get_path_name()
    if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
        raise RuntimeError("failed to save {}".format(path))


def create_parent(name, rgb, roughness):
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    parent_name = "M_Stage3G_{}".format(name)
    parent_path = "{}/{}".format(PACKAGE, parent_name)
    delete_if_exists(parent_path)

    mat = asset_tools.create_asset(
        parent_name, PACKAGE, unreal.Material, unreal.MaterialFactoryNew())
    if not mat:
        raise RuntimeError("failed to create {}".format(parent_name))

    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_SURFACE)
    mat.set_editor_property(
        "shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property("two_sided", False)
    mat.set_editor_property("bUsedWithInstancedStaticMeshes", True)

    color = unreal.MaterialEditingLibrary.create_material_expression(
        mat, unreal.MaterialExpressionVectorParameter, -300, 0)
    color.set_editor_property("parameter_name", "Color")
    color.set_editor_property(
        "default_value",
        unreal.LinearColor(float(rgb[0]), float(rgb[1]), float(rgb[2]), 1.0))
    color.set_editor_property("group", "Stage3G")

    rough = unreal.MaterialEditingLibrary.create_material_expression(
        mat, unreal.MaterialExpressionScalarParameter, -300, 160)
    rough.set_editor_property("parameter_name", "Roughness")
    rough.set_editor_property("default_value", float(roughness))
    rough.set_editor_property("group", "Stage3G")

    unreal.MaterialEditingLibrary.connect_material_property(
        color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    unreal.MaterialEditingLibrary.connect_material_property(
        rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    unreal.MaterialEditingLibrary.recompile_material(mat)
    save(mat)
    return mat


def create_instance(name, parent, rgb, roughness):
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    instance_name = "MI_Stage3G_{}".format(name)
    instance_path = "{}/{}".format(PACKAGE, instance_name)
    delete_if_exists(instance_path)

    mi = asset_tools.create_asset(
        instance_name,
        PACKAGE,
        unreal.MaterialInstanceConstant,
        unreal.MaterialInstanceConstantFactoryNew())
    if not mi:
        raise RuntimeError("failed to create {}".format(instance_name))

    unreal.MaterialEditingLibrary.set_material_instance_parent(mi, parent)
    unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
        mi,
        "Color",
        unreal.LinearColor(float(rgb[0]), float(rgb[1]), float(rgb[2]), 1.0))
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
        mi, "Roughness", float(roughness))
    unreal.MaterialEditingLibrary.update_material_instance(mi)
    save(mi)


def main():
    try:
        ensure_dir()

        # Delete instances before their parents so rerunning the authoring pass
        # cannot leave a parent asset referenced by an old material instance.
        for name, _, _ in MATERIALS:
            delete_if_exists("{}/MI_Stage3G_{}".format(PACKAGE, name))
        for name, _, _ in MATERIALS:
            delete_if_exists("{}/M_Stage3G_{}".format(PACKAGE, name))

        for name, rgb, roughness in MATERIALS:
            parent = create_parent(name, rgb, roughness)
            create_instance(name, parent, rgb, roughness)
        log("SUCCESS: authored {} Stage 3G material pairs".format(len(MATERIALS)))
    except Exception as exc:
        unreal.log_error("[Stage3G] FAILURE: {}".format(exc))
        unreal.log_error(traceback.format_exc())
        sys.exit(1)


main()

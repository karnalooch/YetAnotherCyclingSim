"""Stage 3G material authoring backed by the imported R1 source assets.

The Stage 3G R1 importer creates stable project-owned texture paths first.
This script then authors deterministic material pairs at the long-lived
Stage 3G material paths consumed by AStage3PrototypeTerrainActor.

Foliage remains an explicit placeholder in R1. Real conifer import/alpha/LOD
validation is a separate Stage 3G recovery tranche rather than being hidden in
this ground/rock slice.
"""

import sys
import traceback

import unreal


PACKAGE = "/Game/Prototype/Environment/Stage3G/Materials"
IMPORTED = "/Game/Prototype/Environment/Stage3G/Imported/Textures"

TEXTURED = {
    "Grass": {
        "diffuse": IMPORTED + "/T_Stage3G_Meadow_BaseColor",
        "normal": IMPORTED + "/T_Stage3G_Meadow_Normal",
        "roughness": IMPORTED + "/T_Stage3G_Meadow_Roughness",
        "tiling": 20.0,
    },
    "Forest": {
        "diffuse": IMPORTED + "/T_Stage3G_ForestGround_BaseColor",
        "normal": IMPORTED + "/T_Stage3G_ForestGround_Normal",
        "roughness": IMPORTED + "/T_Stage3G_ForestGround_Roughness",
        "tiling": 20.0,
    },
    "Rock": {
        "diffuse": IMPORTED + "/T_Stage3G_Boulder_BaseColor",
        "normal": IMPORTED + "/T_Stage3G_Boulder_Normal",
        "roughness": IMPORTED + "/T_Stage3G_Boulder_Roughness",
        "tiling": 3.0,
    },
    "DistantRock": {
        "diffuse": IMPORTED + "/T_Stage3G_HighAlpine_BaseColor",
        "normal": IMPORTED + "/T_Stage3G_HighAlpine_Normal",
        "roughness": IMPORTED + "/T_Stage3G_HighAlpine_Roughness",
        "tiling": 18.0,
    },
}

SOLID = {
    "Foliage": ((0.045, 0.13, 0.055), 0.96),
    "Water": ((0.035, 0.22, 0.30), 0.28),
}


def log(message):
    unreal.log("[Stage3G] {}".format(message))


def ensure_dir():
    if not unreal.EditorAssetLibrary.does_directory_exist(PACKAGE):
        if not unreal.EditorAssetLibrary.make_directory(PACKAGE):
            raise RuntimeError("failed to create {}".format(PACKAGE))


def delete_if_exists(path):
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        if not unreal.EditorAssetLibrary.delete_asset(path):
            raise RuntimeError("failed to delete {}".format(path))


def save(asset):
    path = asset.get_path_name()
    if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
        raise RuntimeError("failed to save {}".format(path))


def load_required(path):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if not asset:
        raise RuntimeError("required Stage 3G imported asset is missing: {}".format(path))
    return asset


def configure_material_base(mat):
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_SURFACE)
    mat.set_editor_property(
        "shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT
    )
    mat.set_editor_property("two_sided", False)
    mat.set_editor_property("bUsedWithInstancedStaticMeshes", True)


def create_instance(name, parent):
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    instance_name = "MI_Stage3G_{}".format(name)
    instance_path = "{}/{}".format(PACKAGE, instance_name)
    delete_if_exists(instance_path)

    mi = asset_tools.create_asset(
        instance_name,
        PACKAGE,
        unreal.MaterialInstanceConstant,
        unreal.MaterialInstanceConstantFactoryNew(),
    )
    if not mi:
        raise RuntimeError("failed to create {}".format(instance_name))

    unreal.MaterialEditingLibrary.set_material_instance_parent(mi, parent)
    unreal.MaterialEditingLibrary.update_material_instance(mi)
    save(mi)


def create_texture_sample(mat, texture, x, y, coordinate):
    sample = unreal.MaterialEditingLibrary.create_material_expression(
        mat, unreal.MaterialExpressionTextureSample, x, y
    )
    sample.set_editor_property("texture", texture)
    if coordinate is not None:
        # UE's Python bridge can expose the TextureSample Coordinates pin
        # without a stable display-name mapping. An empty input name is the
        # documented way to connect to the expression's first input, which for
        # UMaterialExpressionTextureSample is Coordinates.
        if not unreal.MaterialEditingLibrary.connect_material_expressions(
            coordinate, "", sample, ""
        ):
            raise RuntimeError("failed to connect Stage 3G texture coordinates")
    return sample


def create_textured_parent(name, spec):
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    parent_name = "M_Stage3G_{}".format(name)
    parent_path = "{}/{}".format(PACKAGE, parent_name)
    delete_if_exists(parent_path)

    mat = asset_tools.create_asset(
        parent_name, PACKAGE, unreal.Material, unreal.MaterialFactoryNew()
    )
    if not mat:
        raise RuntimeError("failed to create {}".format(parent_name))
    configure_material_base(mat)

    diffuse = load_required(spec["diffuse"])
    normal = load_required(spec["normal"])
    roughness = load_required(spec["roughness"])

    coordinate = unreal.MaterialEditingLibrary.create_material_expression(
        mat, unreal.MaterialExpressionTextureCoordinate, -700, 80
    )
    coordinate.set_editor_property("u_tiling", float(spec["tiling"]))
    coordinate.set_editor_property("v_tiling", float(spec["tiling"]))

    diffuse_sample = create_texture_sample(mat, diffuse, -450, -120, coordinate)
    normal_sample = create_texture_sample(mat, normal, -450, 60, coordinate)
    roughness_sample = create_texture_sample(mat, roughness, -450, 240, coordinate)

    if not unreal.MaterialEditingLibrary.connect_material_property(
        diffuse_sample, "RGB", unreal.MaterialProperty.MP_BASE_COLOR
    ):
        raise RuntimeError("failed to connect {} base color".format(name))
    if not unreal.MaterialEditingLibrary.connect_material_property(
        normal_sample, "RGB", unreal.MaterialProperty.MP_NORMAL
    ):
        raise RuntimeError("failed to connect {} normal".format(name))
    if not unreal.MaterialEditingLibrary.connect_material_property(
        roughness_sample, "R", unreal.MaterialProperty.MP_ROUGHNESS
    ):
        raise RuntimeError("failed to connect {} roughness".format(name))

    unreal.MaterialEditingLibrary.recompile_material(mat)
    save(mat)
    return mat


def create_solid_parent(name, rgb, roughness):
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    parent_name = "M_Stage3G_{}".format(name)
    parent_path = "{}/{}".format(PACKAGE, parent_name)
    delete_if_exists(parent_path)

    mat = asset_tools.create_asset(
        parent_name, PACKAGE, unreal.Material, unreal.MaterialFactoryNew()
    )
    if not mat:
        raise RuntimeError("failed to create {}".format(parent_name))
    configure_material_base(mat)

    color = unreal.MaterialEditingLibrary.create_material_expression(
        mat, unreal.MaterialExpressionVectorParameter, -300, 0
    )
    color.set_editor_property("parameter_name", "Color")
    color.set_editor_property(
        "default_value",
        unreal.LinearColor(float(rgb[0]), float(rgb[1]), float(rgb[2]), 1.0),
    )
    color.set_editor_property("group", "Stage3G")

    rough = unreal.MaterialEditingLibrary.create_material_expression(
        mat, unreal.MaterialExpressionScalarParameter, -300, 160
    )
    rough.set_editor_property("parameter_name", "Roughness")
    rough.set_editor_property("default_value", float(roughness))
    rough.set_editor_property("group", "Stage3G")

    unreal.MaterialEditingLibrary.connect_material_property(
        color, "", unreal.MaterialProperty.MP_BASE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        rough, "", unreal.MaterialProperty.MP_ROUGHNESS
    )
    unreal.MaterialEditingLibrary.recompile_material(mat)
    save(mat)
    return mat


def main():
    try:
        ensure_dir()

        names = list(TEXTURED.keys()) + list(SOLID.keys())
        for name in names:
            delete_if_exists("{}/MI_Stage3G_{}".format(PACKAGE, name))
        for name in names:
            delete_if_exists("{}/M_Stage3G_{}".format(PACKAGE, name))

        for name, spec in TEXTURED.items():
            parent = create_textured_parent(name, spec)
            create_instance(name, parent)

        for name, (rgb, roughness) in SOLID.items():
            parent = create_solid_parent(name, rgb, roughness)
            create_instance(name, parent)

        log(
            "SUCCESS: authored {} textured + {} solid Stage 3G material pairs".format(
                len(TEXTURED), len(SOLID)
            )
        )
    except Exception as exc:
        unreal.log_error("[Stage3G] FAILURE: {}".format(exc))
        unreal.log_error(traceback.format_exc())
        sys.exit(1)


main()

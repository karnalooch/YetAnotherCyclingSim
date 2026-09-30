"""
Stage 3F-B stylized material authoring. Idempotent.

Creates and persists the following uassets under
/Game/Prototype/Environment/Stage3F/Materials/:

    M_Stage3F_Road
    MI_Stage3F_Asphalt     (instance of M_Stage3F_Road)
    M_Stage3F_Edge
    MI_Stage3F_Edge        (instance of M_Stage3F_Edge)
    M_Stage3F_Terrain
    MI_Stage3F_Terrain     (instance of M_Stage3F_Terrain)

Design constraints:
    - Single BaseColor + Roughness constants per material. No expression
      graph complexity that is hostile to the office-PC editor renderer
      during 4 GB-VRAM PIE capture.
    - Edge lines for the road are NOT in the material (the road graph
      would be unreliable through the Python MaterialEditingLibrary in
      this baseline pass). They are added by AStage3PrototypeTerrainActor
      as a separate HISM of thin elongated cubes using M_Stage3F_Edge.

Run via:
    UnrealEditor-Cmd YetAnotherCyclingSim.uproject \
        -run=PythonScript -script="<abs>/stage3f_author_materials.py"
"""
import sys, traceback
import unreal


MATERIAL_PACKAGE = "/Game/Prototype/Environment/Stage3F/Materials"


def _log(msg):
    unreal.log("[Stage3F] {}".format(msg))


def _ensure_dir(asset_path):
    if not unreal.EditorAssetLibrary.does_directory_exist(asset_path):
        unreal.EditorAssetLibrary.make_directory(asset_path)
        _log("created directory {}".format(asset_path))


def _delete_if_exists(asset_name):
    full = "{}/{}".format(MATERIAL_PACKAGE, asset_name)
    if unreal.EditorAssetLibrary.does_asset_exist(full):
        unreal.EditorAssetLibrary.delete_asset(full)
        _log("deleted pre-existing {}".format(full))


def _save(asset):
    full = asset.get_path_name()
    saved = unreal.EditorAssetLibrary.save_asset(full, only_if_is_dirty=False)
    if not saved:
        raise RuntimeError("failed to save asset {}".format(full))
    _log("saved {}".format(full))


def _create_parent_material(name, base_rgb, roughness, edge_color=None):
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory = unreal.MaterialFactoryNew()
    mat = asset_tools.create_asset(
        name, MATERIAL_PACKAGE, unreal.Material, factory)
    if not mat:
        raise RuntimeError("failed to create material {}".format(name))

    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_SURFACE)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property("two_sided", False)
    # Required for HierarchicalInstancedStaticMeshComponent usage
    mat.set_editor_property("bUsedWithInstancedStaticMeshes", True)

    # Color parameter
    color_node = unreal.MaterialEditingLibrary.create_material_expression(
        mat, unreal.MaterialExpressionVectorParameter, -300, 0)
    color_node.set_editor_property("parameter_name", "Color")
    color_node.set_editor_property("default_value",
        unreal.LinearColor(float(base_rgb[0]), float(base_rgb[1]), float(base_rgb[2]), 1.0))
    color_node.set_editor_property("group", "Stage3F")

    # Roughness constant
    rough_node = unreal.MaterialEditingLibrary.create_material_expression(
        mat, unreal.MaterialExpressionScalarParameter, -300, 160)
    rough_node.set_editor_property("parameter_name", "Roughness")
    rough_node.set_editor_property("default_value", float(roughness))
    rough_node.set_editor_property("group", "Stage3F")

    unreal.MaterialEditingLibrary.connect_material_property(
        color_node, "", unreal.MaterialProperty.MP_BASE_COLOR)
    unreal.MaterialEditingLibrary.connect_material_property(
        rough_node, "", unreal.MaterialProperty.MP_ROUGHNESS)

    unreal.MaterialEditingLibrary.recompile_material(mat)
    _save(mat)
    return mat


def _create_instance(material_name, instance_name, parent_mat, **overrides):
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory = unreal.MaterialInstanceConstantFactoryNew()
    # Don't set parent on factory (protected). Create first, then set parent.
    mi = asset_tools.create_asset(
        instance_name, MATERIAL_PACKAGE, unreal.MaterialInstanceConstant, factory)
    if not mi:
        raise RuntimeError("failed to create material instance {}".format(instance_name))

    # Set parent after creation
    unreal.MaterialEditingLibrary.set_material_instance_parent(mi, parent_mat)

    for name, value in overrides.items():
        if isinstance(value, unreal.LinearColor):
            unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
                mi, name, value)
        elif isinstance(value, float):
            unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
                mi, name, value)

    unreal.MaterialEditingLibrary.update_material_instance(mi)
    _save(mi)
    return mi


def build_road():
    _delete_if_exists("MI_Stage3F_Asphalt")
    _delete_if_exists("M_Stage3F_Road")
    parent = _create_parent_material(
        "M_Stage3F_Road", (0.07, 0.07, 0.08), 0.85)
    _create_instance(
        "M_Stage3F_Road", "MI_Stage3F_Asphalt", parent,
        Color=unreal.LinearColor(0.07, 0.07, 0.08, 1.0),
        Roughness=0.85)


def build_edge():
    _delete_if_exists("MI_Stage3F_Edge")
    _delete_if_exists("M_Stage3F_Edge")
    parent = _create_parent_material(
        "M_Stage3F_Edge", (0.92, 0.92, 0.93), 0.70)
    _create_instance(
        "M_Stage3F_Edge", "MI_Stage3F_Edge", parent,
        Color=unreal.LinearColor(0.92, 0.92, 0.93, 1.0),
        Roughness=0.70)


def build_terrain():
    _delete_if_exists("MI_Stage3F_Terrain")
    _delete_if_exists("M_Stage3F_Terrain")
    parent = _create_parent_material(
        "M_Stage3F_Terrain", (0.34, 0.41, 0.27), 0.95)
    _create_instance(
        "M_Stage3F_Terrain", "MI_Stage3F_Terrain", parent,
        Color=unreal.LinearColor(0.34, 0.41, 0.27, 1.0),
        Roughness=0.95)


def main():
    try:
        _ensure_dir(MATERIAL_PACKAGE)
        build_road()
        build_edge()
        build_terrain()
        unreal.log("[Stage3F] SUCCESS: Stage 3F-B materials authored.")
    except Exception as exc:
        unreal.log_error("[Stage3F] FAILURE: {}".format(exc))
        unreal.log_error(traceback.format_exc())
        sys.exit(1)


main()

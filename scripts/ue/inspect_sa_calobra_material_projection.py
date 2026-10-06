"""Read installed projection graphs and the frozen material consumer without edits."""

import json
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
LIB = unreal.MaterialEditingLibrary


def inspect():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    expected = "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004"
    if world.get_path_name().split(".")[0] != expected:
        raise RuntimeError("Expected accepted map; no automatic map switching")
    functions = {}

    def visit(path):
        if path in functions:
            return
        asset = unreal.load_asset(path)
        if asset is None:
            raise RuntimeError("Missing installed function: " + path)
        rows = []
        functions[path] = rows
        for expression in LIB.get_material_function_expressions(asset):
            names = list(LIB.get_material_expression_input_names(expression))
            parents = LIB.get_inputs_for_material_function_expression(asset, expression)
            row = {
                "name": expression.get_name(),
                "class": expression.get_class().get_name(),
                "inputs": {
                    str(name): parent.get_name() if parent else None
                    for name, parent in zip(names, parents)
                },
                "outputs": list(LIB.get_material_expression_output_names(expression)),
            }
            for prop in (
                "input_name",
                "output_name",
                "description",
                "r",
                "g",
                "b",
                "a",
                "const_a",
                "const_b",
                "const_alpha",
                "value",
                "transform_source_type",
                "transform_type",
                "use_preview_value_as_default",
            ):
                try:
                    row[prop] = str(expression.get_editor_property(prop))
                except Exception:
                    pass
            if isinstance(expression, unreal.MaterialExpressionMaterialFunctionCall):
                child = expression.get_editor_property("material_function")
                if child:
                    row["function"] = child.get_path_name()
                    visit(child.get_path_name())
            rows.append(row)

    for name in ("WorldAlignedTexture", "WorldAlignedNormal"):
        visit("/Engine/Functions/Engine_MaterialFunctions01/Texturing/" + name)
    landscapes = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    consumers = []
    for landscape in landscapes:
        material = landscape.get_editor_property("landscape_material")
        consumers.append(
            {
                "actor": landscape.get_path_name(),
                "material": material.get_path_name() if material else None,
                "components": len(
                    landscape.get_components_by_class(unreal.LandscapeComponent)
                ),
                "tangent_space_normal": material.get_editor_property(
                    "tangent_space_normal"
                )
                if isinstance(material, unreal.Material)
                else None,
            }
        )
    position, rotation = editor.get_level_viewport_camera_info()
    result = {
        "engine": unreal.SystemLibrary.get_engine_version(),
        "world": world.get_path_name(),
        "consumers": consumers,
        "camera": {
            "position": [position.x, position.y, position.z],
            "rotation": [rotation.pitch, rotation.yaw, rotation.roll],
        },
        "native_audit_available": hasattr(
            unreal.YacsTextureAuditLibrary, "describe_landscape_material_instances"
        ),
        "functions": functions,
        "scene_changed": False,
    }
    out = ROOT / "Saved/RuntimeProof/MaterialRepair"
    out.mkdir(parents=True, exist_ok=True)
    (out / "native-projection.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    unreal.log("YACS_MATERIAL_REPAIR_INSPECTION_COMPLETE")
    return result


if __name__ == "__main__":
    inspect()

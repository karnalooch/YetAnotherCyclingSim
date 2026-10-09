"""Read-only inspection of the installed native projection functions."""

import json
from pathlib import Path
import unreal

LIB = unreal.MaterialEditingLibrary
rows = []
for name in (
    "Engine_MaterialFunctions01/Texturing/WorldAlignedTexture",
    "Engine_MaterialFunctions01/Texturing/WorldAlignedNormal",
    "Engine_MaterialFunctions02/Texturing/WorldAlignedTexture_Complex",
):
    asset = unreal.load_asset("/Engine/Functions/" + name)
    for node in LIB.get_material_function_expressions(asset):
        row = dict(
            function=name,
            node=node.get_name(),
            type=node.get_class().get_name(),
            inputs=list(LIB.get_material_expression_input_names(node)),
        )
        if isinstance(node, unreal.MaterialExpressionFunctionInput):
            row["input_name"] = str(node.get_editor_property("input_name"))
        rows.append(row)
Path(
    r"D:\yacs\project\Saved\RuntimeProof\MaskedMaterials\projection-inspection.json"
).write_text(json.dumps(rows, indent=2))

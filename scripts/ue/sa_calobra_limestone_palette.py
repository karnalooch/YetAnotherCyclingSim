"""Build isolated palette materials and apply the same correction to previews."""

import json
import uuid
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
LIB = unreal.MaterialEditingLibrary
PALETTE = ROOT / "worldgen/materials/sa_calobra_limestone_palette_20261005.json"


def apply_palette(material, settings):
    """Change only the final Base Color connection, in linear shader space."""
    color = unreal.MaterialProperty.MP_BASE_COLOR
    source = LIB.get_material_property_input_node(material, color)
    output = LIB.get_material_property_input_node_output_name(material, color)
    if source is None:
        raise RuntimeError("Source Base Color is not connected")
    preserved = {
        prop: (
            LIB.get_material_property_input_node(material, prop),
            LIB.get_material_property_input_node_output_name(material, prop),
        )
        for prop in (unreal.MaterialProperty.MP_NORMAL, unreal.MaterialProperty.MP_ROUGHNESS)
    }

    def node(cls, **props):
        value = LIB.create_material_expression(material, cls)
        if value is None:
            raise RuntimeError("Palette node creation failed")
        for key, setting in props.items():
            value.set_editor_property(key, setting)
        return value

    def link(a, pin, b, target):
        if not LIB.connect_material_expressions(a, pin, b, target):
            raise RuntimeError("Palette connection failed: " + target)

    desat = node(unreal.MaterialExpressionDesaturation)
    fraction = node(unreal.MaterialExpressionConstant, r=settings["desaturation"])
    link(source, output, desat, "")
    link(fraction, "", desat, "Fraction")
    gain = settings["linear_gain"]
    tint = node(
        unreal.MaterialExpressionConstant3Vector,
        constant=unreal.LinearColor(*(v * gain for v in settings["tint"]), 1),
    )
    multiply = node(unreal.MaterialExpressionMultiply)
    link(desat, "", multiply, "A")
    link(tint, "", multiply, "B")
    clamp = node(unreal.MaterialExpressionSaturate)
    link(multiply, "", clamp, "")
    if not LIB.connect_material_property(clamp, "", color):
        raise RuntimeError("Palette output failed")
    for prop, connection in preserved.items():
        if connection != (
            LIB.get_material_property_input_node(material, prop),
            LIB.get_material_property_input_node_output_name(material, prop),
        ):
            raise RuntimeError("Palette modified data-map shading")
    errors = LIB.recompile_material(material)
    if errors:
        raise RuntimeError("Palette compile errors: " + str(errors))


def main():
    settings = json.loads(PALETTE.read_text(encoding="utf-8"))
    receipt = ROOT / "Saved/RuntimeProof/LimestonePalette/materials.json"
    if receipt.exists():
        prior = json.loads(receipt.read_text(encoding="utf-8"))
        if prior["settings"] == settings and all(
            unreal.EditorAssetLibrary.does_asset_exist(path)
            for path in prior["materials"].values()
        ):
            return prior
    source = json.loads((ROOT / "Saved/RuntimeProof/TextureLibraries" /
                         settings["source_library"] / "result.json").read_text())
    if source["status"] != "generated_review_required" or len(source["items"]) != 7:
        raise RuntimeError("Complete provider-PBR source library required")
    package = source["library"] + "/LimestonePalette/" + uuid.uuid4().hex
    materials = {}
    # Source textures and materials are immutable; only new materials are saved.
    for row in source["items"]:
        role = row["role"]
        recipe = settings["roles"][role]
        if recipe["desaturation"] == 0 and recipe["linear_gain"] == 1:
            materials[role] = row["material"]
            continue
        target = unreal.EditorAssetLibrary.duplicate_asset(
            row["material"], package + "/M_SC_Limestone_" + role
        )
        if target is None:
            raise RuntimeError("Material clone failed: " + role)
        apply_palette(target, recipe)
        if not unreal.EditorAssetLibrary.save_loaded_asset(target, only_if_is_dirty=False):
            raise RuntimeError("Material save failed: " + role)
        materials[role] = target.get_path_name()
    result = {"status": "MATERIALS_PREPARED_VISUAL_REVIEW_REQUIRED",
              "settings": settings, "materials": materials,
              "map_saved": False, "world_assignment": False}
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    unreal.log("YACS_LIMESTONE_PALETTE " + json.dumps(result))
    return result


if __name__ == "__main__":
    main()

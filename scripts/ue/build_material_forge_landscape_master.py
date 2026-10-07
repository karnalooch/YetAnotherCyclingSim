"""Build the fixed Material Forge Landscape blend master once, without applying it.

This bootstrap proof intentionally isolates expensive MaterialEditingLibrary graph
construction in its own editor process. The resulting compiled master is saved
inside the disposable CI checkout and consumed by a fresh offscreen canary
process. No map, Landscape binding, geometry or world semantics are saved.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import unreal


ROOT = Path(__file__).resolve().parents[2]
LIB = unreal.MaterialEditingLibrary
MASTER_PACKAGE = "/Game/Generated/YACS/MaterialForge/Templates"
MASTER_NAME = "M_MaterialForgeLandscapeBlend"
MASTER_PATH = f"{MASTER_PACKAGE}/{MASTER_NAME}"
ORM_PLACEHOLDER_NAME = "T_MF_ORMPlaceholder"
ORM_PLACEHOLDER_PATH = f"{MASTER_PACKAGE}/{ORM_PLACEHOLDER_NAME}"
ORM_PLACEHOLDER_SOURCE = (
    "/Game/Prototype/Environment/Stage3G/Imported/Textures/"
    "T_Stage3G_HighAlpine_Roughness"
)

DEFAULTS = {
    "WeightTex": "/Game/Generated/YACS/SaCalobra/MaterialFoundation/T_Weights_312f9bdd499b",
    "SoilBaseColorTex": "/Game/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_Meadow_BaseColor",
    "SoilNormalTex": "/Game/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_Meadow_Normal",
    "RockBaseColorTex": "/Game/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_HighAlpine_BaseColor",
    "RockNormalTex": "/Game/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_HighAlpine_Normal",
}


def _load(path: str):
    value = unreal.load_asset(path)
    if value is None:
        raise RuntimeError("Fixed-master placeholder missing: " + path)
    return value


def _node(material, cls, **props):
    value = LIB.create_material_expression(material, cls)
    if value is None:
        raise RuntimeError("Material expression creation failed: " + cls.__name__)
    for prop, setting in props.items():
        value.set_editor_property(prop, setting)
    return value


def _link(source, output, target, pin):
    if not LIB.connect_material_expressions(source, output, target, pin):
        raise RuntimeError(f"Material connection failed: {output} -> {pin}")


def _output(source, output, prop):
    if not LIB.connect_material_property(source, output, prop):
        raise RuntimeError("Material output connection failed: " + str(prop))


def _texture_object(material, name, sampler, *, texture=None):
    return _node(
        material,
        unreal.MaterialExpressionTextureObjectParameter,
        texture=texture if texture is not None else _load(DEFAULTS[name]),
        sampler_type=sampler,
        parameter_name=name,
        group="Material Forge Landscape",
    )


def _create_orm_placeholder():
    if unreal.EditorAssetLibrary.does_asset_exist(ORM_PLACEHOLDER_PATH):
        raise RuntimeError("Fixed Material Forge ORM placeholder already exists")

    source = _load(ORM_PLACEHOLDER_SOURCE)
    placeholder = unreal.AssetToolsHelpers.get_asset_tools().duplicate_asset(
        ORM_PLACEHOLDER_NAME,
        MASTER_PACKAGE,
        source,
    )
    if placeholder is None:
        raise RuntimeError("Fixed Material Forge ORM placeholder duplication failed")

    placeholder.set_editor_property("srgb", False)
    placeholder.set_editor_property(
        "compression_settings",
        unreal.TextureCompressionSettings.TC_MASKS,
    )
    placeholder.set_editor_property("filter", unreal.TextureFilter.TF_BILINEAR)

    if not unreal.YacsTextureAuditLibrary.finish_texture_compilation([placeholder]):
        raise RuntimeError("Fixed Material Forge ORM placeholder compilation failed")
    if not unreal.EditorAssetLibrary.save_loaded_asset(
        placeholder,
        only_if_is_dirty=False,
    ):
        raise RuntimeError("Fixed Material Forge ORM placeholder save failed")
    return placeholder


def _project(material, texture, tile, *, normal=False):
    function = _load(
        "/Engine/Functions/Engine_MaterialFunctions01/Texturing/"
        + ("WorldAlignedNormal" if normal else "WorldAlignedTexture")
    )
    call = _node(material, unreal.MaterialExpressionMaterialFunctionCall)
    if not call.set_material_function(function):
        raise RuntimeError("Cannot bind native world-aligned material function")
    _link(texture, "", call, "TextureObject")
    _link(tile, "", call, "TextureSize")
    if normal:
        world_space = _node(material, unreal.MaterialExpressionStaticBool, value=False)
        _link(world_space, "", call, "WorldSpace")
    return call


def main() -> None:
    if unreal.EditorAssetLibrary.does_asset_exist(MASTER_PATH):
        raise RuntimeError("Fixed Material Forge master already exists in bootstrap checkout")

    orm_placeholder = _create_orm_placeholder()

    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        MASTER_NAME,
        MASTER_PACKAGE,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    if material is None:
        raise RuntimeError("Fixed Material Forge master creation failed")
    material.set_editor_property(
        "shading_model",
        unreal.MaterialShadingModel.MSM_DEFAULT_LIT,
    )

    world_position = _node(material, unreal.MaterialExpressionWorldPosition)
    xy = _node(
        material,
        unreal.MaterialExpressionComponentMask,
        r=True,
        g=True,
        b=False,
        a=False,
    )
    _link(world_position, "", xy, "")
    offset = _node(
        material,
        unreal.MaterialExpressionConstant2Vector,
        r=25.0,
        g=25.0,
    )
    add = _node(material, unreal.MaterialExpressionAdd)
    _link(xy, "", add, "A")
    _link(offset, "", add, "B")
    uv = _node(material, unreal.MaterialExpressionDivide, const_b=201650.0)
    _link(add, "", uv, "A")

    texel = 1.0 / 4033.0

    def rock_sample(dx: float, dy: float):
        coordinate = uv
        if dx or dy:
            delta = _node(
                material,
                unreal.MaterialExpressionConstant2Vector,
                r=dx,
                g=dy,
            )
            shifted = _node(material, unreal.MaterialExpressionAdd)
            _link(uv, "", shifted, "A")
            _link(delta, "", shifted, "B")
            coordinate = shifted
        sample = _node(
            material,
            unreal.MaterialExpressionTextureSampleParameter2D,
            texture=_load(DEFAULTS["WeightTex"]),
            sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR,
            parameter_name="WeightTex",
            group="Material Forge Landscape",
        )
        _link(coordinate, "", sample, "")
        blue = _node(
            material,
            unreal.MaterialExpressionComponentMask,
            r=False,
            g=False,
            b=True,
            a=False,
        )
        _link(sample, "RGBA", blue, "")
        return blue

    samples = [
        rock_sample(0.0, 0.0),
        rock_sample(texel, 0.0),
        rock_sample(-texel, 0.0),
        rock_sample(0.0, texel),
        rock_sample(0.0, -texel),
    ]
    weight_sum = samples[0]
    for sample in samples[1:]:
        addition = _node(material, unreal.MaterialExpressionAdd)
        _link(weight_sum, "", addition, "A")
        _link(sample, "", addition, "B")
        weight_sum = addition
    average = _node(material, unreal.MaterialExpressionMultiply, const_b=0.2)
    _link(weight_sum, "", average, "A")
    rock_weight = _node(material, unreal.MaterialExpressionSaturate)
    _link(average, "", rock_weight, "")
    soil_weight = _node(material, unreal.MaterialExpressionOneMinus)
    _link(rock_weight, "", soil_weight, "")

    projected = {}
    for key in ("rock", "soil"):
        prefix = "Rock" if key == "rock" else "Soil"
        tile = _node(
            material,
            unreal.MaterialExpressionScalarParameter,
            parameter_name=prefix + "TileSizeCm",
            group="Material Forge Landscape",
            default_value=400.0 if key == "rock" else 300.0,
        )
        macro_tile = _node(
            material,
            unreal.MaterialExpressionScalarParameter,
            parameter_name=prefix + "MacroTileSizeCm",
            group="Material Forge Landscape",
            default_value=2400.0 if key == "rock" else 1200.0,
        )
        macro_strength = _node(
            material,
            unreal.MaterialExpressionScalarParameter,
            parameter_name=prefix + "MacroStrength",
            group="Material Forge Landscape",
            default_value=0.0,
        )
        color_gain = _node(
            material,
            unreal.MaterialExpressionVectorParameter,
            parameter_name=prefix + "ColorGain",
            group="Material Forge Landscape",
            default_value=unreal.LinearColor(1.0, 1.0, 1.0, 1.0),
        )
        color_gain_rgb = _node(
            material,
            unreal.MaterialExpressionComponentMask,
            r=True,
            g=True,
            b=True,
            a=False,
        )
        _link(color_gain, "", color_gain_rgb, "")
        objects = {
            "BaseColor": _texture_object(
                material,
                prefix + "BaseColorTex",
                unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,
            ),
            "Normal": _texture_object(
                material,
                prefix + "NormalTex",
                unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,
            ),
            "ORM": _texture_object(
                material,
                prefix + "ORMTex",
                unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,
                texture=orm_placeholder,
            ),
            "Detail": _texture_object(
                material,
                prefix + "DetailTex",
                unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,
                texture=orm_placeholder,
            ),
        }
        base_color = _project(material, objects["BaseColor"], tile, normal=False)
        normal = _project(material, objects["Normal"], tile, normal=True)
        orm = _project(material, objects["ORM"], tile, normal=False)
        macro_detail = _project(material, objects["Detail"], macro_tile, normal=False)

        macro_b = _node(
            material,
            unreal.MaterialExpressionComponentMask,
            r=False,
            g=False,
            b=True,
            a=False,
        )
        _link(macro_detail, "XYZ Texture", macro_b, "")
        centered_macro = _node(
            material,
            unreal.MaterialExpressionSubtract,
            const_b=0.5,
        )
        _link(macro_b, "", centered_macro, "A")
        scaled_macro = _node(material, unreal.MaterialExpressionMultiply)
        _link(centered_macro, "", scaled_macro, "A")
        _link(macro_strength, "", scaled_macro, "B")
        macro_gain = _node(
            material,
            unreal.MaterialExpressionAdd,
            const_a=1.0,
        )
        _link(scaled_macro, "", macro_gain, "B")
        graded_base_color = _node(material, unreal.MaterialExpressionMultiply)
        _link(base_color, "XYZ Texture", graded_base_color, "A")
        _link(color_gain_rgb, "", graded_base_color, "B")
        macro_base_color = _node(material, unreal.MaterialExpressionMultiply)
        _link(graded_base_color, "", macro_base_color, "A")
        _link(macro_gain, "", macro_base_color, "B")

        roughness = _node(
            material,
            unreal.MaterialExpressionComponentMask,
            r=False,
            g=True,
            b=False,
            a=False,
        )
        _link(orm, "XYZ Texture", roughness, "")
        ao = _node(
            material,
            unreal.MaterialExpressionComponentMask,
            r=True,
            g=False,
            b=False,
            a=False,
        )
        _link(orm, "XYZ Texture", ao, "")
        projected[key] = {
            "BaseColor": (macro_base_color, ""),
            "Normal": (normal, "XYZ Texture"),
            "Roughness": (roughness, ""),
            "AO": (ao, ""),
        }

    def weighted(source, pin, weight):
        result = _node(material, unreal.MaterialExpressionMultiply)
        _link(source, pin, result, "A")
        _link(weight, "", result, "B")
        return result

    def blend(channel):
        rock = weighted(
            projected["rock"][channel][0],
            projected["rock"][channel][1],
            rock_weight,
        )
        soil = weighted(
            projected["soil"][channel][0],
            projected["soil"][channel][1],
            soil_weight,
        )
        result = _node(material, unreal.MaterialExpressionAdd)
        _link(rock, "", result, "A")
        _link(soil, "", result, "B")
        return result

    base_color = blend("BaseColor")
    roughness = blend("Roughness")
    ao = blend("AO")
    normal_sum = blend("Normal")
    normal = _node(material, unreal.MaterialExpressionNormalize)
    _link(normal_sum, "", normal, "")

    _output(base_color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    _output(roughness, "", unreal.MaterialProperty.MP_ROUGHNESS)
    _output(ao, "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    _output(normal, "", unreal.MaterialProperty.MP_NORMAL)

    errors = LIB.recompile_material(material)
    if errors:
        raise RuntimeError("Fixed Material Forge master compile failed: " + str(errors))
    LIB.layout_material_expressions(material)

    if not unreal.EditorAssetLibrary.save_loaded_asset(
        material,
        only_if_is_dirty=False,
    ):
        raise RuntimeError("Fixed Material Forge master save failed")

    asset_file = (
        ROOT
        / "Content/Generated/YACS/MaterialForge/Templates"
        / (MASTER_NAME + ".uasset")
    )
    if not asset_file.is_file():
        raise RuntimeError("Saved fixed Material Forge master file is missing")

    receipt = {
        "status": "MF_LANDSCAPE_FIXED_MASTER_SAVED",
        "master": MASTER_PATH,
        "sha256": hashlib.sha256(asset_file.read_bytes()).hexdigest(),
        "size_bytes": asset_file.stat().st_size,
        "texture_parameters": [
            "WeightTex",
            "RockBaseColorTex",
            "RockNormalTex",
            "RockORMTex",
            "RockDetailTex",
            "SoilBaseColorTex",
            "SoilNormalTex",
            "SoilORMTex",
            "SoilDetailTex",
        ],
        "scalar_parameters": [
            "RockTileSizeCm",
            "SoilTileSizeCm",
            "RockMacroTileSizeCm",
            "SoilMacroTileSizeCm",
            "RockMacroStrength",
            "SoilMacroStrength",
        ],
        "vector_parameters": [
            "RockColorGain",
            "SoilColorGain",
        ],
        "mask_contract": "five-tap B=rock; soil=1-rock",
        "projection": "WorldAlignedTexture + WorldAlignedNormal",
        "orm_placeholder": ORM_PLACEHOLDER_PATH,
        "orm_placeholder_compression": "TC_MASKS",
        "map_saved": False,
        "geometry_changed": False,
        "world_semantics_changed": False,
    }
    receipt_path = Path(os.environ["YACS_MF_TEMPLATE_RECEIPT"])
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    unreal.log("YACS_MF_FIXED_MASTER " + json.dumps(receipt))


if __name__ == "__main__":
    main()

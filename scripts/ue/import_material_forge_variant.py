"""Import one validated Material Forge variant into unsaved UE assets by default.

Environment:
- YACS_MATERIAL_FORGE_VARIANT_DIR: required variant directory.
- YACS_MATERIAL_FORGE_DESTINATION: optional /Game/... package root.
- YACS_MATERIAL_FORGE_SAVE=1: opt-in save. Default is transient/unsaved.

This importer never assigns world classification or Landscape masks.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

import unreal


ROOT = Path(__file__).resolve().parents[2]
LIB = unreal.MaterialEditingLibrary
DEFAULT_DESTINATION = "/Game/Generated/YACS/MaterialForge"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _require_variant(directory: Path):
    validation = _load_json(directory / "validation.json")
    provenance = _load_json(directory / "provenance.json")
    if validation.get("status") != "MAP_CHECKS_PASS_UE_REVIEW_PENDING":
        raise RuntimeError("Material Forge variant is not CPU-validated")
    if validation.get("semantic_owner") != "PCG/PCGEx":
        raise RuntimeError("Material Forge cannot own world semantics")
    if validation.get("world_semantics_generated") is not False:
        raise RuntimeError("Material Forge must not derive authoritative world semantics")
    if validation.get("normal_convention") != "DirectX":
        raise RuntimeError("UE import requires DirectX normals")
    return validation, provenance


def _verified_map(directory: Path, validation, channel: str) -> Path:
    entry = validation["maps"][channel]
    path = directory / entry["path"]
    if not path.resolve().is_relative_to(directory.resolve()):
        raise RuntimeError("Material Forge map escaped its variant directory")
    if _sha(path) != entry["sha256"]:
        raise RuntimeError("Material Forge map changed after validation: " + channel)
    return path


def _import_texture(package: str, name: str, path: Path, channel: str):
    task = unreal.AssetImportTask()
    for prop, value in {
        "filename": str(path),
        "destination_path": package,
        "destination_name": name,
        "automated": True,
        "replace_existing": False,
        "save": False,
    }.items():
        task.set_editor_property(prop, value)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported = task.get_editor_property("imported_object_paths")
    if len(imported) != 1:
        raise RuntimeError("Texture import failed: " + channel)
    texture = unreal.load_asset(imported[0])
    if texture is None:
        raise RuntimeError("Imported texture cannot be loaded: " + channel)
    texture.set_editor_property("srgb", channel == "BaseColor")
    compression = {
        "BaseColor": unreal.TextureCompressionSettings.TC_DEFAULT,
        "Normal_DX": unreal.TextureCompressionSettings.TC_NORMALMAP,
        "ORM": unreal.TextureCompressionSettings.TC_MASKS,
        "DetailMasks": unreal.TextureCompressionSettings.TC_MASKS,
    }[channel]
    texture.set_editor_property("compression_settings", compression)
    texture.set_editor_property("address_x", unreal.TextureAddress.TA_WRAP)
    texture.set_editor_property("address_y", unreal.TextureAddress.TA_WRAP)
    if channel == "Normal_DX":
        texture.set_editor_property("flip_green_channel", False)
    return texture


def _node(material, cls, **props):
    value = LIB.create_material_expression(material, cls)
    if value is None:
        raise RuntimeError("Material expression creation failed: " + cls.__name__)
    for prop, setting in props.items():
        value.set_editor_property(prop, setting)
    return value


def _link(a, pin, b, socket):
    if not LIB.connect_material_expressions(a, pin, b, socket):
        raise RuntimeError(f"Material connection failed: {pin} -> {socket}")


def _output(a, pin, prop):
    if not LIB.connect_material_property(a, pin, prop):
        raise RuntimeError("Material output connection failed: " + str(prop))


def _texture_parameter(material, texture, name: str, group: str):
    cls = getattr(unreal, "MaterialExpressionTextureObjectParameter", None)
    if cls is None:
        raise RuntimeError(
            "UE 5.8 MaterialExpressionTextureObjectParameter is unavailable in this build"
        )
    return _node(
        material,
        cls,
        texture=texture,
        sampler_type=(
            unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL
            if name == "NormalTex"
            else unreal.MaterialSamplerType.SAMPLERTYPE_MASKS
            if name in ("ORMTex", "DetailMasksTex")
            else unreal.MaterialSamplerType.SAMPLERTYPE_COLOR
        ),
        parameter_name=name,
        group=group,
    )


def _projection(material, texture_parameter, tile_size, normal=False):
    function = unreal.load_asset(
        "/Engine/Functions/Engine_MaterialFunctions01/Texturing/"
        + ("WorldAlignedNormal" if normal else "WorldAlignedTexture")
    )
    if function is None:
        raise RuntimeError("Required native WorldAligned material function is missing")
    call = _node(material, unreal.MaterialExpressionMaterialFunctionCall)
    if not call.set_material_function(function):
        raise RuntimeError("Cannot assign native WorldAligned material function")
    _link(texture_parameter, "", call, "TextureObject")
    _link(tile_size, "", call, "TextureSize")
    if normal:
        world_space = _node(material, unreal.MaterialExpressionStaticBool, value=False)
        _link(world_space, "", call, "WorldSpace")
    return call


def import_variant(
    directory: Path,
    destination_root: str = DEFAULT_DESTINATION,
    save_assets: bool = False,
):
    validation, provenance = _require_variant(directory)
    family = provenance["family"]
    variant = provenance["variant"]
    fingerprint = provenance["graph_sha256"][:12]
    suffix = fingerprint if save_assets else uuid.uuid4().hex[:12]
    package = f"{destination_root}/{family}/{variant}/{suffix}"

    textures = {}
    for channel in ("BaseColor", "Normal_DX", "ORM", "DetailMasks"):
        path = _verified_map(directory, validation, channel)
        textures[channel] = _import_texture(
            package,
            "T_MF_" + channel.replace("_", ""),
            path,
            channel,
        )

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    master = asset_tools.create_asset(
        "M_MaterialForge",
        package,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    if master is None:
        raise RuntimeError("Material Forge master creation failed")

    group = "Material Forge"
    base_tex = _texture_parameter(master, textures["BaseColor"], "BaseColorTex", group)
    normal_tex = _texture_parameter(master, textures["Normal_DX"], "NormalTex", group)
    orm_tex = _texture_parameter(master, textures["ORM"], "ORMTex", group)
    detail_tex = _texture_parameter(
        master, textures["DetailMasks"], "DetailMasksTex", group
    )
    tile = _node(
        master,
        unreal.MaterialExpressionScalarParameter,
        parameter_name="TileSizeCm",
        group=group,
        default_value=float(provenance["tile_metres"]) * 100.0,
    )

    base_projection = _projection(master, base_tex, tile, normal=False)
    normal_projection = _projection(master, normal_tex, tile, normal=True)
    orm_projection = _projection(master, orm_tex, tile, normal=False)
    detail_projection = _projection(master, detail_tex, tile, normal=False)

    _output(base_projection, "XYZ Texture", unreal.MaterialProperty.MP_BASE_COLOR)
    normalized = _node(master, unreal.MaterialExpressionNormalize)
    _link(normal_projection, "XYZ Texture", normalized, "")
    _output(normalized, "", unreal.MaterialProperty.MP_NORMAL)

    for component, prop in (
        ("R", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION),
        ("G", unreal.MaterialProperty.MP_ROUGHNESS),
    ):
        mask = _node(
            master,
            unreal.MaterialExpressionComponentMask,
            r=component == "R",
            g=component == "G",
            b=False,
            a=False,
        )
        _link(orm_projection, "XYZ Texture", mask, "")
        _output(mask, "", prop)

    detail_b = _node(
        master,
        unreal.MaterialExpressionComponentMask,
        r=False,
        g=False,
        b=True,
        a=False,
    )
    _link(detail_projection, "XYZ Texture", detail_b, "")
    zero = _node(master, unreal.MaterialExpressionConstant, r=0.0)
    no_op = _node(master, unreal.MaterialExpressionMultiply)
    _link(detail_b, "", no_op, "A")
    _link(zero, "", no_op, "B")
    _output(no_op, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    if LIB.recompile_material(master):
        raise RuntimeError("Material Forge master compilation reported failure")
    LIB.layout_material_expressions(master)

    factory = unreal.MaterialInstanceConstantFactoryNew()
    instance = asset_tools.create_asset(
        "MI_MaterialForge",
        package,
        unreal.MaterialInstanceConstant,
        factory,
    )
    if instance is None:
        raise RuntimeError("Material Forge instance creation failed")

    # UE 5.8 exposes parent assignment through MaterialEditingLibrary.
    # MaterialInstanceConstantFactoryNew.InitialParent exists in C++, but is
    # not exposed as an editor property in Python on the pinned 5.8 build.
    LIB.set_material_instance_parent(instance, master)

    params = {
        "BaseColorTex": textures["BaseColor"],
        "NormalTex": textures["Normal_DX"],
        "ORMTex": textures["ORM"],
        "DetailMasksTex": textures["DetailMasks"],
    }
    for name, texture in params.items():
        if not LIB.set_material_instance_texture_parameter_value(instance, name, texture):
            raise RuntimeError("Material instance parameter missing: " + name)
    if not LIB.set_material_instance_scalar_parameter_value(
        instance, "TileSizeCm", float(provenance["tile_metres"]) * 100.0
    ):
        raise RuntimeError("Material instance TileSizeCm parameter missing")
    LIB.update_material_instance(instance)

    assets = {
        "master": master.get_path_name(),
        "instance": instance.get_path_name(),
        "textures": {name: value.get_path_name() for name, value in textures.items()},
    }
    if save_assets:
        for path in [
            assets["master"],
            assets["instance"],
            *assets["textures"].values(),
        ]:
            if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
                raise RuntimeError("Failed to save Material Forge asset: " + path)

    receipt = {
        "status": "IMPORTED_UE_REVIEW_PENDING",
        "family": family,
        "variant": variant,
        "graph_sha256": provenance["graph_sha256"],
        "semantic_owner": "PCG/PCGEx",
        "world_semantics_generated": False,
        "normal_convention": "DirectX",
        "tile_metres": provenance["tile_metres"],
        "assets": assets,
        "saved": bool(save_assets),
        "landscape_mutated": False,
        "geometry_changed": False,
        "local_mask_channels": provenance["local_mask_channels"],
    }
    proof = ROOT / "Saved/RuntimeProof/MaterialForge"
    proof.mkdir(parents=True, exist_ok=True)
    receipt_path = proof / f"{family}-{variant}-{suffix}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    unreal.log("YACS_MATERIAL_FORGE_IMPORT " + json.dumps(receipt))
    return instance, receipt


def main():
    raw = os.environ.get("YACS_MATERIAL_FORGE_VARIANT_DIR")
    if not raw:
        raise RuntimeError("Set YACS_MATERIAL_FORGE_VARIANT_DIR to a validated variant")
    destination = os.environ.get(
        "YACS_MATERIAL_FORGE_DESTINATION", DEFAULT_DESTINATION
    )
    save_assets = os.environ.get("YACS_MATERIAL_FORGE_SAVE", "0") == "1"
    import_variant(Path(raw), destination, save_assets)


if __name__ == "__main__":
    main()

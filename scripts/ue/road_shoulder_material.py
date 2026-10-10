"""Create the bounded #364 gravel material; never assign geometry or save assets.

The caller owns whole-network triangle selection, slot assignment, rollback and
saved/fresh-rendered proof. This helper only consumes the three immutable,
already staged FillGravel textures. Its two new assets must be saved explicitly
by the caller; no import, source-texture edit, world edit or displacement occurs.

Native graph operations follow import_material_forge_variant.py and the pinned
UE 5.8.2 projection-function readback in native run 38078459124. Epic references:
https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Editor/MaterialEditor/UMaterialEditingLibrary
https://dev.epicgames.com/documentation/en-us/unreal-engine/texturing-material-functions-in-unreal-engine
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESTINATION_ROOT = "/Game/Generated/YACS/RoadAsphaltConsumer/ShoulderNetwork"
ENGINE_VERSION = "5.8.2-56702186+++UE5+Release-5.8"
LIBRARY = (
    "Content/Generated/YACS/TextureMaterialPrep/Libraries/"
    "3d53743e48394f31beb35e4030dc8a87/"
)
LEDGER = "worldgen/materials/sa_calobra_texture_library_v2_20261005.json"
TILE_SIZE_CM = 150.0
TEXTURES = {
    "BaseColorTex": "BaseColor",
    "NormalTex": "Normal_DX",
    "RoughnessTex": "Roughness",
}
# Package identities from authenticated baseline artifact 11679925399. Provider
# image identities/physical dimensions are retained in the authoritative ledger.
SOURCE_PINS = {
    "BaseColor": {
        "path": LIBRARY + "Sources/T_Source_FillGravel.uasset",
        "sha256": "a0c15b96a2b4f01c0d87429084f9d2b26f1ebc55876b60dfdcfb028511a1c0aa",
        "size_bytes": 834004,
    },
    "Normal_DX": {
        "path": LIBRARY + "ProviderData/FillGravel/T_Normal.uasset",
        "sha256": "e0e342641c0fd035f7a94f85daa60fae191293233014de4a89e0b370ec177fa7",
        "size_bytes": 6358514,
    },
    "Roughness": {
        "path": LIBRARY + "ProviderData/FillGravel/T_Roughness.uasset",
        "sha256": "51645d47b297415378c5a5539b3009dd2c8f180fa1f55271f02a808884183f56",
        "size_bytes": 3805695,
    },
}
SOURCE_MAP_SHA256 = {
    "BaseColor": "bec2573bc8aa9c714b690df753730e41f2077a1f0bbca83b13e055c86b4d5626",
    "Normal_DX": "d556cd8d0eae07d012a1c61fb1c485657528221c18069cf3deed631e32d2492f",
    "Roughness": "ad40a477eeb7cb226927fd4a02c979213a950d2e267b6ef27ac9bdfd6036759d",
}
PROJECTION_ROOT = "/Engine/Functions/Engine_MaterialFunctions01/Texturing/"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def asset_paths(destination_root):
    require(destination_root == DESTINATION_ROOT, "Unapproved shoulder material destination")
    return {
        role: destination_root + "/" + name + "." + name
        for role, name in (
            ("master", "M_ShoulderNetwork"),
            ("instance", "MI_ShoulderNetwork"),
        )
    }


def source_rows(source_dependencies):
    """Require the actual staged inventory, including unique exact pinned rows."""
    require(isinstance(source_dependencies, list) and 3 <= len(source_dependencies) <= 4096,
            "Shoulder source dependency inventory is missing or unbounded")
    indexed = {}
    for row in source_dependencies:
        require(isinstance(row, dict) and isinstance(row.get("path"), str)
                and row["path"] not in indexed, "Invalid or duplicate source dependency")
        indexed[row["path"]] = row
    for expected in SOURCE_PINS.values():
        actual = indexed.get(expected["path"])
        require(actual is not None
                and type(actual.get("size_bytes")) is int
                and all(actual.get(key) == value for key, value in expected.items()),
                "Pinned FillGravel source package changed: " + expected["path"])
    return {channel: dict(row) for channel, row in SOURCE_PINS.items()}


def _object_path(relative):
    package = "/Game/" + relative.removeprefix("Content/").removesuffix(".uasset")
    return package + "." + package.rsplit("/", 1)[-1]


def _validate_ledger(value):
    require(isinstance(value, dict) and isinstance(value.get("items"), list)
            and len(value["items"]) <= 32, "Shoulder source ledger is invalid")
    candidates = [row for row in value["items"]
                  if isinstance(row, dict) and row.get("role") == "FillGravel"]
    require(len(candidates) == 1, "Shoulder source ledger has no unique FillGravel role")
    row = candidates[0]
    require(row.get("source_id") == "rock_ground"
            and row.get("license") == "CC0-1.0"
            and row.get("source_url") == "https://polyhaven.com/a/rock_ground"
            and row.get("source_sha256") == SOURCE_MAP_SHA256["BaseColor"]
            and row.get("world_size_m") == [1.5, 1.5],
            "Shoulder source license, provider scale or identity changed")
    maps = row.get("pbr_maps")
    require(isinstance(maps, dict), "Shoulder provider PBR ledger is missing")
    for channel, expected in SOURCE_MAP_SHA256.items():
        source = maps.get("Normal" if channel == "Normal_DX" else channel)
        require(isinstance(source, dict) and source.get("asset") == "rock_ground"
                and source.get("sha256") == expected
                and source.get("provider_md5_verified") is True,
                "Shoulder provider channel ledger changed: " + channel)


def _authenticate_sources(api, source_dependencies):
    # Inert, existing bounded path/hash validators; no session or editor launch.
    from scripts.ci import official_mcp_bob_session as session

    require(session.ROOT.resolve() == ROOT.resolve(), "Shoulder source helper belongs to another checkout")
    project = Path(api.Paths.convert_relative_path_to_full(api.Paths.project_dir())).resolve()
    require(project == ROOT.resolve(), "Shoulder material authoring belongs to another project")
    require(api.SystemLibrary.get_engine_version() == ENGINE_VERSION,
            "Shoulder material requires the proved UE 5.8.2 build")
    ledger_path = session._safe_path(ROOT, LEDGER)
    ledger_identity = session._identity(ledger_path, 64 * 1024)
    _validate_ledger(session._read_json(
        ledger_path, (ledger_identity["sha256"], ledger_identity["size_bytes"])
    ))
    rows = source_rows(source_dependencies)
    for row in rows.values():
        path = session._safe_path(ROOT, row["path"])
        require(session._identity(path, 8 * 1024 * 1024) == {
            "sha256": row["sha256"], "size_bytes": row["size_bytes"]
        }, "Staged FillGravel package bytes changed: " + row["path"])
    textures = {}
    for channel, row in rows.items():
        path = _object_path(row["path"])
        texture = api.load_asset(path)
        require(texture is not None and isinstance(texture, api.Texture2D)
                and texture.get_path_name() == path,
                "Pinned FillGravel native texture is missing: " + channel)
        _verify_texture_settings(api, texture, channel)
        textures[channel] = texture
    return textures, rows


def _verify_texture_settings(api, texture, channel):
    """Inspect settings only: a mismatched source must never be silently repaired."""
    expected_compression = {
        "BaseColor": api.TextureCompressionSettings.TC_DEFAULT,
        "Normal_DX": api.TextureCompressionSettings.TC_NORMALMAP,
        "Roughness": api.TextureCompressionSettings.TC_MASKS,
    }[channel]
    require(texture.get_editor_property("srgb") is (channel == "BaseColor")
            and texture.get_editor_property("compression_settings") == expected_compression
            and texture.get_editor_property("address_x") == api.TextureAddress.TA_WRAP
            and texture.get_editor_property("address_y") == api.TextureAddress.TA_WRAP,
            "Pinned FillGravel color/data import settings differ: " + channel)
    if channel == "Normal_DX":
        require(texture.get_editor_property("flip_green_channel") is False,
                "Pinned FillGravel normal must retain DirectX green direction")


def _api_evidence(api):
    names = (
        "create_material_expression", "connect_material_expressions",
        "connect_material_property", "recompile_material",
        "set_material_instance_parent", "update_material_instance",
        "get_texture_parameter_names", "get_scalar_parameter_names",
        "get_material_instance_texture_parameter_value",
        "get_material_instance_scalar_parameter_value",
    )
    evidence = {}
    for name in names:
        method = getattr(api.MaterialEditingLibrary, name, None)
        require(callable(method), "Required native material API is missing: " + name)
        doc = str(getattr(method, "__doc__", "") or "")
        require(bool(doc) and len(doc) <= 32768,
                "Required native material API has no bounded signature: " + name)
        evidence[name] = {"signature": doc.splitlines()[0],
                          "doc_sha256": hashlib.sha256(doc.encode()).hexdigest()}
    for name in (
        "MaterialExpressionTextureObjectParameter", "MaterialExpressionScalarParameter",
        "MaterialExpressionMaterialFunctionCall", "MaterialExpressionStaticBool",
        "MaterialExpressionNormalize", "MaterialExpressionComponentMask",
        "MaterialExpressionConstant", "MaterialFactoryNew", "MaterialInstanceConstantFactoryNew",
    ):
        require(callable(getattr(api, name, None)), "Required native material class is missing: " + name)
    return evidence


def _verify_instance(api, instance, master_path, texture_objects):
    require(instance is not None and isinstance(instance, api.MaterialInstanceConstant),
            "Shoulder material instance is missing")
    parent = instance.get_editor_property("parent")
    require(parent is not None and isinstance(parent, api.Material)
            and parent.get_path_name() == master_path,
            "Shoulder material parent differs")
    require(parent.get_editor_property("tangent_space_normal") is True,
            "Shoulder master no longer consumes tangent-space projected normals")
    lib = api.MaterialEditingLibrary
    association = api.MaterialParameterAssociation.GLOBAL_PARAMETER
    require({str(name) for name in lib.get_texture_parameter_names(instance)} == set(TEXTURES)
            and {str(name) for name in lib.get_scalar_parameter_names(instance)} == {"TileSizeCm"},
            "Shoulder material parameter inventory differs")
    tile = float(lib.get_material_instance_scalar_parameter_value(instance, "TileSizeCm", association))
    require(math.isfinite(tile) and abs(tile - TILE_SIZE_CM) <= 0.001,
            "Shoulder texture projection is not the provider's 150 cm tile")
    for parameter, channel in TEXTURES.items():
        texture = lib.get_material_instance_texture_parameter_value(instance, parameter, association)
        require(texture is not None and texture.get_path_name() == texture_objects[channel],
                "Shoulder material texture parameter changed: " + parameter)
        _verify_texture_settings(api, texture, channel)
    return instance


def create_material(api, destination_root, source_dependencies):
    """Create two unsaved assets; return (instance, receipt), without assignment."""
    paths = asset_paths(destination_root)
    textures, sources = _authenticate_sources(api, source_dependencies)
    evidence = _api_evidence(api)
    require(all(not api.EditorAssetLibrary.does_asset_exist(path) for path in paths.values()),
            "Shoulder material assets already exist; refuse overwrite")
    lib = api.MaterialEditingLibrary
    tools = api.AssetToolsHelpers.get_asset_tools()
    master = tools.create_asset("M_ShoulderNetwork", destination_root,
                                api.Material, api.MaterialFactoryNew())
    require(master is not None and master.get_path_name() == paths["master"],
            "Shoulder master creation failed")
    require(master.get_editor_property("tangent_space_normal") is True,
            "New shoulder master has an unexpected normal-space default")

    def node(cls, **properties):
        value = lib.create_material_expression(master, cls)
        require(value is not None, "Shoulder material expression creation failed")
        for name, setting in properties.items():
            value.set_editor_property(name, setting)
        return value

    def link(source, output, target, pin):
        require(lib.connect_material_expressions(source, output, target, pin),
                "Shoulder material connection failed: " + output + " -> " + pin)

    def output(source, pin, prop):
        require(lib.connect_material_property(source, pin, prop),
                "Shoulder material property connection failed: " + str(prop))

    tile = node(api.MaterialExpressionScalarParameter, parameter_name="TileSizeCm",
                group="Road Gravel", default_value=TILE_SIZE_CM)
    projected = {}
    for parameter, channel in TEXTURES.items():
        normal = channel == "Normal_DX"
        sampler = (api.MaterialSamplerType.SAMPLERTYPE_NORMAL if normal else
                   api.MaterialSamplerType.SAMPLERTYPE_COLOR if channel == "BaseColor" else
                   api.MaterialSamplerType.SAMPLERTYPE_MASKS)
        texture = node(api.MaterialExpressionTextureObjectParameter,
                       parameter_name=parameter, group="Road Gravel",
                       texture=textures[channel], sampler_type=sampler)
        function = api.load_asset(PROJECTION_ROOT + ("WorldAlignedNormal" if normal else "WorldAlignedTexture"))
        require(function is not None, "Required native shoulder projection is missing")
        projected[channel] = node(api.MaterialExpressionMaterialFunctionCall)
        require(projected[channel].set_material_function(function),
                "Shoulder native projection assignment failed")
        link(texture, "", projected[channel], "TextureObject")
        link(tile, "", projected[channel], "TextureSize")
        if normal:
            world_space = node(api.MaterialExpressionStaticBool, value=False)
            link(world_space, "", projected[channel], "WorldSpace")
    output(projected["BaseColor"], "XYZ Texture", api.MaterialProperty.MP_BASE_COLOR)
    normal = node(api.MaterialExpressionNormalize)
    link(projected["Normal_DX"], "XYZ Texture", normal, "")
    output(normal, "", api.MaterialProperty.MP_NORMAL)
    rough = node(api.MaterialExpressionComponentMask, r=True, g=False, b=False, a=False)
    link(projected["Roughness"], "XYZ Texture", rough, "")
    output(rough, "", api.MaterialProperty.MP_ROUGHNESS)
    output(node(api.MaterialExpressionConstant, r=0.0), "", api.MaterialProperty.MP_METALLIC)
    output(node(api.MaterialExpressionConstant, r=1.0), "", api.MaterialProperty.MP_AMBIENT_OCCLUSION)
    require(not lib.recompile_material(master), "Shoulder material compilation reported errors")
    instance = tools.create_asset("MI_ShoulderNetwork", destination_root,
                                  api.MaterialInstanceConstant, api.MaterialInstanceConstantFactoryNew())
    require(instance is not None and instance.get_path_name() == paths["instance"],
            "Shoulder instance creation failed")
    lib.set_material_instance_parent(instance, master)
    lib.update_material_instance(instance)
    texture_objects = {channel: texture.get_path_name() for channel, texture in textures.items()}
    _verify_instance(api, instance, paths["master"], texture_objects)
    _authenticate_sources(api, source_dependencies)
    receipt = {
        "schema_version": 1, "status": "SHOULDER_MATERIAL_CREATED_REVIEW_PENDING",
        "engine_version": ENGINE_VERSION, "assets": paths,
        "texture_objects": texture_objects, "source_dependencies": sources,
        "source_ledger": LEDGER, "source_id": "rock_ground", "license": "CC0-1.0",
        "source_url": "https://polyhaven.com/a/rock_ground",
        "source_map_sha256": dict(SOURCE_MAP_SHA256),
        "tile_size_cm": TILE_SIZE_CM, "scale_authority": "provider dimensions",
        "normal_convention": "DirectX", "native_api": evidence,
        "textures_imported": False, "source_textures_modified": False,
        "height_connected": False, "world_assignment": False, "saved": False,
        "geometry_changed": False, "owner_visual_pass": False, "performance_pass": False,
    }
    return instance, receipt


def verify_material(api, receipt, source_dependencies):
    """Read the saved assets and immutable inputs; never reapply or repair them."""
    require(isinstance(receipt, dict) and receipt.get("schema_version") == 1
            and receipt.get("status") == "SHOULDER_MATERIAL_CREATED_REVIEW_PENDING"
            and receipt.get("engine_version") == ENGINE_VERSION
            and receipt.get("assets") == asset_paths(DESTINATION_ROOT)
            and receipt.get("source_dependencies") == source_rows(source_dependencies)
            and receipt.get("source_map_sha256") == SOURCE_MAP_SHA256
            and receipt.get("source_ledger") == LEDGER
            and receipt.get("source_id") == "rock_ground"
            and receipt.get("license") == "CC0-1.0"
            and receipt.get("tile_size_cm") == TILE_SIZE_CM
            and receipt.get("normal_convention") == "DirectX",
            "Shoulder material receipt/source contract differs")
    for name in ("textures_imported", "source_textures_modified", "height_connected",
                 "world_assignment", "saved", "geometry_changed", "owner_visual_pass", "performance_pass"):
        require(receipt.get(name) is False, "Shoulder helper receipt exceeds its authoring scope")
    textures, _ = _authenticate_sources(api, source_dependencies)
    expected = {channel: texture.get_path_name() for channel, texture in textures.items()}
    require(receipt.get("texture_objects") == expected, "Shoulder source texture object inventory differs")
    instance = api.load_asset(receipt["assets"]["instance"])
    require(instance is not None and instance.get_path_name() == receipt["assets"]["instance"],
            "Shoulder instance object identity differs")
    return _verify_instance(api, instance, receipt["assets"]["master"], expected)

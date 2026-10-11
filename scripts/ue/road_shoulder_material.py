"""Create the bounded #364 gravel material; never assign geometry or save assets.

The caller owns whole-network triangle selection, slot assignment, rollback and
saved/fresh-rendered proof. This helper consumes the three immutable FillGravel
textures and the same already imported asphalt PBR used by the road. Its two
new assets must be saved explicitly by the caller; no import, source-texture
edit, world edit or displacement occurs. An explicit source-owned material UV
field blends the inner shoulder edge in a bounded 3–8 cm strip.

Native graph operations follow import_material_forge_variant.py and the pinned
UE 5.8.2 projection-function readback in native run 38078459124. Epic references:
https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Editor/MaterialEditor/UMaterialEditingLibrary
https://dev.epicgames.com/documentation/en-us/unreal-engine/texturing-material-functions-in-unreal-engine
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

from scripts.ue import road_shoulder_edges as edges
from scripts.ue import road_asphalt_source_preflight as asphalt_source

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
ASPHALT_TEXTURES = {
    "EdgeAsphaltBaseColorTex": "BaseColor",
    "EdgeAsphaltNormalTex": "Normal_DX",
    "EdgeAsphaltORMTex": "ORM",
}
ASPHALT_ROOT = "/Game/Generated/YACS/RoadAsphaltConsumer/aged_mountain_asphalt/dry_varied"
SCALARS = {"TileSizeCm": TILE_SIZE_CM, "AsphaltTileSizeCm": 400.0}
EDGE_TRANSITION = {
    "material_uv_channel": edges.CHANNEL, "distance_units": "centimetres",
    "pure_asphalt_until_cm": 3.0, "pure_gravel_from_cm": 8.0,
    "breakup_source": "projected_gravel_base_color_red", "breakup_gain": 4.0,
    "breakup_polarity": "bright_gravel_towards_pavement",
    "breakup_width_cm": 4.0, "feather_width_cm": 1.0,
    "asphalt_specular": 0.2, "gravel_specular": 0.5,
    "outer_terrain_transition": False, "opacity_or_displacement": False,
}
EDGE_NODE_TYPES = (
    "MaterialExpressionTextureCoordinate", "MaterialExpressionSubtract",
    "MaterialExpressionMultiply", "MaterialExpressionAdd", "MaterialExpressionSaturate",
    "MaterialExpressionLinearInterpolate",
)
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
        "ORM": api.TextureCompressionSettings.TC_MASKS,
    }[channel]
    require(texture.get_editor_property("srgb") is (channel == "BaseColor")
            and texture.get_editor_property("compression_settings") == expected_compression
            and texture.get_editor_property("address_x") == api.TextureAddress.TA_WRAP
            and texture.get_editor_property("address_y") == api.TextureAddress.TA_WRAP,
            "Pinned FillGravel color/data import settings differ: " + channel)
    if channel == "Normal_DX":
        require(texture.get_editor_property("flip_green_channel") is False,
                "Pinned FillGravel normal must retain DirectX green direction")


def asphalt_asset_paths():
    def path(name):
        return ASPHALT_ROOT + "/" + asphalt_source.GRAPH_SHA256[:12] + "/" + name + "." + name
    return {"master": path("M_MaterialForge"), "instance": path("MI_MaterialForge"),
            "textures": {channel: path("T_MF_" + channel.replace("_", ""))
                         for channel in ("BaseColor", "Normal_DX", "ORM", "DetailMasks")}}


def _authenticate_asphalt(api, assets):
    """Reuse the exact road instance's PBR objects; no second texture import."""
    require(assets == asphalt_asset_paths(), "Edge asphalt is not the current imported road PBR")
    instance = api.load_asset(assets["instance"])
    require(instance is not None and isinstance(instance, api.MaterialInstanceConstant)
            and instance.get_path_name() == assets["instance"], "Imported edge asphalt instance is missing")
    parent = instance.get_editor_property("parent")
    require(parent is not None and isinstance(parent, api.Material)
            and parent.get_path_name() == assets["master"], "Edge asphalt parent differs from the road")
    lib, association = api.MaterialEditingLibrary, api.MaterialParameterAssociation.GLOBAL_PARAMETER
    for name, expected in {"TileSizeCm": 400.0, "DrySpecular": 0.2, "DryMetallic": 0.0}.items():
        actual = lib.get_material_instance_scalar_parameter_value(instance, name, association)
        require(type(actual) in (int, float) and math.isfinite(actual) and abs(actual - expected) <= 0.000001,
                "Edge asphalt metric/dry response differs from the road")
    textures = {}
    for parameter, channel in (("BaseColorTex", "BaseColor"), ("NormalTex", "Normal_DX"), ("ORMTex", "ORM")):
        texture = lib.get_material_instance_texture_parameter_value(instance, parameter, association)
        require(texture is not None and isinstance(texture, api.Texture2D)
                and texture.get_path_name() == assets["textures"][channel],
                "Edge asphalt texture differs from the road: " + channel)
        _verify_texture_settings(api, texture, channel)
        textures[channel] = texture
    return textures


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
    ) + EDGE_NODE_TYPES:
        require(callable(getattr(api, name, None)), "Required native material class is missing: " + name)
    # A/B/Alpha and the TextureCoordinate channel index are documented in
    # Epic's UE 5.8 Math / Coordinates Material Expressions references. Read
    # the installed class sources before authoring; every link also requires
    # the real native bool-returning connection API to succeed.
    from scripts.ci import official_mcp_bob_session as session
    engine = Path(api.Paths.convert_relative_path_to_full(api.Paths.engine_dir())).resolve()
    evidence["edge_node_sources"] = {}
    for name in EDGE_NODE_TYPES:
        # UE 5.8 moved expression headers to Public; discover the actual
        # defining header on this installed build, retaining its exact path.
        candidates = ["Source/Runtime/Engine/" + directory + "/Materials/" + name + ".h"
                      for directory in ("Public", "Classes")]
        available = [relative for relative in candidates if session._safe_path(engine, relative).is_file()]
        require(bool(available), "Installed edge material node header is missing: " + name)
        relative = available[0]
        path = session._safe_path(engine, relative)
        identity = session._identity(path, 1024 * 1024)
        require("U" + name in path.read_text(encoding="utf-8-sig"),
                "Installed edge material node source differs: " + name)
        evidence["edge_node_sources"][relative] = identity
    return evidence


def _verify_instance(api, instance, master_path, texture_objects, asphalt_objects):
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
    require({str(name) for name in lib.get_texture_parameter_names(instance)} == {*TEXTURES, *ASPHALT_TEXTURES}
            and {str(name) for name in lib.get_scalar_parameter_names(instance)} == set(SCALARS),
            "Shoulder material parameter inventory differs")
    for name, expected in SCALARS.items():
        tile = float(lib.get_material_instance_scalar_parameter_value(instance, name, association))
        require(math.isfinite(tile) and abs(tile - expected) <= 0.001,
                "Shoulder provider/asphalt metric projection changed: " + name)
    for parameters, objects in ((TEXTURES, texture_objects), (ASPHALT_TEXTURES, asphalt_objects)):
        for parameter, channel in parameters.items():
            texture = lib.get_material_instance_texture_parameter_value(instance, parameter, association)
            require(texture is not None and texture.get_path_name() == objects[channel],
                    "Shoulder material texture parameter changed: " + parameter)
            _verify_texture_settings(api, texture, channel)
    return instance


def create_material(api, destination_root, source_dependencies, asphalt_assets):
    """Create two unsaved assets; return (instance, receipt), without assignment."""
    paths = asset_paths(destination_root)
    textures, sources = _authenticate_sources(api, source_dependencies)
    asphalt = _authenticate_asphalt(api, asphalt_assets)
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

    def projections(parameters, objects, scale):
        tile = node(api.MaterialExpressionScalarParameter, parameter_name=scale,
                    group="Road Shoulder", default_value=SCALARS[scale])
        projected = {}
        for parameter, channel_name in parameters.items():
            normal_map = channel_name == "Normal_DX"
            sampler = (api.MaterialSamplerType.SAMPLERTYPE_NORMAL if normal_map else
                       api.MaterialSamplerType.SAMPLERTYPE_COLOR if channel_name == "BaseColor" else
                       api.MaterialSamplerType.SAMPLERTYPE_MASKS)
            texture = node(api.MaterialExpressionTextureObjectParameter,
                           parameter_name=parameter, group="Road Shoulder",
                           texture=objects[channel_name], sampler_type=sampler)
            function = api.load_asset(PROJECTION_ROOT + ("WorldAlignedNormal" if normal_map else "WorldAlignedTexture"))
            require(function is not None, "Required native shoulder projection is missing")
            projected[channel_name] = node(api.MaterialExpressionMaterialFunctionCall)
            require(projected[channel_name].set_material_function(function), "Shoulder native projection assignment failed")
            link(texture, "", projected[channel_name], "TextureObject")
            link(tile, "", projected[channel_name], "TextureSize")
            if normal_map:
                world_space = node(api.MaterialExpressionStaticBool, value=False)
                link(world_space, "", projected[channel_name], "WorldSpace")
        return projected

    def constant(value):
        return node(api.MaterialExpressionConstant, r=value)

    def channel(expression, pin="", *, green=False):
        mask = node(api.MaterialExpressionComponentMask, r=not green, g=green, b=False, a=False)
        link(expression, pin, mask, "")
        return mask

    def binary(cls, a, b):
        result = node(cls)
        link(a, "", result, "A")
        link(b, "", result, "B")
        return result

    projected = projections(TEXTURES, textures, "TileSizeCm")
    road = projections(ASPHALT_TEXTURES, asphalt, "AsphaltTileSizeCm")
    edge_uv = node(api.MaterialExpressionTextureCoordinate, coordinate_index=edges.CHANNEL,
                   u_tiling=1.0, v_tiling=1.0)
    require(edge_uv.get_editor_property("coordinate_index") == edges.CHANNEL,
            "Edge material reads a different UV channel")
    distance = channel(edge_uv)
    breakup_color = channel(projected["BaseColor"], "XYZ Texture")
    breakup = node(api.MaterialExpressionSaturate)
    link(binary(api.MaterialExpressionMultiply, breakup_color, constant(EDGE_TRANSITION["breakup_gain"])),
         "", breakup, "")
    # Light mineral fragments intrude towards the road; darker interstices
    # retain the quiet asphalt rim. This uses the scanned grain, without a
    # procedural sawtooth, a uniform blurred ribbon, opacity or a new texture.
    recess = binary(api.MaterialExpressionSubtract, constant(1.0), breakup)
    threshold = binary(api.MaterialExpressionAdd, constant(EDGE_TRANSITION["pure_asphalt_until_cm"]),
                       binary(api.MaterialExpressionMultiply, recess, constant(EDGE_TRANSITION["breakup_width_cm"])))
    alpha = node(api.MaterialExpressionSaturate)
    ramp = binary(api.MaterialExpressionSubtract, distance, threshold)
    link(binary(api.MaterialExpressionMultiply, ramp, constant(1.0 / EDGE_TRANSITION["feather_width_cm"])),
         "", alpha, "")

    def blend(a, a_pin, b, b_pin):
        result = node(api.MaterialExpressionLinearInterpolate)
        link(a, a_pin, result, "A")
        link(b, b_pin, result, "B")
        link(alpha, "", result, "Alpha")
        return result

    output(blend(road["BaseColor"], "XYZ Texture", projected["BaseColor"], "XYZ Texture"),
           "", api.MaterialProperty.MP_BASE_COLOR)
    normal = node(api.MaterialExpressionNormalize)
    link(blend(road["Normal_DX"], "XYZ Texture", projected["Normal_DX"], "XYZ Texture"), "", normal, "")
    output(normal, "", api.MaterialProperty.MP_NORMAL)
    output(blend(channel(road["ORM"], "XYZ Texture", green=True), "",
                 channel(projected["Roughness"], "XYZ Texture"), ""), "", api.MaterialProperty.MP_ROUGHNESS)
    output(blend(channel(road["ORM"], "XYZ Texture"), "", constant(1.0), ""),
           "", api.MaterialProperty.MP_AMBIENT_OCCLUSION)
    output(blend(constant(EDGE_TRANSITION["asphalt_specular"]), "",
                 constant(EDGE_TRANSITION["gravel_specular"]), ""), "", api.MaterialProperty.MP_SPECULAR)
    output(constant(0.0), "", api.MaterialProperty.MP_METALLIC)
    require(not lib.recompile_material(master), "Shoulder material compilation reported errors")
    instance = tools.create_asset("MI_ShoulderNetwork", destination_root,
                                  api.MaterialInstanceConstant, api.MaterialInstanceConstantFactoryNew())
    require(instance is not None and instance.get_path_name() == paths["instance"],
            "Shoulder instance creation failed")
    lib.set_material_instance_parent(instance, master)
    lib.update_material_instance(instance)
    texture_objects = {channel: texture.get_path_name() for channel, texture in textures.items()}
    asphalt_objects = {channel: texture.get_path_name() for channel, texture in asphalt.items()}
    _verify_instance(api, instance, paths["master"], texture_objects, asphalt_objects)
    _authenticate_sources(api, source_dependencies)
    _authenticate_asphalt(api, asphalt_assets)
    receipt = {
        "schema_version": 2, "status": "SHOULDER_MATERIAL_CREATED_REVIEW_PENDING",
        "engine_version": ENGINE_VERSION, "assets": paths,
        "texture_objects": texture_objects, "source_dependencies": sources,
        "asphalt_assets": asphalt_assets, "asphalt_texture_objects": asphalt_objects,
        "edge_transition": dict(EDGE_TRANSITION), "asphalt_tile_size_cm": SCALARS["AsphaltTileSizeCm"],
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
    require(isinstance(receipt, dict) and receipt.get("schema_version") == 2
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
    require(receipt.get("edge_transition") == EDGE_TRANSITION
            and receipt.get("asphalt_assets") == asphalt_asset_paths()
            and receipt.get("asphalt_tile_size_cm") == SCALARS["AsphaltTileSizeCm"],
            "Shoulder material edge/asphalt contract differs")
    for name in ("textures_imported", "source_textures_modified", "height_connected",
                 "world_assignment", "saved", "geometry_changed", "owner_visual_pass", "performance_pass"):
        require(receipt.get(name) is False, "Shoulder helper receipt exceeds its authoring scope")
    textures, _ = _authenticate_sources(api, source_dependencies)
    expected = {channel: texture.get_path_name() for channel, texture in textures.items()}
    require(receipt.get("texture_objects") == expected, "Shoulder source texture object inventory differs")
    asphalt = _authenticate_asphalt(api, receipt["asphalt_assets"])
    asphalt_expected = {channel: texture.get_path_name() for channel, texture in asphalt.items()}
    require(receipt.get("asphalt_texture_objects") == asphalt_expected, "Edge asphalt object inventory differs")
    instance = api.load_asset(receipt["assets"]["instance"])
    require(instance is not None and instance.get_path_name() == receipt["assets"]["instance"],
            "Shoulder instance object identity differs")
    return _verify_instance(api, instance, receipt["assets"]["master"], expected, asphalt_expected)

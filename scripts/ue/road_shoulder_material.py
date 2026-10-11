"""Create the bounded #364 gravel material; never assign geometry or save assets.

The caller owns whole-network triangle selection, slot assignment, rollback and
saved/fresh-rendered proof. This helper consumes the three immutable FillGravel
textures and the same already imported asphalt PBR used by the road. Its two
new assets must be saved explicitly by the caller; no import, source-texture
edit, world edit or displacement occurs. An explicit source-owned material UV
field blends the inner shoulder edge in a bounded 3–8 cm strip.

An optional separate material variant reuses the actual frozen five-role
Landscape surface at the same world coordinates. UV1 controls its opaque outer
edge blend; UV0 and the entire original inner transition remain unchanged.
This does not establish physical contact or native normal-response acceptance.

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
from scripts.ue import sa_calobra_whole_map_prep as terrain_prep

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
OUTER_TRANSITION = {
    "material_uv_channel": edges.OUTER_CHANNEL, "distance_units": "centimetres",
    "coordinates": "outer_distance_and_along_edge",
    "pure_terrain_until_cm": 1.0, "pure_gravel_from_cm": 10.0,
    "breakup_source": "projected_gravel_base_color_red", "breakup_gain": 4.0,
    "breakup_polarity": "bright_gravel_towards_terrain",
    "breakup_width_cm": 7.0, "feather_width_cm": 2.0,
    "inner_transition_preserved_until_cm": 8.0, "inner_guard_width_cm": 1.0,
    "world_position_source": "same_absolute_world_position_as_frozen_landscape",
    "normal_space": "WorldAlignedNormal WorldSpace=False; material tangent_space_normal=True",
    "physical_contact_verified": False, "normal_response_visual_verified": False,
    "opacity_or_displacement": False, "landscape_material_modified": False,
}
TERRAIN_NODE_TYPES = (
    "MaterialExpressionWorldPosition", "MaterialExpressionConstant2Vector",
    "MaterialExpressionConstant3Vector", "MaterialExpressionTextureSampleParameter2D",
    "MaterialExpressionDivide", "MaterialExpressionOneMinus", "MaterialExpressionDistance",
    "MaterialExpressionCameraPositionWS", "MaterialExpressionMax",
    "MaterialExpressionFloor", "MaterialExpressionFrac",
)
# Actual frozen #363 package identities retained in native4258's authenticated
# road-material-baseline.json; these are inputs, never rebuilt by this helper.
TERRAIN_ROOT = "Content/Generated/YACS/SaCalobra/WholeMapPreparation/"
TERRAIN_PINS = {
    "master": {"path": TERRAIN_ROOT + "M_SaCalobraWholeMapPreparation.uasset",
               "sha256": "2df2ef1d3b377cd951c74e6c8dfe3977fd4e45f22c8d784ec7c6ef2902781f1e", "size_bytes": 111106},
    "instance": {"path": TERRAIN_ROOT + "MI_SaCalobraWholeMapPreparation.uasset",
                 "sha256": "694f58bf7c9515d451b93906f8ad1c156e93647c51f04eac58d509b11289af09", "size_bytes": 8122},
    "WeightTex": {"path": TERRAIN_ROOT + "T_WholeMapWeights.uasset",
                  "sha256": "29a7f8a25738353f14cb833a87328f97c0f83dcdb178567a54ad9ad183ae173b", "size_bytes": 28166244},
}
for _role, _base, _normal in (
    ("DryGrass", ("13ec5f0be03f849515c1136268750a9e1c5576961d97f147dbf616e653ccaa2f", 1153614),
     ("b54bd273e99b61a3f51ed700db015cc13d431c42739c06b9bbdfe306d4885a32", 6533124)),
    ("ForestLitter", ("ae5276d75d1362f4df9803f41f2b0fc1626a2506c5930c2e42461dc3b4487861", 835692),
     ("2c0bf480850798e0b9c98af18b16cd3c4b8b4225eb0c9ccf9c0f39dfa8a75463", 3239923)),
    ("ExposedRock", ("a754df8989666b2c2146346cc66cd2461bdefe74c2146f356fe0ab1de5b0ab2d", 1433833),
     ("6b99c94d4679c99df5fc175a02f2da724bb802a7497035c35669ffacb860d747", 6166243)),
    ("DryMineral", ("fab7494f3e7d209b33f3afd031ff3dd1035404777cd8883489d19d1a0238c73a", 969347),
     ("2b5265fd3397e779613355e9978af8f8dbc61406d968bbfa190e4be6aae8f853", 2963121)),
    ("Scree", ("1bc24bb30053875f8f47b0fbc6e6fdaf97629598c9670a217034ba72470d6933", 936623),
     ("05d06202ef0d127cb08e16df442f96e901e568d34db1adb87af2b3df4679ecb4", 2888628)),
):
    for _channel, _suffix, (_sha, _size) in (
        ("BaseColor", "Sources/T_Source_" + _role, _base),
        ("Normal", "ProviderData/" + _role + "/T_Normal", _normal),
    ):
        TERRAIN_PINS[_role + _channel + "Tex"] = {
            "path": LIBRARY + _suffix + ".uasset", "sha256": _sha, "size_bytes": _size}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def asset_paths(destination_root, *, outer_terrain=False):
    require(destination_root == DESTINATION_ROOT, "Unapproved shoulder material destination")
    require(type(outer_terrain) is bool, "Outer terrain material variant must be explicit")
    suffix = "Terrain" if outer_terrain else ""
    package = destination_root + ("/TerrainBlend" if outer_terrain else "")
    return {
        role: package + "/" + name + "." + name
        for role, name in (
            ("master", "M_ShoulderNetwork" + suffix),
            ("instance", "MI_ShoulderNetwork" + suffix),
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


def terrain_rows(consumer_assets, source_dependencies):
    """Bind the three frozen generated packages and all ten original role maps."""
    indices = []
    for name, rows in (("consumer", consumer_assets), ("dependencies", source_dependencies)):
        require(isinstance(rows, list) and 3 <= len(rows) <= 4096,
                "Terrain " + name + " inventory is missing or unbounded")
        index = {}
        for row in rows:
            require(isinstance(row, dict) and isinstance(row.get("path"), str)
                    and row["path"] not in index, "Invalid or duplicate terrain " + name + " row")
            index[row["path"]] = row
        indices.append(index)
    for name, expected in TERRAIN_PINS.items():
        for index in indices[:1] if name in ("master", "instance", "WeightTex") else indices:
            actual = index.get(expected["path"])
            require(actual is not None and type(actual.get("size_bytes")) is int
                    and all(actual.get(key) == value for key, value in expected.items()),
                    "Frozen terrain package inventory differs: " + expected["path"])
    return {name: dict(row) for name, row in TERRAIN_PINS.items()}


def _verify_terrain_texture(api, texture, parameter):
    if parameter != "WeightTex":
        _verify_texture_settings(api, texture, "Normal_DX" if parameter.endswith("NormalTex") else "BaseColor")
        return
    expected = {"srgb": False, "filter": api.TextureFilter.TF_BILINEAR,
                "address_x": api.TextureAddress.TA_CLAMP, "address_y": api.TextureAddress.TA_CLAMP,
                "compression_settings": api.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP,
                "never_stream": False}
    require(all(texture.get_editor_property(key) == value for key, value in expected.items()),
            "Frozen whole-map weight texture no longer has its linear registered CLAMP settings")


def _authenticate_terrain(api, consumer_assets, source_dependencies, landscape):
    """Read the actual frozen Landscape material, without assigning or repairing it."""
    from scripts.ci import official_mcp_bob_session as session

    require(terrain_prep.ROOT.resolve() == ROOT.resolve(), "Terrain producer belongs to another checkout")
    rows = terrain_rows(consumer_assets, source_dependencies)
    for row in rows.values():
        require(session._identity(session._safe_path(ROOT, row["path"]), 40 * 1024 * 1024)
                == {key: row[key] for key in ("sha256", "size_bytes")},
                "Frozen terrain source bytes changed: " + row["path"])
    source_assets, recipe = terrain_prep.source_assets(), terrain_prep.rendering_recipe()
    for role in terrain_prep.ROLES:
        for channel in ("BaseColor", "Normal"):
            source, pinned = source_assets[role][channel], rows[role + channel + "Tex"]
            require(source == {"asset": _object_path(pinned["path"]).split(".")[0],
                               "file": pinned["path"], "sha256": pinned["sha256"],
                               "size_bytes": pinned["size_bytes"]},
                    "Terrain source producer differs from the accepted role bytes")
    master, instance = (api.load_asset(_object_path(rows[name]["path"])) for name in ("master", "instance"))
    require(isinstance(master, api.Material) and isinstance(instance, api.MaterialInstanceConstant)
            and master.get_path_name() == _object_path(rows["master"]["path"])
            and instance.get_path_name() == _object_path(rows["instance"]["path"])
            and instance.get_editor_property("parent") == master,
            "Frozen terrain master/instance identity differs")
    readback = terrain_prep.verify_instance(api, master, instance,
                                          {"rendering_recipe": recipe, "source_assets": source_assets})
    lib, association = api.MaterialEditingLibrary, api.MaterialParameterAssociation.GLOBAL_PARAMETER
    scalars = {name: float(lib.get_material_instance_scalar_parameter_value(instance, name, association))
               for name in readback["scalars"]}
    require(scalars["DomainMix"] == 0.0 and scalars["CheckerMix"] == 0.0,
            "Outer terrain blend requires the ordinary frozen surface, not a diagnostic overlay")
    bindings = {}
    for name, row in rows.items():
        if name in ("master", "instance"):
            continue
        texture = lib.get_material_instance_texture_parameter_value(instance, name, association)
        require(isinstance(texture, api.Texture2D) and texture.get_path_name() == _object_path(row["path"]),
                "Frozen terrain texture binding differs: " + name)
        _verify_terrain_texture(api, texture, name)
        bindings[name] = texture
    require(isinstance(landscape, api.Landscape)
            and landscape.get_editor_property("landscape_material") == instance,
            "The actual Landscape does not consume the frozen terrain instance")
    landscape_rows = terrain_prep.LandscapeBinding(api, landscape, master, instance).audit()
    require(len(landscape_rows) == 1024, "Incomplete frozen Landscape material binding witness")
    graph_source = "scripts/ue/build_sa_calobra_whole_map_master.py"
    contract = {
        "source_packages": rows, "master": master.get_path_name(), "instance": instance.get_path_name(),
        "texture_objects": {name: value.get_path_name() for name, value in bindings.items()},
        "scalar_values": scalars, "rendering_recipe": recipe,
        "rendering_recipe_sha256": hashlib.sha256(terrain_prep.canonical(recipe)).hexdigest(),
        "source_assets": source_assets, "landscape_component_count": 1024,
        "shared_graph_source": {"file": graph_source,
                                **session._identity(session._safe_path(ROOT, graph_source), 1024 * 1024)},
        "world_mapping": dict(terrain_prep.WORLD_MAPPING), "material_formula": terrain_prep.FORMULA,
        "terrain_assets_modified": False, "weight_texture_reimported": False,
    }
    return {"weight": bindings["WeightTex"],
            "textures": {role: {channel: bindings[role + channel + "Tex"] for channel in ("BaseColor", "Normal")}
                         for role in terrain_prep.ROLES},
            "contract": contract,
            "observation": {"landscape_actor": landscape.get_path_name(),
                            "landscape_bindings_sha256": hashlib.sha256(terrain_prep.canonical(landscape_rows)).hexdigest(),
                            "landscape_component_count": len(landscape_rows), **readback}}


def _terrain_terms(api, master, terrain):
    from scripts.ue import build_sa_calobra_whole_map_master as builder

    require(builder.unreal is api, "Shared terrain graph does not use the caller's actual Unreal API")
    source = terrain["contract"]
    recipe = {**source["rendering_recipe"], "roles": {
        role: {**row, "tile_cm": source["scalar_values"][role + "TileSizeCm"],
               "roughness": source["scalar_values"][role + "Roughness"]}
        for role, row in source["rendering_recipe"]["roles"].items()}}
    graph = builder.Graph(master)
    return builder.build_surface_terms(
        graph, terrain["weight"], terrain["textures"], recipe,
        scalar_values={name: source["scalar_values"][name] for name in terrain_prep.SCALARS})


def _api_evidence(api, *, outer_terrain=False):
    names = (
        "create_material_expression", "connect_material_expressions",
        "connect_material_property", "recompile_material",
        "set_material_instance_parent", "update_material_instance",
        "get_texture_parameter_names", "get_scalar_parameter_names",
        "get_material_instance_texture_parameter_value",
        "get_material_instance_scalar_parameter_value",
    )
    if outer_terrain:
        names += ("get_statistics",)
    evidence = {}
    for name in names:
        method = getattr(api.MaterialEditingLibrary, name, None)
        require(callable(method), "Required native material API is missing: " + name)
        doc = str(getattr(method, "__doc__", "") or "")
        require(bool(doc) and len(doc) <= 32768,
                "Required native material API has no bounded signature: " + name)
        evidence[name] = {"signature": doc.splitlines()[0],
                          "doc_sha256": hashlib.sha256(doc.encode()).hexdigest()}
    node_types = EDGE_NODE_TYPES + (TERRAIN_NODE_TYPES if outer_terrain else ())
    for name in (
        "MaterialExpressionTextureObjectParameter", "MaterialExpressionScalarParameter",
        "MaterialExpressionMaterialFunctionCall", "MaterialExpressionStaticBool",
        "MaterialExpressionNormalize", "MaterialExpressionComponentMask",
        "MaterialExpressionConstant", "MaterialFactoryNew", "MaterialInstanceConstantFactoryNew",
    ) + node_types:
        require(callable(getattr(api, name, None)), "Required native material class is missing: " + name)
    # A/B/Alpha and the TextureCoordinate channel index are documented in
    # Epic's UE 5.8 Math / Coordinates Material Expressions references. Read
    # the installed class sources before authoring; every link also requires
    # the real native bool-returning connection API to succeed.
    from scripts.ci import official_mcp_bob_session as session
    engine = Path(api.Paths.convert_relative_path_to_full(api.Paths.engine_dir())).resolve()
    evidence["edge_node_sources"] = {}
    for name in node_types:
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
    if outer_terrain:
        relative = "Source/Editor/MaterialEditor/Public/MaterialEditingLibrary.h"
        path = session._safe_path(engine, relative)
        text = path.read_text(encoding="utf-8-sig")
        require(all(symbol in text for symbol in ("GetStatistics", "FMaterialStatistics", "NumSamplers",
                                                   "NumPixelShaderInstructions", "NumPixelTextureSamples")),
                "Installed native material statistics API differs")
        evidence["material_statistics_source"] = {"file": relative, **session._identity(path, 2 * 1024 * 1024)}
    return evidence


def _verify_instance(api, instance, master_path, texture_objects, asphalt_objects, terrain=None):
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
    scalar_values = {**SCALARS, **({} if terrain is None else terrain["scalar_values"])}
    terrain_textures = {} if terrain is None else terrain["texture_objects"]
    require({str(name) for name in lib.get_texture_parameter_names(instance)}
            == {*TEXTURES, *ASPHALT_TEXTURES, *terrain_textures}
            and {str(name) for name in lib.get_scalar_parameter_names(instance)} == set(scalar_values),
            "Shoulder material parameter inventory differs")
    for name, expected in scalar_values.items():
        tile = float(lib.get_material_instance_scalar_parameter_value(instance, name, association))
        tolerance = 0.001 if name in SCALARS else 0.000001
        require(math.isfinite(tile) and abs(tile - expected) <= tolerance,
                "Shoulder provider/asphalt metric projection changed: " + name)
    for parameters, objects in ((TEXTURES, texture_objects), (ASPHALT_TEXTURES, asphalt_objects)):
        for parameter, channel in parameters.items():
            texture = lib.get_material_instance_texture_parameter_value(instance, parameter, association)
            require(texture is not None and texture.get_path_name() == objects[channel],
                    "Shoulder material texture parameter changed: " + parameter)
            _verify_texture_settings(api, texture, channel)
    for parameter, expected in terrain_textures.items():
        texture = lib.get_material_instance_texture_parameter_value(instance, parameter, association)
        require(texture is not None and texture.get_path_name() == expected,
                "Shoulder terrain texture differs from the actual Landscape: " + parameter)
        _verify_terrain_texture(api, texture, parameter)
    return instance


STATISTICS_FIELDS = (
    "num_samplers", "num_pixel_shader_instructions", "num_pixel_texture_samples",
    "num_vertex_shader_instructions", "num_vertex_texture_samples", "num_virtual_texture_samples",
    "num_uv_scalars", "num_interpolator_scalars",
)


def _validate_statistics(values):
    require(isinstance(values, dict) and set(values) == set(STATISTICS_FIELDS)
            and all(type(value) is int and 0 <= value <= 1000000 for value in values.values())
            and values["num_virtual_texture_samples"] == 0,
            "The terrain shoulder has invalid native direct-texture statistics")
    return values


def native_statistics(api, instance):
    """Retain observations, including NullRHI zeros; these are not GPU admission."""
    stats = api.MaterialEditingLibrary.get_statistics(instance)
    return _validate_statistics({name: stats.get_editor_property(name) for name in STATISTICS_FIELDS})


def verify_gpu_material_statistics(api, instance):
    """Read the exact outer MI after the caller's GPU drain/readiness barrier.

    This does not recompile or repair a saved material. The stock statistics
    API has no compile-error text output; actual host shader-log checks and
    retained images remain required, alongside the independent binding audit.
    """
    paths = asset_paths(DESTINATION_ROOT, outer_terrain=True)
    require(isinstance(instance, api.MaterialInstanceConstant) and instance.get_path_name() == paths["instance"],
            "GPU terrain statistics require the exact saved outer material instance")
    parent = instance.get_editor_property("parent")
    require(isinstance(parent, api.Material) and parent.get_path_name() == paths["master"],
            "GPU terrain statistics refer to a different master")
    values = native_statistics(api, instance)
    require(all(values[name] > 0 for name in (
        "num_samplers", "num_pixel_shader_instructions", "num_pixel_texture_samples")),
        "GPU terrain material statistics have no compiled sampler/instruction/sample observations")
    return {"status": "SHOULDER_TERRAIN_GPU_STATISTICS_VERIFIED", "instance": instance.get_path_name(),
            "master": parent.get_path_name(), "native_statistics": values, "read_only": True,
            "gpu_compile_verified": False, "compile_error_text_observed": False,
            "host_shader_log_check_required": True, "owner_visual_pass": False, "performance_pass": False}


def create_material(api, destination_root, source_dependencies, asphalt_assets, *,
                    terrain_consumer_assets=None, landscape=None):
    """Create two unsaved assets; return (instance, receipt), without assignment."""
    outer = terrain_consumer_assets is not None or landscape is not None
    require(not outer or (terrain_consumer_assets is not None and landscape is not None),
            "Outer terrain authoring requires both the frozen inventory and actual Landscape")
    paths = asset_paths(destination_root, outer_terrain=outer)
    textures, sources = _authenticate_sources(api, source_dependencies)
    asphalt = _authenticate_asphalt(api, asphalt_assets)
    terrain = _authenticate_terrain(api, terrain_consumer_assets, source_dependencies, landscape) if outer else None
    evidence = _api_evidence(api, outer_terrain=outer)
    require(all(not api.EditorAssetLibrary.does_asset_exist(path) for path in paths.values()),
            "Shoulder material assets already exist; refuse overwrite")
    lib = api.MaterialEditingLibrary
    tools = api.AssetToolsHelpers.get_asset_tools()
    master = tools.create_asset(paths["master"].rsplit(".", 1)[1], paths["master"].rsplit("/", 1)[0],
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

    def blend(a, a_pin, b, b_pin, *, blend_alpha=None):
        result = node(api.MaterialExpressionLinearInterpolate)
        link(a, a_pin, result, "A")
        link(b, b_pin, result, "B")
        link(alpha if blend_alpha is None else blend_alpha, "", result, "Alpha")
        return result

    base_color = blend(road["BaseColor"], "XYZ Texture", projected["BaseColor"], "XYZ Texture")
    normal = node(api.MaterialExpressionNormalize)
    link(blend(road["Normal_DX"], "XYZ Texture", projected["Normal_DX"], "XYZ Texture"), "", normal, "")
    roughness = blend(channel(road["ORM"], "XYZ Texture", green=True), "",
                      channel(projected["Roughness"], "XYZ Texture"), "")
    if outer:
        terms = _terrain_terms(api, master, terrain)
        outer_uv = node(api.MaterialExpressionTextureCoordinate, coordinate_index=edges.OUTER_CHANNEL,
                        u_tiling=1.0, v_tiling=1.0)
        require(outer_uv.get_editor_property("coordinate_index") == edges.OUTER_CHANNEL,
                "Outer terrain material reads a different UV channel")
        outer_threshold = binary(api.MaterialExpressionAdd, constant(OUTER_TRANSITION["pure_terrain_until_cm"]),
                                 binary(api.MaterialExpressionMultiply, recess,
                                        constant(OUTER_TRANSITION["breakup_width_cm"])))
        outer_gravel = node(api.MaterialExpressionSaturate)
        link(binary(api.MaterialExpressionMultiply,
                    binary(api.MaterialExpressionSubtract, channel(outer_uv), outer_threshold),
                    constant(1.0 / OUTER_TRANSITION["feather_width_cm"])), "", outer_gravel, "")
        # The two independently metric edge fields can approach on a taper.
        # Preserve the entire existing inner transition instead of assuming a
        # constant strip width or letting terrain alter asphalt at that edge.
        inner_guard = node(api.MaterialExpressionSaturate)
        link(binary(api.MaterialExpressionMultiply,
                    binary(api.MaterialExpressionSubtract, distance,
                           constant(OUTER_TRANSITION["inner_transition_preserved_until_cm"])),
                    constant(1.0 / OUTER_TRANSITION["inner_guard_width_cm"])), "", inner_guard, "")
        terrain_alpha = binary(api.MaterialExpressionMultiply, inner_guard,
                               binary(api.MaterialExpressionSubtract, constant(1.0), outer_gravel))
        base_color = blend(base_color, "", terms["BaseColor"], "", blend_alpha=terrain_alpha)
        mixed_normal = blend(normal, "", terms["Normal"], "", blend_alpha=terrain_alpha)
        normal = node(api.MaterialExpressionNormalize)
        link(mixed_normal, "", normal, "")
        roughness = blend(roughness, "", terms["Roughness"], "", blend_alpha=terrain_alpha)
        # Retain the original surface's complete connected parameter inventory.
        # The authenticated ordinary instance has DomainMix=CheckerMix=0, so
        # this is exactly zero and introduces no emissive terrain coloration.
        output(binary(api.MaterialExpressionMultiply, terms["Emissive"], terrain_alpha),
               "", api.MaterialProperty.MP_EMISSIVE_COLOR)
    output(base_color, "", api.MaterialProperty.MP_BASE_COLOR)
    output(normal, "", api.MaterialProperty.MP_NORMAL)
    output(roughness, "", api.MaterialProperty.MP_ROUGHNESS)
    output(blend(channel(road["ORM"], "XYZ Texture"), "", constant(1.0), ""),
           "", api.MaterialProperty.MP_AMBIENT_OCCLUSION)
    output(blend(constant(EDGE_TRANSITION["asphalt_specular"]), "",
                 constant(EDGE_TRANSITION["gravel_specular"]), ""), "", api.MaterialProperty.MP_SPECULAR)
    output(constant(0.0), "", api.MaterialProperty.MP_METALLIC)
    compile_errors = lib.recompile_material(master)
    require(not compile_errors, "Shoulder material compilation reported errors: " + str(compile_errors))
    instance = tools.create_asset(paths["instance"].rsplit(".", 1)[1], paths["instance"].rsplit("/", 1)[0],
                                  api.MaterialInstanceConstant, api.MaterialInstanceConstantFactoryNew())
    require(instance is not None and instance.get_path_name() == paths["instance"],
            "Shoulder instance creation failed")
    lib.set_material_instance_parent(instance, master)
    lib.update_material_instance(instance)
    texture_objects = {channel: texture.get_path_name() for channel, texture in textures.items()}
    asphalt_objects = {channel: texture.get_path_name() for channel, texture in asphalt.items()}
    _verify_instance(api, instance, paths["master"], texture_objects, asphalt_objects,
                     None if terrain is None else terrain["contract"])
    _authenticate_sources(api, source_dependencies)
    _authenticate_asphalt(api, asphalt_assets)
    receipt = {
        "schema_version": 3 if outer else 2, "status": "SHOULDER_MATERIAL_CREATED_REVIEW_PENDING",
        "engine_version": ENGINE_VERSION, "assets": paths,
        "texture_objects": texture_objects, "source_dependencies": sources,
        "asphalt_assets": asphalt_assets, "asphalt_texture_objects": asphalt_objects,
        "edge_transition": {**EDGE_TRANSITION, "outer_terrain_transition": outer},
        "asphalt_tile_size_cm": SCALARS["AsphaltTileSizeCm"],
        "source_ledger": LEDGER, "source_id": "rock_ground", "license": "CC0-1.0",
        "source_url": "https://polyhaven.com/a/rock_ground",
        "source_map_sha256": dict(SOURCE_MAP_SHA256),
        "tile_size_cm": TILE_SIZE_CM, "scale_authority": "provider dimensions",
        "normal_convention": "DirectX", "native_api": evidence,
        "textures_imported": False, "source_textures_modified": False,
        "height_connected": False, "world_assignment": False, "saved": False,
        "geometry_changed": False, "owner_visual_pass": False, "performance_pass": False,
    }
    if outer:
        after_terrain = _authenticate_terrain(api, terrain_consumer_assets, source_dependencies, landscape)
        require(after_terrain["contract"] == terrain["contract"], "Frozen terrain inputs changed during graph creation")
        receipt.update(outer_transition=dict(OUTER_TRANSITION), terrain_source=terrain["contract"],
                       terrain_observation=after_terrain["observation"],
                       native_statistics=native_statistics(api, instance), native_compile_errors=list(compile_errors),
                       gpu_compile_verified=False,
                       unique_texture_objects=17, outer_terrain_enabled=True)
    return instance, receipt


def verify_material(api, receipt, source_dependencies, *, terrain_consumer_assets=None, landscape=None):
    """Read the saved assets and immutable inputs; never reapply or repair them."""
    require(isinstance(receipt, dict), "Shoulder material receipt is not an object")
    outer = receipt.get("schema_version") == 3
    require(isinstance(receipt, dict) and receipt.get("schema_version") in (2, 3)
            and receipt.get("status") == "SHOULDER_MATERIAL_CREATED_REVIEW_PENDING"
            and receipt.get("engine_version") == ENGINE_VERSION
            and receipt.get("assets") == asset_paths(DESTINATION_ROOT, outer_terrain=outer)
            and receipt.get("source_dependencies") == source_rows(source_dependencies)
            and receipt.get("source_map_sha256") == SOURCE_MAP_SHA256
            and receipt.get("source_ledger") == LEDGER
            and receipt.get("source_id") == "rock_ground"
            and receipt.get("license") == "CC0-1.0"
            and receipt.get("tile_size_cm") == TILE_SIZE_CM
            and receipt.get("normal_convention") == "DirectX",
            "Shoulder material receipt/source contract differs")
    require(receipt.get("edge_transition") == {**EDGE_TRANSITION, "outer_terrain_transition": outer}
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
    terrain = None
    if outer:
        require(terrain_consumer_assets is not None and landscape is not None
                and receipt.get("outer_transition") == OUTER_TRANSITION
                and receipt.get("outer_terrain_enabled") is True
                and receipt.get("native_compile_errors") == []
                and receipt.get("gpu_compile_verified") is False
                and type(receipt.get("unique_texture_objects")) is int and receipt["unique_texture_objects"] == 17,
                "Outer terrain material source/readback contract differs")
        terrain = _authenticate_terrain(api, terrain_consumer_assets, source_dependencies, landscape)
        require(receipt.get("terrain_source") == terrain["contract"], "Saved frozen terrain material inputs changed")
        _validate_statistics(receipt.get("native_statistics"))
        # Save/reload run with NullRHI; actual GPU resources may have different
        # counters. Validate both observations without treating them as a pin.
        native_statistics(api, instance)
    else:
        require(terrain_consumer_assets is None and landscape is None and "outer_transition" not in receipt,
                "Legacy shoulder material cannot claim outer terrain inputs")
    return _verify_instance(api, instance, receipt["assets"]["master"], expected, asphalt_expected,
                            None if terrain is None else terrain["contract"])

"""New source-clipped Surface/Masked crack materials, without placement or saves.

The measured neutral source pixels define a relative color/ORM change over the
current 4 m asphalt. DirectX crack normals follow each patch's own UV frame;
the base normal stays world projected. This graph is a candidate until an
actual WorldNormal A/B on an opaque NeutralProbe patch confirms the spaces.
NeutralProbe=1 bypasses every local map contribution and covers the full patch;
saved MICs always remain zero; the diagnostic controller uses transient MIDs.

Stock UE 5.8 references, complemented by installed headers/function identities:
https://dev.epicgames.com/documentation/unreal-engine/vector-operation-material-expressions-in-unreal-engine
https://dev.epicgames.com/documentation/en-us/unreal-engine/texturing-material-functions-in-unreal-engine
https://dev.epicgames.com/documentation/en-us/unreal-engine/material-blend-modes-in-unreal-engine
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import math
from pathlib import Path

from scripts.ci import official_mcp_bob_session as session
from scripts.ue import road_crack_sources as sources
from scripts.ue import road_shoulder_material as road_material

ROOT = Path(__file__).resolve().parents[2]
ENGINE_VERSION = road_material.ENGINE_VERSION
MAX_GRAPH_NODES = 96
BASE_TEXTURES = {"AsphaltBaseColorTex": "BaseColor", "AsphaltNormalTex": "Normal_DX", "AsphaltORMTex": "ORM"}
LOCAL_TEXTURES = {"CrackBaseColorTex": "BaseColor", "CrackNormalTex": "Normal_DX",
                  "CrackORMTex": "ORM", "CrackMasksTex": "DetailMasks"}
COMMON_SCALARS = {"TileSizeCm": 400.0, "NeutralProbe": 0.0}
VECTOR_NAMES = {"NeutralBaseColor", "NeutralORM", "NeutralNormalXY"}
PROBE_CONTRACT = {
    "parameter": "NeutralProbe", "default_value": 0.0, "probe_value": 1.0,
    "probe_coverage": "entire_source_clipped_patch",
    "probe_normal": "base_world_aligned_normal_without_local_delta",
    "probe_color_orm": "unchanged_base_asphalt",
    "reset_value": 0.0, "native_reset_readback_required": True,
    "separate_world_normal_ab_required": True,
    "owned_process_env": "YACS_ROAD_CRACK_CONTROLS_OWNED",
    "probe_material_kind": "transient_MaterialInstanceDynamic",
    "saved_material_parameter_changes": False,
}
NORMAL_CONTRACT = {
    "base": "WorldAlignedNormal_WorldSpace_true",
    "local": "DirectX_UV0_tangent_to_world",
    "composition": "normalize(base_world_normal_plus_local_world_normal_minus_neutral_frame_normal)",
    "source_xy_quantization_bias_removed": True,
    "world_normal_canary_required": True, "normal_space_verified": False,
}
FALSE_FLAGS = ("textures_imported", "source_textures_modified", "world_assignment", "saved", "geometry_changed",
               "road_clipped", "world_position_offset", "pixel_depth_offset", "temporal_dither",
               "source_texture_pixels_verified_in_ue", "normal_space_verified", "owner_visual_pass", "performance_pass")
EXTRA_NODE_TYPES = (
    "MaterialExpressionTextureSampleParameter2D", "MaterialExpressionWorldPosition", "MaterialExpressionTransform",
    "MaterialExpressionVectorParameter", "MaterialExpressionConstant3Vector", "MaterialExpressionDivide",
    "MaterialExpressionMin", "MaterialExpressionMax", "MaterialExpressionOneMinus",
)


def require(value, message):
    if not value:
        raise ValueError(message)


def geometry_contract(source_motif, *, uv_rotation_degrees=0.0):
    extent = source_motif.get("extent_cm")
    require(type(extent) in (int, float) and math.isfinite(extent) and 100 <= extent <= 200
            and source_motif.get("empty_border_cm") == 6.0 and source_motif.get("resolution") == 2048,
            "Crack geometry needs the authenticated metric source extent")
    require(type(uv_rotation_degrees) in (int, float) and uv_rotation_degrees in (0.0, 90.0),
            "Crack normal canary permits only the explicit 0/90 degree UV frames")
    # u/v name the source road frame before this declared geometry-owned turn.
    # The material samples UV0 as delivered, with no second shader rotation.
    return {"channel": 0, "u": "across_road_station", "v": "along_positive_road_station", "uv_range": [0.0, 1.0],
            "uv_rotation_degrees": float(uv_rotation_degrees),
            "extent_cm": float(extent), "empty_border_cm": 6.0, "surface_offset_cm": 0.1,
            "surface_offset_axis": "world_positive_z", "actor_scale": [1.0, 1.0, 1.0],
            "normal_contract": "normalized_barycentric_native_road_split_corner_normals",
            "tangents": "AUTO_CALCULATED", "opacity_mask_clip_value": 0.1, "world_normal_canary_required": True}


def asset_paths(source):
    root = sources.asset_paths(source)["root"]
    master = root + "/M_RoadCracks.M_RoadCracks"
    return {motif: {"master": master, "instance": root + "/MI_RoadCracks_" + motif + ".MI_RoadCracks_" + motif}
            for motif in source["selected_motifs"]}


def _master_properties(api):
    return {"material_domain": api.MaterialDomain.MD_SURFACE, "shading_model": api.MaterialShadingModel.MSM_DEFAULT_LIT,
            "blend_mode": api.BlendMode.BLEND_MASKED, "opacity_mask_clip_value": 0.1, "tangent_space_normal": False,
            "two_sided": False, "dither_opacity_mask": False, "dithered_lod_transition": False}


def _api_evidence(api):
    result = road_material._api_evidence(api)
    engine = Path(api.Paths.convert_relative_path_to_full(api.Paths.engine_dir())).resolve()
    installed = {}
    for name, symbols in (
        *((name, ("U" + name,)) for name in EXTRA_NODE_TYPES),
        ("Material", ("OpacityMaskClipValue", "DitherOpacityMask", "DitheredLODTransition", "TangentSpaceNormal")),
    ):
        if name != "Material":
            require(callable(getattr(api, name, None)), "Required crack expression is missing: " + name)
        candidates = ["Source/Runtime/Engine/" + directory + "/Materials/" + name + ".h" for directory in ("Public", "Classes")]
        matches = [relative for relative in candidates if session._safe_path(engine, relative).is_file()]
        require(bool(matches), "Installed crack material header is missing: " + name)
        path = session._safe_path(engine, matches[0])
        identity = session._identity(path, 2 * 1024 * 1024)
        require(all(symbol in path.read_text(encoding="utf-8-sig") for symbol in symbols),
                "Installed crack material source differs: " + name)
        installed[matches[0]] = {**identity, "verified_symbols": list(symbols)}
    for enum, member in ((api.MaterialVectorCoordTransformSource, "TRANSFORMSOURCE_TANGENT"),
                         (api.MaterialVectorCoordTransform, "TRANSFORM_WORLD"),
                         (api.SamplerSourceMode, "SSM_FROM_TEXTURE_ASSET"), (api.MaterialSamplerType, "SAMPLERTYPE_MASKS")):
        require(hasattr(enum, member), "Required native crack sampler/normal enum is missing: " + member)
    signatures = {}
    for name in ("get_vector_parameter_names", "get_material_instance_vector_parameter_value",
                 "set_material_instance_texture_parameter_value", "set_material_instance_scalar_parameter_value",
                 "set_material_instance_vector_parameter_value"):
        method = getattr(api.MaterialEditingLibrary, name, None)
        doc = str(getattr(method, "__doc__", "") or "")
        require(callable(method) and 0 < len(doc) <= 32768, "Required crack parameter API is unavailable: " + name)
        signatures[name] = {"signature": doc.splitlines()[0], "sha256": hashlib.sha256(doc.encode()).hexdigest()}
    functions = {}
    for name in ("WorldAlignedTexture", "WorldAlignedNormal"):
        package = road_material.PROJECTION_ROOT + name
        loaded = api.load_asset(package)
        require(loaded is not None and loaded.get_path_name() == package + "." + name,
                "Native crack projection function identity differs: " + name)
        relative = "Content/" + package.removeprefix("/Engine/") + ".uasset"
        functions[package] = {"file": relative, **session._identity(session._safe_path(engine, relative), 4 * 1024 * 1024)}
    return {**result, "crack_sources": installed, "crack_parameter_signatures": signatures,
            "projection_function_packages": functions, "engine_source_redistributed": False,
            "normal_space_verified": False}


def _parameters(source_motif, neutral):
    require(neutral.get("source_png_border_verified") is True and neutral.get("ue_normal_space_verified") is False,
            "Crack material requires measured source neutrality without a native normal claim")
    vectors = {"NeutralBaseColor": [*neutral["base_color_linear"], 1.0],
               "NeutralORM": [*neutral["orm_linear"], 1.0], "NeutralNormalXY": [*neutral["normal_xy_bias"], 0.0, 1.0]}
    return {**COMMON_SCALARS, "ExtentCm": float(source_motif["extent_cm"])}, vectors


def _close(actual, expected):
    return type(actual) in (int, float) and math.isfinite(actual) and abs(actual - expected) <= 0.000001


def _verify_instance(api, instance, paths, asphalt, local, scalars, vectors):
    require(instance is not None and isinstance(instance, api.MaterialInstanceConstant)
            and instance.get_path_name() == paths["instance"], "Crack instance identity differs")
    master = instance.get_editor_property("parent")
    require(master is not None and isinstance(master, api.Material) and master.get_path_name() == paths["master"],
            "Crack master identity differs")
    for name, expected in _master_properties(api).items():
        actual = master.get_editor_property(name)
        require(_close(actual, expected) if type(expected) is float else (
            actual is expected if type(expected) is bool else actual == expected), "Crack master property differs: " + name)
    lib, association = api.MaterialEditingLibrary, api.MaterialParameterAssociation.GLOBAL_PARAMETER
    require({str(n) for n in lib.get_texture_parameter_names(instance)} == set(BASE_TEXTURES) | set(LOCAL_TEXTURES)
            and {str(n) for n in lib.get_scalar_parameter_names(instance)} == set(scalars)
            and {str(n) for n in lib.get_vector_parameter_names(instance)} == VECTOR_NAMES,
            "Crack material parameter inventory differs")
    for name, value in scalars.items():
        require(_close(lib.get_material_instance_scalar_parameter_value(instance, name, association), value),
                "Crack scalar differs or neutral probe was not reset: " + name)
    for name, values in vectors.items():
        observed = lib.get_material_instance_vector_parameter_value(instance, name, association)
        require(observed is not None and all(_close(getattr(observed, c, None), v) for c, v in zip("rgba", values, strict=True)),
                "Crack neutral-source parameter differs: " + name)
    expected_textures = {**{p: asphalt[c] for p, c in BASE_TEXTURES.items()}, **{p: local[c] for p, c in LOCAL_TEXTURES.items()}}
    for name, expected in expected_textures.items():
        actual = lib.get_material_instance_texture_parameter_value(instance, name, association)
        require(actual is not None and isinstance(actual, api.Texture2D) and actual.get_path_name() == expected.get_path_name(),
                "Crack material texture identity differs: " + name)
    return instance


def _build_graph(api, master, asphalt, local, scalars, vectors):
    lib, nodes, links, observations = api.MaterialEditingLibrary, [], [], []

    def node(cls, **properties):
        require(len(nodes) < MAX_GRAPH_NODES, "Crack graph exceeded its bounded node budget")
        value = lib.create_material_expression(master, cls)
        require(value is not None, "Native crack expression creation failed")
        nodes.append(value)
        for name, setting in properties.items():
            value.set_editor_property(name, setting)
        return value

    def link(source, target, pin="", output=""):
        require(lib.connect_material_expressions(source, output, target, pin), "Native crack connection failed: " + output + " -> " + pin)
        links.append({"source_node": nodes.index(source), "source_output": output, "target_node": nodes.index(target), "target_input": pin})

    def output(source, prop):
        require(lib.connect_material_property(source, "", prop), "Native crack material output connection failed")

    def binary(cls, a, b):
        result = node(cls)
        link(a, result, "A")
        link(b, result, "B")
        return result

    def unary(cls, source):
        result = node(cls)
        link(source, result)
        return result

    def component(source, index, output_name=""):
        result = node(api.MaterialExpressionComponentMask, r=index == 0, g=index == 1, b=index == 2, a=False)
        link(source, result, output=output_name)
        return result

    def xyz(source, output_name=""):
        result = node(api.MaterialExpressionComponentMask, r=True, g=True, b=True, a=False)
        link(source, result, output=output_name)
        return result

    def constant(value):
        return node(api.MaterialExpressionConstant, r=value)

    def vector(values):
        return node(api.MaterialExpressionConstant3Vector, constant=api.LinearColor(*values, 1.0))

    scalar = {name: node(api.MaterialExpressionScalarParameter, parameter_name=name, group="Road Local Cracks", default_value=value)
              for name, value in scalars.items()}
    neutral = {name: node(api.MaterialExpressionVectorParameter, parameter_name=name, group="Road Local Cracks",
                          default_value=api.LinearColor(*values)) for name, values in vectors.items()}
    # Restore the original source-road projection phase under the one agreed
    # render-only +Z 1 mm lift. This is a texture coordinate, never WPO/PDO.
    source_position = binary(api.MaterialExpressionSubtract, node(api.MaterialExpressionWorldPosition), vector((0.0, 0.0, 0.1)))
    projected = {}
    for parameter, channel in BASE_TEXTURES.items():
        normal = channel == "Normal_DX"
        sample_type = api.MaterialSamplerType.SAMPLERTYPE_NORMAL if normal else (
            api.MaterialSamplerType.SAMPLERTYPE_COLOR if channel == "BaseColor" else api.MaterialSamplerType.SAMPLERTYPE_MASKS)
        texture = node(api.MaterialExpressionTextureObjectParameter, parameter_name=parameter, group="Road Local Cracks",
                       texture=asphalt[channel], sampler_type=sample_type)
        name = "WorldAlignedNormal" if normal else "WorldAlignedTexture"
        function = api.load_asset(road_material.PROJECTION_ROOT + name)
        require(function is not None, "Native crack projection function is missing")
        call = node(api.MaterialExpressionMaterialFunctionCall)
        require(call.set_material_function(function), "Native crack projection assignment failed")
        link(texture, call, "TextureObject")
        link(scalar["TileSizeCm"], call, "TextureSize")
        link(source_position, call, "WorldPosition")
        if normal:
            world_space = node(api.MaterialExpressionStaticBool, value=True)
            require(world_space.get_editor_property("value") is True, "Native WorldSpace switch did not retain true")
            link(world_space, call, "WorldSpace")
            observations.append({"kind": "base_normal_world_space", "value": True})
        projected[channel] = xyz(call, "XYZ Texture")
    uv = node(api.MaterialExpressionTextureCoordinate, coordinate_index=0, u_tiling=1.0, v_tiling=1.0)
    require(uv.get_editor_property("coordinate_index") == 0, "Crack texture coordinate is not UV0")
    samples = {}
    for parameter, channel in LOCAL_TEXTURES.items():
        sample_type = api.MaterialSamplerType.SAMPLERTYPE_NORMAL if channel == "Normal_DX" else (
            api.MaterialSamplerType.SAMPLERTYPE_COLOR if channel == "BaseColor" else api.MaterialSamplerType.SAMPLERTYPE_MASKS)
        sample = node(api.MaterialExpressionTextureSampleParameter2D, parameter_name=parameter, group="Road Local Cracks",
                      texture=local[channel], sampler_type=sample_type, sampler_source=api.SamplerSourceMode.SSM_FROM_TEXTURE_ASSET,
                      const_coordinate=0)
        require(sample.get_editor_property("sampler_source") == api.SamplerSourceMode.SSM_FROM_TEXTURE_ASSET
                and sample.get_editor_property("sampler_type") == sample_type and sample.get_editor_property("const_coordinate") == 0,
                "Native crack sample does not retain its CLAMP/UV0 contract")
        # Empty input selects the first Coordinates socket. This is the native
        # bridge pattern already used by stage3g_author_materials.py.
        link(uv, sample)
        samples[channel] = xyz(sample, "RGB")
        observations.append({"kind": "local_texture_sampler", "parameter": parameter, "uv_channel": 0, "address": "from_clamped_texture"})

    zero, one = constant(0.0), constant(1.0)
    probe = scalar["NeutralProbe"]

    def normal_mix(local_value, base_value):
        result = node(api.MaterialExpressionLinearInterpolate)
        link(local_value, result, "A")
        link(base_value, result, "B")
        link(probe, result, "Alpha")
        return result

    color_ratio = binary(api.MaterialExpressionDivide, samples["BaseColor"], xyz(neutral["NeutralBaseColor"]))
    color = binary(api.MaterialExpressionMultiply, projected["BaseColor"], color_ratio)
    output(normal_mix(color, projected["BaseColor"]), api.MaterialProperty.MP_BASE_COLOR)
    base_rough, local_rough = component(projected["ORM"], 1), component(samples["ORM"], 1)
    rough_delta = binary(api.MaterialExpressionSubtract, local_rough, component(neutral["NeutralORM"], 1))
    rough = unary(api.MaterialExpressionSaturate, binary(api.MaterialExpressionAdd, base_rough, rough_delta))
    output(normal_mix(rough, base_rough), api.MaterialProperty.MP_ROUGHNESS)
    base_ao = component(projected["ORM"], 0)
    ao_ratio = binary(api.MaterialExpressionDivide, component(samples["ORM"], 0), component(neutral["NeutralORM"], 0))
    ao = unary(api.MaterialExpressionSaturate, binary(api.MaterialExpressionMultiply, base_ao, ao_ratio))
    output(normal_mix(ao, base_ao), api.MaterialProperty.MP_AMBIENT_OCCLUSION)

    local_normal = unary(api.MaterialExpressionNormalize, binary(api.MaterialExpressionSubtract,
                         samples["Normal_DX"], xyz(neutral["NeutralNormalXY"])))

    def to_world(value):
        result = node(api.MaterialExpressionTransform,
                      transform_source_type=api.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_TANGENT,
                      transform_type=api.MaterialVectorCoordTransform.TRANSFORM_WORLD)
        require(result.get_editor_property("transform_source_type") == api.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_TANGENT
                and result.get_editor_property("transform_type") == api.MaterialVectorCoordTransform.TRANSFORM_WORLD,
                "Native crack normal transform did not retain tangent-to-world")
        link(value, result)
        observations.append({"kind": "local_normal_transform", "from": "tangent", "to": "world"})
        return result

    local_delta = binary(api.MaterialExpressionSubtract, to_world(local_normal), to_world(vector((0.0, 0.0, 1.0))))
    detail = binary(api.MaterialExpressionMultiply, local_delta, unary(api.MaterialExpressionOneMinus, probe))
    combined = binary(api.MaterialExpressionAdd, projected["Normal_DX"], detail)
    output(unary(api.MaterialExpressionNormalize, combined), api.MaterialProperty.MP_NORMAL)

    mask = binary(api.MaterialExpressionMax, component(samples["DetailMasks"], 0), component(samples["DetailMasks"], 1))
    mask = binary(api.MaterialExpressionMax, mask, component(samples["DetailMasks"], 2))
    u, v = component(uv, 0), component(uv, 1)
    du = binary(api.MaterialExpressionMin, u, unary(api.MaterialExpressionOneMinus, u))
    dv = binary(api.MaterialExpressionMin, v, unary(api.MaterialExpressionOneMinus, v))
    distance_cm = binary(api.MaterialExpressionMultiply, binary(api.MaterialExpressionMin, du, dv), scalar["ExtentCm"])
    border_distance = binary(api.MaterialExpressionSubtract, distance_cm, constant(6.0))
    texel_cm = binary(api.MaterialExpressionDivide, scalar["ExtentCm"], constant(2048.0))
    border = unary(api.MaterialExpressionSaturate, binary(api.MaterialExpressionDivide, border_distance, texel_cm))
    masked = binary(api.MaterialExpressionMultiply, mask, border)
    # Probe=1 intentionally bypasses even the empty border: the full patch is
    # visible for its base-normal comparison, not only the sparse source mask.
    output(normal_mix(masked, one), api.MaterialProperty.MP_OPACITY_MASK)
    output(constant(0.2), api.MaterialProperty.MP_SPECULAR)
    output(zero, api.MaterialProperty.MP_METALLIC)
    output(zero, api.MaterialProperty.MP_EMISSIVE_COLOR)
    return {"node_count": len(nodes), "node_budget": MAX_GRAPH_NODES,
            "native_connections": links, "native_property_observations": observations,
            "normal_space_verified": False}


def _inputs(api, source_root, pins, import_receipt, asphalt_assets, geometry_contracts, source_repo_root):
    sources._context(api)
    local = sources.verify_import(api, source_root, pins, import_receipt, source_repo_root=source_repo_root)
    source = import_receipt["sources"]
    require(isinstance(geometry_contracts, dict) and set(geometry_contracts) == set(source["selected_motifs"]),
            "Crack geometry contract omitted or added a motif")
    expected = {motif: geometry_contract(source["motifs"][motif],
                uv_rotation_degrees=geometry_contracts[motif].get("uv_rotation_degrees")) for motif in source["selected_motifs"]}
    require(geometry_contracts == expected, "Crack geometry, UV frame, border or render offset differs")
    asphalt = road_material._authenticate_asphalt(api, asphalt_assets)
    parameters = {m: _parameters(source["motifs"][m], import_receipt["neutral_sources"][m]) for m in source["selected_motifs"]}
    return source, local, asphalt, parameters


def create_materials(api, source_root, pins, import_receipt, asphalt_assets, geometry_contracts, *, source_repo_root=ROOT):
    """Return (new unsaved instances by motif, receipt); import is a prior step."""
    source, local, asphalt, parameters = _inputs(api, source_root, pins, import_receipt, asphalt_assets, geometry_contracts, source_repo_root)
    paths, evidence = asset_paths(source), _api_evidence(api)
    require(all(not api.EditorAssetLibrary.does_asset_exist(path) for row in paths.values() for path in row.values()),
            "Crack material destination exists; refuse overwrite")
    tools, lib = api.AssetToolsHelpers.get_asset_tools(), api.MaterialEditingLibrary
    first = source["selected_motifs"][0]
    package, name = paths[first]["master"].split(".")[0].rsplit("/", 1)
    master = tools.create_asset(name, package, api.Material, api.MaterialFactoryNew())
    require(master is not None and isinstance(master, api.Material), "New crack master creation failed")
    for prop, value in _master_properties(api).items():
        master.set_editor_property(prop, value)
    graph = _build_graph(api, master, asphalt, local[first], *parameters[first])
    require(not lib.recompile_material(master), "Native crack material compilation failed")
    instances = {}
    for motif, row in paths.items():
        package, name = row["instance"].split(".")[0].rsplit("/", 1)
        instance = tools.create_asset(name, package, api.MaterialInstanceConstant, api.MaterialInstanceConstantFactoryNew())
        require(instance is not None and isinstance(instance, api.MaterialInstanceConstant), "New crack instance creation failed")
        lib.set_material_instance_parent(instance, master)
        # Refresh inherited metadata as in the admitted Material Forge importer.
        lib.update_material_instance(instance)
        scalars, vectors = parameters[motif]
        # Epic UE-291403: these setters may return false after a successful
        # update. Their bool is not a material readback. The complete native
        # parameter inventory and each effective value are checked below by
        # _verify_instance, including the second motif's distinct textures.
        # https://issues.unrealengine.com/issue/UE-291403
        for parameter, channel in LOCAL_TEXTURES.items():
            lib.set_material_instance_texture_parameter_value(instance, parameter, local[motif][channel])
        for parameter, value in scalars.items():
            lib.set_material_instance_scalar_parameter_value(instance, parameter, value)
        for parameter, value in vectors.items():
            lib.set_material_instance_vector_parameter_value(instance, parameter, api.LinearColor(*value))
        lib.update_material_instance(instance)
        instances[motif] = _verify_instance(api, instance, row, asphalt, local[motif], scalars, vectors)
    # These rechecks read existing asphalt and all source/texture identities;
    # creation never edits the pre-existing road assets or the source files.
    _inputs(api, source_root, pins, import_receipt, asphalt_assets, geometry_contracts, source_repo_root)
    require(_api_evidence(api) == evidence, "Installed crack projection/API bytes changed during authoring")
    receipt = {"schema_version": 1, "status": "ROAD_CRACK_MATERIALS_AUTHORED_NATIVE_CANARY_PENDING",
               "engine_version": ENGINE_VERSION, "source_pins_sha256": source["pins_sha256"],
               "import_receipt_sha256": sources.digest(import_receipt), "assets": paths,
               "asphalt_assets": deepcopy(asphalt_assets), "geometry_contracts": deepcopy(geometry_contracts),
               "parameters": {m: {"scalars": s, "vectors": v} for m, (s, v) in parameters.items()},
               "normal_contract": deepcopy(NORMAL_CONTRACT), "neutral_probe": deepcopy(PROBE_CONTRACT),
               "native_api": evidence, "graph_creation": graph, "world_normal_canary_required": True,
               "caller_saved_asset_bytes_required": True, "effective_parameters_read_back": True,
               **{name: False for name in FALSE_FLAGS}}
    return instances, receipt


def verify_materials(api, source_root, pins, import_receipt, material_receipt, asphalt_assets, geometry_contracts, *, source_repo_root=ROOT):
    """Read-only effective native parameters; caller also binds saved asset bytes."""
    source, local, asphalt, parameters = _inputs(api, source_root, pins, import_receipt, asphalt_assets, geometry_contracts, source_repo_root)
    receipt, paths = material_receipt, asset_paths(source)
    require(isinstance(receipt, dict) and receipt.get("schema_version") == 1
            and receipt.get("status") == "ROAD_CRACK_MATERIALS_AUTHORED_NATIVE_CANARY_PENDING"
            and receipt.get("engine_version") == ENGINE_VERSION and receipt.get("assets") == paths
            and receipt.get("source_pins_sha256") == source["pins_sha256"]
            and receipt.get("import_receipt_sha256") == sources.digest(import_receipt)
            and receipt.get("asphalt_assets") == asphalt_assets and receipt.get("geometry_contracts") == geometry_contracts
            and receipt.get("parameters") == {m: {"scalars": s, "vectors": v} for m, (s, v) in parameters.items()}
            and receipt.get("normal_contract") == NORMAL_CONTRACT and receipt.get("neutral_probe") == PROBE_CONTRACT
            and receipt.get("caller_saved_asset_bytes_required") is True and receipt.get("world_normal_canary_required") is True
            and receipt.get("effective_parameters_read_back") is True, "Crack material receipt contract differs")
    sources._false(receipt, FALSE_FLAGS, "Crack material")
    graph = receipt.get("graph_creation", {})
    require(type(graph.get("node_count")) is int and 1 <= graph["node_count"] <= MAX_GRAPH_NODES
            and graph.get("node_budget") == MAX_GRAPH_NODES and graph.get("normal_space_verified") is False,
            "Crack graph receipt exceeds its bounded authority")
    require(receipt.get("native_api") == _api_evidence(api), "Installed crack projection/API identity changed")
    return {m: _verify_instance(api, api.load_asset(paths[m]["instance"]), paths[m], asphalt, local[m], *parameters[m])
            for m in source["selected_motifs"]}

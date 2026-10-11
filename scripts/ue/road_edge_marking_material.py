"""Bounded matte paint for source-clipped road-edge ribbons; no world writes.

Create only a new M/MI pair. The caller owns ribbon geometry, assignment, asset
saving, immutable saved-package identities and fresh-rendered proof. Reuse the
current road's pinned asphalt textures; never import or repair source textures.

UV0.U is normalized across the 10 cm paint ribbon, on both road sides. UV0.V
is source edge station in metres and deliberately does not drive a pattern.
The mask removes only small worn paint margins; the central 8 cm stays solid.
This is a separate paint layer, so masked visibility reveals the underlying
road. It never clips the road, conceals road geometry failures, or adds dither.

Primary UE 5.8 references (installed source/reflection are also recorded):
https://dev.epicgames.com/documentation/unreal-engine/material-blend-modes-in-unreal-engine
https://dev.epicgames.com/documentation/unreal-engine/math-material-expressions-in-unreal-engine
https://dev.epicgames.com/documentation/unreal-engine/coordinates-material-expressions-in-unreal-engine
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import math
from pathlib import Path

from scripts.ci import official_mcp_bob_session as session
from scripts.ue import road_shoulder_material as road_material

ROOT = Path(__file__).resolve().parents[2]
DESTINATION_ROOT = "/Game/Generated/YACS/RoadAsphaltConsumer/EdgeMarkings"
ENGINE_VERSION = road_material.ENGINE_VERSION
UV_CONTRACT = {"channel": 0, "u": "normalized_paint_width", "u_range": [0.0, 1.0],
               "v": "edge_station_metres", "line_width_cm": 10.0}
COLOR = (0.64, 0.63, 0.59, 1.0)  # Linear colour; muted white with slight warmth.
SCALARS = {
    "TileSizeCm": 400.0, "LineWidthCm": 10.0,
    "EdgeWearMinCm": 0.08, "EdgeWearSpanCm": 0.72, "MaskFeatherCm": 0.05,
    "PaintRoughness": 0.90, "PaintSpecular": 0.20, "NormalStrength": 0.35,
}
TEXTURES = {"AsphaltBaseColorTex": "BaseColor", "AsphaltNormalTex": "Normal_DX"}
APPEARANCE = {
    "color_linear_rgba": list(COLOR), "continuous_core_width_cm": 8.0,
    "grain_source": "world_projected_asphalt_basecolor_red_linear",
    # Calibrated from the retained 27f native source: red linear p05=0.05448,
    # p95=0.09759. Clip only outliers, leaving quiet areas between granules.
    "grain_black": 0.05, "grain_white": 0.12,
    "color_multiplier_min": 0.96, "color_multiplier_span": 0.04,
    "roughness_grain_span": 0.05, "opacity_mask_clip_value": 0.5,
    "metallic": 0.0, "emissive": 0.0, "ambient_occlusion": 1.0,
    "edge_wear_only": True, "periodic_dash_or_hole_pattern": False,
}
FALSE_FLAGS = (
    "textures_imported", "source_textures_modified", "world_assignment", "saved",
    "geometry_changed", "road_clipped", "world_position_offset", "pixel_depth_offset",
    "temporal_dither", "owner_visual_pass", "performance_pass",
)
EXTRA_NODE_TYPES = (
    "MaterialExpressionMin", "MaterialExpressionOneMinus",
    "MaterialExpressionVectorParameter", "MaterialExpressionConstant3Vector", "MaterialExpressionDivide",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def asset_paths(destination_root=DESTINATION_ROOT):
    require(destination_root == DESTINATION_ROOT, "Unapproved edge-marking material destination")
    return {role: destination_root + "/" + name + "." + name for role, name in (
        ("master", "M_RoadEdgeMarkings"), ("instance", "MI_RoadEdgeMarkings"))}


def _context(api):
    require(api.SystemLibrary.get_engine_version() == ENGINE_VERSION,
            "Edge-marking material requires the pinned UE 5.8.2 build")
    project = Path(api.Paths.convert_relative_path_to_full(api.Paths.project_dir())).resolve()
    require(project == ROOT.resolve() == session.ROOT.resolve(), "Edge-marking material belongs to another project")


def _api_evidence(api):
    result = road_material._api_evidence(api)
    engine = Path(api.Paths.convert_relative_path_to_full(api.Paths.engine_dir())).resolve()
    installed = {}
    for name, symbols in (
        *((name, ("U" + name,)) for name in EXTRA_NODE_TYPES),
        ("Material", ("OpacityMaskClipValue", "DitherOpacityMask", "DitheredLODTransition", "TangentSpaceNormal")),
    ):
        if name != "Material":
            require(callable(getattr(api, name, None)), "Required native paint expression is missing: " + name)
        candidates = ["Source/Runtime/Engine/" + directory + "/Materials/" + name + ".h"
                      for directory in ("Public", "Classes")]
        matches = [relative for relative in candidates if session._safe_path(engine, relative).is_file()]
        require(bool(matches), "Installed paint material source is missing: " + name)
        path = session._safe_path(engine, matches[0])
        identity = session._identity(path, 2 * 1024 * 1024)
        source = path.read_text(encoding="utf-8-sig")
        require(all(symbol in source for symbol in symbols), "Installed paint material source contract differs: " + name)
        installed[matches[0]] = {**identity, "verified_symbols": list(symbols)}
    signatures = {}
    for name in ("get_vector_parameter_names", "get_material_instance_vector_parameter_value"):
        method = getattr(api.MaterialEditingLibrary, name, None)
        doc = str(getattr(method, "__doc__", "") or "")
        require(callable(method) and 0 < len(doc) <= 32768, "Installed paint readback API is unavailable: " + name)
        signatures[name] = {"signature": doc.splitlines()[0], "sha256": hashlib.sha256(doc.encode()).hexdigest()}
    return {**result, "paint_sources": installed, "paint_readback_signatures": signatures,
            "engine_source_redistributed": False}


def _master_properties(api):
    return {
        "material_domain": api.MaterialDomain.MD_SURFACE,
        "shading_model": api.MaterialShadingModel.MSM_DEFAULT_LIT,
        "blend_mode": api.BlendMode.BLEND_MASKED,
        "opacity_mask_clip_value": APPEARANCE["opacity_mask_clip_value"],
        "tangent_space_normal": True, "two_sided": False,
        "dither_opacity_mask": False, "dithered_lod_transition": False,
    }


def _close(actual, expected):
    return type(actual) in (int, float) and math.isfinite(actual) and abs(actual - expected) <= 0.000001


def _verify_instance(api, instance, paths, textures):
    require(instance is not None and isinstance(instance, api.MaterialInstanceConstant)
            and instance.get_path_name() == paths["instance"], "Edge paint instance identity differs")
    master = instance.get_editor_property("parent")
    require(master is not None and isinstance(master, api.Material)
            and master.get_path_name() == paths["master"], "Edge paint master identity differs")
    for name, expected in _master_properties(api).items():
        actual = master.get_editor_property(name)
        require(_close(actual, expected) if type(expected) is float else (
            actual is expected if type(expected) is bool else actual == expected),
            "Edge paint master property differs: " + name)
    lib, association = api.MaterialEditingLibrary, api.MaterialParameterAssociation.GLOBAL_PARAMETER
    require({str(name) for name in lib.get_texture_parameter_names(instance)} == set(TEXTURES)
            and {str(name) for name in lib.get_scalar_parameter_names(instance)} == set(SCALARS)
            and {str(name) for name in lib.get_vector_parameter_names(instance)} == {"PaintColor"},
            "Edge paint parameter inventory differs")
    for name, expected in SCALARS.items():
        require(_close(lib.get_material_instance_scalar_parameter_value(instance, name, association), expected),
                "Edge paint scalar value differs: " + name)
    color = lib.get_material_instance_vector_parameter_value(instance, "PaintColor", association)
    require(color is not None and all(_close(getattr(color, channel, None), expected)
                                     for channel, expected in zip("rgba", COLOR, strict=True)),
            "Edge paint is not the specified muted warm white")
    for parameter, channel in TEXTURES.items():
        texture = lib.get_material_instance_texture_parameter_value(instance, parameter, association)
        require(texture is not None and isinstance(texture, api.Texture2D)
                and texture.get_path_name() == textures[channel].get_path_name(),
                "Edge paint uses a foreign asphalt texture: " + parameter)
        road_material._verify_texture_settings(api, texture, channel)
    return instance


def _build_graph(api, master, textures):
    """Author one bounded new paint graph; every connection needs native success."""
    lib = api.MaterialEditingLibrary

    def node(cls, **properties):
        value = lib.create_material_expression(master, cls)
        require(value is not None, "Edge paint expression creation failed")
        for name, setting in properties.items():
            value.set_editor_property(name, setting)
        return value

    def link(source, target, pin="", output=""):
        require(lib.connect_material_expressions(source, output, target, pin),
                "Edge paint graph connection failed: " + output + " -> " + pin)

    def output(source, prop):
        require(lib.connect_material_property(source, "", prop), "Edge paint property connection failed")

    def constant(value):
        return node(api.MaterialExpressionConstant, r=value)

    scalar_nodes = {name: node(api.MaterialExpressionScalarParameter,
                             parameter_name=name, group="Road Edge Paint", default_value=value)
                    for name, value in SCALARS.items()}

    def binary(cls, a, b):
        value = node(cls)
        link(a, value, "A")
        link(b, value, "B")
        return value

    def saturate(value):
        result = node(api.MaterialExpressionSaturate)
        link(value, result)
        return result

    def mask(value, output_name=""):
        result = node(api.MaterialExpressionComponentMask, r=True, g=False, b=False, a=False)
        link(value, result, output=output_name)
        return result

    projected = {}
    for parameter, channel in TEXTURES.items():
        normal = channel == "Normal_DX"
        texture = node(api.MaterialExpressionTextureObjectParameter, parameter_name=parameter,
                       group="Road Edge Paint", texture=textures[channel], sampler_type=(
                           api.MaterialSamplerType.SAMPLERTYPE_NORMAL if normal else api.MaterialSamplerType.SAMPLERTYPE_COLOR))
        function = api.load_asset(road_material.PROJECTION_ROOT + ("WorldAlignedNormal" if normal else "WorldAlignedTexture"))
        require(function is not None, "Native paint projection function is missing")
        call = node(api.MaterialExpressionMaterialFunctionCall)
        require(call.set_material_function(function), "Native paint projection assignment failed")
        link(texture, call, "TextureObject")
        link(scalar_nodes["TileSizeCm"], call, "TextureSize")
        if normal:
            link(node(api.MaterialExpressionStaticBool, value=False), call, "WorldSpace")
        projected[channel] = call

    red = mask(projected["BaseColor"], "XYZ Texture")
    shifted = binary(api.MaterialExpressionSubtract, red, constant(APPEARANCE["grain_black"]))
    grain = saturate(binary(api.MaterialExpressionMultiply, shifted,
                           constant(1.0 / (APPEARANCE["grain_white"] - APPEARANCE["grain_black"]))))
    uv = node(api.MaterialExpressionTextureCoordinate, coordinate_index=UV_CONTRACT["channel"], u_tiling=1.0, v_tiling=1.0)
    u = mask(uv)
    opposite = node(api.MaterialExpressionOneMinus)
    link(u, opposite)
    distance = binary(api.MaterialExpressionMultiply, binary(api.MaterialExpressionMin, u, opposite), scalar_nodes["LineWidthCm"])
    retreat = binary(api.MaterialExpressionAdd, scalar_nodes["EdgeWearMinCm"],
                     binary(api.MaterialExpressionMultiply, grain, scalar_nodes["EdgeWearSpanCm"]))
    # Only the literal paint border can wear away. The full raw mask equals one
    # across at least the middle 8 cm for every possible sampled grain value.
    feather = node(api.MaterialExpressionDivide)
    link(binary(api.MaterialExpressionSubtract, distance, retreat), feather, "A")
    link(scalar_nodes["MaskFeatherCm"], feather, "B")
    output(saturate(feather), api.MaterialProperty.MP_OPACITY_MASK)

    color = node(api.MaterialExpressionVectorParameter, parameter_name="PaintColor",
                 group="Road Edge Paint", default_value=api.LinearColor(*COLOR))
    modulation = binary(api.MaterialExpressionAdd, constant(APPEARANCE["color_multiplier_min"]),
                        binary(api.MaterialExpressionMultiply, grain, constant(APPEARANCE["color_multiplier_span"])))
    output(binary(api.MaterialExpressionMultiply, color, modulation), api.MaterialProperty.MP_BASE_COLOR)
    output(binary(api.MaterialExpressionAdd, scalar_nodes["PaintRoughness"],
                  binary(api.MaterialExpressionMultiply, grain, constant(APPEARANCE["roughness_grain_span"]))),
           api.MaterialProperty.MP_ROUGHNESS)
    normal = node(api.MaterialExpressionLinearInterpolate)
    link(node(api.MaterialExpressionConstant3Vector, constant=api.LinearColor(0.0, 0.0, 1.0, 1.0)), normal, "A")
    link(projected["Normal_DX"], normal, "B", "XYZ Texture")
    link(scalar_nodes["NormalStrength"], normal, "Alpha")
    normalized = node(api.MaterialExpressionNormalize)
    link(normal, normalized)
    output(normalized, api.MaterialProperty.MP_NORMAL)
    output(scalar_nodes["PaintSpecular"], api.MaterialProperty.MP_SPECULAR)
    output(constant(0.0), api.MaterialProperty.MP_METALLIC)
    output(constant(0.0), api.MaterialProperty.MP_EMISSIVE_COLOR)
    output(constant(1.0), api.MaterialProperty.MP_AMBIENT_OCCLUSION)


def create_material(api, destination_root, asphalt_assets, uv_contract):
    """Return (new unsaved MI, receipt); do not assign a mesh, save, or import."""
    paths = asset_paths(destination_root)
    require(uv_contract == UV_CONTRACT, "Edge paint UV/physical width contract differs from its ribbon")
    _context(api)
    textures = road_material._authenticate_asphalt(api, asphalt_assets)
    evidence = _api_evidence(api)
    require(all(not api.EditorAssetLibrary.does_asset_exist(path) for path in paths.values()),
            "Edge-marking material already exists; refuse overwrite")
    assets = api.AssetToolsHelpers.get_asset_tools()
    master = assets.create_asset("M_RoadEdgeMarkings", destination_root, api.Material, api.MaterialFactoryNew())
    require(master is not None and master.get_path_name() == paths["master"], "Edge paint master creation failed")
    for name, value in _master_properties(api).items():
        master.set_editor_property(name, value)
    _build_graph(api, master, textures)
    lib = api.MaterialEditingLibrary
    require(not lib.recompile_material(master), "Edge paint material compilation reported errors")
    instance = assets.create_asset("MI_RoadEdgeMarkings", destination_root,
                                   api.MaterialInstanceConstant, api.MaterialInstanceConstantFactoryNew())
    require(instance is not None and instance.get_path_name() == paths["instance"], "Edge paint instance creation failed")
    lib.set_material_instance_parent(instance, master)
    lib.update_material_instance(instance)
    _verify_instance(api, instance, paths, textures)
    road_material._authenticate_asphalt(api, asphalt_assets)
    receipt = {
        "schema_version": 1, "status": "EDGE_MARKING_MATERIAL_CREATED_REVIEW_PENDING",
        "engine_version": ENGINE_VERSION, "assets": paths, "asphalt_assets": deepcopy(asphalt_assets),
        "texture_objects": {channel: textures[channel].get_path_name() for channel in TEXTURES.values()},
        "uv_contract": deepcopy(UV_CONTRACT), "appearance": deepcopy(APPEARANCE),
        "scalar_parameters": dict(SCALARS), "normal_convention": "DirectX",
        "blend_mode": "BLEND_MASKED", "mask_applies_to": "new_paint_ribbon_only",
        "caller_saved_asset_bytes_required": True, "native_api": evidence,
        **dict.fromkeys(FALSE_FLAGS, False),
    }
    return instance, receipt


def verify_material(api, receipt, asphalt_assets, uv_contract):
    """Read actual saved native values; do not reapply or repair any binding.

    The caller must separately authenticate saved M/MI and texture package
    bytes. This function does not claim fresh graph traversal or visual PASS.
    """
    _context(api)
    require(isinstance(receipt, dict) and receipt.get("schema_version") == 1
            and receipt.get("status") == "EDGE_MARKING_MATERIAL_CREATED_REVIEW_PENDING"
            and receipt.get("engine_version") == ENGINE_VERSION
            and receipt.get("assets") == asset_paths()
            and receipt.get("asphalt_assets") == asphalt_assets == road_material.asphalt_asset_paths()
            and receipt.get("uv_contract") == uv_contract == UV_CONTRACT
            and receipt.get("appearance") == APPEARANCE
            and receipt.get("scalar_parameters") == SCALARS
            and receipt.get("normal_convention") == "DirectX"
            and receipt.get("blend_mode") == "BLEND_MASKED"
            and receipt.get("mask_applies_to") == "new_paint_ribbon_only"
            and receipt.get("caller_saved_asset_bytes_required") is True
            and all(receipt.get(name) is False for name in FALSE_FLAGS),
            "Edge paint receipt or source contract differs")
    textures = road_material._authenticate_asphalt(api, asphalt_assets)
    require(receipt.get("texture_objects") == {channel: textures[channel].get_path_name() for channel in TEXTURES.values()},
            "Edge paint source texture inventory differs")
    return _verify_instance(api, api.load_asset(receipt["assets"]["instance"]), receipt["assets"], textures)

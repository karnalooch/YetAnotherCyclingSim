"""Build one fixed five-role master in the isolated engine Entry map.

Only generated preparation packages in the disposable checkout are saved. The
fresh scene process consumes these packages and restores all live bindings.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.ue.sa_calobra_whole_map_prep import (
    DOMAIN_COLORS,
    INSTANCE_NAME,
    INSTANCE_PATH,
    MASTER_NAME,
    MASTER_PACKAGE,
    MASTER_PATH,
    ROLES,
    SCALARS,
    assert_isolated_bootstrap,
    asset_file,
    canonical,
    digest,
    drain_compilation,
    load_inputs,
    memory_checkpoint,
    package_files,
    rendering_recipe,
    source_assets,
    write_json,
)

LIB = unreal.MaterialEditingLibrary
WEIGHT_PATH = MASTER_PACKAGE + "/T_WholeMapWeights"
TEXTURE_PARAMETERS = ["WeightTex"] + [
    role + channel + "Tex" for role in ROLES for channel in ("BaseColor", "Normal")
]
SCALAR_PARAMETERS = list(SCALARS) + [
    role + suffix for role in ROLES for suffix in ("TileSizeCm", "Roughness")
]


def load_required(path):
    value = unreal.load_asset(path)
    if value is None:
        raise RuntimeError("Whole-map preparation asset is missing: " + path)
    return value


class Graph:
    def __init__(self, material):
        self.material, self.nodes = material, []

    def node(self, cls, **properties):
        node = LIB.create_material_expression(self.material, cls)
        if node is None:
            raise RuntimeError(
                "Cannot create native material expression: " + cls.__name__
            )
        self.nodes.append(node)
        for key, value in properties.items():
            node.set_editor_property(key, value)
        return node

    @staticmethod
    def link(source, target, pin, output=""):
        if not LIB.connect_material_expressions(source, output, target, pin):
            raise RuntimeError(
                "Native material pin connection failed: " + output + " -> " + pin
            )

    def unary(self, cls, source, **props):
        node = self.node(cls, **props)
        self.link(source, node, "")
        return node

    def binary(self, cls, a, b=None, **props):
        node = self.node(cls, **props)
        self.link(a, node, "A")
        if b is not None:
            self.link(b, node, "B")
        return node

    def scalar(self, name, value):
        return self.node(
            unreal.MaterialExpressionScalarParameter,
            parameter_name=name,
            group="Whole Map Preparation",
            default_value=float(value),
        )

    def constant(self, value):
        return self.node(unreal.MaterialExpressionConstant, r=float(value))

    def color(self, values):
        return self.node(
            unreal.MaterialExpressionConstant3Vector,
            constant=unreal.LinearColor(*values, 1.0),
        )

    def lerp(self, a, b, alpha):
        node = self.node(unreal.MaterialExpressionLinearInterpolate)
        self.link(a, node, "A")
        self.link(b, node, "B")
        self.link(alpha, node, "Alpha")
        return node

    def channel(self, value, channel, output=""):
        node = self.node(
            unreal.MaterialExpressionComponentMask,
            **{name: name == channel for name in ("r", "g", "b", "a")},
        )
        self.link(value, node, "", output)
        return node

    def project(self, texture, tile, normal):
        function = load_required(
            "/Engine/Functions/Engine_MaterialFunctions01/Texturing/"
            + ("WorldAlignedNormal" if normal else "WorldAlignedTexture")
        )
        call = self.node(unreal.MaterialExpressionMaterialFunctionCall)
        if not call.set_material_function(function):
            raise RuntimeError("Native metric material function unavailable")
        self.link(texture, call, "TextureObject")
        self.link(tile, call, "TextureSize")
        if normal:
            self.link(
                self.node(unreal.MaterialExpressionStaticBool, value=False),
                call,
                "WorldSpace",
            )
        # A multiply is an explicit output adapter, keeping all downstream
        # arithmetic on the usual output pin rather than guessing function pins.
        output = self.node(unreal.MaterialExpressionMultiply, const_b=1.0)
        self.link(call, output, "A", "XYZ Texture")
        return output

    def output(self, node, prop):
        if not LIB.connect_material_property(node, "", prop):
            raise RuntimeError("Native material output connection failed")


def import_weight(inputs):
    task = unreal.AssetImportTask()
    for key, value in {
        "filename": str(inputs["root"] / "material-weights.png"),
        "destination_path": MASTER_PACKAGE,
        "destination_name": "T_WholeMapWeights",
        "automated": True,
        "replace_existing": False,
        "save": False,
    }.items():
        task.set_editor_property(key, value)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported = task.get_editor_property("imported_object_paths")
    if len(imported) != 1:
        raise RuntimeError("Whole-grid weight texture import failed")
    texture = load_required(imported[0])
    for key, value in {
        "srgb": False,
        "filter": unreal.TextureFilter.TF_BILINEAR,
        "address_x": unreal.TextureAddress.TA_CLAMP,
        "address_y": unreal.TextureAddress.TA_CLAMP,
        "compression_settings": unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP,
        "never_stream": False,
    }.items():
        texture.set_editor_property(key, value)
        if texture.get_editor_property(key) != value:
            raise RuntimeError("Whole-grid data texture setting failed: " + key)
    return texture


def build_graph(material, weights, textures, recipe):
    graph = Graph(material)
    add, multiply = unreal.MaterialExpressionAdd, unreal.MaterialExpressionMultiply
    subtract, divide = (
        unreal.MaterialExpressionSubtract,
        unreal.MaterialExpressionDivide,
    )
    params = {name: graph.scalar(name, value) for name, value in SCALARS.items()}
    position = graph.node(unreal.MaterialExpressionWorldPosition)
    xy = graph.node(
        unreal.MaterialExpressionComponentMask, r=True, g=True, b=False, a=False
    )
    graph.link(position, xy, "")
    offset = graph.node(unreal.MaterialExpressionConstant2Vector, r=25.0, g=25.0)
    uv = graph.binary(divide, graph.binary(add, xy, offset), const_b=201650.0)
    sample = graph.node(
        unreal.MaterialExpressionTextureSampleParameter2D,
        texture=weights,
        sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR,
        parameter_name="WeightTex",
        group="Whole Map Preparation",
    )
    graph.link(uv, sample, "")
    r, g, b, alpha = [
        graph.channel(sample, name, "RGBA") for name in ("r", "g", "b", "a")
    ]
    rgb_sum = graph.binary(add, graph.binary(add, r, g), b)
    residual = graph.unary(
        unreal.MaterialExpressionSaturate,
        graph.unary(unreal.MaterialExpressionOneMinus, rgb_sum),
    )
    underneath = graph.unary(unreal.MaterialExpressionOneMinus, alpha)
    weights_by_role = {
        role: graph.binary(multiply, weight, underneath)
        for role, weight in zip(ROLES[:4], (r, g, b, residual), strict=True)
    }
    weights_by_role["Scree"] = alpha

    sums = {}
    for role in ROLES:
        settings = recipe["roles"][role]
        tile = graph.scalar(role + "TileSizeCm", settings["tile_cm"])
        roughness = graph.scalar(role + "Roughness", settings["roughness"])
        projected = {"Roughness": roughness, "Domain": graph.color(DOMAIN_COLORS[role])}
        for channel in ("BaseColor", "Normal"):
            normal = channel == "Normal"
            texture = graph.node(
                unreal.MaterialExpressionTextureObjectParameter,
                texture=textures[role][channel],
                parameter_name=role + channel + "Tex",
                group="Whole Map Preparation",
                sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL
                if normal
                else unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,
            )
            projected[channel] = graph.project(texture, tile, normal)
        for channel, value in projected.items():
            weighted = graph.binary(multiply, value, weights_by_role[role])
            sums[channel] = (
                graph.binary(add, sums[channel], weighted)
                if channel in sums
                else weighted
            )

    distance = graph.binary(
        unreal.MaterialExpressionDistance,
        position,
        graph.node(unreal.MaterialExpressionCameraPositionWS),
    )
    interval = graph.binary(
        unreal.MaterialExpressionMax,
        graph.binary(subtract, params["FarDetailEndCm"], params["NearDetailStartCm"]),
        const_b=1.0,
    )
    fade = graph.unary(
        unreal.MaterialExpressionOneMinus,
        graph.unary(
            unreal.MaterialExpressionSaturate,
            graph.binary(
                divide,
                graph.binary(subtract, distance, params["NearDetailStartCm"]),
                interval,
            ),
        ),
    )
    factor = graph.lerp(fade, params["ForcedDetailFactor"], params["ForceDetailMix"])
    normal = graph.unary(unreal.MaterialExpressionNormalize, sums["Normal"])
    normal = graph.unary(
        unreal.MaterialExpressionNormalize,
        graph.lerp(
            graph.color([0.0, 0.0, 1.0]),
            normal,
            graph.binary(multiply, factor, params["MicroNormalStrength"]),
        ),
    )

    # A one-metre analytic XY checker demonstrates registration and metric
    # scale, without importing an extra texture or consuming another sampler.
    checker_xy = graph.binary(divide, xy, params["CheckerCellSizeCm"])
    checker_sum = graph.binary(
        add,
        graph.unary(unreal.MaterialExpressionFloor, graph.channel(checker_xy, "r")),
        graph.unary(unreal.MaterialExpressionFloor, graph.channel(checker_xy, "g")),
    )
    checker = graph.binary(
        multiply,
        graph.unary(
            unreal.MaterialExpressionFrac,
            graph.binary(multiply, checker_sum, const_b=0.5),
        ),
        const_b=2.0,
    )
    checker_color = graph.lerp(
        graph.color([0.025, 0.025, 0.025]), graph.color([0.8, 0.8, 0.8]), checker
    )
    diagnostic = graph.binary(
        unreal.MaterialExpressionMax, params["DomainMix"], params["CheckerMix"]
    )
    diagnostic_color = graph.lerp(sums["Domain"], checker_color, params["CheckerMix"])
    # Diagnostics emit their legend colors. The ordinary preparation mode keeps
    # the exact same macro albedo while camera distance changes only micro normals.
    graph.output(
        graph.binary(
            multiply,
            sums["BaseColor"],
            graph.unary(unreal.MaterialExpressionOneMinus, diagnostic),
        ),
        unreal.MaterialProperty.MP_BASE_COLOR,
    )
    graph.output(
        graph.binary(multiply, diagnostic_color, diagnostic),
        unreal.MaterialProperty.MP_EMISSIVE_COLOR,
    )
    graph.output(
        graph.lerp(normal, graph.color([0.0, 0.0, 1.0]), diagnostic),
        unreal.MaterialProperty.MP_NORMAL,
    )
    graph.output(sums["Roughness"], unreal.MaterialProperty.MP_ROUGHNESS)
    # No WPO, pixel depth offset, displacement, tessellation, AO, or opacity.
    return len(graph.nodes)


def main():
    if not unreal.SystemLibrary.get_engine_version().startswith("5.8.2-56702186"):
        raise RuntimeError("Unverified Unreal Engine version")
    bootstrap_world = assert_isolated_bootstrap(unreal)
    # Matching installed headers are also bound by the workflow before this
    # process. Require the actual reflected classes before creating any assets.
    for name in (
        "MaterialExpressionCameraPositionWS",
        "MaterialExpressionDistance",
        "MaterialExpressionFloor",
        "MaterialExpressionFrac",
        "MaterialExpressionMax",
    ):
        if not hasattr(unreal, name):
            raise RuntimeError("Unverified native preparation node: " + name)
    memory = [memory_checkpoint("before_preparation", 8, 12)]
    inputs = load_inputs(Path(os.environ["YACS_WHOLE_MAP_PREP"]))
    identities, recipe = source_assets(), rendering_recipe()
    paths = (MASTER_PATH, INSTANCE_PATH, WEIGHT_PATH)
    if any(unreal.EditorAssetLibrary.does_asset_exist(path) for path in paths):
        raise RuntimeError("Whole-map bootstrap requires a clean generated package")
    textures = {
        role: {
            channel: load_required(row["asset"])
            for channel, row in identities[role].items()
        }
        for role in ROLES
    }
    weight = import_weight(inputs)
    all_textures = [weight] + [
        texture for maps in textures.values() for texture in maps.values()
    ]
    if not unreal.YacsTextureAuditLibrary.finish_texture_compilation(all_textures):
        raise RuntimeError("Whole-map input texture compilation failed")
    texture_readbacks = [
        json.loads(unreal.YacsTextureAuditLibrary.describe_texture(texture))
        for texture in all_textures
    ]
    if any(
        row.get("is_default_texture", True) or row.get("is_compiling", True)
        for row in texture_readbacks
    ):
        raise RuntimeError("Whole-map texture fallback or pending compilation")
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        MASTER_NAME, MASTER_PACKAGE, unreal.Material, unreal.MaterialFactoryNew()
    )
    if material is None:
        raise RuntimeError("Whole-map fixed master could not be created")
    material.set_editor_property(
        "shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT
    )
    material.set_editor_property("tangent_space_normal", True)
    if material.get_editor_property("tangent_space_normal") is not True:
        raise RuntimeError("Whole-map material normal-space setting differs")
    node_count = build_graph(material, weight, textures, recipe)
    errors = LIB.recompile_material(material)
    if errors:
        raise RuntimeError("Whole-map fixed master compilation failed: " + str(errors))
    LIB.layout_material_expressions(material)
    instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        INSTANCE_NAME,
        MASTER_PACKAGE,
        unreal.MaterialInstanceConstant,
        unreal.MaterialInstanceConstantFactoryNew(),
    )
    if instance is None:
        raise RuntimeError("Whole-map preparation instance could not be created")
    LIB.set_material_instance_parent(instance, material)
    LIB.update_material_instance(instance)
    drain = drain_compilation(unreal)
    if {str(name) for name in LIB.get_texture_parameter_names(instance)} != set(
        TEXTURE_PARAMETERS
    ):
        raise RuntimeError("Whole-map texture parameter contract differs")
    if {str(name) for name in LIB.get_scalar_parameter_names(instance)} != set(
        SCALAR_PARAMETERS
    ):
        raise RuntimeError("Whole-map scalar parameter contract differs")
    for asset in (weight, material, instance):
        if not unreal.EditorAssetLibrary.save_loaded_asset(
            asset, only_if_is_dirty=False
        ):
            raise RuntimeError("Whole-map preparation package save failed")
    generated = [
        {
            "asset": path,
            "file": asset_file(path).relative_to(ROOT).as_posix(),
            "sha256": digest(asset_file(path)),
            "size_bytes": asset_file(path).stat().st_size,
            "package_files": package_files(path),
        }
        for path in paths
    ]
    receipt = {
        "schema_version": 1,
        "status": "WHOLE_MAP_FIXED_MASTER_SAVED",
        "exact_sha": os.environ["YACS_CLIFF_VISUAL_EXPECTED_SHA"],
        "master": MASTER_PATH,
        "instance": INSTANCE_PATH,
        "prep_manifest_sha256": inputs["manifest_sha256"],
        "rendering_recipe": recipe,
        "rendering_recipe_sha256": hashlib.sha256(canonical(recipe)).hexdigest(),
        "source_assets": identities,
        "generated_assets": generated,
        "texture_parameters": TEXTURE_PARAMETERS,
        "scalar_parameters": SCALAR_PARAMETERS,
        "texture_readbacks": texture_readbacks,
        "node_count": node_count,
        "compile_drain": drain,
        "memory_checkpoints": memory,
        "bootstrap_world": bootstrap_world,
        "map_loaded": False,
        "working_map_loaded": False,
        "engine_entry_map_loaded": True,
        "map_saved": False,
        "geometry_changed": False,
        "final_material_acceptance": "PENDING_OWNER",
        "shader_cost_reduction_claimed": False,
    }
    write_json(Path(os.environ["YACS_WHOLE_MAP_MASTER_RECEIPT"]), receipt)
    unreal.log(
        "YACS_WHOLE_MAP_MASTER "
        + json.dumps({key: receipt[key] for key in ("status", "master", "node_count")})
    )


if __name__ == "__main__":
    main()

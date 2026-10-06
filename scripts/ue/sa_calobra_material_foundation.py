"""Author/apply a native, reversible 2B material on the current frozen Landscape.

No map load/save, height import, road build, displacement or PCG operation.
Run apply_foundation() in the existing UE 5.8.2 authoring editor.
"""

import builtins
import hashlib
import json
import sys
from pathlib import Path

import unreal

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.manage_local_workspace import load_workspace  # noqa: E402

LIB = unreal.MaterialEditingLibrary


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_required(path):
    asset = unreal.load_asset(path)
    if asset is None:
        raise RuntimeError("Required material asset missing: " + path)
    return asset


def verified_inputs(path):
    value = json.loads(path.read_text(encoding="utf8"))
    content = {k: v for k, v in value.items() if k != "fingerprint"}
    if (
        hashlib.sha256(
            json.dumps(
                content, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
        != value["fingerprint"]
    ):
        raise RuntimeError("Stale material input manifest")
    if (
        value["status"] != "PRESENTATION_FALLBACK_MATERIAL_INPUTS"
        or value["geometry_mutation"] is not False
    ):
        raise RuntimeError("Unexpected material input contract")
    producer = REPO / "scripts/assets/prepare_sa_calobra_material_inputs.py"
    if (
        hashlib.sha256(producer.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        != value["producer_sha256_lf"]
    ):
        raise RuntimeError(
            "Material input producer identity changed; regenerate inputs"
        )
    grid = value["grid"]
    if (grid["crs"], grid["width"], grid["height"], grid["transform"]) != (
        "EPSG:25831",
        4033,
        4033,
        [0.5, 0, 483000, 0, -0.5, 4409516.5],
    ):
        raise RuntimeError("Material input grid is not the frozen grid")
    for row in value["outputs"]:
        relative = Path(row["path"])
        if relative.is_absolute() or len(relative.parts) != 1:
            raise RuntimeError("Unsafe material input path")
        source = path.parent / relative
        if (
            source.stat().st_size != row["size_bytes"]
            or digest(source) != row["sha256"]
        ):
            raise RuntimeError("Stale packed material input")
    # The derived bytes cannot substitute for the two pinned upstream manifests.
    for source in value["sources"]:
        if digest(source["path"]) != source["sha256"]:
            raise RuntimeError("Material upstream manifest changed")
    return value


def scene_snapshot(world, landscape, map_file):
    def numeric_tuple(value):
        if hasattr(value, "to_tuple"):
            return tuple(numeric_tuple(item) for item in value.to_tuple())
        return float(value)

    actors = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    traces = []
    for x in (25000, 100000, 175000):
        for y in (25000, 100000, 175000):
            hit = unreal.SystemLibrary.line_trace_single(
                world,
                unreal.Vector(x, y, 150000),
                unreal.Vector(x, y, 0),
                unreal.TraceTypeQuery.ECC_VISIBILITY,
                True,
                [],
                unreal.DrawDebugTrace.NONE,
                True,
            )
            positions = [
                (float(point.x), float(point.y), float(point.z))
                for point in (() if hit is None else hit.to_tuple())
                if all(hasattr(point, name) for name in ("x", "y", "z"))
                and abs(point.x - x) < 0.1
                and abs(point.y - y) < 0.1
                and 0 < point.z < 150000
            ]
            if not positions:
                raise RuntimeError("Frozen Landscape trace missed")
            traces.append(positions)
    return {
        "actors": sorted(
            (a.get_path_name(), numeric_tuple(a.get_actor_transform())) for a in actors
        ),
        "components": sorted(
            c.get_path_name()
            for c in landscape.get_components_by_class(unreal.LandscapeComponent)
        ),
        "layers": [
            str(layer.get_name_bp()) for layer in landscape.get_edit_layers_bp()
        ],
        "traces": traces,
        "saved_map_sha256": digest(map_file),
    }


def create_material(recipe, manifest, input_root, key):
    package = recipe["package"]
    texture_name, material_name = "T_Weights_" + key, "M_Foundation_" + key
    for name in (texture_name, material_name):
        if unreal.EditorAssetLibrary.does_asset_exist(package + "/" + name):
            raise RuntimeError("Existing asset collision; no overwrite: " + name)
    task = unreal.AssetImportTask()
    for prop, value in {
        "filename": str(input_root / "material-weights.png"),
        "destination_path": package,
        "destination_name": texture_name,
        "automated": True,
        "replace_existing": False,
        "save": False,
    }.items():
        task.set_editor_property(prop, value)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths = task.get_editor_property("imported_object_paths")
    if len(paths) != 1:
        raise RuntimeError("Weight import did not produce exactly one asset")
    texture = load_required(paths[0])
    for prop, value in {
        "srgb": False,
        "filter": unreal.TextureFilter.TF_BILINEAR,
        "address_x": unreal.TextureAddress.TA_CLAMP,
        "address_y": unreal.TextureAddress.TA_CLAMP,
        "mip_gen_settings": unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS,
        "compression_settings": unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP,
        "never_stream": True,
    }.items():
        texture.set_editor_property(prop, value)
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        material_name, package, unreal.Material, unreal.MaterialFactoryNew()
    )
    if material is None:
        raise RuntimeError("Material creation failed")
    material.set_editor_property(
        "shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT
    )
    nodes = []

    def node(cls, **props):
        value = LIB.create_material_expression(
            material, cls, -300 * (1 + len(nodes) % 6), 160 * (len(nodes) // 6)
        )
        if value is None:
            raise RuntimeError("Material node creation failed")
        for prop, setting in props.items():
            value.set_editor_property(prop, setting)
        nodes.append(value)
        return value

    def link(source, output, target, pin):
        if pin and pin not in LIB.get_material_expression_input_names(target):
            raise RuntimeError("Native material input missing: " + pin)
        if output and output not in LIB.get_material_expression_output_names(source):
            raise RuntimeError("Native material output missing: " + output)
        if not LIB.connect_material_expressions(source, output, target, pin):
            raise RuntimeError("Material link failed: " + output + " -> " + pin)

    def vector(name, rgb):
        return node(
            unreal.MaterialExpressionVectorParameter,
            parameter_name=name,
            default_value=unreal.LinearColor(*rgb, 1),
        )

    position = node(unreal.MaterialExpressionWorldPosition)
    xy = node(unreal.MaterialExpressionComponentMask, r=True, g=True, b=False, a=False)
    link(position, "", xy, "")
    bounds = manifest["world_mapping"]["footprint_world_bounds_cm"]
    offset = node(unreal.MaterialExpressionConstant2Vector, r=-bounds[0], g=-bounds[1])
    add = node(unreal.MaterialExpressionAdd)
    link(xy, "", add, "A")
    link(offset, "", add, "B")
    divide = node(
        unreal.MaterialExpressionDivide,
        const_b=manifest["grid"]["width"] * manifest["grid"]["pixel_size_m"] * 100,
    )
    link(add, "", divide, "A")
    weights = node(
        unreal.MaterialExpressionTextureSample,
        texture=texture,
        sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR,
    )
    link(divide, "", weights, "")
    world_space = node(unreal.MaterialExpressionStaticBool, value=False)

    def project_channels(layer):
        tile_cm = layer["tile_size_m"] * 100
        size = vector(layer["id"] + "TileSizeCm", [tile_cm] * 3)
        projected = {}
        for channel, suffix, sampler in (
            ("color", "BaseColor", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR),
            (
                "roughness",
                "Roughness",
                unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR,
            ),
            ("normal", "Normal", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL),
        ):
            source = load_required(layer["texture_family"] + "_" + suffix)
            tex_object = node(
                unreal.MaterialExpressionTextureObject,
                texture=source,
                sampler_type=sampler,
            )
            fn = node(unreal.MaterialExpressionMaterialFunctionCall)
            if not fn.set_material_function(
                load_required(
                    recipe["functions"]["normal" if channel == "normal" else "texture"]
                )
            ):
                raise RuntimeError("Native function binding failed")
            link(tex_object, "", fn, "TextureObject")
            link(size, "", fn, "TextureSize")
            if channel == "normal":
                link(world_space, "", fn, "WorldSpace")
            result = fn
            if channel == "roughness":
                result = node(
                    unreal.MaterialExpressionComponentMask,
                    r=True,
                    g=False,
                    b=False,
                    a=False,
                )
                link(fn, "XYZ Texture", result, "")
            projected[channel] = (
                result,
                "" if channel == "roughness" else "XYZ Texture",
            )
        return projected

    neutral = project_channels(recipe["neutral_fallback"])
    color = node(unreal.MaterialExpressionMultiply)
    link(*neutral["color"], color, "A")
    link(
        vector("NeutralGroundTint", recipe["neutral_ground_color_linear"]),
        "",
        color,
        "B",
    )
    roughness = node(unreal.MaterialExpressionMultiply)
    link(*neutral["roughness"], roughness, "A")
    roughness_scale = node(
        unreal.MaterialExpressionScalarParameter,
        parameter_name="NeutralGroundRoughnessScale",
        default_value=recipe["neutral_ground_roughness"],
    )
    link(roughness_scale, "", roughness, "B")
    normal = node(
        unreal.MaterialExpressionComponentMask, r=True, g=True, b=True, a=False
    )
    link(*neutral["normal"], normal, "")
    sum_weights = node(unreal.MaterialExpressionDotProduct)
    link(weights, "RGB", sum_weights, "A")
    link(vector("BlendWeightSum", [1, 1, 1]), "", sum_weights, "B")
    residual = node(unreal.MaterialExpressionOneMinus)
    link(sum_weights, "", residual, "")
    residual_channels = []
    for base in (color, roughness, normal):
        product = node(unreal.MaterialExpressionMultiply)
        link(base, "", product, "A")
        link(residual, "", product, "B")
        residual_channels.append(product)
    color, roughness, normal = residual_channels
    for layer in recipe["layers"]:
        projected = project_channels(layer)
        blended = []
        for previous, channel in (
            (color, "color"),
            (roughness, "roughness"),
            (normal, "normal"),
        ):
            product = node(unreal.MaterialExpressionMultiply)
            link(*projected[channel], product, "A")
            link(weights, layer["weight_channel"], product, "B")
            addition = node(unreal.MaterialExpressionAdd)
            link(previous, "", addition, "A")
            link(product, "", addition, "B")
            blended.append(addition)
        color, roughness, normal = blended
    normalized = node(unreal.MaterialExpressionNormalize)
    link(normal, "", normalized, "")
    for expression, prop in (
        (color, unreal.MaterialProperty.MP_BASE_COLOR),
        (roughness, unreal.MaterialProperty.MP_ROUGHNESS),
        (normalized, unreal.MaterialProperty.MP_NORMAL),
    ):
        if not LIB.connect_material_property(expression, "", prop):
            raise RuntimeError("Material output connection failed")
    # No WorldPositionOffset or displacement connection exists in this producer.
    errors = LIB.recompile_material(material)
    if errors:
        raise RuntimeError("Material recompile errors: " + str(errors))
    return material, texture, nodes, task


def apply_foundation(mode="foundation", save_assets=False):
    if mode not in ("foundation", "original"):
        raise ValueError("Expected foundation or original")
    config = load_workspace()
    if Path(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    ).resolve() != Path(config["project"]):
        raise RuntimeError("Wrong authoring project")
    if not unreal.SystemLibrary.get_engine_version().startswith("5.8.2-56702186"):
        raise RuntimeError("Unverified engine version")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    recipe_path = REPO / "worldgen/materials/sa_calobra_foundation.json"
    recipe = json.loads(recipe_path.read_text(encoding="utf8"))
    if (
        world.get_path_name().split(".")[0] != recipe["map"]
        or recipe["map"] != config["map"]
    ):
        raise RuntimeError("Wrong map; automatic loading forbidden")
    landscapes = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    if len(landscapes) != 1:
        raise RuntimeError("Expected exactly one frozen Landscape")
    landscape = landscapes[0]
    map_file = REPO / "Content" / (recipe["map"].removeprefix("/Game/") + ".umap")
    path = Path(config["data"]) / recipe["input_manifest_relative"]
    manifest = verified_inputs(path)
    key = hashlib.sha256(
        (digest(recipe_path) + digest(path) + digest(__file__)).encode()
    ).hexdigest()[:12]
    cache = getattr(builtins, "_yacs_2b_material", None)
    if cache is None:
        cache = {
            "key": key,
            "world": world.get_path_name(),
            "original": landscape.get_editor_property("landscape_material"),
            "objects": None,
        }
        builtins._yacs_2b_material = cache
    if cache["world"] != world.get_path_name():
        raise RuntimeError("Material cache belongs to another world")
    if mode != "original" and cache["key"] != key:
        raise RuntimeError(
            "Material cache identity changed; restore original before replacing a recipe"
        )
    before = scene_snapshot(world, landscape, map_file)
    if mode == "original":
        material = cache["original"]
    else:
        if cache["objects"] is None:
            cache["objects"] = create_material(recipe, manifest, path.parent, key)
        material = cache["objects"][0]
    try:
        landscape.set_editor_property("landscape_material", material)
        after = scene_snapshot(world, landscape, map_file)
        if (
            before != after
            or landscape.get_editor_property("landscape_material") != material
        ):
            raise RuntimeError("Frozen scene invariant or material readback differs")
        if save_assets and mode == "foundation":
            for asset in cache["objects"][:2]:
                if not unreal.EditorAssetLibrary.save_asset(
                    asset.get_path_name(), only_if_is_dirty=False
                ):
                    raise RuntimeError("Material asset save failed")
    except Exception:
        landscape.set_editor_property("landscape_material", cache["original"])
        raise
    report = {
        "status": "MATERIAL_APPLIED_GEOMETRY_UNCHANGED",
        "mode": mode,
        "material": material.get_path_name() if material else None,
        "recipe_sha256": digest(recipe_path),
        "input_manifest_sha256": digest(path),
        "script_sha256": digest(__file__),
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "scene_snapshot_equal": before == after,
        "saved_map_sha256": after["saved_map_sha256"],
        "map_saved": False,
        "assets_saved": bool(save_assets and mode == "foundation"),
        "visual_acceptance": "PENDING",
        "performance": "PENDING_2B",
        "classification_admission": False,
    }
    (Path(config["work"]) / "2b-material-live-proof.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf8"
    )
    unreal.log("YACS 2B material applied; frozen geometry unchanged; map not saved")
    if mode == "original":
        del builtins._yacs_2b_material
    return report

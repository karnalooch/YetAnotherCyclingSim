"""Apply generated surfaces using existing masks; save a separate review map.

Execute in the existing texture-checkpoint editor. No terrain, road, height,
mask-classification, displacement or PCG authoring occurs.
"""

import json
import runpy
import uuid
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
LIB = unreal.MaterialEditingLibrary


def stages(presentation=None):
    """Yield between native operations; one compile can still block the editor."""
    foundation = runpy.run_path(
        str(ROOT / "scripts/ue/sa_calobra_material_foundation.py")
    )
    digest = foundation["digest"]
    config = foundation["load_workspace"]()
    if Path(unreal.Paths.project_dir()).resolve() != ROOT or ROOT != Path(
        config["project"]
    ):
        raise RuntimeError("Wrong authoring project")
    if not unreal.SystemLibrary.get_engine_version().startswith("5.8.2-56702186"):
        raise RuntimeError("Unverified engine version")
    manifest = json.loads(
        (
            ROOT / "worldgen/materials/sa_calobra_texture_library_20261005.json"
        ).read_text()
    )
    receipt = json.loads(
        (
            ROOT / "worldgen/materials/sa_calobra_texture_library_result_20261005.json"
        ).read_text()
    )
    generation = json.loads(Path(receipt["generation_receipt"]).read_text())
    if presentation:
        manifest["map_asset"] = presentation["source_map"]
        manifest["map_file"] = (
            "Content/" + presentation["source_map"].removeprefix("/Game/") + ".umap"
        )
        receipt["map_sha256"] = presentation["source_sha256"]
    if (
        generation["status"] != "generated_review_required"
        or len(generation["items"]) != 7
    ):
        raise RuntimeError("Incomplete generated library")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name().split(".")[0] != manifest["map_asset"]:
        raise RuntimeError(
            "Open the recorded texture checkpoint; no automatic map switch"
        )
    map_file = ROOT / manifest["map_file"]
    if digest(map_file) != receipt["map_sha256"]:
        raise RuntimeError("Texture checkpoint bytes changed")
    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    if len(actors) != 1:
        raise RuntimeError("Expected exactly one Landscape")
    landscape = actors[0]
    before = foundation["scene_snapshot"](world, landscape, map_file)
    if len(before["components"]) != 1024:
        raise RuntimeError("Unexpected Landscape topology")
    original = landscape.get_editor_property("landscape_material")
    input_path = (
        Path(config["data"])
        / "world-data/sa-calobra-working-v1/material-foundation-v3-2026-10-05/material-input-manifest.json"
    )
    if presentation and presentation.get("surface_domains"):
        input_path = Path(presentation["surface_domains"])
    inputs = foundation["verified_inputs"](input_path)
    key = uuid.uuid4().hex
    package = generation["library"] + "/Landscape/" + key
    output_map = "/Game/Worlds/SaCalobra/L_SaCalobraGeneratedSurfaces_" + key[:12]
    if unreal.EditorAssetLibrary.does_asset_exist(output_map):
        raise RuntimeError("Review map already exists")
    evidence = ROOT / "Saved/RuntimeProof/TextureLandscape" / key
    evidence.mkdir(parents=True, exist_ok=False)
    task = unreal.AssetImportTask()
    for prop, value in {
        "filename": str(input_path.parent / "material-weights.png"),
        "destination_path": package,
        "destination_name": "T_SurfaceWeights",
        "automated": True,
        "replace_existing": False,
        "save": False,
    }.items():
        task.set_editor_property(prop, value)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths = task.get_editor_property("imported_object_paths")
    if len(paths) != 1:
        raise RuntimeError("Weight import failed")
    weights_texture = foundation["load_required"](paths[0])
    for prop, value in {
        "srgb": False,
        "filter": unreal.TextureFilter.TF_NEAREST,
        "address_x": unreal.TextureAddress.TA_CLAMP,
        "address_y": unreal.TextureAddress.TA_CLAMP,
        "mip_gen_settings": unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS,
        "compression_settings": unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP,
        "never_stream": True,
    }.items():
        weights_texture.set_editor_property(prop, value)
    yield {
        "phase": "WEIGHTS_IMPORTED",
        "weights_texture": weights_texture.get_path_name(),
    }
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_SaCalobraGeneratedSurfaces",
        package,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    if material is None:
        raise RuntimeError("Material creation failed")
    nodes = []

    def node(cls, **properties):
        value = LIB.create_material_expression(
            material, cls, -300 * (1 + len(nodes) % 8), 150 * (len(nodes) // 8)
        )
        if value is None:
            raise RuntimeError("Material node creation failed")
        for prop, setting in properties.items():
            value.set_editor_property(prop, setting)
        nodes.append(value)
        return value

    def link(source, output, target, pin):
        if not LIB.connect_material_expressions(source, output, target, pin):
            raise RuntimeError("Native material connection failed: " + pin)

    position = node(unreal.MaterialExpressionWorldPosition)
    xy = node(unreal.MaterialExpressionComponentMask, r=True, g=True)
    link(position, "", xy, "")
    bounds = inputs["world_mapping"]["footprint_world_bounds_cm"]
    offset = node(unreal.MaterialExpressionConstant2Vector, r=-bounds[0], g=-bounds[1])
    add = node(unreal.MaterialExpressionAdd)
    link(xy, "", add, "A")
    link(offset, "", add, "B")
    uv = node(
        unreal.MaterialExpressionDivide,
        const_b=inputs["grid"]["width"] * inputs["grid"]["pixel_size_m"] * 100,
    )
    link(add, "", uv, "A")
    weight_sample = node(
        unreal.MaterialExpressionTextureSample,
        texture=weights_texture,
        sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR,
    )
    link(uv, "", weight_sample, "")
    generated = {row["role"]: row for row in generation["items"]}
    sources = {row["role"]: row for row in manifest["items"]}
    grass_patch = None
    if presentation:
        macro = node(
            unreal.MaterialExpressionTextureObject,
            texture=foundation["load_required"](
                generated["DryGrass"]["outputs"]["MacroMask"]["asset"]
            ),
            sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,
        )
        macro_size = presentation["grass_patch_size_cm"]
        size = node(
            unreal.MaterialExpressionConstant3Vector,
            constant=unreal.LinearColor(macro_size, macro_size, macro_size, 1),
        )
        fn = node(unreal.MaterialExpressionMaterialFunctionCall)
        if not fn.set_material_function(
            foundation["load_required"](
                "/Engine/Functions/Engine_MaterialFunctions01/Texturing/WorldAlignedTexture"
            )
        ):
            raise RuntimeError("Grass macro projection failed")
        link(macro, "", fn, "TextureObject")
        link(size, "", fn, "TextureSize")
        red = node(
            unreal.MaterialExpressionComponentMask, r=True, g=False, b=False, a=False
        )
        link(fn, "XYZ Texture", red, "")
        threshold = node(
            unreal.MaterialExpressionSubtract,
            const_b=presentation["grass_patch_threshold"],
        )
        link(red, "", threshold, "A")
        ramp = node(
            unreal.MaterialExpressionDivide, const_b=presentation["grass_patch_width"]
        )
        link(threshold, "", ramp, "A")
        grass_patch = node(unreal.MaterialExpressionSaturate)
        link(ramp, "", grass_patch, "")
    channels = {}
    raw_channels = []
    for role, channel in (
        ("DryGrass", "R"),
        ("ForestLitter", "G"),
        ("ExposedRock", "B"),
    ):
        mask = node(
            unreal.MaterialExpressionComponentMask,
            r=channel == "R",
            g=channel == "G",
            b=channel == "B",
            a=False,
        )
        link(weight_sample, "", mask, "")
        raw_channels.append(mask)
        if role == "DryGrass":
            # Bounded decorative fibres, not blanket grass or a geographic claim.
            amount = node(
                unreal.MaterialExpressionScalarParameter,
                parameter_name="DryFibreContribution",
                default_value=presentation["grass_contribution"]
                if presentation
                else 0.35,
            )
            limited = node(unreal.MaterialExpressionMultiply)
            link(mask, "", limited, "A")
            link(amount, "", limited, "B")
            mask = limited
            if grass_patch:
                patch = node(unreal.MaterialExpressionMultiply)
                link(mask, "", patch, "A")
                link(grass_patch, "", patch, "B")
                mask = patch
        channels[role] = mask
    if presentation and presentation.get("inferred_gap_fill"):
        # Owner-authorized appearance fallback only; never geographic/PCG truth.
        raw_sum = raw_channels[0]
        for raw in raw_channels[1:]:
            addition = node(unreal.MaterialExpressionAdd)
            link(raw_sum, "", addition, "A")
            link(raw, "", addition, "B")
            raw_sum = addition
        small = node(unreal.MaterialExpressionMultiply, const_b=-1000.0)
        link(raw_sum, "", small, "A")
        gap = node(unreal.MaterialExpressionAdd, const_b=1.0)
        link(small, "", gap, "A")
        gap_gate = node(unreal.MaterialExpressionSaturate)
        link(gap, "", gap_gate, "")
        vertex_normal = node(unreal.MaterialExpressionVertexNormalWS)
        nz = node(
            unreal.MaterialExpressionComponentMask, r=False, g=False, b=True, a=False
        )
        link(vertex_normal, "", nz, "")
        absolute = node(unreal.MaterialExpressionAbs)
        link(nz, "", absolute, "")
        steepness = node(unreal.MaterialExpressionOneMinus)
        link(absolute, "", steepness, "")
        offset = node(unreal.MaterialExpressionSubtract, const_b=0.06)
        link(steepness, "", offset, "A")
        ramp = node(unreal.MaterialExpressionDivide, const_b=0.34)
        link(offset, "", ramp, "A")
        rock_fraction = node(unreal.MaterialExpressionSaturate)
        link(ramp, "", rock_fraction, "")
        rock_fill = node(unreal.MaterialExpressionMultiply)
        link(gap_gate, "", rock_fill, "A")
        link(rock_fraction, "", rock_fill, "B")
        rock = node(unreal.MaterialExpressionAdd)
        link(channels["ExposedRock"], "", rock, "A")
        link(rock_fill, "", rock, "B")
        channels["ExposedRock"] = rock
        gentle = node(unreal.MaterialExpressionOneMinus)
        link(rock_fraction, "", gentle, "")
        grass_fill = node(unreal.MaterialExpressionMultiply)
        link(gap_gate, "", grass_fill, "A")
        link(gentle, "", grass_fill, "B")
        limited = node(unreal.MaterialExpressionMultiply, const_b=0.22)
        link(grass_fill, "", limited, "A")
        patch = node(unreal.MaterialExpressionMultiply)
        link(limited, "", patch, "A")
        link(grass_patch, "", patch, "B")
        grass = node(unreal.MaterialExpressionAdd)
        link(channels["DryGrass"], "", grass, "A")
        link(patch, "", grass, "B")
        channels["DryGrass"] = grass
    if presentation and presentation.get("dry_channel_overlay"):
        if "dry-channel" not in inputs["semantics"]["A"]:
            raise RuntimeError("Alpha is not a dry-channel appearance domain")
        channel = node(
            unreal.MaterialExpressionComponentMask, r=True, g=False, b=False, a=False
        )
        link(weight_sample, "A", channel, "")
        underneath = node(unreal.MaterialExpressionOneMinus)
        link(channel, "", underneath, "")
        for role, weight in list(channels.items()):
            product = node(unreal.MaterialExpressionMultiply)
            link(weight, "", product, "A")
            link(underneath, "", product, "B")
            channels[role] = product
        channels["Scree"] = channel
    summed = channels["DryGrass"]
    for role in (role for role in channels if role != "DryGrass"):
        addition = node(unreal.MaterialExpressionAdd)
        link(summed, "", addition, "A")
        link(channels[role], "", addition, "B")
        summed = addition
    residual = node(unreal.MaterialExpressionOneMinus)
    link(summed, "", residual, "")
    channels["DryMineral"] = residual
    generated = {row["role"]: row for row in generation["items"]}
    sources = {row["role"]: row for row in manifest["items"]}
    world_space = node(unreal.MaterialExpressionStaticBool, value=False)
    outputs = {}
    for role, weight in channels.items():
        scale = sources[role]["world_size_m"]
        if scale[0] != scale[1]:
            raise RuntimeError("Expected square physical tile")
        tile = scale[0] * 100
        size = node(
            unreal.MaterialExpressionVectorParameter,
            parameter_name=role + "TileSizeCm",
            default_value=unreal.LinearColor(tile, tile, tile, 1),
        )
        for channel, sampler in (
            ("BaseColor", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR),
            ("Normal", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL),
            ("Roughness", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS),
        ):
            texture = foundation["load_required"](
                generated[role]["outputs"][channel]["asset"]
            )
            obj = node(
                unreal.MaterialExpressionTextureObject,
                texture=texture,
                sampler_type=sampler,
            )
            fn = node(unreal.MaterialExpressionMaterialFunctionCall)
            name = (
                "WorldAlignedNormal" if channel == "Normal" else "WorldAlignedTexture"
            )
            if not fn.set_material_function(
                foundation["load_required"](
                    "/Engine/Functions/Engine_MaterialFunctions01/Texturing/" + name
                )
            ):
                raise RuntimeError("Native projection function binding failed")
            link(obj, "", fn, "TextureObject")
            link(size, "", fn, "TextureSize")
            if channel == "Normal":
                link(world_space, "", fn, "WorldSpace")
            sample, pin = fn, "XYZ Texture"
            if channel == "BaseColor" and presentation:
                tuning = presentation["color_tuning"][role]
                desaturate = node(unreal.MaterialExpressionDesaturation)
                fraction = node(
                    unreal.MaterialExpressionScalarParameter,
                    parameter_name=role + "Desaturation",
                    default_value=tuning["desaturation"],
                )
                link(sample, pin, desaturate, "")
                link(fraction, "", desaturate, "Fraction")
                gain = node(
                    unreal.MaterialExpressionVectorParameter,
                    parameter_name=role + "ColorGain",
                    default_value=unreal.LinearColor(*tuning["gain"], 1),
                )
                corrected = node(unreal.MaterialExpressionMultiply)
                link(desaturate, "", corrected, "A")
                link(gain, "", corrected, "B")
                sample, pin = corrected, ""
                if presentation.get("macro_variation"):
                    macro = node(
                        unreal.MaterialExpressionTextureObject,
                        texture=foundation["load_required"](
                            generated[role]["outputs"]["MacroMask"]["asset"]
                        ),
                        sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,
                    )
                    macro_size = node(
                        unreal.MaterialExpressionConstant3Vector,
                        constant=unreal.LinearColor(3000, 3000, 3000, 1),
                    )
                    projected = node(unreal.MaterialExpressionMaterialFunctionCall)
                    if not projected.set_material_function(
                        foundation["load_required"](
                            "/Engine/Functions/Engine_MaterialFunctions01/Texturing/WorldAlignedTexture"
                        )
                    ):
                        raise RuntimeError("Macro projection binding failed")
                    link(macro, "", projected, "TextureObject")
                    link(macro_size, "", projected, "TextureSize")
                    mask = node(
                        unreal.MaterialExpressionComponentMask,
                        r=True,
                        g=False,
                        b=False,
                        a=False,
                    )
                    link(projected, "XYZ Texture", mask, "")
                    amount = node(unreal.MaterialExpressionMultiply, const_b=0.2)
                    link(mask, "", amount, "A")
                    factor = node(unreal.MaterialExpressionAdd, const_b=0.9)
                    link(amount, "", factor, "A")
                    varied = node(unreal.MaterialExpressionMultiply)
                    link(sample, pin, varied, "A")
                    link(factor, "", varied, "B")
                    sample, pin = varied, ""
            if channel == "Roughness":
                sample = node(
                    unreal.MaterialExpressionComponentMask,
                    r=True,
                    g=False,
                    b=False,
                    a=False,
                )
                link(fn, pin, sample, "")
                pin = ""
            product = node(unreal.MaterialExpressionMultiply)
            link(sample, pin, product, "A")
            link(weight, "", product, "B")
            if channel in outputs:
                addition = node(unreal.MaterialExpressionAdd)
                link(outputs[channel], "", addition, "A")
                link(product, "", addition, "B")
                outputs[channel] = addition
            else:
                outputs[channel] = product
        yield {"phase": "ROLE_GRAPH_BUILT", "role": role, "nodes": len(nodes)}
    normal = node(unreal.MaterialExpressionNormalize)
    link(outputs["Normal"], "", normal, "")
    outputs["Normal"] = normal
    for channel, prop in (
        ("BaseColor", unreal.MaterialProperty.MP_BASE_COLOR),
        ("Normal", unreal.MaterialProperty.MP_NORMAL),
        ("Roughness", unreal.MaterialProperty.MP_ROUGHNESS),
    ):
        if not LIB.connect_material_property(outputs[channel], "", prop):
            raise RuntimeError("Material output connection failed")
    yield {
        "phase": "GRAPH_CONNECTED",
        "material": material.get_path_name(),
        "nodes": len(nodes),
    }
    errors = LIB.recompile_material(material)
    if errors:
        raise RuntimeError("Material compile errors: " + str(errors))
    yield {"phase": "COMPILE_CALL_RETURNED", "material": material.get_path_name()}
    if presentation and presentation.get("prepare_only"):
        for asset in (material, weights_texture):
            if not unreal.EditorAssetLibrary.save_loaded_asset(
                asset, only_if_is_dirty=False
            ):
                raise RuntimeError("Prepared material save failed")
        report = {
            "status": "MATERIAL_PREPARED_NOT_APPLIED",
            "material": material.get_path_name(),
            "weights_texture": weights_texture.get_path_name(),
            "source_checkpoint": manifest["map_asset"],
            "source_checkpoint_sha256": digest(map_file),
            "geometry_snapshot_equal": before
            == foundation["scene_snapshot"](world, landscape, map_file),
            "landscape_material_unchanged": landscape.get_editor_property(
                "landscape_material"
            )
            == original,
            "weights_manifest_sha256": digest(input_path),
            "producer_sha256": digest(__file__),
            "presentation": presentation,
            "whole_landscape_assignment": "NOT_EXECUTED",
            "visual_acceptance": "pending",
            "performance": "not measured",
        }
        if (
            not report["geometry_snapshot_equal"]
            or not report["landscape_material_unchanged"]
        ):
            raise RuntimeError("Prepare-only altered the current consumer")
        (evidence / "result.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        unreal.log("YACS_SURFACE_MATERIAL_PREPARED " + str(evidence))
        return report
    try:
        landscape.set_editor_property("landscape_material", material)
        after = foundation["scene_snapshot"](world, landscape, map_file)
        if (
            before != after
            or landscape.get_editor_property("landscape_material") != material
        ):
            raise RuntimeError("Frozen geometry or material assignment differs")
        audit = getattr(
            unreal.YacsTextureAuditLibrary,
            "describe_landscape_material_instances",
            None,
        )
        instance_count = 0
        if audit:
            for component in landscape.get_components_by_class(
                unreal.LandscapeComponent
            ):
                observed = json.loads(audit(component, material))
                if not observed.get("all_instances_match"):
                    raise RuntimeError("Landscape render instance differs")
                instance_count += observed["render_instance_count"]
        for asset in (material, weights_texture):
            if not unreal.EditorAssetLibrary.save_loaded_asset(
                asset, only_if_is_dirty=False
            ):
                raise RuntimeError("Generated material save failed")
        if not unreal.EditorLoadingAndSavingUtils.save_map(world, output_map):
            raise RuntimeError("Review-map save failed")
        if digest(map_file) != receipt["map_sha256"]:
            raise RuntimeError("Original checkpoint bytes changed")
    except Exception:
        landscape.set_editor_property("landscape_material", original)
        raise
    report = {
        "status": "GENERATED_SURFACES_APPLIED_REVIEW_MAP_SAVED",
        "material": material.get_path_name(),
        "review_map": output_map,
        "source_checkpoint": manifest["map_asset"],
        "source_checkpoint_sha256": digest(map_file),
        "source_checkpoint_saved": False,
        "geometry_snapshot_equal": before == after,
        "component_count": len(before["components"]),
        "render_instances_verified": instance_count if audit else "unavailable",
        "applied_roles": list(channels),
        "unmapped_roles": [role for role in generated if role not in channels],
        "unmapped_reason": "No dedicated admitted geographic masks; no invented assignment",
        "weights_manifest_sha256": digest(input_path),
        "producer_sha256": digest(__file__),
        "physical_scale": "provider tile dimensions, native world-aligned projection",
        "visual_acceptance": "pending",
        "performance": "not measured",
        "fresh_editor_reopen": "pending",
        "presentation": presentation,
    }
    (evidence / "result.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    unreal.EditorAssetLibrary.sync_browser_to_objects([material.get_path_name()])
    unreal.log("YACS_GENERATED_SURFACES_APPLIED " + str(evidence))
    return report


def main(presentation=None):
    """Retain the synchronous entry point for existing callers."""
    iterator = stages(presentation)
    while True:
        try:
            next(iterator)
        except StopIteration as completed:
            return completed.value


if __name__ == "__main__":
    main()

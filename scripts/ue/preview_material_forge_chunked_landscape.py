"""Bounded Material Forge Landscape repair preview.

This is a session-only technical pilot for two visible defects:
- blocky appearance blending from nearest-neighbour presentation weights;
- stretched steep-face surface projection.

Actions are deliberately incremental:
    cleanup -> probe -> prepare -> apply (repeat up to 9) -> status -> restore

The script never saves the map or assets and never mutates Landscape geometry.
It uses at most nine components around the current editor camera. Each apply
changes one component only and checks memory headroom before continuing.

Material Forge remains appearance-only. PCG/PCGEx remains semantic authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import runpy
import traceback
import uuid
from pathlib import Path

import unreal


ROOT = Path(__file__).resolve().parents[2]
PROOF_ROOT = Path(
    os.environ.get("YACS_MF_PROOF_ROOT", "D:/yacs/material-forge-v2-final/run-a")
)
ROCK = Path(
    os.environ.get(
        "YACS_MF_ROCK_VARIANT",
        str(PROOF_ROOT / "regional_limestone" / "refined_c"),
    )
)
SOIL = Path(
    os.environ.get(
        "YACS_MF_SOIL_VARIANT",
        str(PROOF_ROOT / "mediterranean_soil" / "refined_c"),
    )
)
MASK_ROOT = ROOT / "worldgen/materials/visual_fill"
WEIGHTS = MASK_ROOT / "material-weights.png"
MANIFEST = MASK_ROOT / "material-input-manifest.json"

MAP = "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004"
STATE = "_yacs_mf_chunked_fix"
MAX_COMPONENTS = 9
REQUESTED_COMPONENTS = int(os.environ.get("YACS_MF_MAX_COMPONENTS", str(MAX_COMPONENTS)))
ACTIVE_COMPONENTS = max(1, min(MAX_COMPONENTS, REQUESTED_COMPONENTS))
TARGET_COMPONENT = os.environ.get("YACS_MF_TARGET_COMPONENT")
PREPARE_FREE_PHYSICAL_GB = 8
PREPARE_FREE_COMMIT_GB = 12
APPLY_FREE_PHYSICAL_GB = 6
APPLY_FREE_COMMIT_GB = 8

LIB = unreal.MaterialEditingLibrary


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _emit(action: str, ok: bool = True, **extra):
    payload = {
        "ok": bool(ok),
        "action": action,
        "map_saved": False,
        "assets_saved": False,
        "geometry_changed": False,
        "world_semantics_generated": False,
        **extra,
    }
    out = ROOT / "Saved/RuntimeProof/MaterialForgeChunked"
    out.mkdir(parents=True, exist_ok=True)
    (out / "latest.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    message = "YACS_MF_CHUNK " + json.dumps(payload, default=str)
    if ok:
        unreal.log(message)
    else:
        unreal.log_error(message)
    return payload


def _memory():
    available = runpy.run_path(
        str(ROOT / "scripts/ue/sa_calobra_material_waves.py")
    )["available_memory"]()
    return {
        "free_physical_gb": round(available["free_physical"] / 1024**3, 2),
        "free_commit_gb": round(available["free_commit"] / 1024**3, 2),
        "_raw": available,
    }


def _memory_ok(memory, physical_gb: int, commit_gb: int) -> bool:
    return (
        memory["_raw"]["free_physical"] >= physical_gb * 1024**3
        and memory["_raw"]["free_commit"] >= commit_gb * 1024**3
    )


def _context():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world.get_path_name().split(".")[0] != MAP:
        raise RuntimeError("Open the accepted Sa Calobra map first")

    landscapes = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    if len(landscapes) != 1:
        raise RuntimeError("Expected exactly one Landscape")

    landscape = landscapes[0]
    components = landscape.get_components_by_class(unreal.LandscapeComponent)
    if len(components) != 1024:
        raise RuntimeError(f"Unexpected Landscape topology: {len(components)}")

    return editor, world, landscape, components


def _nearest_cluster(editor, components):
    if TARGET_COMPONENT:
        matches = [
            component
            for component in components
            if component.get_name() == TARGET_COMPONENT
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"Expected exactly one target Landscape component: {TARGET_COMPONENT}"
            )
        center = matches[0]
    else:
        camera = editor.get_level_viewport_camera_info()
        if not camera:
            raise RuntimeError("No active editor viewport camera")
        camera_position = camera[0]

        def camera_distance(component):
            origin = unreal.SystemLibrary.get_component_bounds(component)[0]
            return (
                (origin.x - camera_position.x) ** 2
                + (origin.y - camera_position.y) ** 2
            )

        center = min(components, key=camera_distance)

    center_origin = unreal.SystemLibrary.get_component_bounds(center)[0]

    def center_distance(component):
        origin = unreal.SystemLibrary.get_component_bounds(component)[0]
        return (
            (origin.x - center_origin.x) ** 2
            + (origin.y - center_origin.y) ** 2
        )

    capped = sorted(components, key=center_distance)[:MAX_COMPONENTS]
    return capped[:ACTIVE_COMPONENTS]


def _validate_visual_fill():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    payload = {key: value for key, value in data.items() if key != "fingerprint"}
    fingerprint = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    if fingerprint != data.get("fingerprint"):
        raise RuntimeError("Visual-fill manifest fingerprint mismatch")
    if (
        data.get("status") != "PRESENTATION_VISUAL_FILL_CANDIDATE"
        or data.get("geometry_mutation") is not False
        or data.get("grid", {}).get("width") != 4033
        or data.get("grid", {}).get("height") != 4033
        or data.get("world_mapping", {}).get("footprint_world_bounds_cm")
        != [-25, -25, 201625, 201625]
    ):
        raise RuntimeError("Unexpected visual-fill registration")

    entry = next(
        (row for row in data["outputs"] if row["path"] == WEIGHTS.name),
        None,
    )
    if entry is None:
        raise RuntimeError("Visual-fill weight entry missing")
    if _sha(WEIGHTS) != entry["sha256"]:
        raise RuntimeError("Visual-fill weight bytes changed")
    return data


def _validate_variant(directory: Path):
    for name in ("validation.json", "provenance.json"):
        path = directory / name
        if not path.is_file():
            raise RuntimeError(f"Missing Material Forge file: {path}")
    importer = runpy.run_path(
        str(ROOT / "scripts/ue/import_material_forge_variant.py")
    )
    validation, provenance = importer["_require_variant"](directory)
    return importer, validation, provenance


def _cleanup_known():
    restored = []

    previous = getattr(unreal, "_yacs_mf_near_camera", None)
    if previous:
        previous["component"].set_editor_property(
            "override_material",
            previous["original"],
        )
        unreal._yacs_mf_near_camera = None
        restored.append("mf_near_camera")

    previous = getattr(unreal, "_yacs_material_forge_canary", None)
    if previous:
        previous["component"].set_editor_property(
            "override_material",
            previous["original"],
        )
        unreal._yacs_material_forge_canary = None
        restored.append("material_forge_canary")

    state = getattr(unreal, STATE, None)
    if state:
        for component in reversed(state["applied"]):
            component.set_editor_property(
                "override_material",
                state["originals"][component.get_path_name()],
            )
        setattr(unreal, STATE, None)
        restored.append("chunked_fix")

    return restored


def probe():
    editor, _world, _landscape, components = _context()
    _validate_visual_fill()
    _validate_variant(ROCK)
    _validate_variant(SOIL)

    cluster = _nearest_cluster(editor, components)
    occupied = [
        component.get_name()
        for component in cluster
        if component.get_editor_property("override_material") is not None
    ]
    memory = _memory()

    if not _memory_ok(
        memory,
        PREPARE_FREE_PHYSICAL_GB,
        PREPARE_FREE_COMMIT_GB,
    ):
        return _emit(
            "probe",
            False,
            reason="insufficient memory headroom for preparation",
            memory=memory,
        )

    if occupied:
        return _emit(
            "probe",
            False,
            reason="target components already have material overrides",
            occupied=occupied,
            memory=memory,
        )

    return _emit(
        "probe",
        True,
        component_count=len(cluster),
        components=[component.get_name() for component in cluster],
        rock=str(ROCK),
        soil=str(SOIL),
        weights=str(WEIGHTS),
        memory=memory,
        sampling="bilinear appearance mask",
        projection="WorldAlignedTexture + WorldAlignedNormal",
    )


def _import_weight(package: str):
    task = unreal.AssetImportTask()
    for property_name, value in {
        "filename": str(WEIGHTS),
        "destination_path": package,
        "destination_name": "T_MF_SmoothWeights",
        "automated": True,
        "replace_existing": False,
        "save": False,
    }.items():
        task.set_editor_property(property_name, value)

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported = task.get_editor_property("imported_object_paths")
    if len(imported) != 1:
        raise RuntimeError("Appearance weight import failed")

    texture = unreal.load_asset(imported[0])
    if texture is None:
        raise RuntimeError("Appearance weight texture unavailable after import")

    for property_name, value in {
        "srgb": False,
        "filter": unreal.TextureFilter.TF_BILINEAR,
        "address_x": unreal.TextureAddress.TA_CLAMP,
        "address_y": unreal.TextureAddress.TA_CLAMP,
        "compression_settings": unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP,
        "never_stream": False,
    }.items():
        texture.set_editor_property(property_name, value)
        if texture.get_editor_property(property_name) != value:
            raise RuntimeError("Weight texture setting failed: " + property_name)

    return texture


def _create_fixed_master_instance(package: str, weights, checkpoints):
    master_path = os.environ.get("YACS_MF_FIXED_MASTER_PATH")
    if not master_path:
        raise RuntimeError("YACS_MF_FIXED_MASTER_PATH is required for fixed-master proof")
    master = unreal.load_asset(master_path)
    if master is None:
        raise RuntimeError("Fixed Material Forge Landscape master could not be loaded")
    checkpoints.append({"stage": "fixed_master_loaded", "memory": _memory()})

    importer, rock_validation, rock_provenance = _validate_variant(ROCK)
    _same_importer, soil_validation, soil_provenance = _validate_variant(SOIL)

    surfaces = {}
    for key, directory, validation, provenance in (
        ("rock", ROCK, rock_validation, rock_provenance),
        ("soil", SOIL, soil_validation, soil_provenance),
    ):
        textures = {}
        for channel in ("BaseColor", "Normal_DX", "ORM", "DetailMasks"):
            source = importer["_verified_map"](directory, validation, channel)
            texture = importer["_import_texture"](
                package,
                f"T_{key}_{channel.replace('_', '')}",
                source,
                channel,
            )
            texture.set_editor_property("filter", unreal.TextureFilter.TF_BILINEAR)
            texture.set_editor_property("never_stream", False)
            textures[channel] = texture
        landscape_profile = (
            provenance.get("parameters", {}).get("landscape", {}) or {}
        )
        macro_tile_metres = float(
            landscape_profile.get("macro_tile_metres", 16.0)
        )
        macro_strength = float(landscape_profile.get("macro_strength", 0.0))
        if not 8.0 <= macro_tile_metres <= 30.0:
            raise RuntimeError("Material Forge macro tile must stay within 8..30 m")
        if not 0.0 <= macro_strength <= 0.30:
            raise RuntimeError("Material Forge macro strength must stay within 0..0.30")
        surfaces[key] = {
            "textures": textures,
            "tile_cm": float(provenance["tile_metres"]) * 100.0,
            "macro_tile_cm": macro_tile_metres * 100.0,
            "macro_strength": macro_strength,
        }
        checkpoints.append(
            {
                "stage": f"{key}_textures_imported",
                "memory": _memory(),
            }
        )

    imported_textures = [weights] + [
        texture
        for surface in surfaces.values()
        for texture in surface["textures"].values()
    ]
    if not unreal.YacsTextureAuditLibrary.finish_texture_compilation(
        imported_textures
    ):
        raise RuntimeError("Fixed-master texture compilation did not drain cleanly")
    checkpoints.append(
        {
            "stage": "texture_compilation_drained",
            "memory": _memory(),
        }
    )

    instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "MI_MF_ChunkedRockSoil",
        package,
        unreal.MaterialInstanceConstant,
        unreal.MaterialInstanceConstantFactoryNew(),
    )
    if instance is None:
        raise RuntimeError("Fixed-master Material Instance creation failed")
    LIB.set_material_instance_parent(instance, master)
    LIB.update_material_instance(instance)
    checkpoints.append({"stage": "material_instance_created", "memory": _memory()})

    texture_values = {
        "WeightTex": weights,
        "RockBaseColorTex": surfaces["rock"]["textures"]["BaseColor"],
        "RockNormalTex": surfaces["rock"]["textures"]["Normal_DX"],
        "RockORMTex": surfaces["rock"]["textures"]["ORM"],
        "RockDetailTex": surfaces["rock"]["textures"]["DetailMasks"],
        "SoilBaseColorTex": surfaces["soil"]["textures"]["BaseColor"],
        "SoilNormalTex": surfaces["soil"]["textures"]["Normal_DX"],
        "SoilORMTex": surfaces["soil"]["textures"]["ORM"],
        "SoilDetailTex": surfaces["soil"]["textures"]["DetailMasks"],
    }
    scalar_values = {
        "RockTileSizeCm": surfaces["rock"]["tile_cm"],
        "SoilTileSizeCm": surfaces["soil"]["tile_cm"],
        "RockMacroTileSizeCm": surfaces["rock"]["macro_tile_cm"],
        "SoilMacroTileSizeCm": surfaces["soil"]["macro_tile_cm"],
        "RockMacroStrength": surfaces["rock"]["macro_strength"],
        "SoilMacroStrength": surfaces["soil"]["macro_strength"],
    }
    vector_values = {
        "RockColorGain": unreal.LinearColor(1.0, 1.0, 1.0, 1.0),
        "SoilColorGain": unreal.LinearColor(1.0, 1.0, 1.0, 1.0),
    }
    visible_textures = {str(name) for name in LIB.get_texture_parameter_names(instance)}
    visible_scalars = {str(name) for name in LIB.get_scalar_parameter_names(instance)}
    visible_vectors = {str(name) for name in LIB.get_vector_parameter_names(instance)}
    if set(texture_values) - visible_textures:
        raise RuntimeError(
            "Fixed-master texture parameter contract missing: "
            + ",".join(sorted(set(texture_values) - visible_textures))
        )
    if set(scalar_values) - visible_scalars:
        raise RuntimeError(
            "Fixed-master scalar parameter contract missing: "
            + ",".join(sorted(set(scalar_values) - visible_scalars))
        )
    if set(vector_values) - visible_vectors:
        raise RuntimeError(
            "Fixed-master vector parameter contract missing: "
            + ",".join(sorted(set(vector_values) - visible_vectors))
        )

    association = unreal.MaterialParameterAssociation.GLOBAL_PARAMETER
    for name, texture in texture_values.items():
        LIB.set_material_instance_parameter_override(instance, name, True, association)
        LIB.set_material_instance_texture_parameter_value(
            instance,
            name,
            texture,
            association,
        )
    for name, value in scalar_values.items():
        LIB.set_material_instance_parameter_override(instance, name, True, association)
        LIB.set_material_instance_scalar_parameter_value(
            instance,
            name,
            float(value),
            association,
        )
    for name, value in vector_values.items():
        LIB.set_material_instance_parameter_override(instance, name, True, association)
        LIB.set_material_instance_vector_parameter_value(
            instance,
            name,
            value,
            association,
        )
    LIB.update_material_instance(instance)
    checkpoints.append({"stage": "material_instance_updated", "memory": _memory()})

    for name, expected in texture_values.items():
        actual = LIB.get_material_instance_texture_parameter_value(
            instance,
            name,
            association,
        )
        if actual is None or actual.get_path_name() != expected.get_path_name():
            raise RuntimeError("Fixed-master texture readback failed: " + name)
    for name, expected in scalar_values.items():
        actual = LIB.get_material_instance_scalar_parameter_value(
            instance,
            name,
            association,
        )
        if abs(float(actual) - float(expected)) > 0.001:
            raise RuntimeError("Fixed-master scalar readback failed: " + name)
    for name, expected in vector_values.items():
        actual = LIB.get_material_instance_vector_parameter_value(
            instance,
            name,
            association,
        )
        channels = ("r", "g", "b", "a")
        if any(
            abs(float(getattr(actual, channel)) - float(getattr(expected, channel)))
            > 0.001
            for channel in channels
        ):
            raise RuntimeError("Fixed-master vector readback failed: " + name)

    drain_raw = (
        unreal.YacsTextureAuditLibrary.drain_asset_compilation_and_collect_garbage()
    )
    drain = json.loads(drain_raw)
    if (
        not drain.get("ok")
        or int(drain.get("remaining_after", -1)) != 0
        or int(drain.get("shader_jobs_after", -1)) != 0
    ):
        raise RuntimeError("Fixed-master compile drain failed: " + drain_raw)
    checkpoints.append(
        {
            "stage": "fixed_master_instance_drained",
            "memory": _memory(),
            "compile_drain": drain,
        }
    )
    return instance, drain


def _build_surface_material(package: str, weights, checkpoints):
    importer, rock_validation, rock_provenance = _validate_variant(ROCK)
    _same_importer, soil_validation, soil_provenance = _validate_variant(SOIL)

    surfaces = {}
    for key, directory, validation, provenance in (
        ("rock", ROCK, rock_validation, rock_provenance),
        ("soil", SOIL, soil_validation, soil_provenance),
    ):
        textures = {}
        for channel in ("BaseColor", "Normal_DX", "ORM"):
            source = importer["_verified_map"](directory, validation, channel)
            texture = importer["_import_texture"](
                package,
                f"T_{key}_{channel.replace('_', '')}",
                source,
                channel,
            )
            texture.set_editor_property("filter", unreal.TextureFilter.TF_BILINEAR)
            texture.set_editor_property("never_stream", False)
            textures[channel] = texture
        surfaces[key] = {
            "textures": textures,
            "tile_cm": float(provenance["tile_metres"]) * 100.0,
        }
        checkpoints.append(
            {
                "stage": f"{key}_textures_imported",
                "memory": _memory(),
            }
        )

    imported_textures = [
        texture
        for surface in surfaces.values()
        for texture in surface["textures"].values()
    ]
    if not unreal.YacsTextureAuditLibrary.finish_texture_compilation(
        imported_textures
    ):
        raise RuntimeError("Material Forge texture compilation did not drain cleanly")
    checkpoints.append(
        {
            "stage": "texture_compilation_drained",
            "memory": _memory(),
        }
    )

    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_MF_ChunkedRockSoil",
        package,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    if material is None:
        raise RuntimeError("Chunked preview material creation failed")
    material.set_editor_property(
        "shading_model",
        unreal.MaterialShadingModel.MSM_DEFAULT_LIT,
    )

    node = importer["_node"]
    link = importer["_link"]
    output = importer["_output"]
    projection = importer["_projection"]

    world_position = node(material, unreal.MaterialExpressionWorldPosition)
    xy = node(
        material,
        unreal.MaterialExpressionComponentMask,
        r=True,
        g=True,
        b=False,
        a=False,
    )
    link(world_position, "", xy, "")

    offset = node(
        material,
        unreal.MaterialExpressionConstant2Vector,
        r=25.0,
        g=25.0,
    )
    add = node(material, unreal.MaterialExpressionAdd)
    link(xy, "", add, "A")
    link(offset, "", add, "B")

    uv = node(material, unreal.MaterialExpressionDivide, const_b=201650.0)
    link(add, "", uv, "A")

    # Bilinear filtering plus a one-pixel cross average smooths appearance only.
    # Source mask bytes and PCG/PCGEx semantic authority are untouched.
    texel = 1.0 / 4033.0

    def rock_sample(dx: float, dy: float):
        coordinate = uv
        if dx or dy:
            delta = node(
                material,
                unreal.MaterialExpressionConstant2Vector,
                r=dx,
                g=dy,
            )
            shifted = node(material, unreal.MaterialExpressionAdd)
            link(uv, "", shifted, "A")
            link(delta, "", shifted, "B")
            coordinate = shifted

        sample = node(
            material,
            unreal.MaterialExpressionTextureSample,
            texture=weights,
            sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR,
        )
        link(coordinate, "", sample, "")
        blue = node(
            material,
            unreal.MaterialExpressionComponentMask,
            r=False,
            g=False,
            b=True,
            a=False,
        )
        link(sample, "RGBA", blue, "")
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
        addition = node(material, unreal.MaterialExpressionAdd)
        link(weight_sum, "", addition, "A")
        link(sample, "", addition, "B")
        weight_sum = addition

    average = node(
        material,
        unreal.MaterialExpressionMultiply,
        const_b=0.2,
    )
    link(weight_sum, "", average, "A")
    rock_weight = node(material, unreal.MaterialExpressionSaturate)
    link(average, "", rock_weight, "")
    soil_weight = node(material, unreal.MaterialExpressionOneMinus)
    link(rock_weight, "", soil_weight, "")

    projected = {}
    for key in ("rock", "soil"):
        textures = surfaces[key]["textures"]
        size = node(
            material,
            unreal.MaterialExpressionConstant3Vector,
            constant=unreal.LinearColor(
                surfaces[key]["tile_cm"],
                surfaces[key]["tile_cm"],
                surfaces[key]["tile_cm"],
                1.0,
            ),
        )

        objects = {
            "BaseColor": node(
                material,
                unreal.MaterialExpressionTextureObject,
                texture=textures["BaseColor"],
                sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,
            ),
            "Normal": node(
                material,
                unreal.MaterialExpressionTextureObject,
                texture=textures["Normal_DX"],
                sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,
            ),
            "ORM": node(
                material,
                unreal.MaterialExpressionTextureObject,
                texture=textures["ORM"],
                sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,
            ),
        }

        base_color = projection(material, objects["BaseColor"], size, normal=False)
        normal = projection(material, objects["Normal"], size, normal=True)
        orm = projection(material, objects["ORM"], size, normal=False)

        roughness = node(
            material,
            unreal.MaterialExpressionComponentMask,
            r=False,
            g=True,
            b=False,
            a=False,
        )
        link(orm, "XYZ Texture", roughness, "")

        ao = node(
            material,
            unreal.MaterialExpressionComponentMask,
            r=True,
            g=False,
            b=False,
            a=False,
        )
        link(orm, "XYZ Texture", ao, "")

        projected[key] = {
            "BaseColor": (base_color, "XYZ Texture"),
            "Normal": (normal, "XYZ Texture"),
            "Roughness": (roughness, ""),
            "AO": (ao, ""),
        }

    def weighted(source, pin, weight):
        multiply = node(material, unreal.MaterialExpressionMultiply)
        link(source, pin, multiply, "A")
        link(weight, "", multiply, "B")
        return multiply

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
        result = node(material, unreal.MaterialExpressionAdd)
        link(rock, "", result, "A")
        link(soil, "", result, "B")
        return result

    base_color = blend("BaseColor")
    roughness = blend("Roughness")
    ao = blend("AO")
    normal_sum = blend("Normal")
    normal = node(material, unreal.MaterialExpressionNormalize)
    link(normal_sum, "", normal, "")

    output(base_color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    output(roughness, "", unreal.MaterialProperty.MP_ROUGHNESS)
    output(ao, "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    output(normal, "", unreal.MaterialProperty.MP_NORMAL)
    checkpoints.append(
        {
            "stage": "material_graph_built",
            "memory": _memory(),
        }
    )

    errors = LIB.recompile_material(material)
    if errors:
        raise RuntimeError("Chunked preview material compile failed: " + str(errors))
    LIB.layout_material_expressions(material)
    checkpoints.append(
        {
            "stage": "material_recompile_returned",
            "memory": _memory(),
        }
    )

    drain_raw = (
        unreal.YacsTextureAuditLibrary.drain_asset_compilation_and_collect_garbage()
    )
    try:
        drain = json.loads(drain_raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Material Forge compile-drain receipt was not valid JSON"
        ) from exc
    if (
        not drain.get("ok")
        or int(drain.get("remaining_after", -1)) != 0
        or int(drain.get("shader_jobs_after", -1)) != 0
    ):
        raise RuntimeError(
            "Material Forge asset/shader compilation did not drain cleanly: "
            + drain_raw
        )
    checkpoints.append(
        {
            "stage": "asset_shader_compilation_drained",
            "memory": _memory(),
            "compile_drain": drain,
        }
    )
    return material, drain


def prepare():
    if getattr(unreal, STATE, None):
        return _emit(
            "prepare",
            False,
            reason="chunked preview already prepared",
        )

    result = probe()
    if not result["ok"]:
        return result

    editor, world, landscape, components = _context()
    cluster = _nearest_cluster(editor, components)
    memory = _memory()
    if not _memory_ok(
        memory,
        PREPARE_FREE_PHYSICAL_GB,
        PREPARE_FREE_COMMIT_GB,
    ):
        return _emit(
            "prepare",
            False,
            reason="memory gate failed before material preparation",
            memory=memory,
        )

    package = "/Game/Generated/YACS/MFChunkedPreview/" + uuid.uuid4().hex
    checkpoints = [
        {
            "stage": "prepare_start",
            "memory": _memory(),
        }
    ]
    weights = _import_weight(package)
    checkpoints.append(
        {
            "stage": "weight_texture_imported",
            "memory": _memory(),
        }
    )
    if os.environ.get("YACS_MF_FIXED_MASTER_PATH"):
        material, compile_drain = _create_fixed_master_instance(
            package,
            weights,
            checkpoints,
        )
        material_mode = "fixed_master_instance"
    else:
        material, compile_drain = _build_surface_material(
            package,
            weights,
            checkpoints,
        )
        material_mode = "dynamic_graph_legacy"
    memory_after_compile_drain = _memory()

    foundation = runpy.run_path(
        str(ROOT / "scripts/ue/sa_calobra_material_foundation.py")
    )
    map_file = ROOT / "Content/Worlds/SaCalobra/L_SaCalobraAccepted_20261004.umap"
    snapshot = foundation["scene_snapshot"](world, landscape, map_file)

    state = {
        "world": world,
        "landscape": landscape,
        "components": cluster,
        "material": material,
        "originals": {
            component.get_path_name():
                component.get_editor_property("override_material")
            for component in cluster
        },
        "global_material": landscape.get_editor_property("landscape_material"),
        "applied": [],
        "snapshot": snapshot,
        "foundation": foundation,
        "map_file": map_file,
        "package": package,
        "compile_drain": compile_drain,
        "material_mode": material_mode,
        "memory_checkpoints": checkpoints,
        "memory_after_compile_drain": memory_after_compile_drain,
    }
    setattr(unreal, STATE, state)

    return _emit(
        "prepare",
        True,
        prepared=True,
        applied=0,
        total=len(cluster),
        material=material.get_path_name(),
        package=package,
        compile_drain=compile_drain,
        material_mode=material_mode,
        memory_checkpoints=checkpoints,
        memory=memory_after_compile_drain,
        sampling="bilinear + five-tap appearance smoothing",
        projection="WorldAlignedTexture + WorldAlignedNormal",
        scope="REFINEMENT_B_ROCK_SOIL_LANDSCAPE_BLEND",
    )


def apply_next():
    state = getattr(unreal, STATE, None)
    if not state:
        return _emit("apply", False, reason="run prepare first")

    if len(state["applied"]) >= len(state["components"]):
        return _emit(
            "apply",
            True,
            done=True,
            applied=len(state["applied"]),
            total=len(state["components"]),
        )

    memory = _memory()
    if not _memory_ok(
        memory,
        APPLY_FREE_PHYSICAL_GB,
        APPLY_FREE_COMMIT_GB,
    ):
        return _emit(
            "apply",
            False,
            reason="memory gate stopped before next component",
            applied=len(state["applied"]),
            memory=memory,
        )

    component = state["components"][len(state["applied"])]
    original = state["originals"][component.get_path_name()]
    if component.get_editor_property("override_material") != original:
        return _emit(
            "apply",
            False,
            reason="component override changed externally",
            component=component.get_name(),
        )

    try:
        component.set_editor_property("override_material", state["material"])
        if component.get_material(0) != state["material"]:
            raise RuntimeError("component render material did not update")
        if (
            state["landscape"].get_editor_property("landscape_material")
            != state["global_material"]
        ):
            raise RuntimeError("global Landscape material changed")
        state["applied"].append(component)
    except Exception:
        component.set_editor_property("override_material", original)
        raise

    return _emit(
        "apply",
        True,
        component=component.get_name(),
        applied=len(state["applied"]),
        total=len(state["components"]),
        remaining=len(state["components"]) - len(state["applied"]),
        memory=_memory(),
    )


def status():
    state = getattr(unreal, STATE, None)
    if not state:
        return _emit(
            "status",
            True,
            prepared=False,
            applied=0,
            memory=_memory(),
        )

    index = len(state["applied"])
    return _emit(
        "status",
        True,
        prepared=True,
        applied=index,
        total=len(state["components"]),
        applied_components=[
            component.get_name()
            for component in state["applied"]
        ],
        next_component=(
            None
            if index >= len(state["components"])
            else state["components"][index].get_name()
        ),
        memory=_memory(),
    )


def restore():
    state = getattr(unreal, STATE, None)
    if not state:
        return _emit(
            "restore",
            True,
            restored=0,
            note="nothing active",
        )

    restored = 0
    for component in reversed(state["applied"]):
        component.set_editor_property(
            "override_material",
            state["originals"][component.get_path_name()],
        )
        restored += 1

    current = state["foundation"]["scene_snapshot"](
        state["world"],
        state["landscape"],
        state["map_file"],
    )
    if current != state["snapshot"]:
        return _emit(
            "restore",
            False,
            reason="frozen scene snapshot mismatch after restore",
            restored=restored,
        )

    setattr(unreal, STATE, None)
    return _emit(
        "restore",
        True,
        restored=restored,
        memory=_memory(),
    )


def cleanup():
    try:
        return _emit(
            "cleanup",
            True,
            restored=_cleanup_known(),
            memory=_memory(),
        )
    except Exception as error:
        return _emit(
            "cleanup",
            False,
            error=str(error),
        )


def main(action: str):
    try:
        if action == "cleanup":
            return cleanup()
        if action == "probe":
            return probe()
        if action == "prepare":
            return prepare()
        if action == "apply":
            return apply_next()
        if action == "status":
            return status()
        if action == "restore":
            return restore()
        return _emit(action, False, reason="unknown action")
    except Exception as error:
        unreal.log_error(traceback.format_exc())
        return _emit(
            action,
            False,
            error=str(error),
            memory=_memory(),
        )

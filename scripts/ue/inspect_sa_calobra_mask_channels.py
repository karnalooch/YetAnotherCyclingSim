"""Save an isolated Landscape mask diagnostic with native unlit materials.

RGB is the unchanged input amplitude (R low vegetation, G forest fallback,
B dated rock share). Individual R/G/B/A views use grayscale. Neither mask data
nor geometry is edited; show_channel only changes the diagnostic-map material.
"""

import builtins
import json
import runpy
import uuid
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
LIB = unreal.MaterialEditingLibrary


def main():
    foundation = runpy.run_path(
        str(ROOT / "scripts/ue/sa_calobra_material_foundation.py")
    )
    canonical = runpy.run_path(
        str(ROOT / "scripts/ue/verify_sa_calobra_generated_surface_map.py")
    )["geometry"]
    receipt = json.loads(
        (
            ROOT
            / "worldgen/materials/sa_calobra_surface_presentation_result_20261005.json"
        ).read_text()
    )
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if (
        Path(unreal.Paths.project_dir()).resolve() != ROOT
        or world.get_path_name().split(".")[0] != receipt["review_map"]
    ):
        raise RuntimeError(
            "Open the saved presentation review map; no automatic switch"
        )
    if unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        raise RuntimeError("Preserve unsaved map edits first")
    source_file = (
        ROOT / "Content" / (receipt["review_map"].removeprefix("/Game/") + ".umap")
    )
    if foundation["digest"](source_file) != receipt["review_map_sha256"]:
        raise RuntimeError("Source review bytes changed")
    config = foundation["load_workspace"]()
    input_path = (
        Path(config["data"])
        / "world-data/sa-calobra-working-v1/material-foundation-v3-2026-10-05/material-input-manifest.json"
    )
    inputs = foundation["verified_inputs"](input_path)
    landscapes = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    if len(landscapes) != 1:
        raise RuntimeError("Expected one Landscape")
    landscape = landscapes[0]
    before = foundation["scene_snapshot"](world, landscape, source_file)
    if len(before["components"]) != 1024:
        raise RuntimeError("Unexpected topology")
    original = landscape.get_editor_property("landscape_material")
    if original.get_path_name() != receipt["material"]:
        raise RuntimeError("Unexpected source material")
    texture = foundation["load_required"](
        receipt["material"].rsplit("/", 1)[0] + "/T_SurfaceWeights"
    )
    if (
        texture.get_editor_property("srgb")
        or texture.get_editor_property("filter") != unreal.TextureFilter.TF_NEAREST
    ):
        raise RuntimeError("Unexpected weight sampling")
    key = uuid.uuid4().hex
    package = "/Game/Generated/YACS/MaskDiagnostic/" + key
    output_map = "/Game/Worlds/SaCalobra/L_SaCalobraMaskDiagnostic_" + key[:12]
    evidence = ROOT / "Saved/RuntimeProof/MaskDiagnostic" / key
    evidence.mkdir(parents=True, exist_ok=False)
    materials = {}
    for channel in ("RGB", "R", "G", "B", "A"):
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            "M_Mask_" + channel, package, unreal.Material, unreal.MaterialFactoryNew()
        )
        material.set_editor_property(
            "shading_model", unreal.MaterialShadingModel.MSM_UNLIT
        )

        def node(cls, **properties):
            value = LIB.create_material_expression(material, cls)
            if value is None:
                raise RuntimeError("Native node creation failed")
            for prop, setting in properties.items():
                value.set_editor_property(prop, setting)
            return value

        def link(source, output, target, pin):
            if not LIB.connect_material_expressions(source, output, target, pin):
                raise RuntimeError("Native connection failed: " + pin)

        position = node(unreal.MaterialExpressionWorldPosition)
        xy = node(unreal.MaterialExpressionComponentMask, r=True, g=True)
        link(position, "", xy, "")
        bounds = inputs["world_mapping"]["footprint_world_bounds_cm"]
        offset = node(
            unreal.MaterialExpressionConstant2Vector, r=-bounds[0], g=-bounds[1]
        )
        add = node(unreal.MaterialExpressionAdd)
        link(xy, "", add, "A")
        link(offset, "", add, "B")
        uv = node(
            unreal.MaterialExpressionDivide,
            const_b=inputs["grid"]["width"] * inputs["grid"]["pixel_size_m"] * 100,
        )
        link(add, "", uv, "A")
        sample = node(
            unreal.MaterialExpressionTextureSample,
            texture=texture,
            sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR,
        )
        link(uv, "", sample, "")
        mask = node(
            unreal.MaterialExpressionComponentMask,
            r="R" in channel or channel == "A",
            g="G" in channel,
            b="B" in channel,
            a=False,
        )
        link(sample, "A" if channel == "A" else "", mask, "")
        if not LIB.connect_material_property(
            mask, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
        ):
            raise RuntimeError("Diagnostic output failed")
        errors = LIB.recompile_material(material)
        if errors:
            raise RuntimeError("Diagnostic compile failed: " + str(errors))
        if not unreal.EditorAssetLibrary.save_loaded_asset(
            material, only_if_is_dirty=False
        ):
            raise RuntimeError("Diagnostic save failed")
        materials[channel] = material.get_path_name()
    try:
        landscape.set_editor_property(
            "landscape_material", foundation["load_required"](materials["RGB"])
        )
        after = foundation["scene_snapshot"](world, landscape, source_file)
        if before != after:
            raise RuntimeError("Frozen geometry differs")
        if not unreal.EditorLoadingAndSavingUtils.save_map(world, output_map):
            raise RuntimeError("Diagnostic map save failed")
    except Exception:
        landscape.set_editor_property("landscape_material", original)
        raise
    camera = editor.get_level_viewport_camera_info()
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(
        output_map
    ):
        raise RuntimeError("Diagnostic reload failed")
    world = editor.get_editor_world()
    landscape = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)[
        0
    ]
    if (
        canonical(before)
        != canonical(foundation["scene_snapshot"](world, landscape, source_file))
        or landscape.get_editor_property("landscape_material").get_path_name()
        != materials["RGB"]
    ):
        raise RuntimeError("Saved diagnostic consumer differs")
    if camera:
        editor.set_level_viewport_camera_info(*camera)
    if foundation["digest"](source_file) != receipt["review_map_sha256"]:
        raise RuntimeError("Source map bytes changed")
    report = {
        "status": "MASK_DIAGNOSTIC_SAVED_AND_RELOADED",
        "source_map": receipt["review_map"],
        "source_map_sha256": receipt["review_map_sha256"],
        "diagnostic_map": output_map,
        "materials": materials,
        "component_count": len(before["components"]),
        "actor_count": len(before["actors"]),
        "geometry_equal": True,
        "mask_sha256": foundation["digest"](input_path.parent / "material-weights.png"),
        "semantics": inputs["semantics"],
        "producer_sha256": foundation["digest"](__file__),
        "visual_review": "pending",
    }
    (evidence / "result.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )

    def show_channel(channel):
        current = editor.get_editor_world()
        if (
            current.get_path_name().split(".")[0] != output_map
            or channel not in materials
        ):
            raise RuntimeError("Channel switching is limited to this diagnostic map")
        target = unreal.GameplayStatics.get_all_actors_of_class(
            current, unreal.Landscape
        )[0]
        target.set_editor_property(
            "landscape_material", foundation["load_required"](materials[channel])
        )
        unreal.log("YACS_MASK_DIAGNOSTIC_CHANNEL " + channel)

    builtins.yacs_show_mask_channel = show_channel
    unreal.log("YACS_MASK_DIAGNOSTIC_READY " + str(evidence))
    return report


if __name__ == "__main__":
    main()

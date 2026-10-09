"""Toggle rock with sharper projection blending on the existing canary."""

import json
import os
import runpy
import uuid
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
LIB = unreal.MaterialEditingLibrary


def main():
    active = getattr(unreal, "_yacs_surface_component_preview", None)
    repair = getattr(unreal, "_yacs_projection_contrast_preview", None)
    if not active or not repair:
        raise RuntimeError("The contrast-checker one-component preview is required")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    foundation = runpy.run_path(
        str(ROOT / "scripts/ue/sa_calobra_material_foundation.py")
    )
    if (
        world.get_path_name() != active["world"]
        or foundation["scene_snapshot"](world, active["landscape"], active["map_file"])
        != active["snapshot"]
    ):
        raise RuntimeError("Preview world or frozen geometry changed")
    component = active["component"]
    state = getattr(unreal, "_yacs_rock_contrast_preview", None)
    expected = state["material"] if state else repair["material"]
    if component.get_editor_property("override_material") != expected:
        raise RuntimeError("The canary material changed outside this diagnostic")
    original = component.get_editor_property("override_material")
    global_material = active["landscape"].get_editor_property("landscape_material")
    others = {
        c.get_path_name(): c.get_editor_property("override_material")
        for c in active["landscape"].get_components_by_class(unreal.LandscapeComponent)
        if c != component
    }
    if state:
        target = state["original"]
        status = "CONTRAST_CHECKER_RESTORED"
    else:
        memory = runpy.run_path(str(ROOT / "scripts/ue/sa_calobra_material_waves.py"))[
            "available_memory"
        ]()
        if (
            memory["free_physical"] < 8 * 1024**3
            or memory["free_commit"] < 12 * 1024**3
        ):
            raise RuntimeError("Pause: insufficient memory headroom")
        receipt = json.loads(
            (
                ROOT
                / "worldgen/materials/sa_calobra_texture_library_result_20261005.json"
            ).read_text()
        )
        generation = json.loads(Path(receipt["generation_receipt"]).read_text())
        rock = next(row for row in generation["items"] if row["role"] == "ExposedRock")
        package = generation["library"] + "/Diagnostics/" + uuid.uuid4().hex
        target = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            "M_RockProjectionContrast",
            package,
            unreal.Material,
            unreal.MaterialFactoryNew(),
        )
        if target is None:
            raise RuntimeError("Diagnostic material creation failed")

        def node(cls, **properties):
            value = LIB.create_material_expression(target, cls)
            if value is None:
                raise RuntimeError("Diagnostic node creation failed")
            for name, setting in properties.items():
                value.set_editor_property(name, setting)
            return value

        def link(source, output, destination, pin):
            if not LIB.connect_material_expressions(source, output, destination, pin):
                raise RuntimeError("Diagnostic connection failed: " + pin)

        size = node(
            unreal.MaterialExpressionConstant3Vector,
            constant=unreal.LinearColor(300, 300, 300, 1),
        )
        contrast = node(
            unreal.MaterialExpressionConstant3Vector,
            constant=unreal.LinearColor(4, 4, 4, 1),
        )
        world_space = node(unreal.MaterialExpressionStaticBool, value=False)
        for channel, sampler, prop in (
            (
                "BaseColor",
                unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,
                unreal.MaterialProperty.MP_BASE_COLOR,
            ),
            (
                "Normal",
                unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,
                unreal.MaterialProperty.MP_NORMAL,
            ),
            (
                "Roughness",
                unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,
                unreal.MaterialProperty.MP_ROUGHNESS,
            ),
        ):
            obj = node(
                unreal.MaterialExpressionTextureObject,
                texture=foundation["load_required"](rock["outputs"][channel]["asset"]),
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
                raise RuntimeError("Native projection binding failed")
            link(obj, "", fn, "TextureObject")
            link(size, "", fn, "TextureSize")
            if channel != "Normal":
                link(contrast, "", fn, "ProjectionTransitionContrast")
            sample, pin = fn, "XYZ Texture"
            if channel == "Normal":
                link(world_space, "", fn, "WorldSpace")
                sample = node(unreal.MaterialExpressionNormalize)
                link(fn, pin, sample, "")
                pin = ""
            elif channel == "Roughness":
                sample = node(
                    unreal.MaterialExpressionComponentMask,
                    r=True,
                    g=False,
                    b=False,
                    a=False,
                )
                link(fn, pin, sample, "")
                pin = ""
            else:
                desaturate = node(unreal.MaterialExpressionDesaturation)
                fraction = node(unreal.MaterialExpressionConstant, r=0.65)
                link(fn, pin, desaturate, "")
                link(fraction, "", desaturate, "Fraction")
                gain = node(
                    unreal.MaterialExpressionConstant3Vector,
                    constant=unreal.LinearColor(0.98, 1, 1.02, 1),
                )
                sample = node(unreal.MaterialExpressionMultiply)
                link(desaturate, "", sample, "A")
                link(gain, "", sample, "B")
                pin = ""
            if not LIB.connect_material_property(sample, pin, prop):
                raise RuntimeError("Diagnostic material output failed")
        errors = LIB.recompile_material(target)
        if errors:
            raise RuntimeError("Diagnostic compile errors: " + str(errors))
        state = {"original": original, "material": target}
        status = "ROCK_CONTRAST_ONE_COMPONENT_ASSIGNED"
    try:
        component.set_editor_property("override_material", target)
        if component.get_material(0) != target:
            raise RuntimeError("Diagnostic consumer failed to update")
        if (
            active["landscape"].get_editor_property("landscape_material")
            != global_material
        ):
            raise RuntimeError("Global material changed")
        if any(
            c.get_editor_property("override_material") != others[c.get_path_name()]
            for c in active["landscape"].get_components_by_class(
                unreal.LandscapeComponent
            )
            if c != component
        ):
            raise RuntimeError("Another component changed")
        if (
            foundation["scene_snapshot"](world, active["landscape"], active["map_file"])
            != active["snapshot"]
        ):
            raise RuntimeError("Frozen geometry changed")
    except Exception:
        component.set_editor_property("override_material", original)
        raise
    unreal._yacs_rock_contrast_preview = state if status.startswith("ROCK") else None
    result = {
        "status": status,
        "material": target.get_path_name(),
        "component": component.get_path_name(),
        "map_saved": False,
        "source_masks_changed": False,
        "geometry_unchanged": True,
    }
    out = ROOT / "Saved/RuntimeProof/RockProjectionContrast"
    out.mkdir(parents=True, exist_ok=True)
    (out / (str(os.getpid()) + ".json")).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    unreal.log("YACS_ROCK_PROJECTION_CONTRAST " + json.dumps(result))


if __name__ == "__main__":
    main()

"""Toggle subtle continuous 3D limestone colour detail; no repeating image edges."""

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
    repair = getattr(unreal, "_yacs_uniform_limestone_preview", None)
    if not active or not repair:
        raise RuntimeError("The active uniform limestone preview is required")
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
    state = getattr(unreal, "_yacs_continuous_limestone_preview", None)
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
        status = "UNIFORM_MATERIAL_RESTORED"
    else:
        memory = runpy.run_path(str(ROOT / "scripts/ue/sa_calobra_material_waves.py"))[
            "available_memory"
        ]()
        if (
            memory["free_physical"] < 8 * 1024**3
            or memory["free_commit"] < 12 * 1024**3
        ):
            raise RuntimeError("Pause: insufficient memory headroom")
        package = original.get_path_name().rsplit("/", 2)[0] + "/" + uuid.uuid4().hex
        target = unreal.EditorAssetLibrary.duplicate_asset(
            original.get_path_name(), package + "/M_ContinuousPaleLimestone"
        )
        if target is None:
            raise RuntimeError("Diagnostic clone failed")
        for cls, property_name, value, output_property in (
            (unreal.MaterialExpressionConstant3Vector, "constant",
             unreal.LinearColor(0.45, 0.45, 0.45, 1), unreal.MaterialProperty.MP_BASE_COLOR),
            (unreal.MaterialExpressionConstant3Vector, "constant",
             unreal.LinearColor(0, 0, 1, 1), unreal.MaterialProperty.MP_NORMAL),
            (unreal.MaterialExpressionConstant, "r", 0.85,
             unreal.MaterialProperty.MP_ROUGHNESS),
        ):
            expression = LIB.create_material_expression(target, cls)
            if expression is None:
                raise RuntimeError("Uniform shading node creation failed")
            expression.set_editor_property(property_name, value)
            if not LIB.connect_material_property(expression, "", output_property):
                raise RuntimeError("Uniform shading connection failed")
        # Absolute world position sampled as a continuous 3D field: no UV image seams.
        def node(cls, **properties):
            value = LIB.create_material_expression(target, cls)
            if value is None:
                raise RuntimeError("Continuous detail node creation failed")
            for name, setting in properties.items():
                value.set_editor_property(name, setting)
            return value

        # UE 5.8 Noise uses absolute world position when its position pin is unconnected.
        noise = node(unreal.MaterialExpressionNoise, scale=0.04, levels=2,
                     quality=1, output_min=0.41, output_max=0.49,
                     turbulence=False, tiling=False)
        if not LIB.connect_material_property(noise, "", unreal.MaterialProperty.MP_BASE_COLOR):
            raise RuntimeError("Continuous grey output failed")
        errors = LIB.recompile_material(target)
        if errors:
            raise RuntimeError("Diagnostic compile errors: " + str(errors))
        state = {"original": original, "material": target}
        status = "CONTINUOUS_LIMESTONE_ONE_COMPONENT_ASSIGNED"
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
    unreal._yacs_continuous_limestone_preview = state if status.startswith("CONTINUOUS") else None
    result = {
        "status": status,
        "material": target.get_path_name(),
        "component": component.get_path_name(),
        "map_saved": False,
        "shading": "continuous 3D grey variation 0.41-0.49 linear; flat Normal; Roughness 0.85",
        "source_masks_changed": False,
        "geometry_unchanged": True,
    }
    out = ROOT / "Saved/RuntimeProof/ContinuousLimestonePreview"
    out.mkdir(parents=True, exist_ok=True)
    (out / (str(os.getpid()) + ".json")).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    unreal.log("YACS_CONTINUOUS_LIMESTONE_PREVIEW " + json.dumps(result))


if __name__ == "__main__":
    main()

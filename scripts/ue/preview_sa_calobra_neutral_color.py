"""Toggle neutral Base Color on the existing canary; retain all other shading."""

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
    repair = getattr(unreal, "_yacs_rock_contrast_preview", None)
    if not active or not repair:
        raise RuntimeError("The rock-contrast one-component preview is required")
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
    state = getattr(unreal, "_yacs_neutral_color_preview", None)
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
        status = "ROCK_COLOR_RESTORED"
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
            original.get_path_name(), package + "/M_NeutralRockColor"
        )
        if target is None:
            raise RuntimeError("Diagnostic clone failed")
        preserved = {}
        for prop in (
            unreal.MaterialProperty.MP_NORMAL,
            unreal.MaterialProperty.MP_ROUGHNESS,
        ):
            preserved[prop] = (
                LIB.get_material_property_input_node(target, prop),
                LIB.get_material_property_input_node_output_name(target, prop),
            )
        gray = LIB.create_material_expression(
            target, unreal.MaterialExpressionConstant3Vector
        )
        if gray is None:
            raise RuntimeError("Gray node creation failed")
        gray.set_editor_property("constant", unreal.LinearColor(0.5, 0.5, 0.5, 1))
        if not LIB.connect_material_property(
            gray, "", unreal.MaterialProperty.MP_BASE_COLOR
        ):
            raise RuntimeError("Gray Base Color connection failed")
        for prop, connection in preserved.items():
            if connection != (
                LIB.get_material_property_input_node(target, prop),
                LIB.get_material_property_input_node_output_name(target, prop),
            ):
                raise RuntimeError("Normal or Roughness connection changed")
        errors = LIB.recompile_material(target)
        if errors:
            raise RuntimeError("Diagnostic compile errors: " + str(errors))
        state = {"original": original, "material": target}
        status = "NEUTRAL_COLOR_ONE_COMPONENT_ASSIGNED"
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
    unreal._yacs_neutral_color_preview = state if status.startswith("NEUTRAL") else None
    result = {
        "status": status,
        "material": target.get_path_name(),
        "component": component.get_path_name(),
        "map_saved": False,
        "normal_and_roughness": "unchanged from cloned source",
        "source_masks_changed": False,
        "geometry_unchanged": True,
    }
    out = ROOT / "Saved/RuntimeProof/NeutralColorPreview"
    out.mkdir(parents=True, exist_ok=True)
    (out / (str(os.getpid()) + ".json")).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    unreal.log("YACS_NEUTRAL_COLOR_PREVIEW " + json.dumps(result))


if __name__ == "__main__":
    main()

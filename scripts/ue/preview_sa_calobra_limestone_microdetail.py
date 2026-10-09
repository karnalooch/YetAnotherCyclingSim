"""Toggle restrained procedural micro-normal and roughness on the continuous canary."""

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
    repair = getattr(unreal, "_yacs_continuous_limestone_preview", None)
    if not active or not repair:
        raise RuntimeError("The active continuous limestone preview is required")
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
    state = getattr(unreal, "_yacs_limestone_microdetail_preview", None)
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
        status = "CONTINUOUS_MATERIAL_RESTORED"
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
            original.get_path_name(), package + "/M_MicrodetailPaleLimestone"
        )
        if target is None:
            raise RuntimeError("Diagnostic clone failed")
        def node(cls, **properties):
            value = LIB.create_material_expression(target, cls)
            if value is None:
                raise RuntimeError("Microdetail node creation failed")
            for name, setting in properties.items():
                value.set_editor_property(name, setting)
            return value

        def link(source, destination, pin):
            if not LIB.connect_material_expressions(source, "", destination, pin):
                raise RuntimeError("Microdetail connection failed: " + pin)

        # Decorative low-amplitude normal variation, not a scanned height derivative.
        # Absolute-world noise avoids repeating image edges and projection blends.
        nx = node(unreal.MaterialExpressionNoise, scale=0.18, levels=1,
                  quality=1, output_min=-0.055, output_max=0.055,
                  turbulence=False, tiling=False)
        ny = node(unreal.MaterialExpressionNoise, scale=0.237, levels=1,
                  quality=1, output_min=-0.055, output_max=0.055,
                  turbulence=False, tiling=False)
        xy = node(unreal.MaterialExpressionAppendVector)
        link(nx, xy, "A")
        link(ny, xy, "B")
        one = node(unreal.MaterialExpressionConstant, r=1.0)
        xyz = node(unreal.MaterialExpressionAppendVector)
        link(xy, xyz, "A")
        link(one, xyz, "B")
        normal = node(unreal.MaterialExpressionNormalize)
        link(xyz, normal, "")
        roughness = node(unreal.MaterialExpressionNoise, scale=0.08, levels=1,
                         quality=1, output_min=0.78, output_max=0.88,
                         turbulence=False, tiling=False)
        for expression, prop in (
            (normal, unreal.MaterialProperty.MP_NORMAL),
            (roughness, unreal.MaterialProperty.MP_ROUGHNESS),
        ):
            if not LIB.connect_material_property(expression, "", prop):
                raise RuntimeError("Microdetail output failed")
        errors = LIB.recompile_material(target)
        if errors:
            raise RuntimeError("Diagnostic compile errors: " + str(errors))
        state = {"original": original, "material": target}
        status = "MICRODETAIL_LIMESTONE_ONE_COMPONENT_ASSIGNED"
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
    unreal._yacs_limestone_microdetail_preview = state if status.startswith("MICRODETAIL") else None
    result = {
        "status": status,
        "material": target.get_path_name(),
        "component": component.get_path_name(),
        "map_saved": False,
        "shading": "unchanged continuous grey; decorative XY normal +/-0.055; roughness 0.78-0.88",
        "source_masks_changed": False,
        "geometry_unchanged": True,
    }
    out = ROOT / "Saved/RuntimeProof/MicrodetailLimestonePreview"
    out.mkdir(parents=True, exist_ok=True)
    (out / (str(os.getpid()) + ".json")).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    unreal.log("YACS_MICRODETAIL_LIMESTONE_PREVIEW " + json.dumps(result))


if __name__ == "__main__":
    main()

"""Repair sharp inferred gaps in three bounded waves on the active canary."""

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
    if active is None:
        raise RuntimeError("An active one-component preview is required")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world.get_path_name() != active["world"]:
        raise RuntimeError("Preview world changed")
    foundation = runpy.run_path(
        str(ROOT / "scripts/ue/sa_calobra_material_foundation.py")
    )
    current_snapshot = foundation["scene_snapshot"](
        world, active["landscape"], active["map_file"]
    )
    if current_snapshot != active["snapshot"]:
        before_actors = dict(active["snapshot"]["actors"])
        current_actors = dict(current_snapshot["actors"])
        added = set(current_actors) - set(before_actors)
        expected_registry = active["world"] + ":PersistentLevel.PCGWorldActor_0"
        other_fields_equal = all(
            value == active["snapshot"][key]
            for key, value in current_snapshot.items()
            if key != "actors"
        )
        existing_actors_equal = all(
            current_actors.get(path) == transform
            for path, transform in before_actors.items()
        )
        if (
            added == {expected_registry}
            and other_fields_equal
            and existing_actors_equal
        ):
            registries = [
                actor
                for actor in unreal.get_editor_subsystem(
                    unreal.EditorActorSubsystem
                ).get_all_level_actors()
                if actor.get_path_name() == expected_registry
            ]
            if (
                len(registries) == 1
                and registries[0].get_class().get_name() == "PCGWorldActor"
                and not registries[0].get_components_by_class(unreal.PrimitiveComponent)
            ):
                # Adopt only the verified non-geometric editor registry addition.
                active["snapshot"] = current_snapshot
                active["registry_addition"] = expected_registry
                unreal.log(
                    "YACS_NON_GEOMETRIC_PCG_REGISTRY_ADDITION " + expected_registry
                )
    if current_snapshot != active["snapshot"]:
        differences = {
            key: {"before": active["snapshot"][key], "current": value}
            for key, value in current_snapshot.items()
            if value != active["snapshot"][key]
        }
        out = ROOT / "Saved/RuntimeProof/SurfaceTransitionRepair"
        out.mkdir(parents=True, exist_ok=True)
        (out / "geometry-difference.json").write_text(
            json.dumps(differences, indent=2) + "\n", encoding="utf-8"
        )
        unreal.log_error("YACS_PREVIEW_DIFFERENCE_FIELDS " + str(list(differences)))
        raise RuntimeError("Preview state differs; diagnostic saved, no repair applied")
    memory = runpy.run_path(str(ROOT / "scripts/ue/sa_calobra_material_waves.py"))[
        "available_memory"
    ]()
    if memory["free_physical"] < 8 * 1024**3 or memory["free_commit"] < 12 * 1024**3:
        raise RuntimeError("Pause: insufficient memory headroom")
    state = getattr(unreal, "_yacs_transition_repair", None)
    if state is None:
        original = active["component"].get_editor_property("override_material")
        if (
            not original
            or "/c73151db58b34971b70d2bd74e6f4795/" not in original.get_path_name()
        ):
            raise RuntimeError("Unexpected original canary material")
        package = original.get_path_name().rsplit("/", 2)[0] + "/" + uuid.uuid4().hex
        state = {"phase": "CLONING", "original": original, "package": package}
        unreal._yacs_transition_repair = state
        material = unreal.EditorAssetLibrary.duplicate_asset(
            original.get_path_name(), package + "/M_SaCalobraSmoothTransitions"
        )
        if material is None:
            raise RuntimeError("Material clone failed")
        expressions = LIB.get_material_expressions(material)
        gaps = [
            e
            for e in expressions
            if isinstance(e, unreal.MaterialExpressionMultiply)
            and e.get_editor_property("const_b") == -1000.0
        ]
        samples = [
            e
            for e in expressions
            if isinstance(e, unreal.MaterialExpressionTextureSample)
            and e.get_editor_property("texture").get_name() == "T_SurfaceWeights"
        ]
        if len(gaps) != 1 or len(samples) != 1:
            raise RuntimeError("Unexpected graph; fail before changing the consumer")
        texture = unreal.EditorAssetLibrary.duplicate_asset(
            samples[0].get_editor_property("texture").get_path_name(),
            package + "/T_SmoothSurfaceWeights",
        )
        if texture is None:
            raise RuntimeError("Weight texture clone failed")
        texture.set_editor_property("filter", unreal.TextureFilter.TF_BILINEAR)
        samples[0].set_editor_property("texture", texture)
        # Continuous unclassified remainder instead of an exact zero/one gate.
        # Existing raw data/placement masks stay unchanged and unadmitted.
        gaps[0].set_editor_property("const_b", -1.0)
        state.update(material=material, texture=texture, phase="EDITED_NOT_COMPILED")
    elif state["phase"] == "EDITED_NOT_COMPILED":
        errors = LIB.recompile_material(state["material"])
        if errors:
            raise RuntimeError("Compile errors: " + str(errors))
        state["phase"] = "COMPILE_CALL_RETURNED"
    elif state["phase"] == "COMPILE_CALL_RETURNED":
        for asset in (state["material"], state["texture"]):
            if not unreal.EditorAssetLibrary.save_loaded_asset(
                asset, only_if_is_dirty=False
            ):
                raise RuntimeError("Repair asset save failed")
        component = active["component"]
        others = {
            c.get_path_name(): c.get_editor_property("override_material")
            for c in active["landscape"].get_components_by_class(
                unreal.LandscapeComponent
            )
            if c != component
        }
        global_material = active["landscape"].get_editor_property("landscape_material")
        try:
            component.set_editor_property("override_material", state["material"])
            if component.get_material(0) != state["material"]:
                raise RuntimeError("Canary consumer failed to update")
            if (
                active["landscape"].get_editor_property("landscape_material")
                != global_material
            ):
                raise RuntimeError("Global Landscape material changed")
            if any(
                c.get_editor_property("override_material") != others[c.get_path_name()]
                for c in active["landscape"].get_components_by_class(
                    unreal.LandscapeComponent
                )
                if c != component
            ):
                raise RuntimeError("Another component changed")
            if (
                foundation["scene_snapshot"](
                    world, active["landscape"], active["map_file"]
                )
                != active["snapshot"]
            ):
                raise RuntimeError("Frozen geometry changed")
        except Exception:
            component.set_editor_property("override_material", state["original"])
            raise
        state["phase"] = "ONE_COMPONENT_REPAIR_ASSIGNED"
    else:
        raise RuntimeError("Do not rerun a completed or interrupted repair")
    result = {
        "status": state["phase"],
        "memory_before": memory,
        "material": state["material"].get_path_name(),
        "texture": state["texture"].get_path_name(),
        "recipe": "Bilinear appearance sampling; gap = saturate(1 - RGBsum)",
        "map_saved": False,
        "source_masks_changed": False,
        "changed_component_count": 1
        if state["phase"] == "ONE_COMPONENT_REPAIR_ASSIGNED"
        else 0,
        "visual_acceptance": "pending",
        "performance": "not measured",
    }
    out = ROOT / "Saved/RuntimeProof/SurfaceTransitionRepair"
    out.mkdir(parents=True, exist_ok=True)
    (out / (str(os.getpid()) + ".json")).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    unreal.log("YACS_TRANSITION_REPAIR " + json.dumps(result))


if __name__ == "__main__":
    main()

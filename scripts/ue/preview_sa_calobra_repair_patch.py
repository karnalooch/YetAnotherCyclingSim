"""Reversible one-component preview of a hash-verified offline material.

Run again to restore. Never saves a map or changes texture residency settings.
"""

import hashlib
import json
import runpy
import uuid
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "Saved/RuntimeProof/MaterialRepair/offline-preparation.json"
KEY = "_yacs_repair_patch"


def main(action="toggle"):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    active = getattr(unreal, KEY, None)
    if action == "save_instance":
        if not active:
            raise RuntimeError("No active patch preview")
        instance = active["instance"]
        path = instance.get_path_name().split(".")[0]
        if not path.startswith("/Game/Generated/YACS/MaterialRepair/"):
            raise RuntimeError("Instance outside repair namespace")
        if not unreal.EditorAssetLibrary.save_loaded_asset(
            instance, only_if_is_dirty=False
        ):
            raise RuntimeError("Instance save failed")
        file = ROOT / "Content" / (path.removeprefix("/Game/") + ".uasset")
        receipt = {
            "status": "SAVED_DIAGNOSTIC_INSTANCE",
            "asset": file.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
            "instance": instance.get_path_name(),
            "map_saved": False,
            "tints": active.get("tints", {}),
            "visual_acceptance": "PENDING",
            "performance": "NOT_MEASURED",
        }
        (REPORT.parent / "saved-patch-instance.json").write_text(
            json.dumps(receipt, indent=2), encoding="utf-8"
        )
        unreal.log("YACS_REPAIR_PATCH_INSTANCE_SAVED")
        return
    if action == "tune":
        if not active:
            raise RuntimeError("No active patch preview")
        lib = unreal.MaterialEditingLibrary
        values = {
            "GrassTint": (0.32, 0.42, 0.20),
            "ForestTint": (0.19, 0.25, 0.13),
            "RockTint": (0.72, 0.73, 0.70),
            "RockLift": (0.05, 0.05, 0.048),
        }
        for name, value in values.items():
            lib.set_material_instance_vector_parameter_value(
                active["instance"], name, unreal.LinearColor(*value, 1)
            )
            actual = lib.get_material_instance_vector_parameter_value(
                active["instance"], name
            )
            if any(
                abs(a - b) > 1e-6 for a, b in zip((actual.r, actual.g, actual.b), value)
            ):
                raise RuntimeError("Tint readback failed: " + name)
        origin, extent, _ = unreal.SystemLibrary.get_component_bounds(
            active["component"]
        )
        hit = unreal.SystemLibrary.line_trace_single(
            active["state"]["world"],
            unreal.Vector(origin.x, origin.y, origin.z + extent.z + 1000),
            unreal.Vector(origin.x, origin.y, origin.z - extent.z - 1000),
            unreal.TraceTypeQuery.ECC_VISIBILITY,
            True,
            [],
            unreal.DrawDebugTrace.NONE,
            True,
        )
        points = [
            p
            for p in (() if hit is None else hit.to_tuple())
            if all(hasattr(p, axis) for axis in ("x", "y", "z"))
            and abs(p.x - origin.x) < 0.1
            and abs(p.y - origin.y) < 0.1
        ]
        if not points:
            raise RuntimeError("No surface trace for detail camera")
        editor.set_level_viewport_camera_info(
            unreal.Vector(origin.x, origin.y, points[0].z + 180),
            unreal.Rotator(pitch=-20, yaw=45, roll=0),
        )
        active["tints"] = values
        unreal.log("YACS_REPAIR_PATCH_TUNED")
        return
    if action == "inspect":
        if not active:
            raise RuntimeError("No active patch preview")
        rows = [
            json.loads(unreal.YacsTextureAuditLibrary.describe_texture(t))
            for t in unreal.MaterialEditingLibrary.get_used_textures(
                active["instance"].get_editor_property("parent")
            )
        ]
        (REPORT.parent / "patch-residency.json").write_text(
            json.dumps(rows, indent=2), encoding="utf-8"
        )
        unreal.log("YACS_REPAIR_PATCH_RESIDENCY_CAPTURED")
        return
    if action != "toggle":
        raise ValueError("Unknown preview action")
    if active:
        if editor.get_editor_world() != active["state"]["world"]:
            raise RuntimeError("Preview world changed; preserve user work")
        active["component"].set_editor_property("override_material", active["original"])
        editor.set_level_viewport_camera_info(*active["camera"])
        setattr(unreal, KEY, None)
        unreal.log("YACS_REPAIR_PATCH_RESTORED")
        return
    report = json.loads(REPORT.read_text())
    file = (ROOT / report["asset"]).resolve()
    if not file.is_relative_to(ROOT / "Content/Generated/YACS/MaterialRepair"):
        raise RuntimeError("Material outside repair namespace")
    if hashlib.sha256(file.read_bytes()).hexdigest() != report["sha256"]:
        raise RuntimeError("Prepared material identity mismatch")
    if unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        raise RuntimeError("Preserve unsaved map work before a new preview")
    memory = runpy.run_path(str(ROOT / "scripts/ue/sa_calobra_material_waves.py"))[
        "available_memory"
    ]()
    if memory["free_physical"] < 8 * 1024**3 or memory["free_commit"] < 12 * 1024**3:
        raise RuntimeError("Insufficient memory headroom for one-component preview")
    repair = runpy.run_path(str(ROOT / "scripts/ue/sa_calobra_material_repair.py"))
    state = repair["context"]()
    camera = editor.get_level_viewport_camera_info()
    component = min(
        state["components"],
        key=lambda c: sum(
            (
                getattr(unreal.SystemLibrary.get_component_bounds(c)[0], axis)
                - getattr(camera[0], axis)
            )
            ** 2
            for axis in ("x", "y")
        ),
    )
    parent = unreal.load_asset(report["material"])
    if not parent:
        raise RuntimeError("Cannot load prepared material")
    lib = unreal.MaterialEditingLibrary
    instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "MI_SaCalobraRepairPreview",
        "/Game/Generated/YACS/MaterialRepair/" + uuid.uuid4().hex,
        unreal.MaterialInstanceConstant,
        unreal.MaterialInstanceConstantFactoryNew(),
    )
    lib.set_material_instance_parent(instance, parent)
    parameters = {"GroundMetres": 3.0, "RockMesoMetres": 8.0, "NormalStrength": 0.25}
    available = {str(name) for name in lib.get_scalar_parameter_names(parent)}
    for name, value in parameters.items():
        if name not in available:
            raise RuntimeError("Unknown material parameter: " + name)
        # Installed UE 5.8.2 returns false unconditionally from this setter.
        # Verify the parameter inventory and actual readback instead.
        lib.set_material_instance_scalar_parameter_value(instance, name, value)
        if (
            abs(
                lib.get_material_instance_scalar_parameter_value(instance, name) - value
            )
            > 1e-6
        ):
            raise RuntimeError("Material parameter readback mismatch: " + name)
    lib.update_material_instance(instance)
    original = component.get_editor_property("override_material")
    active = dict(
        state=state,
        component=component,
        original=original,
        camera=camera,
        instance=instance,
    )
    setattr(unreal, KEY, active)
    try:
        component.set_editor_property("override_material", instance)
        if component.get_material(0) != instance:
            raise RuntimeError("Preview consumer did not update")
        if any(
            c.get_editor_property("override_material")
            for c in state["components"]
            if c != component
        ):
            raise RuntimeError("Other component overrides changed")
        if (
            state["landscape"].get_editor_property("landscape_material")
            != state["original"]
        ):
            raise RuntimeError("Global material changed")
        if repair["snapshot"](state) != state["before"]:
            raise RuntimeError("Frozen scene changed")
    except Exception:
        component.set_editor_property("override_material", original)
        setattr(unreal, KEY, None)
        raise
    origin, extent, _ = unreal.SystemLibrary.get_component_bounds(component)
    editor.set_level_viewport_camera_info(
        unreal.Vector(origin.x - 3500, origin.y - 3500, origin.z + extent.z + 4000),
        unreal.Rotator(pitch=-40, yaw=45, roll=0),
    )
    output = dict(
        status="ONE_COMPONENT_PREVIEW_ASSIGNED",
        component=component.get_path_name(),
        parent=report["material"],
        parameters=parameters,
        geometry_snapshot_equal=True,
        changed_component_count=1,
        map_saved=False,
        visual_acceptance="PENDING",
        performance="NOT_MEASURED",
        memory_before=memory,
    )
    (REPORT.parent / "patch-preview.json").write_text(
        json.dumps(output, indent=2), encoding="utf-8"
    )
    unreal.log("YACS_REPAIR_PATCH_ASSIGNED")


if __name__ == "__main__":
    main()

"""Toggle a session-only material preview on one Landscape component.

Run again to restore its original override and camera. Do not save the map
while the preview is active. SetMaterial is intentionally NOT used: UE 5.8's
Landscape implementation changes the entire proxy through that API.
"""

import json
import os
import runpy
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
REPORT = (
    ROOT
    / "Saved/RuntimeProof/TextureLandscape/c73151db58b34971b70d2bd74e6f4795/result.json"
)


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    active = getattr(unreal, "_yacs_surface_component_preview", None)
    foundation = runpy.run_path(
        str(ROOT / "scripts/ue/sa_calobra_material_foundation.py")
    )
    if active is not None:
        if world.get_path_name() != active["world"]:
            raise RuntimeError("Preview belongs to another world; no automatic switch")
        active["component"].set_editor_property("override_material", active["original"])
        if active["camera"]:
            editor.set_level_viewport_camera_info(*active["camera"])
        if (
            foundation["scene_snapshot"](world, active["landscape"], active["map_file"])
            != active["snapshot"]
        ):
            raise RuntimeError("Geometry changed during preview; preserve user work")
        unreal._yacs_surface_component_preview = None
        unreal.log("YACS_SURFACE_COMPONENT_PREVIEW_RESTORED")
        return
    receipt = json.loads(REPORT.read_text())
    if receipt["status"] != "MATERIAL_PREPARED_NOT_APPLIED":
        raise RuntimeError("Expected saved prepared material")
    if world.get_path_name().split(".")[0] != receipt["source_checkpoint"]:
        raise RuntimeError("Open the preparation source map")
    if unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        raise RuntimeError("Preserve unsaved map edits before preview")
    map_file = (
        ROOT
        / "Content"
        / (receipt["source_checkpoint"].removeprefix("/Game/") + ".umap")
    )
    if foundation["digest"](map_file) != receipt["source_checkpoint_sha256"]:
        raise RuntimeError("Recorded source map bytes changed")
    foundation["verified_inputs"](Path(receipt["presentation"]["surface_domains"]))
    memory = runpy.run_path(str(ROOT / "scripts/ue/sa_calobra_material_waves.py"))[
        "available_memory"
    ]()
    if memory["free_physical"] < 8 * 1024**3 or memory["free_commit"] < 12 * 1024**3:
        raise RuntimeError("Not enough memory headroom for the preview")
    landscapes = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    if len(landscapes) != 1:
        raise RuntimeError("Expected one frozen Landscape")
    landscape = landscapes[0]
    components = landscape.get_components_by_class(unreal.LandscapeComponent)
    if len(components) != 1024:
        raise RuntimeError("Unexpected Landscape topology")
    camera = editor.get_level_viewport_camera_info()
    if not camera:
        raise RuntimeError("No active editor camera")

    def distance(component):
        origin = unreal.SystemLibrary.get_component_bounds(component)[0]
        return (origin.x - camera[0].x) ** 2 + (origin.y - camera[0].y) ** 2

    component = min(components, key=distance)
    original = component.get_editor_property("override_material")
    other_overrides = {
        c.get_path_name(): c.get_editor_property("override_material")
        for c in components
        if c != component
    }
    original_global = landscape.get_editor_property("landscape_material")
    snapshot = foundation["scene_snapshot"](world, landscape, map_file)
    material = foundation["load_required"](receipt["material"])
    active = {
        "world": world.get_path_name(),
        "component": component,
        "original": original,
        "camera": camera,
        "landscape": landscape,
        "snapshot": snapshot,
        "map_file": map_file,
    }
    # Keep a restore handle even if the native update/check fails.
    unreal._yacs_surface_component_preview = active
    try:
        component.set_editor_property("override_material", material)
        if component.get_material(0) != material:
            raise RuntimeError("Component material consumer did not update")
        if landscape.get_editor_property("landscape_material") != original_global:
            raise RuntimeError("Whole Landscape material unexpectedly changed")
        if any(
            c.get_editor_property("override_material")
            != other_overrides[c.get_path_name()]
            for c in components
            if c != component
        ):
            raise RuntimeError("Another component override changed")
        if snapshot != foundation["scene_snapshot"](world, landscape, map_file):
            raise RuntimeError("Preview changed frozen geometry")
    except Exception:
        component.set_editor_property("override_material", original)
        unreal._yacs_surface_component_preview = None
        raise
    origin, extent, _ = unreal.SystemLibrary.get_component_bounds(component)
    editor.set_level_viewport_camera_info(
        unreal.Vector(origin.x - 7000, origin.y - 7000, origin.z + extent.z + 8000),
        unreal.Rotator(pitch=-40, yaw=45, roll=0),
    )
    result = {
        "status": "ONE_COMPONENT_SESSION_PREVIEW_ASSIGNED",
        "component": component.get_path_name(),
        "material": material.get_path_name(),
        "component_count": len(components),
        "changed_component_count": 1,
        "other_overrides_unchanged": True,
        "global_material_unchanged": True,
        "geometry_snapshot_equal": True,
        "saved_map_unchanged": True,
        "memory_before": memory,
        "map_saved": False,
        "visual_acceptance": "pending",
        "performance": "not measured",
        "restore": "Execute this same script again; do not save the map during preview",
    }
    out = ROOT / "Saved/RuntimeProof/SurfaceComponentPreview"
    out.mkdir(parents=True, exist_ok=True)
    (out / (str(os.getpid()) + ".json")).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    unreal.log("YACS_SURFACE_COMPONENT_PREVIEW " + json.dumps(result))


if __name__ == "__main__":
    main()

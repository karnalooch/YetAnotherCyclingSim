"""Reload the saved review map in the existing editor and verify its consumer.

This is a same-process persistence check, not fresh-editor or performance proof.
The source checkpoint is never saved; its live material change was preserved in
the separate review map before the explicit map switch.
"""

import json
import os
import runpy
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
REPORT = (
    ROOT
    / "Saved/RuntimeProof/TextureLandscape/9970b3cdfd464d619eb7f8fc873b23d7/result.json"
)


def geometry(snapshot):
    return {
        "actors": [
            (path.split(":", 1)[-1], transform)
            for path, transform in snapshot["actors"]
        ],
        "components": [path.split(":", 1)[-1] for path in snapshot["components"]],
        "layers": snapshot["layers"],
        "traces": snapshot["traces"],
    }


def main():
    if Path(unreal.Paths.project_dir()).resolve() != ROOT:
        raise RuntimeError("Wrong project")
    foundation = runpy.run_path(
        str(ROOT / "scripts/ue/sa_calobra_material_foundation.py")
    )
    receipt = json.loads(REPORT.read_text())
    if receipt["status"] != "GENERATED_SURFACES_APPLIED_REVIEW_MAP_SAVED":
        raise RuntimeError("Review map not saved")
    output = REPORT.parent / "same-editor-reload.json"
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if output.exists():
        previous = json.loads(output.read_text())
        fresh_output = REPORT.parent / "fresh-editor-reload.json"
        if previous["process_id"] == os.getpid() or fresh_output.exists():
            raise RuntimeError("Fresh-editor proof requires a new process and receipt")
        if world.get_path_name().split(".")[0] == foundation["load_workspace"]()["map"]:
            if unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
                raise RuntimeError("Preserve unsaved changes to the startup map")
            if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(
                receipt["review_map"]
            ):
                raise RuntimeError("Review map did not load in the fresh editor")
            world = editor.get_editor_world()
        if world.get_path_name().split(".")[0] != receipt["review_map"]:
            raise RuntimeError("Open the saved review map in the fresh editor")
        landscapes = unreal.GameplayStatics.get_all_actors_of_class(
            world, unreal.Landscape
        )
        if len(landscapes) != 1:
            raise RuntimeError("Saved Landscape missing")
        source = (
            ROOT
            / "Content"
            / (receipt["source_checkpoint"].removeprefix("/Game/") + ".umap")
        )
        review = (
            ROOT / "Content" / (receipt["review_map"].removeprefix("/Game/") + ".umap")
        )
        assigned = landscapes[0].get_editor_property("landscape_material")
        actual = geometry(foundation["scene_snapshot"](world, landscapes[0], source))
        if (
            json.loads(json.dumps(actual)) != previous["geometry_snapshot"]
            or assigned.get_path_name() != receipt["material"]
        ):
            raise RuntimeError("Fresh-editor geometry or material differs")
        if (
            foundation["digest"](source) != receipt["source_checkpoint_sha256"]
            or foundation["digest"](review) != previous["review_map_sha256"]
        ):
            raise RuntimeError("Saved map bytes changed")
        fresh_output.write_text(
            json.dumps(
                {
                    "status": "FRESH_EDITOR_GEOMETRY_AND_MATERIAL_VERIFIED",
                    "process_id": os.getpid(),
                    "previous_process_id": previous["process_id"],
                    "map": world.get_path_name(),
                    "material": assigned.get_path_name(),
                    "component_count": len(actual["components"]),
                    "geometry_equal": True,
                    "source_checkpoint_unchanged": True,
                    "review_map_sha256": previous["review_map_sha256"],
                    "native_render_instance_audit": "unavailable in current binary",
                    "visual_acceptance": "pending",
                    "performance": "not measured",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        unreal.log("YACS_SURFACE_FRESH_EDITOR_VERIFIED " + str(fresh_output))
        return
    if world.get_path_name().split(".")[0] != receipt["source_checkpoint"]:
        raise RuntimeError("Unexpected current map; preserve the user's session")
    landscapes = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    if (
        len(landscapes) != 1
        or landscapes[0].get_editor_property("landscape_material").get_path_name()
        != receipt["material"]
    ):
        raise RuntimeError("Expected applied review material")
    source = (
        ROOT
        / "Content"
        / (receipt["source_checkpoint"].removeprefix("/Game/") + ".umap")
    )
    review = ROOT / "Content" / (receipt["review_map"].removeprefix("/Game/") + ".umap")
    digest = foundation["digest"]
    if digest(source) != receipt["source_checkpoint_sha256"]:
        raise RuntimeError("Source checkpoint differs")
    before = geometry(foundation["scene_snapshot"](world, landscapes[0], source))
    review_hash = digest(review)
    camera = editor.get_level_viewport_camera_info()
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(
        receipt["review_map"]
    ):
        raise RuntimeError("Saved review map did not load")
    world = editor.get_editor_world()
    landscapes = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    if len(landscapes) != 1:
        raise RuntimeError("Reloaded Landscape missing")
    assigned = landscapes[0].get_editor_property("landscape_material")
    after = geometry(foundation["scene_snapshot"](world, landscapes[0], source))
    if before != after or assigned.get_path_name() != receipt["material"]:
        raise RuntimeError("Saved geometry or material assignment differs")
    if (
        digest(source) != receipt["source_checkpoint_sha256"]
        or digest(review) != review_hash
    ):
        raise RuntimeError("Map bytes changed during reload")
    if camera is not None:
        editor.set_level_viewport_camera_info(*camera)
    report = {
        "status": "SAME_EDITOR_RELOAD_VERIFIED",
        "process_id": os.getpid(),
        "map": world.get_path_name(),
        "material": assigned.get_path_name(),
        "geometry_equal": True,
        "component_count": len(after["components"]),
        "actor_count": len(after["actors"]),
        "geometry_snapshot": after,
        "review_map_sha256": review_hash,
        "source_checkpoint_unchanged": True,
        "fresh_editor_proof": False,
        "native_render_instance_audit": "unavailable in current binary",
        "visual_acceptance": "pending",
        "performance": "not measured",
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    unreal.log("YACS_SURFACE_MAP_RELOAD_VERIFIED " + str(output))


if __name__ == "__main__":
    main()

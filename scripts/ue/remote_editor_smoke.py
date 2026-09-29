"""Transient Unreal Editor proof for the YACS remote command bridge.

This script is intentionally fixed-purpose. It does not load arbitrary user input,
save a level, create an asset, or persist an actor.
"""

import json
import os
from pathlib import Path

import unreal


PROOF_ENV = "YACS_REMOTE_PROOF_PATH"
ACTOR_LABEL = "YACS_REMOTE_SMOKE_CUBE"
CUBE_ASSET = "/Engine/BasicShapes/Cube.Cube"


def _require_proof_path() -> Path:
    raw = os.environ.get(PROOF_ENV, "").strip()
    if not raw:
        raise RuntimeError(f"{PROOF_ENV} is required")
    path = Path(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def main() -> None:
    proof_path = _require_proof_path()

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    editor_subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if actor_subsystem is None or editor_subsystem is None:
        raise RuntimeError("Required Unreal Editor subsystems are unavailable")

    world = editor_subsystem.get_editor_world()
    if world is None:
        raise RuntimeError("No editor world is available")

    cube_mesh = unreal.load_asset(CUBE_ASSET)
    if cube_mesh is None:
        raise RuntimeError(f"Could not load engine cube asset: {CUBE_ASSET}")

    actor = actor_subsystem.spawn_actor_from_class(
        unreal.StaticMeshActor,
        unreal.Vector(0.0, 0.0, 300.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        transient=True,
    )
    if actor is None:
        raise RuntimeError("EditorActorSubsystem failed to spawn transient cube")

    actor.set_actor_label(ACTOR_LABEL)
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    if component is None:
        raise RuntimeError("Spawned StaticMeshActor has no StaticMeshComponent")
    if not component.set_static_mesh(cube_mesh):
        raise RuntimeError("Failed to assign engine cube mesh")

    actor_path = actor.get_path_name()
    location = actor.get_actor_location()

    destroyed = actor_subsystem.destroy_actor(actor)
    if not destroyed:
        raise RuntimeError("Failed to destroy transient smoke actor")

    payload = {
        "command": "smoke-cube",
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "world": world.get_path_name(),
        "actor_label": ACTOR_LABEL,
        "actor_path": actor_path,
        "actor_location_cm": {
            "x": location.x,
            "y": location.y,
            "z": location.z,
        },
        "mesh": CUBE_ASSET,
        "transient": True,
        "destroyed": True,
        "map_saved": False,
        "persistent_asset_created": False,
    }

    proof_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    unreal.log(f"YACS remote editor smoke PASS: {proof_path}")


if __name__ == "__main__":
    main()

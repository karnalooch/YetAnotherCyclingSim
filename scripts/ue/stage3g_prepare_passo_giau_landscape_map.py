"""Create a clean isolated map package for the Passo Giau Landscape spike.

The map is created as a brand-new non-partitioned blank level through UE 5.8's
LevelEditorSubsystem. This intentionally avoids loading or duplicating
L_CyclingTest, so the authoring workflow does not need unrelated Git LFS
payloads and the canonical cycling map stays outside the mutation path.

Landscape creation itself is handled by the project C++ commandlet.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback

import unreal


SPIKE_MAP = "/Game/Prototype/Maps/L_PassoGiauTerrainSpike"


def fail(message: str) -> None:
    raise RuntimeError(message)


def main() -> None:
    proof_value = os.environ.get("YACS_PASSO_GIAU_MAP_PREP_PROOF", "")
    if not proof_value:
        fail("YACS_PASSO_GIAU_MAP_PREP_PROOF is not set")

    if unreal.EditorAssetLibrary.does_asset_exist(SPIKE_MAP):
        if not unreal.EditorAssetLibrary.delete_asset(SPIKE_MAP):
            fail(f"failed to delete stale spike map: {SPIKE_MAP}")

    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not level_subsystem:
        fail("LevelEditorSubsystem is unavailable")

    if not level_subsystem.new_level(SPIKE_MAP, is_partitioned_world=False):
        fail(f"failed to create blank isolated spike map: {SPIKE_MAP}")

    editor_subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor_subsystem.get_editor_world()
    if not world:
        fail("new isolated spike map did not expose an editor world")

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    inherited_actors = [
        actor
        for actor in actor_subsystem.get_all_level_actors()
        if not isinstance(actor, unreal.WorldSettings)
    ]
    if inherited_actors:
        fail(
            "new blank spike map unexpectedly contains non-WorldSettings actors: "
            + ", ".join(str(actor.get_name()) for actor in inherited_actors)
        )

    if not unreal.EditorLoadingAndSavingUtils.save_map(world, SPIKE_MAP):
        fail(f"failed to save clean isolated spike map: {SPIKE_MAP}")

    proof = {
        "schema_version": 1,
        "passo_giau_map_prep": "PASS",
        "creation_method": "LevelEditorSubsystem.new_level",
        "spike_map": SPIKE_MAP,
        "is_partitioned_world": False,
        "non_world_settings_actor_count": 0,
        "canonical_map_loaded": False,
        "canonical_map_mutated": False,
        "presentation_only": True,
    }
    proof_path = Path(proof_value)
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(
        json.dumps(proof, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    unreal.log("[PassoGiauMapPrep] PASS: blank isolated non-partitioned map created")


try:
    main()
except Exception as exc:
    unreal.log_error(f"[PassoGiauMapPrep] FAILURE: {exc}")
    unreal.log_error(traceback.format_exc())
    sys.exit(1)

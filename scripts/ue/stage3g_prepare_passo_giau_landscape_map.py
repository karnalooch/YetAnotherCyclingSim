"""Create a clean isolated map package for the Passo Giau Landscape spike.

UE's Python API is deliberately used only for safe level/package duplication and
cleanup. Landscape creation itself is handled by the project C++ commandlet
because spawning a Landscape through Python is not a reliable UE 5.8 authoring
path.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback

import unreal


SOURCE_MAP = "/Game/Prototype/Maps/L_CyclingTest"
SPIKE_MAP = "/Game/Prototype/Maps/L_PassoGiauTerrainSpike"


def fail(message: str) -> None:
    raise RuntimeError(message)


def main() -> None:
    proof_value = os.environ.get("YACS_PASSO_GIAU_MAP_PREP_PROOF", "")
    if not proof_value:
        fail("YACS_PASSO_GIAU_MAP_PREP_PROOF is not set")

    if not unreal.EditorAssetLibrary.does_asset_exist(SOURCE_MAP):
        fail(f"source map missing: {SOURCE_MAP}")

    if unreal.EditorAssetLibrary.does_asset_exist(SPIKE_MAP):
        if not unreal.EditorAssetLibrary.delete_asset(SPIKE_MAP):
            fail(f"failed to delete stale spike map: {SPIKE_MAP}")

    duplicated = unreal.EditorAssetLibrary.duplicate_asset(SOURCE_MAP, SPIKE_MAP)
    if not duplicated:
        fail(f"failed to duplicate {SOURCE_MAP} -> {SPIKE_MAP}")

    world = unreal.EditorLoadingAndSavingUtils.load_map(SPIKE_MAP)
    if not world:
        fail(f"failed to load isolated spike map: {SPIKE_MAP}")

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    destroyed = []
    for actor in list(actor_subsystem.get_all_level_actors()):
        if isinstance(actor, unreal.WorldSettings):
            continue
        destroyed.append(str(actor.get_name()))
        if not actor_subsystem.destroy_actor(actor):
            fail(f"failed to destroy inherited actor: {actor.get_name()}")

    if not unreal.EditorLoadingAndSavingUtils.save_map(world, SPIKE_MAP):
        fail(f"failed to save clean isolated spike map: {SPIKE_MAP}")

    proof = {
        "schema_version": 1,
        "passo_giau_map_prep": "PASS",
        "source_map": SOURCE_MAP,
        "spike_map": SPIKE_MAP,
        "destroyed_inherited_actor_count": len(destroyed),
        "destroyed_inherited_actors": destroyed,
        "canonical_map_mutated": False,
        "presentation_only": True,
    }
    proof_path = Path(proof_value)
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(
        json.dumps(proof, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    unreal.log(
        "[PassoGiauMapPrep] PASS: isolated map created; "
        f"destroyed_inherited_actor_count={len(destroyed)}"
    )


try:
    main()
except Exception as exc:
    unreal.log_error(f"[PassoGiauMapPrep] FAILURE: {exc}")
    unreal.log_error(traceback.format_exc())
    sys.exit(1)

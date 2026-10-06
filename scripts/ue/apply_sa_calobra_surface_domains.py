"""Advance one material wave; never assign it to the Landscape.

Run this same file for the next wave after background shader work settles.
"""

import json
import os
import runpy
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]


def start_or_advance():
    active = getattr(unreal, "_yacs_surface_domain_waves", None)
    if active is None:
        foundation = runpy.run_path(
            str(ROOT / "scripts/ue/sa_calobra_material_foundation.py")
        )
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        current = editor.get_editor_world().get_path_name().split(".")[0]
        allowed = (
            foundation["load_workspace"]()["map"],
            "/Game/Worlds/SaCalobra/L_SaCalobraGeneratedSurfaces_24761d13ffbd",
            "/Game/Worlds/SaCalobra/L_SaCalobraMaskDiagnostic_615cb1c66d11",
        )
        if (
            current not in allowed
            or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
        ):
            raise RuntimeError("Open a clean recorded map; preserve unsaved changes")
        recipe = json.loads(
            (
                ROOT
                / "worldgen/materials/sa_calobra_surface_domains_presentation_20261005.json"
            ).read_text()
        )
        source_file = ROOT / "Content" / (current.removeprefix("/Game/") + ".umap")
        recipe.update(
            source_map=current,
            source_sha256=foundation["digest"](source_file),
            prepare_only=True,
            dry_channel_overlay=False,
            macro_variation=False,
        )
        producer = runpy.run_path(
            str(ROOT / "scripts/ue/apply_sa_calobra_generated_surfaces.py")
        )
        waves = runpy.run_path(str(ROOT / "scripts/ue/sa_calobra_material_waves.py"))
        active = waves["Waves"](producer["stages"](recipe))
        active.source_map = current
        unreal._yacs_surface_domain_waves = active
    current = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem
    ).get_editor_world()
    if current.get_path_name().split(".")[0] != active.source_map:
        raise RuntimeError("Map changed between stages; do not resume")
    if unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        raise RuntimeError("Unsaved map edits between stages; preserve them")
    result = active.advance()
    journal = ROOT / "Saved/RuntimeProof/SurfaceDomainWaves"
    journal.mkdir(parents=True, exist_ok=True)
    (journal / (str(os.getpid()) + ".json")).write_text(
        json.dumps(
            {
                "status": active.status,
                "source_map": active.source_map,
                "completed": active.completed,
                "latest": result,
                "whole_landscape_assignment": "NOT_EXECUTED",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    unreal.log("YACS_SURFACE_DOMAIN_WAVE " + json.dumps(result))
    return result


if __name__ == "__main__":
    start_or_advance()

"""Run bounded Material Forge UE canary assignment and rollback in one editor session."""

from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
CANARY_SCRIPT = ROOT / "scripts/ue/preview_material_forge_canary.py"
MAP = "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004"
CANARY_COMPONENT = "LandscapeComponent_230"


def _load_canary():
    spec = importlib.util.spec_from_file_location("yacs_material_forge_canary", CANARY_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load Material Forge canary")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main(*, load_map: bool = True):
    started = time.perf_counter()
    proof_root = Path(os.environ["YACS_MATERIAL_FORGE_CANARY_ROOT"])
    proof_root.mkdir(parents=True, exist_ok=True)
    artifact_sha = os.environ["YACS_MATERIAL_FORGE_ARTIFACT_SHA"]
    execution_sha = os.environ["YACS_MATERIAL_FORGE_EXECUTION_SHA"]
    variant_dir = Path(os.environ["YACS_MATERIAL_FORGE_VARIANT_DIR"])
    expected_provenance = _load_json(variant_dir / "provenance.json")
    expected_family = expected_provenance.get("family")
    expected_variant = expected_provenance.get("variant")
    if expected_family != "regional_limestone" or not expected_variant:
        raise RuntimeError("Unexpected canary input provenance")

    map_started = time.perf_counter()
    if load_map:
        world = unreal.EditorLoadingAndSavingUtils.load_map(MAP)
        if world is None:
            raise RuntimeError("Cannot load frozen accepted Sa Calobra map")
    else:
        world = unreal.get_editor_subsystem(
            unreal.UnrealEditorSubsystem
        ).get_editor_world()
        if world is None or world.get_path_name().split(".")[0] != MAP:
            raise RuntimeError(
                "Single-session import canary expected the accepted Sa Calobra map"
            )
    map_load_seconds = time.perf_counter() - map_started

    landscapes = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    if len(landscapes) != 1:
        raise RuntimeError("Expected exactly one Landscape")
    landscape = landscapes[0]
    components = landscape.get_components_by_class(unreal.LandscapeComponent)
    matches = [c for c in components if c.get_name() == CANARY_COMPONENT]
    if len(components) != 1024 or len(matches) != 1:
        raise RuntimeError("Unexpected canary Landscape topology")
    component = matches[0]
    original_override = component.get_editor_property("override_material")

    canary = _load_canary()
    latest = ROOT / "Saved/RuntimeProof/MaterialForgeCanary/latest.json"

    canary.main()
    assigned = _load_json(latest)
    (proof_root / "assigned.json").write_text(json.dumps(assigned, indent=2) + "\n", encoding="utf-8")
    if assigned.get("status") != "CANARY_ASSIGNED":
        raise RuntimeError("Canary did not reach CANARY_ASSIGNED")
    if assigned.get("map_saved") is not False or assigned.get("geometry_changed") is not False:
        raise RuntimeError("Canary violated map/geometry contract")
    if assigned.get("world_semantics_changed") is not False:
        raise RuntimeError("Canary changed world semantics")
    imported = assigned.get("import", {})
    if imported.get("saved") is not False or imported.get("landscape_mutated") is not False:
        raise RuntimeError("Importer violated transient contract")
    if (
        imported.get("family") != expected_family
        or imported.get("variant") != expected_variant
    ):
        raise RuntimeError("Unexpected canary material identity")

    assigned_override = component.get_editor_property("override_material")
    if assigned_override is None or assigned_override == original_override:
        raise RuntimeError("Canary override was not assigned")

    canary.main()
    restored = _load_json(latest)
    (proof_root / "restored.json").write_text(json.dumps(restored, indent=2) + "\n", encoding="utf-8")
    if restored.get("status") != "RESTORED":
        raise RuntimeError("Canary did not reach RESTORED")
    if component.get_editor_property("override_material") != original_override:
        raise RuntimeError("Canary component did not restore original override")
    if restored.get("map_saved") is not False or restored.get("geometry_changed") is not False:
        raise RuntimeError("Rollback violated map/geometry contract")
    if restored.get("world_semantics_changed") is not False:
        raise RuntimeError("Rollback changed world semantics")

    aggregate = {
        "status": "UE_CANARY_ASSIGN_ROLLBACK_PASS",
        "artifact_exact_sha": artifact_sha,
        "execution_sha": execution_sha,
        "map": MAP,
        "component": CANARY_COMPONENT,
        "variant": f"{expected_family}/{expected_variant}",
        "assigned_material": assigned.get("material"),
        "restored_material": restored.get("material"),
        "map_saved": False,
        "assets_saved": False,
        "geometry_changed": False,
        "world_semantics_changed": False,
        "visual_acceptance": "pending",
        "performance_acceptance": "pending",
        "map_load_seconds": round(map_load_seconds, 3),
        "map_reloaded": bool(load_map),
        "phase_seconds": round(time.perf_counter() - started, 3),
    }
    (proof_root / "ue-canary-proof.json").write_text(json.dumps(aggregate, indent=2) + "\n", encoding="utf-8")
    unreal.log("YACS_MATERIAL_FORGE_UE_CANARY " + json.dumps(aggregate))
    return aggregate


if __name__ == "__main__":
    main()

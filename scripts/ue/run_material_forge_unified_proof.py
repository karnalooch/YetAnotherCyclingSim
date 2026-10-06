"""Run Material Forge import and Landscape blend proofs in one UnrealEditor session."""

from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
CANARY_RUNNER = ROOT / "scripts/ue/run_material_forge_canary_proof.py"
CHUNKED_RUNNER = ROOT / "scripts/ue/run_material_forge_chunked_proof.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load Material Forge proof module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    started = time.perf_counter()
    proof_root = Path(os.environ["YACS_MATERIAL_FORGE_CANARY_ROOT"])
    proof_root.mkdir(parents=True, exist_ok=True)
    artifact_sha = os.environ["YACS_MATERIAL_FORGE_ARTIFACT_SHA"]
    execution_sha = os.environ["YACS_MATERIAL_FORGE_EXECUTION_SHA"]

    # Run the stronger Landscape proof first while the process still has the
    # full fail-closed memory headroom. The standalone importer canary is
    # deliberately second because it has no separate 8 GB preparation gate.
    chunked = _load("yacs_material_forge_chunked_runner", CHUNKED_RUNNER)
    landscape_started = time.perf_counter()
    landscape_receipt = chunked.main(load_map=True)
    landscape_seconds = time.perf_counter() - landscape_started

    if (
        landscape_receipt.get("status")
        != "UE_LANDSCAPE_BLEND_ASSIGN_ROLLBACK_PASS"
    ):
        raise RuntimeError("Single-session Landscape blend did not pass")
    if landscape_receipt.get("map_reloaded") is not True:
        raise RuntimeError("Landscape phase did not perform the single map load")

    # The Landscape phase has restored all component overrides. Release
    # unreferenced transient material objects before the importer-only check.
    unreal.collect_garbage()

    canary = _load("yacs_material_forge_canary_runner", CANARY_RUNNER)
    canary_started = time.perf_counter()
    canary_receipt = canary.main(load_map=False)
    canary_seconds = time.perf_counter() - canary_started

    if canary_receipt.get("status") != "UE_CANARY_ASSIGN_ROLLBACK_PASS":
        raise RuntimeError("Single-session import canary did not pass")
    if canary_receipt.get("map_reloaded") is not False:
        raise RuntimeError("Import canary reloaded the map in single-session mode")

    aggregate = {
        "status": "UE_MATERIAL_FORGE_SINGLE_SESSION_PASS",
        "artifact_exact_sha": artifact_sha,
        "execution_sha": execution_sha,
        "editor_process_count": 1,
        "map_load_count": 1,
        "canary_status": canary_receipt["status"],
        "landscape_status": landscape_receipt["status"],
        "map_load_seconds": landscape_receipt.get("phase_seconds"),
        "canary_seconds": round(canary_seconds, 3),
        "landscape_seconds": round(landscape_seconds, 3),
        "total_seconds": round(time.perf_counter() - started, 3),
        "map_saved": False,
        "assets_saved": False,
        "geometry_changed": False,
        "world_semantics_changed": False,
        "visual_acceptance": "pending",
        "performance_acceptance": "pending",
    }
    path = proof_root / "ue-single-session-proof.json"
    path.write_text(
        json.dumps(aggregate, indent=2) + "\n",
        encoding="utf-8",
    )
    unreal.log("YACS_MATERIAL_FORGE_SINGLE_SESSION " + json.dumps(aggregate))


if __name__ == "__main__":
    main()

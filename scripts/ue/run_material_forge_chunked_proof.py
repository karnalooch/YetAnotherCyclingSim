"""Run refined Material Forge rock/soil blend on real Landscape and roll it back."""

from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
PREVIEW_SCRIPT = ROOT / "scripts/ue/preview_material_forge_chunked_landscape.py"
MAP = "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004"
TARGET_COMPONENT = "LandscapeComponent_230"


def _load_preview():
    spec = importlib.util.spec_from_file_location(
        "yacs_material_forge_chunked_preview",
        PREVIEW_SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load refined Material Forge Landscape preview")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def main(*, load_map: bool = True) -> dict:
    started = time.perf_counter()
    proof_root = Path(os.environ["YACS_MF_CHUNKED_PROOF_ROOT"])
    proof_root.mkdir(parents=True, exist_ok=True)
    artifact_sha = os.environ["YACS_MATERIAL_FORGE_ARTIFACT_SHA"]
    execution_sha = os.environ["YACS_MATERIAL_FORGE_EXECUTION_SHA"]

    os.environ["YACS_MF_TARGET_COMPONENT"] = TARGET_COMPONENT
    os.environ["YACS_MF_MAX_COMPONENTS"] = "1"

    if load_map:
        world = unreal.EditorLoadingAndSavingUtils.load_map(MAP)
        if world is None:
            raise RuntimeError("Cannot load accepted Sa Calobra map for blend proof")
    else:
        world = unreal.get_editor_subsystem(
            unreal.UnrealEditorSubsystem
        ).get_editor_world()
        if world is None or world.get_path_name().split(".")[0] != MAP:
            raise RuntimeError(
                "Single-session Landscape blend expected the accepted Sa Calobra map"
            )

    preview = _load_preview()

    cleanup = preview.cleanup()
    _write(proof_root / "00-cleanup.json", cleanup)
    if not cleanup.get("ok"):
        raise RuntimeError("Refined Landscape cleanup failed")

    probe = preview.probe()
    _write(proof_root / "01-probe.json", probe)
    if not probe.get("ok") or probe.get("component_count") != 1:
        raise RuntimeError("Refined Landscape probe failed")
    if probe.get("sampling") != "bilinear appearance mask":
        raise RuntimeError("Unexpected refined Landscape mask sampling")

    prepared = preview.prepare()
    _write(proof_root / "02-prepare.json", prepared)
    if not prepared.get("ok") or prepared.get("total") != 1:
        raise RuntimeError("Refined Landscape material preparation failed")

    applied = preview.apply_next()
    _write(proof_root / "03-applied.json", applied)
    if not applied.get("ok") or applied.get("applied") != 1:
        raise RuntimeError("Refined Landscape assignment failed")

    status = preview.status()
    _write(proof_root / "04-status.json", status)
    if (
        not status.get("ok")
        or status.get("applied") != 1
        or status.get("next_component") is not None
    ):
        raise RuntimeError("Refined Landscape assignment status is inconsistent")

    restored = preview.restore()
    _write(proof_root / "05-restored.json", restored)
    if not restored.get("ok") or restored.get("restored") != 1:
        raise RuntimeError("Refined Landscape rollback failed")

    aggregate = {
        "status": "UE_LANDSCAPE_BLEND_ASSIGN_ROLLBACK_PASS",
        "artifact_exact_sha": artifact_sha,
        "execution_sha": execution_sha,
        "map": MAP,
        "component": TARGET_COMPONENT,
        "rock_variant": "regional_limestone/refined_a",
        "soil_variant": "mediterranean_soil/refined_a",
        "mask": str(preview.WEIGHTS),
        "mask_sha256": preview._sha(preview.WEIGHTS),
        "mask_channel": "B=rock; soil=1-rock",
        "sampling": "bilinear + five-tap appearance smoothing",
        "projection": "WorldAlignedTexture + WorldAlignedNormal",
        "map_saved": False,
        "assets_saved": False,
        "geometry_changed": False,
        "world_semantics_changed": False,
        "visual_acceptance": "pending",
        "performance_acceptance": "pending",
        "map_reloaded": bool(load_map),
        "phase_seconds": round(time.perf_counter() - started, 3),
    }
    _write(proof_root / "landscape-blend-proof.json", aggregate)
    unreal.log("YACS_MF_LANDSCAPE_BLEND " + json.dumps(aggregate))
    return aggregate


if __name__ == "__main__":
    main()

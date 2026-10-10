"""Run the reversible #364 asphalt slot-zero trial in one isolated UE Editor.

A trusted host has already staged and authenticated the accepted #363 consumer
and its normal read-only native baseline. This script is a separate transient
Editor invocation: no save, no changed geography, no BOB repair and no MCP.
Shader/render and persistent consumer admission remain independent.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

from scripts.ci import official_mcp_bob_session as session
from scripts.ue import read_road_material_baseline as baseline
from scripts.ue import road_asphalt_slot_canary as canary
from scripts.ue import road_asphalt_source_preflight as source
from scripts.ue import sa_calobra_whole_map_prep as prep

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_NAME = "road-asphalt-canary.json"
MAX_RECEIPT_BYTES = 2 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def output_path(proof_root: str) -> Path:
    requested = Path(proof_root)
    require(requested.is_absolute(), "Canary evidence root must be absolute")
    relative = requested.relative_to(ROOT).as_posix()
    prefix = "Saved/RuntimeProof/RoadMaterialBaseline/"
    token = relative.removeprefix(prefix)
    require(
        relative.startswith(prefix) and re.fullmatch(r"[1-9][0-9]{0,19}-[1-9][0-9]{0,5}", token),
        "Canary output must be in its owned run/attempt evidence directory",
    )
    target = session._safe_path(ROOT, relative + "/" + OUTPUT_NAME)
    require(target.parent.is_dir() and not target.exists(), "Canary output already exists")
    return target


def assert_pinned_entry_source(exact_sha):
    from scripts import committed_git_blobs as git_blobs

    relative = "scripts/ue/run_road_asphalt_native_canary.py"
    blobs = git_blobs._read_exact_blobs(
        ROOT, exact_sha, (relative,), blob_limit=MAX_RECEIPT_BYTES,
        total_limit=MAX_RECEIPT_BYTES, timeout_seconds=30,
        path_validator=session._safe_path,
    )
    require(
        hashlib.sha256(session._safe_path(ROOT, relative).read_bytes()).digest()
        == hashlib.sha256(blobs[relative]).digest(),
        "Native asphalt entry source differs from committed exact SHA",
    )


def main():
    exact_sha = os.environ.get("YACS_ROAD_MATERIAL_EXPECTED_HEAD", "")
    preparation_sha = os.environ.get("YACS_ROAD_MATERIAL_PREPARATION_SHA256", "")
    require(re.fullmatch(r"[0-9a-f]{40}", exact_sha) is not None, "Missing native exact SHA")
    require(re.fullmatch(r"[0-9a-f]{64}", preparation_sha) is not None, "Missing staging digest")
    session._assert_isolated_root()
    require(session.ROOT.resolve() == ROOT and prep.ROOT.resolve() == ROOT,
            "Native asphalt imports belong to another checkout")
    output = output_path(os.environ.get("YACS_ROAD_MATERIAL_PROOF_ROOT", ""))
    assert_pinned_entry_source(exact_sha)
    source_gate = source.verify_retained_replay()
    staging_path, staging_identity, staging, map_row = baseline.authenticated_preparation(
        session, exact_sha, preparation_sha
    )
    require(staging.get("source_sha256") == session._sources(exact_sha),
            "Canary staging source identity differs")
    all_rows = staging["consumer_assets"] + staging["source_dependencies"]
    session._verify_rows(ROOT, all_rows)
    session._assert_package_members(ROOT, all_rows)

    import unreal

    actual_project = Path(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    ).resolve()
    require(actual_project == ROOT, "Wrong Unreal project for asphalt canary")
    engine = str(unreal.SystemLibrary.get_engine_version())
    require(engine.startswith("5.8.2-56702186"), "Pinned Unreal 5.8.2 is required")
    baseline.dirty_packages(unreal)
    prep.assert_isolated_bootstrap(unreal)
    require(
        unreal.EditorLoadingAndSavingUtils.load_map(session.operation.MAP_PACKAGE) is not None,
        "Frozen derived consumer failed to load for asphalt",
    )
    baseline.dirty_packages(unreal)
    original = baseline.native_inventory(unreal, prep, session.operation.MAP_PACKAGE)
    canary.verify_accepted_surface(original)
    projection = baseline.native_projection(unreal)
    for kind in ("WorldAlignedTexture", "WorldAlignedNormal"):
        require(
            "TextureObject" in projection[kind]["input_names"]
            and "TextureSize" in projection[kind]["input_names"]
            and "XYZ Texture" in projection[kind]["output_names"],
            "Actual native world-aligned projection contract differs: " + kind,
        )
    result = canary.candidate_on_loaded_accepted_map(
        unreal, source.source_root(), source.SOURCE_RECEIPT_SHA256,
        source.SOURCE_HEAD, source.SOURCE_FINGERPRINT,
    )
    require(
        result.get("status") == "ROAD_ASPHALT_TRANSIENT_CANARY_ROLLED_BACK"
        and result.get("consumer_snapshot_restored") is True
        and result.get("road_slot_readback") is True
        and result.get("all_186_supports_unchanged") is True
        and result.get("landscape_1024_components_unchanged") is True
        and result.get("material_authoring_admitted") is False
        and result.get("source_receipt_sha256") == source.SOURCE_RECEIPT_SHA256
        and result.get("graph_sha256") == source.GRAPH_SHA256,
        "Native asphalt rollback or provenance did not pass",
    )
    after = baseline.native_inventory(unreal, prep, session.operation.MAP_PACKAGE)
    require(after == original, "Native asphalt did not fully restore the original scene")
    session._verify_rows(ROOT, all_rows)
    session._assert_package_members(ROOT, all_rows)
    require(session._identity(staging_path, MAX_RECEIPT_BYTES) == staging_identity,
            "Original staging receipt changed during transient asphalt trial")
    require(source.verify_retained_replay() == source_gate,
            "Original source proof changed during native asphalt trial")
    require(staging.get("source_sha256") == session._sources(exact_sha),
            "Canary source changed during Editor session")
    payload = {
        "schema_version": 1,
        "issue": 364,
        "status": "ROAD_ASPHALT_TRANSIENT_CANARY_ROLLED_BACK",
        "exact_sha": exact_sha,
        "engine_version": engine,
        "project": str(actual_project),
        "map_package": session.operation.MAP_PACKAGE,
        "frozen_map": map_row,
        "staging_sha256": preparation_sha,
        "source_gate": source_gate,
        "native_projection": projection,
        "result": result,
        "all_source_assets_unchanged": True,
        "native_material_bind_and_rollback_verified": True,
        "map_saved": False,
        "shader_gpu_compilation_verified": False,
        "saved_consumer_verified": False,
        "owner_visual_status": "PENDING_FINAL_M3",
        "performance_status": "DEFERRED_AFTER_M3",
        "performance_pass": False,
    }
    raw = (json.dumps(payload, sort_keys=True, allow_nan=False, indent=2) + "\n").encode()
    require(0 < len(raw) <= MAX_RECEIPT_BYTES, "Native canary receipt too large")
    with output.open("xb") as stream:
        stream.write(raw)
    unreal.log(
        "ROAD_ASPHALT_TRANSIENT_CANARY_ROLLED_BACK road=1 supports=186 "
        "landscape=1024 saved=false"
    )


if __name__ == "__main__":
    main()

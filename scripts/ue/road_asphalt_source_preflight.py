"""Read-only #364 bridge from the retained two-render source to the native canary.

This does not download, render, import, save or alter the accepted world. The
original producer run and receipt hashes are frozen; a missing retained source
is BLOCKED, never silently regenerated from a different execution revision.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.assets.road_material_contract import check_asphalt_replay
from scripts.manage_local_workspace import load_workspace

SOURCE_HEAD = "6fa54b508019bd4a1b4aa6fad601835295ec664f"
SOURCE_RUN = "38045485913-1"
SOURCE_RECEIPT_SHA256 = (
    "3626bf85da28d63908feb9d820171dc03d9d6cc444c8f799f7048f7a8052f79c"
)
SOURCE_FINGERPRINT = (
    "b4d93e24d2059c74e0b8d44f23ee10632e63f44c5c932b3ee1b849e0a6868d97"
)
GRAPH_SHA256 = "6b381516854c44dc4bdeb69b69fbb2b97ecf22c228db2c09204822d7f0bc0970"
SOURCE_RELATIVE = (
    "material-forge/road-asphalt/" + SOURCE_HEAD + "/" + SOURCE_RUN
)


def source_root() -> Path:
    config = load_workspace()
    work = Path(config["work"])
    path = work / SOURCE_RELATIVE
    if not work.is_dir() or not path.is_dir():
        raise ValueError("Pinned asphalt source bundle is not retained in the canonical workspace")
    # The underlying read checker also rejects linked ancestors and source drift.
    return path


def verify_retained_replay() -> dict:
    root = source_root()
    result = check_asphalt_replay(
        root, SOURCE_RECEIPT_SHA256, SOURCE_HEAD, SOURCE_FINGERPRINT
    )
    if (
        result.get("status") != "ROAD_ASPHALT_REPLAY_RECEIPT_VERIFIED"
        or result.get("source_head") != SOURCE_HEAD
        or result.get("source_fingerprint") != SOURCE_FINGERPRINT
        or result.get("authenticated_source_receipt", {}).get("sha256")
        != SOURCE_RECEIPT_SHA256
        or result.get("retained_two_run_graph_and_map_bytes_equal") is not True
        or result.get("producer_attestation_authenticated") is not True
        or result.get("unreal_verified") is not False
        or result.get("world_mutation") is not False
        or not isinstance(result.get("runs"), list)
        or len(result["runs"]) != 2
        or any(row.get("graph_sha256") != GRAPH_SHA256 for row in result["runs"])
    ):
        raise ValueError("Pinned two-render asphalt source bridge is not admitted")
    return {
        "status": "PINNED_ROAD_ASPHALT_SOURCE_READY",
        "proof_root": str(root),
        "source_head": SOURCE_HEAD,
        "source_receipt_sha256": SOURCE_RECEIPT_SHA256,
        "source_fingerprint": SOURCE_FINGERPRINT,
        "graph_sha256": GRAPH_SHA256,
        "verified_original_runs": 2,
        "native_material_verified": False,
        "source_changed": False,
        "performance_pass": False,
    }


def main() -> None:
    print(json.dumps(verify_retained_replay(), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

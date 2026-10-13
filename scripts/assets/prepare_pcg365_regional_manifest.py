"""Reproduce the authenticated, bounded window-0067 diagnostic inputs on CPU.

Read-only CLI: --check compares generated canonical bytes with reviewed files
and their existing stage copies. This never writes sources or invokes Unreal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.live_host.recipes import rock_contact_scatter as contact  # noqa: E402

STAGE = Path("D:/yacs/work/pcg365/remote-rock-preview")
DOCS = Path("docs/experiments/sa-calobra-spatial-treatment-plan-20261013")
LEGACY_SHA = "2981ce1f35f60a4cd1bf9d8abd424b52b2e82241731eedd2946d482aba13bb4f"
VISIBILITY_SHA = "16c8e872d31cfc38b920b28e1d68ae408d71920c39d2ae98df9db14ac7c4266c"
NATIVE_SHA = "53c9a0a6aa5cebaf904ef0b2e395fed71856150d664729319ff6d60838440649"
PLAN_SHA = "99b7d4d67a14ee62ac3bb8dff392d4b9a3d330a74bc53d8e64fdd76e866ab684"
SEARCH_SHA = "2d0079969b422374e5f9dfcd0e26da39a7087bc72bafae2133f76d09853d2e9c"
ROWS = (
    ("W0067_R01", "namaqualand_boulder_06_01", [113000, 116450]),
    ("W0067_R02", "namaqualand_boulder_05_01", [113300, 116350]),
    ("W0067_R03", "namaqualand_boulder_06_01", [113350, 116750]),
)


def canonical(value: dict) -> bytes:
    return (json.dumps(value, indent=2) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def authenticated(path: Path, sha: str) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing or aliased source: " + str(path))
    raw = path.read_bytes()
    if digest(raw) != sha:
        raise ValueError("Source digest differs: " + str(path))
    return raw


def proof(path: str, raw: bytes) -> dict:
    return {"path": path, "bytes": len(raw), "sha256": digest(raw)}


def build(stage: Path = STAGE, root: Path = ROOT) -> tuple[dict, dict]:
    """Generate outputs exclusively from pinned original inputs and exact rows."""
    legacy = json.loads(authenticated(stage / "preview-manifest.json", LEGACY_SHA))
    visibility = json.loads(
        authenticated(root / DOCS / "visibility-plan.json", VISIBILITY_SHA)
    )
    archive = root / DOCS / "visibility-arrays.npz"
    authenticated(archive, visibility["array_file_sha256"])
    with np.load(archive, allow_pickle=False) as saved:
        if set(saved.files) != set(visibility["array_logical_sha256"]):
            raise ValueError("Visibility logical array set differs")
        arrays = {name: saved[name].copy() for name in saved.files}
    for name, expected in visibility["array_logical_sha256"].items():
        if digest(np.ascontiguousarray(arrays[name]).tobytes()) != expected:
            raise ValueError("Visibility logical digest differs: " + name)
        if arrays[name].shape != tuple(visibility["grid_shape"]):
            raise ValueError("Visibility grid shape differs: " + name)
    if visibility["grid_cell_m"] != 4 or visibility["grid_origin_edges_local_m"] != [
        -0.25,
        -0.25,
    ]:
        raise ValueError("Visibility grid registration differs")
    slopes = [p for p in visibility["sources"] if Path(p["path"]).name == "slope.tif"]
    if len(slopes) != 1:
        raise ValueError("Unique original slope source required")
    slope_path = Path(slopes[0]["path"])
    authenticated(slope_path, slopes[0]["sha256"])
    with rasterio.open(slope_path) as ds:
        if (
            ds.shape != (4033, 4033)
            or str(ds.crs) != "EPSG:25831"
            or list(ds.transform)[:6] != [0.5, 0.0, 483000.0, 0.0, -0.5, 4409516.5]
        ):
            raise ValueError("Slope source grid differs")
        slope = ds.read(1)
    previous = contact.STAGE
    try:
        contact.STAGE = stage
        for item in legacy["exclusion_sources"]:
            contact.file_proof(stage, item)
        distances_raw, reasons_raw = contact.authenticated_exclusion_buffers(legacy)
        for asset in legacy["assets"]:
            contact.file_proof(stage, asset["fbx"])
    finally:
        contact.STAGE = previous
    distances = np.frombuffer(distances_raw, dtype="<f4").reshape(4033, 4033)
    reasons = np.frombuffer(reasons_raw, dtype="<u2").reshape(4033, 4033)
    native_raw = authenticated(
        root / DOCS / "window0067-native-inspection.json", NATIVE_SHA
    )
    native = json.loads(native_raw)["readback"]["native_readback"]
    owner = "/Game/Generated/YACS/LiveCheckpoints/R2a00f7ebba40/L_RoadSurface.L_RoadSurface:PersistentLevel.SaCalobraLandscape"
    if (
        native["operation_status"] != "REGION_OBSERVED_NOT_REGISTERED"
        or len(native["samples"]) != 26
        or any(
            s["actor"] != owner or s["actor_class"] != "Landscape"
            for s in native["samples"]
        )
    ):
        raise ValueError("Native inspection identity differs")
    authenticated(
        root / "docs/tooling/SA_CALOBRA_ROCK_ROLLOUT_PLAN_20261013.md", PLAN_SHA
    )
    assets = [a for a in legacy["assets"] if a["id"] in {r[1] for r in ROWS}]
    assets.sort(key=lambda a: a["id"])
    if len(assets) != 2:
        raise ValueError("Expected unique N05/N06 source variants")
    by_id = {a["id"]: a for a in assets}
    binding = digest(
        json.dumps(
            legacy["exclusion_sources"], sort_keys=True, separators=(",", ":")
        ).encode()
    )
    placements, measurements = [], []
    for site, asset_id, xy in ROWS:
        bounds = by_id[asset_id]["bounds_cm"]
        radius = math.hypot(
            *(abs(bounds["origin"][i]) + bounds["extent"][i] for i in (0, 1))
        )
        col, row = (math.floor(v / 50 + 0.5) for v in xy)
        distance, reason = float(distances[row, col]), int(reasons[row, col])
        contact.footprint_clearance_sample(xy, radius, distance, reason)
        maximum = float(np.max(slope[row - 3 : row + 4, col - 3 : col + 4]))
        br, bc = row // 8, col // 8
        hits, pixels = (
            int(arrays["hits"][br, bc]),
            float(arrays["pixels_per_m"][br, bc]),
        )
        if not math.isfinite(maximum) or maximum > 10 or hits <= 0 or pixels < 8:
            raise ValueError("Source screen rejects " + site)
        exclusions = {
            "status": "PASS_SOURCE_MASK_FOOTPRINT_CURRENT_ROAD_UNVERIFIED",
            "road_source_compatible": False,
            "footprint_radius_cm": radius,
            "unknown": False,
            "road": False,
            "nodata": False,
            "holdback": False,
            "aoi": False,
            "source_binding_sha256": binding,
        }
        placements.append(
            {
                "site": site,
                "asset_id": asset_id,
                "world_xy_cm": xy,
                "exclusions": exclusions,
            }
        )
        measurements.append(
            {
                "site": site,
                "asset_id": asset_id,
                "world_xy_cm": xy,
                "source_cell": [row, col],
                "maximum_7x7_slope_deg": maximum,
                "clearance_lower_bound_m": distance,
                "exclusion_reasons": reason,
                "visibility_bin": [br, bc],
                "hits": hits,
                "pixels_per_m": pixels,
            }
        )
    screen = {
        "schema_version": 1,
        "surface_id": "window0067-landscape-v1",
        "scope": "THREE_ROCK_DIAGNOSTIC_NOT_PRODUCTION",
        "source_slope_sha256": slopes[0]["sha256"],
        "visibility_archive_sha256": visibility["array_file_sha256"],
        "visibility_logical_sha256": visibility["array_logical_sha256"],
        "method": "Original 0.5m grid; 7x7 max slope <=10deg; reasons=0; original full radius +50cm exclusion clearance; 4m visibility bins hits>0 and px/m>=8. Planning evidence only.",
        "placements": measurements,
    }
    surface = {
        "surface_id": "window0067-landscape-v1",
        "version": 1,
        "kind": "LANDSCAPE_DIAGNOSTIC",
        "bounds_xy_cm": [112850, 116200, 113550, 117350],
        "owner_actor": owner,
        "inspection_receipt": proof(
            "evidence/window0067-native-inspection.json", native_raw
        ),
        "search_manifest_sha256": SEARCH_SHA,
        "plan_sha256": PLAN_SHA,
        "source_screen": proof(
            "evidence/window0067-source-screen.json", canonical(screen)
        ),
    }
    manifest = {
        "schema_version": 2,
        "scope": "WINDOW0067_THREE_ROCK_DIAGNOSTIC",
        "map_package": legacy["map_package"],
        "exclusion_sources": legacy["exclusion_sources"],
        "protected_packages": legacy["protected_packages"],
        "assets": assets,
        "placements": placements,
        "surface": surface,
    }
    return manifest, screen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Read-only reproduction check (also the default)",
    )
    parser.add_argument("--stage", type=Path, default=STAGE)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    manifest, screen = build(args.stage, args.root)
    outputs = (
        (
            args.root / "worldgen/live_host/window0067-regional-manifest.json",
            canonical(manifest),
        ),
        (args.root / DOCS / "window0067-source-screen.json", canonical(screen)),
        (args.stage / "regional-manifest.json", canonical(manifest)),
        (args.stage / "evidence/window0067-source-screen.json", canonical(screen)),
    )
    for path, raw in outputs:
        if path.read_bytes() != raw:
            raise ValueError("Generated canonical bytes differ: " + str(path))
    authenticated(args.stage / "evidence/window0067-native-inspection.json", NATIVE_SHA)
    print(
        json.dumps(
            {
                "status": "PASS_CPU_REPRODUCTION_NOT_NATIVE_QUALIFICATION",
                "manifest_sha256": digest(canonical(manifest)),
                "source_screen_sha256": digest(canonical(screen)),
                "placements": len(manifest["placements"]),
                "writes": False,
            }
        )
    )


if __name__ == "__main__":
    main()

"""Stage hash-bound repaired rocks for a bounded P0-P4 live preview.

This producer never writes the live project, starts UE or admits production
scatter. Existing World Authority exclusions remain binding. Optional diagnostic
placements are requests only; the live consumer must exclude actual native road
geometry independently before measuring contact or spawning any asset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil


def require(ok, message):
    if not ok:
        raise ValueError(message)


def proof(path):
    path = Path(path).resolve(strict=True)
    require(path.is_file() and not path.is_symlink(), "Regular input required")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest}


def footprint_clearance(distances, reasons, xy, radius_cm, clearance_cm=50.0):
    """Use conservative existing radius rule; never infer a rock land-cover class."""
    require(len(xy) == 2 and all(math.isfinite(v) for v in xy), "Invalid XY")
    require(math.isfinite(radius_cm) and radius_cm > 0, "Invalid radius")
    require(math.isfinite(clearance_cm) and clearance_cm >= 0, "Invalid clearance")
    require(distances.shape == reasons.shape == (4033, 4033), "Frozen grid required")
    x, y = xy
    col, row = math.floor(x / 50 + 0.5), math.floor(y / 50 + 0.5)
    if not (0 <= row < 4033 and 0 <= col < 4033):
        return {"eligible": False, "reason": "OUTSIDE_AOI"}
    if min(x + 25, y + 25, 201625 - x, 201625 - y) < radius_cm + clearance_cm:
        return {"eligible": False, "reason": "FOOTPRINT_OUTSIDE_AOI"}
    bits = int(reasons[row, col])
    distance = float(distances[row, col])
    if bits != 0 or not math.isfinite(distance) or distance < 0:
        return {"eligible": False, "reason": "EXCLUDED_OR_UNKNOWN", "bits": bits}
    lower_cm = max(0.0, 100 * distance - math.hypot(x - col * 50, y - row * 50))
    return {
        "eligible": lower_cm >= radius_cm + clearance_cm,
        "reason": "AUTHENTICATED_CLEARANCE"
        if lower_cm >= radius_cm + clearance_cm
        else "INSUFFICIENT_CLEARANCE",
        "clearance_lower_bound_cm": lower_cm,
        "required_clearance_cm": radius_cm + clearance_cm,
        "source_cell": [row, col],
        "exclusion_bits": bits,
    }


def copy_input(path, destination):
    before = proof(path)
    require(not destination.exists(), "Preserve staged bytes")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, destination)
    after = proof(destination)
    require(
        (after["bytes"], after["sha256"]) == (before["bytes"], before["sha256"]),
        "Staging copy changed",
    )
    require(proof(path) == before, "Source changed while staging")
    return after


def staged_proof(path, destination, output):
    result = copy_input(path, destination)
    result["path"] = destination.relative_to(output).as_posix()
    return result


def build(
    *,
    repaired,
    masks,
    anchors,
    output,
    forge_binding,
    forge_project,
    diagnostic_placements=False,
):
    import rasterio
    from prepare_sa_calobra_pcg_masks import verified_manifest

    require(not output.exists(), "Preserve previous preview stage")
    collection = json.loads(repaired.read_text(encoding="utf-8"))
    require(
        collection.get("placement") is False, "Source repair cannot admit placement"
    )
    require(
        collection.get("qualified_assets") == [],
        "Source-only repair cannot qualify native contact",
    )
    graph = (
        Path(__file__).resolve().parents[2]
        / "worldgen/sa_calobra/world_graph_inputs_v1.json"
    )
    pins = json.loads(graph.read_text(encoding="utf-8"))["sources"]["pcg"]
    require(
        proof(masks)["sha256"] == pins["sha256"], "World Authority manifest differs"
    )
    authority = verified_manifest(masks)
    require(
        authority["fingerprint"] == pins["fingerprint"],
        "World Authority fingerprint differs",
    )
    with rasterio.open(masks.parent / "exclusion-distance-lower-bound.tif") as ds:
        distances = ds.read(1)
    with rasterio.open(masks.parent / "exclusion-reasons.tif") as ds:
        reasons = ds.read(1)
    points = json.loads(anchors.read_text(encoding="utf-8"))["points"]
    require(len(points) == 5, "Exactly five owner-reviewed anchors required")
    map_package = "/Game/Generated/YACS/LiveCheckpoints/R2a00f7ebba40/L_RoadSurface"
    forge = json.loads(forge_binding.read_text(encoding="utf-8"))
    forge_files = [p for p in forge["saved_packages"] if "/MaterialForge/" in p["path"]]
    require(len(forge_files) == 6, "Exact six-package Forge material closure required")
    for row in forge_files:
        path = forge_project / row["path"]
        require(
            row["path"].startswith(
                "Content/Generated/YACS/PCG365Qualification/MaterialForge/"
            )
            and ".." not in Path(row["path"]).parts,
            "Unowned Forge package",
        )
        require(
            proof(path)["sha256"] == row["sha256"]
            and proof(path)["bytes"] == row["bytes"],
            "Forge package bytes differ",
        )
    require(
        1 <= len(collection["variants"]) <= 20, "Repaired candidate subset required"
    )
    output.mkdir(parents=True)
    source_proofs = [
        staged_proof(masks, output / "evidence/pcg-mask-manifest.json", output)
    ]
    for name, array, dtype in (
        ("exclusion-distance-lower-bound", distances, "<f4"),
        ("exclusion-reasons", reasons, "<u2"),
    ):
        source_proofs.append(
            staged_proof(
                masks.parent / (name + ".tif"),
                output / "evidence" / (name + ".tif"),
                output,
            )
        )
        raw = array.astype(dtype, copy=False).tobytes()
        original = next(r for r in authority["outputs"] if r["path"] == name + ".tif")
        require(
            hashlib.sha256(raw).hexdigest() == original["logical_sha256"],
            "Lossless logical mask bytes differ",
        )
        target = output / "evidence" / (name + ".bin")
        target.write_bytes(raw)
        item = proof(target)
        item["path"] = target.relative_to(output).as_posix()
        source_proofs.append(item)
    source_proofs.append(
        staged_proof(repaired, output / "evidence/rock-collection-catalog.json", output)
    )
    staged_proof(forge_binding, output / "evidence/forge-binding.json", output)
    protected = []
    for row in forge_files:
        staged_proof(
            forge_project / row["path"], output / "packages" / row["path"], output
        )
        protected.append({**row, "package": "/Game/" + row["path"][8:-7]})
    material_package = next(
        p["package"] for p in protected if p["package"].endswith("/MI_MaterialForge")
    )
    anchor_proof = staged_proof(anchors, output / "contact-request.json", output)
    binding = hashlib.sha256(
        json.dumps(source_proofs, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    # One bounded alternative per anchor, selected by stable sorted source ID.
    # Native ground contact is measured again by the live consumer before spawn.
    assets, candidates, rejected = [], [], []
    for row in sorted(collection["variants"], key=lambda item: item["id"]):
        source = Path(row["source"])
        require(
            proof(source)["sha256"] == row["sha256"]
            and proof(source)["bytes"] == row["bytes"],
            "Repaired FBX identity differs",
        )
        bounds = row["expected_native_bounds_cm"]
        origin = [(a + b) / 2 for a, b in zip(bounds["min"], bounds["max"])]
        extent = [(b - a) / 2 for a, b in zip(bounds["min"], bounds["max"])]
        require(
            all(math.isfinite(v) for v in origin + extent)
            and all(v > 0 for v in extent),
            "Invalid repaired bounds",
        )
        radius = math.hypot(abs(origin[0]) + extent[0], abs(origin[1]) + extent[1])
        assets.append(
            {
                "id": row["id"],
                "fbx": staged_proof(source, output / "fbx" / source.name, output),
                "bounds_cm": {"origin": origin, "extent": extent},
                "material_package": material_package,
                "expected_lod0_triangles": row["expected_lod0_triangles"],
            }
        )
        for index, point in enumerate(points):
            xy = point["world_xy_cm"]
            result = footprint_clearance(distances, reasons, xy, radius)
            entry = {
                "site": f"P{index}",
                "asset_id": row["id"],
                "world_xy_cm": xy,
                "clearance_evidence": result,
            }
            if result["eligible"]:
                entry["exclusions"] = {
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
                candidates.append(entry)
            else:
                rejected.append(entry)
    placements = []
    if diagnostic_placements:
        for site in (f"P{i}" for i in range(5)):
            choices = [r for r in candidates if r["site"] == site]
            if choices:
                # Stable smallest-radius candidate minimizes ground footprint.
                chosen = min(
                    choices,
                    key=lambda r: (
                        r["exclusions"]["footprint_radius_cm"],
                        r["asset_id"],
                    ),
                )
                placements.append(
                    {k: v for k, v in chosen.items() if k != "clearance_evidence"}
                )
    receipt = {
        "candidate_alternatives": candidates,
        "rejected_exclusions": rejected,
        "production_admitted": False,
        "placement": False,
        "native_contact": "NOT_RUN",
        "current_native_road_clearance": "NOT_RUN_REQUIRED_PER_FOOTPRINT",
        "diagnostic_placements_requested": diagnostic_placements,
        "material_installation": "NOT_RUN",
        "parent_catalog": proof(repaired),
    }
    (output / "preparation-receipt.json").write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    manifest = {
        "schema_version": 1,
        "scope": "P0_P4_DIAGNOSTIC_ONLY",
        "map_package": map_package,
        "anchor_source": anchor_proof,
        "exclusion_sources": source_proofs,
        "protected_packages": protected,
        "assets": assets,
        "placements": placements,
    }
    target = output / "preview-manifest.json"
    target.write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return proof(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in (
        "repaired",
        "masks",
        "anchors",
        "output",
        "forge-binding",
        "forge-project",
    ):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--diagnostic-placements", action="store_true")
    arguments = parser.parse_args()
    print(json.dumps(build(**vars(arguments)), indent=2))

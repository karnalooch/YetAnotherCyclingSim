"""Read-only, fail-closed triage of #365 real native Landscape contact receipts.

Diagnostic ranking is NOT a physics policy evaluator, placement admission, or
license to search unknown/non-admitted terrain. Does not import or launch Unreal.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import zipfile

VALID_SHA = re.compile(r"^[0-9a-f]{40}$")
VALID_MESH = re.compile(r"^[a-z0-9_]+$")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
EXACT_VIEW = {"boulder-low-angle-01.png", "boulder-low-angle-02.png"}
EXACT_WARMUP = {"warmup-01.png", "warmup-02.png"}
EXPECTED_REASON = {
    "EXCESSIVE_LOCAL_SLOPE", "EXCESSIVE_EMBEDDING",
    "INSUFFICIENT_EXPOSED_HEIGHT", "INSUFFICIENT_EXPOSED_RAYS",
    "ROOT_NOT_CONVERGED", "EMBEDDING_NOT_CONVERGED",
}


def need(ok: bool, msg: str):
    if not ok:
        raise ValueError(msg)


def json_from_zip(archive: zipfile.ZipFile, name: str) -> dict:
    return json.loads(archive.read(name))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def numeric(value):
    need(type(value) in (float, int) and math.isfinite(value), "Nonfinite contact metric")
    return float(value)


def check_phase(archive: zipfile.ZipFile, review: dict) -> dict:
    phase = review["phases"]["contact_readback"]
    need(phase["path"] == "proof/collection-contact-review/contact-fresh-phase.json", "Unexpected phase identity")
    data = archive.read("contact-fresh-phase.json")
    need(len(data) == phase["bytes"] and sha256(data) == phase["sha256"], "Fresh phase hash mismatch")
    return json.loads(data)


def check_frames(archive: zipfile.ZipFile, captures: list, known_ids: set[str]):
    need(len(captures) == 20, "Need 20 UE rock captures")
    need({c["mesh_id"] for c in captures} == known_ids, "Duplicate/missing capture identity")
    final_bytes, warm_bytes = 0, 0
    for row in captures:
        mesh = row["mesh_id"]
        need(VALID_MESH.fullmatch(mesh) is not None, "Unsafe mesh ID")
        capture = row["capture"]
        need(capture["status"] == "CAPTURE_COMPLETED" and capture.get("error") is None, "Incomplete native GPU capture")
        for key, names in (("frames", EXACT_VIEW), ("warmup_frames", EXACT_WARMUP)):
            shots = capture[key]
            need(len(shots) == 2 and {shot["file"] for shot in shots} == names, "Incomplete shot set")
            for shot in shots:
                path = mesh + "/" + shot["file"]
                data = archive.read(path)
                need(len(data) == shot["size_bytes"] and sha256(data) == shot["sha256"], "PNG hash or size mismatch")
                need(len(data) >= 24 and data[:8] == PNG_MAGIC and data[12:16] == b"IHDR", "Non-PNG native frame")
                need(struct.unpack(">II", data[16:24]) == (1920, 1080), "Unexpected native frame resolution")
                need(shot["width_px"] == 1920 and shot["height_px"] == 1080, "Capture metadata mismatch")
                if key == "frames":
                    final_bytes += len(data)
                else:
                    warm_bytes += len(data)
    return final_bytes, warm_bytes


def assess_archive(path: Path, expected_sha: str) -> dict:
    need(bool(VALID_SHA.fullmatch(expected_sha)), "Expected exact 40-character commit SHA")
    with zipfile.ZipFile(path) as archive:
        marker = json_from_zip(archive, "launcher-completed.json")
        report = json_from_zip(archive, "collection-contact-review-receipt.json")
        need(marker.get("code_sha") == expected_sha and marker.get("action") == "collection-contact-review", "Review marker identity mismatch")
        need(type(marker.get("exit_code")) is int and marker["exit_code"] == 0 and marker.get("staged_bytes_unchanged") is True, "No genuine exit-zero completion marker")
        need(marker.get("proof_admission") == "LOCAL_DIAGNOSTIC_ONLY", "Unexpected admission marker")
        need(report.get("code_sha") == expected_sha and report.get("action") == marker["action"], "Native review HEAD mismatch")
        need(report.get("status") == "COLLECTION_CONTACT_REAL_GPU_CAPTURED" and report.get("contact_execution_mode") == "THREE_SESSION_MEASURE", "Native review not completed")
        for key in ("placement", "full_qualification", "terrain_modified", "map_saved"):
            need(report.get(key) is False, "Unexpected scene or qualification mutation: " + key)
        need(report.get("qualified_assets") == [] and report.get("terrain_file_before") == report.get("terrain_file_after") and report.get("ground_transform_before") == report.get("ground_transform_after"), "Frozen terrain identity or qualification mismatch")
        fresh = check_phase(archive, report)
        need(fresh.get("code_sha") == expected_sha and fresh.get("status") == "COLLECTION_CONTACT_FRESH_READBACK", "Fresh result identity drift")
        need(fresh.get("placement") is False and fresh.get("qualified_assets") == [], "Fresh result wrongly admitted")
        roster = [m["id"] for m in fresh["meshes"]]
        need(len(roster) == 20 and len(set(roster)) == 20, "Expected 20 unique rock identities")
        need(len(fresh["cases"]) == 100, "Expected 100 actual terrain cases")
        final_bytes, warmup_bytes = check_frames(archive, report["captures"], set(roster))
        keys = {(c["mesh_id"], c["point_index"]) for c in fresh["cases"]}
        need(len(keys) == 100 and keys == {(mesh, i) for mesh in roster for i in range(5)}, "Incomplete mesh/site matrix")
        summary = Counter()
        sites = {i: [] for i in range(5)}
        per_mesh = {mesh: [] for mesh in roster}
        for case in fresh["cases"]:
            policy = case["policy_decision"]
            need(case["status"] == "MEASURED" and policy["status"] in ("REJECTED", "PASS_SAMPLED_CONTACT_ONLY"), "Missing policy decision")
            metrics = policy["metrics"]
            slope = numeric(case["measurement"]["max_local_slope_deg"])
            burial = numeric(metrics["embedding_fraction"])
            exposure = numeric(metrics["exposed_height_fraction"])
            rays = numeric(metrics["exposed_ray_fraction"])
            ground = numeric(metrics["valid_ground_fraction"])
            need(0 <= exposure <= 1 and 0 <= rays <= 1 and 0 <= ground <= 1 and burial >= 0 and slope >= 0, "Out of range metric")
            reasons = policy.get("reasons", [])
            need(isinstance(reasons, list) and set(reasons) <= EXPECTED_REASON, "Unexpected policy reason")
            need(policy.get("placement") is False and policy.get("full_qualification") is False, "Unsafe case admission")
            summary[policy["status"]] += 1
            for reason in reasons:
                summary[reason] += 1
            row = {
                "mesh_id": case["mesh_id"], "site": case["point_index"],
                "candidate_id": case["candidate_id"],
                "world_xy_cm": case["world_xy_cm"],
                "slope_deg": slope, "embedding_fraction": burial,
                "exposed_height_fraction": exposure, "exposed_ray_fraction": rays,
                "status": policy["status"], "reasons": reasons,
            }
            sites[row["site"]].append(row)
            per_mesh[row["mesh_id"]].append(row)
        site_rows = []
        for site, cases in sorted(sites.items()):
            need(len(cases) == 20 and len({c["candidate_id"] for c in cases}) == 1 and len({tuple(c["world_xy_cm"]) for c in cases}) == 1, "Site identity drift")
            site_rows.append({
                "site": site, "xy_cm": cases[0]["world_xy_cm"], "candidate_id": cases[0]["candidate_id"],
                "min_slope_deg": min(c["slope_deg"] for c in cases), "max_slope_deg": max(c["slope_deg"] for c in cases),
                "min_embedding_fraction": min(c["embedding_fraction"] for c in cases),
                "max_embedding_fraction": max(c["embedding_fraction"] for c in cases),
                "rejected": sum(c["status"] == "REJECTED" for c in cases),
            })
        priority = []
        for mesh, cases in sorted(per_mesh.items()):
            # Diagnostic review priority ONLY: fewer rejected reasons, then smaller
            # relative embedding and slope. This DOES NOT change policy evaluation.
            best = min(cases, key=lambda c: (len(c["reasons"]), c["embedding_fraction"], c["slope_deg"], c["site"]))
            priority.append({"mesh_id": mesh, "best_diagnostic_site": best["site"], "reason_count": len(best["reasons"]), "embedding_fraction": best["embedding_fraction"], "slope_deg": best["slope_deg"], "status": best["status"]})
        return {
            "schema_version": 1, "issue": 365, "source_sha": expected_sha,
            "origin": "EXACT_HEAD_NATIVE_GPU_REVIEW_ARCHIVE",
            "scope": "READ_ONLY_DIAGNOSTIC_TRIAGE_NOT_GEOGRAPHIC_ADMISSION",
            "cases": len(keys), "meshes": len(roster), "final_png": 40, "warmup_png": 40,
            "final_png_bytes": final_bytes, "warmup_png_bytes": warmup_bytes,
            "decision_counts": dict(sorted(summary.items())), "sites": site_rows,
            "priority_review": priority,
            "qualified_assets": [], "placement": False, "full_qualification": False,
            "owner_visual_status": "OWNER_ACCEPTED_IMAGES_NOT_CONTACT_POLICY",
            "performance_pass": False,
            "next_gate": "Authenticate per-mesh World Authority rock masks/exclusions and distinct source-valid XY; independently prove source-cap and Q90-baked candidates before new native placement validation",
        }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--expected-sha", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = assess_archive(args.archive, args.expected_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Read-only triage PASS: {result['cases']} cases, {result['final_png']} final PNGs, qualified_assets=[]")


if __name__ == "__main__":
    main()

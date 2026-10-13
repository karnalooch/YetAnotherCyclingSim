"""Allowlisted public projection of authenticated Remote status receipts."""

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path

OUTPUT = Path(
    r"D:\yacs\engine\UE_5.8\Engine\Plugins\Media\PixelStreaming2\Resources\WebServers\SignallingWebServer\www\yacs-progress.data.js"
)


def count(value):
    return value if type(value) is int and 0 <= value <= 1000000000 else None


def token(value):
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", value)
        else "UNKNOWN"
    )


def project(receipt, request, session, revision, manifest):
    if (
        request.get("session") != session
        or request.get("recipe_revision") != revision
        or request.get("recipe") != "rock_contact_scatter"
        or request.get("action") != "run_recipe"
        or request.get("parameters")
        != {"operation": "status", "manifest_sha256": manifest}
        or receipt.get("request_id") != request.get("request_id")
        or receipt.get("sequence") != request.get("sequence")
    ):
        raise ValueError("Status identity mismatch")
    stamp = receipt.get("recorded_utc")
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Missing timestamp timezone")
    readback = receipt.get("readback") or {}
    if receipt.get("status") == "COMPLETED_VISUAL_ONLY" and (
        readback.get("recipe") != "rock_contact_scatter"
        or readback.get("recipe_revision") != revision
    ):
        raise ValueError("Readback recipe mismatch")
    job = readback.get("native_readback") or {}
    if job.get("manifest_sha256") not in (None, manifest):
        raise ValueError("Job manifest mismatch")
    cases = job.get("cases") if isinstance(job.get("cases"), list) else []
    rejected = sum(
        1
        for c in cases
        if isinstance(c, dict)
        and (
            str(c.get("status", "")).startswith("REJECTED")
            or (c.get("decision") or {}).get("status") == "REJECTED"
        )
    )
    placed = count(job.get("preview_placed"))
    return {
        "schema_version": 1,
        "session": session,
        "observed_utc": stamp,
        "observer_alive": True,
        "operation_status": token(job.get("operation_status")),
        "phase": token(job.get("phase")),
        "triangles_read": count(job.get("native_geometry_triangle_ids_read")),
        "triangles_per_scan": count(job.get("native_geometry_triangle_ids_per_scan")),
        "sampled_positions": count(job.get("sampled_positions")),
        "maximum_grid_positions": count(job.get("maximum_grid_positions")),
        "placed": placed,
        "accepted": sum(
            1
            for c in cases
            if isinstance(c, dict)
            and (c.get("decision") or {}).get("status") == "PASS_SAMPLED_CONTACT_ONLY"
        ),
        "rejected": rejected,
        "cases_total": len(cases),
        "active_site": job.get("active_site")
        if job.get("active_site") in ("P0", "P1", "P2", "P3", "P4")
        else None,
        "error": receipt.get("status") != "COMPLETED_VISUAL_ONLY"
        or bool(job.get("error"))
        or "FAILED" in str(job.get("operation_status", "")),
    }


def atomic_write(data):
    if any(p.is_symlink() or p.is_junction() for p in (OUTPUT, *OUTPUT.parents)):
        raise ValueError("Unexpected linked output")
    temp = OUTPUT.with_name("yacs-progress.data.js.tmp")
    if temp.is_symlink():
        raise ValueError("Unexpected linked temporary output")
    temp.write_text(json.dumps(data, ensure_ascii=True), encoding="utf-8")
    os.replace(temp, OUTPUT)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--receipt")
    parser.add_argument("--unavailable", action="store_true")
    args = parser.parse_args()
    root = Path(r"D:\yacs\live-host\runtime\sessions") / args.session
    if not re.fullmatch(r"\d{8}T\d{6}Z-[a-f0-9]{12}", args.session):
        raise ValueError("Invalid session")
    if args.unavailable:
        if OUTPUT.exists():
            data = json.loads(OUTPUT.read_text(encoding="utf-8-sig"))
            if data.get("session") == args.session:
                data["observer_alive"] = False
                atomic_write(data)
        return
    if not re.fullmatch(r"\d{6}-[a-f0-9]{20}\.result\.json", args.receipt or ""):
        raise ValueError("Invalid receipt")
    receipt = json.loads(
        (root / "commands" / args.receipt).read_text(encoding="utf-8-sig")
    )
    started = json.loads(
        (root / "commands" / args.receipt.replace(".result.", ".started.")).read_text(
            encoding="utf-8-sig"
        )
    )
    if started.get("input") != receipt.get("input"):
        raise ValueError("Receipt source differs")
    data = project(
        receipt, started["request"], args.session, args.revision, args.manifest
    )
    atomic_write(data)


if __name__ == "__main__":
    main()

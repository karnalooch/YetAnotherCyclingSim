"""Bounded, read-only surface-owner evidence for Issue #459 window 0112."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import struct

from scripts.proof.sa_calobra_tpp_survey import (
    FROZEN_SHA,
    SurveyConfig,
    build_survey_plan,
)

WINDOW = "reviewed-VIAL_TR70190001272-1-interval-24-0"
FRAME_IDS = tuple(
    f"window-0112-{direction}-{sample:05}"
    for direction in ("forward", "reverse")
    for sample in (1, 2)
)
MODES = ("baseline", "support-hidden", "local-landscape-hidden")
SURVEY_FILE = "docs/experiments/sa-calobra-tpp-survey-20261008/frames.csv"
SURVEY_SHA256 = "15e0a2350c613bf52bfb1354192043ca0c6cd785493c59e7721305b67de099a3"
# The immutable target CUT manifest covers these inclusive 0.5 m source cells.
CUT_FILE = f"Network/{WINDOW}.json"
CUT_SHA256 = "e49baa2073514c6f4df881daa022a158604a319f99c83932f0dd0ecd47c02506"
CUT_BOUNDS_CM = (55550.0, 50550.0, 60300.0, 54000.0)
MAP_SHA256 = "276d1621fa083850f6d603b6d115b01b74c9a92c182254d15302e786abfbf29c"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def diagnostic_plan(source, exact_sha, csv_path):
    """Reuse the original full-window ordering and prove all four camera poses."""
    data = Path(csv_path).read_bytes()
    if hashlib.sha256(data).hexdigest() != SURVEY_SHA256:
        raise ValueError("Original survey camera CSV differs")
    original = {
        row["frame_id"]: row
        for row in csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    }
    plan = build_survey_plan(
        source["windows"],
        SurveyConfig(exact_sha),
        source_identity=source["source_identity"],
    )
    poses = {
        row["frame_id"]: row for row in plan["frames"] if row["frame_id"] in FRAME_IDS
    }
    if set(poses) != set(FRAME_IDS):
        raise ValueError("Exact original window0112 camera poses unavailable")
    for frame_id in FRAME_IDS:
        row, old = poses[frame_id], original[frame_id]
        if row["window_id"] != WINDOW or old["window_id"] != WINDOW:
            raise ValueError("Original camera window identity differs")
        for field in (
            "road_position_cm",
            "camera_location_cm",
            "target_cm",
            "ball_location_cm",
        ):
            if math.dist(row[field], json.loads(old[field])) > 1e-5:
                raise ValueError("Original camera pose differs: " + frame_id)
        if abs(row["station_m"] - float(old["station_m"])) > 1e-8 or row[
            "fov_deg"
        ] != float(old["fov_deg"]):
            raise ValueError("Original camera station/FOV differs")
    steps = []
    for frame_id in FRAME_IDS:
        for mode in MODES:
            row = dict(poses[frame_id], source_frame_id=frame_id, diagnostic_mode=mode)
            row["frame_id"] = f"{frame_id}-{mode}"
            row["file"] = f"frames/{row['frame_id']}.png"
            steps.append(row)
    return {
        "frames": steps,
        "frame_count": len(steps),
        "source_poses": list(FRAME_IDS),
        "original_survey_csv_sha256": SURVEY_SHA256,
    }


def interior_top_triangles(sections):
    """Address saved support top faces using unchanged road points, not a builder.

    The archived support has 27 points per section: shoulder, 25 pavement points,
    shoulder. Its source top order is two triangles per adjacent pair. Only the
    24 interior pairs are reconstructed; the outer shoulders are read natively.
    """
    if len(sections) != 110 or any(len(row) != 25 for row in sections):
        raise ValueError("Target frozen 110x25 pavement section inventory differs")
    for i in range(len(sections) - 1):
        for j in range(1, 25):
            a, b = sections[i][j - 1], sections[i][j]
            c, d = sections[i + 1][j - 1], sections[i + 1][j]
            for offset, points in enumerate(((a, b, c), (b, d, c))):
                yield (
                    i * 52 + j * 2 + offset,
                    tuple(
                        (
                            float(p[0]) * 100,
                            float(p[1]) * 100,
                            (float(p[2]) - 0.08) * 100,
                        )
                        for p in points
                    ),
                )


def triangle_delta(actual, expected):
    if (
        len(actual) != 3
        or len(expected) != 3
        or any(len(p) != 3 for p in (*actual, *expected))
        or any(not math.isfinite(v) for p in (*actual, *expected) for v in p)
    ):
        raise ValueError("Missing saved support triangle coordinates")
    return max(
        abs(a - b)
        for p, q in zip(actual, expected, strict=True)
        for a, b in zip(p, q, strict=True)
    )


def overlaps(bounds, target=CUT_BOUNDS_CM):
    x0, y0, x1, y1 = bounds
    if not all(math.isfinite(v) for v in bounds) or x1 <= x0 or y1 <= y0:
        raise ValueError("Invalid Landscape component bounds")
    return x0 <= target[2] and y0 <= target[3] and x1 >= target[0] and y1 >= target[1]


def verify(root, exact_sha):
    root = Path(root)
    report = json.loads((root / "shoulder-contact.json").read_text(encoding="utf-8"))
    capture = root / "capture"
    survey = json.loads((capture / "survey.json").read_text(encoding="utf-8"))
    if (
        report.get("status") != "SHOULDER_CONTACT_CAPTURED"
        or report.get("exact_sha") != exact_sha
        or report.get("source_road_sha") != FROZEN_SHA
        or report.get("window_id") != WINDOW
        or report.get("restoration", {}).get("status") != "RESTORED"
        or report.get("geometry_mutated") is not False
        or report.get("saved_to_map") is not False
        or report.get("rendered_owner") != "PENDING_PAIRED_VISUAL_REVIEW"
        or survey.get("status") != "CAPTURED"
    ):
        raise ValueError("Shoulder-contact capture/cleanup contract failed")
    support = report.get("support", {})
    components = report.get("landscape", {}).get("components", [])
    if (
        support.get("interior_top_triangles_compared") != 5232
        or not 0 <= support.get("max_coordinate_delta_cm", float("inf")) <= 0.0001
        or not support.get("triangle_sha256")
        or report["restoration"].get("support_triangle_sha256")
        != support["triangle_sha256"]
        or report["restoration"].get("map_sha256") != MAP_SHA256
        or report.get("cut_manifest_sha256") != CUT_SHA256
        or not 1 <= len(components) <= 16
        or any(not overlaps(c["bounds_cm"]) for c in components)
    ):
        raise ValueError("Source ownership or native geometry conservation failed")
    expected = {(frame, mode) for frame in FRAME_IDS for mode in MODES}
    rows = survey.get("frames", [])
    if (
        len(rows) != 12
        or {(r["source_frame_id"], r["diagnostic_mode"]) for r in rows} != expected
    ):
        raise ValueError("Incomplete or duplicate paired diagnostic frame inventory")
    planned = {r["frame_id"]: r for r in report["plan"]["frames"]}
    for row in rows:
        if row["window_id"] != WINDOW or row["frame_id"] not in planned:
            raise ValueError("Unexpected diagnostic camera/window identity")
        for field in (
            "road_position_cm",
            "camera_location_cm",
            "target_cm",
            "ball_location_cm",
            "station_m",
            "fov_deg",
            "diagnostic_mode",
        ):
            if row[field] != planned[row["frame_id"]][field]:
                raise ValueError("Captured diagnostic source camera recipe differs")
        file = Path(row["file"])
        if file.is_absolute() or ".." in file.parts or file.parent != Path("frames"):
            raise ValueError("Diagnostic frame path escapes retained evidence")
        data = (capture / file).read_bytes()
        if (
            data[:8] != b"\x89PNG\r\n\x1a\n"
            or data[12:16] != b"IHDR"
            or len(data) < 45
            or struct.unpack(">II", data[16:24]) != (1280, 720)
            or len(data) != row["size_bytes"]
            or hashlib.sha256(data).hexdigest() != row["sha256"]
        ):
            raise ValueError("Invalid original diagnostic PNG: " + row["file"])
        if (
            row.get("native_readiness", {}).get("status")
            != "NATIVE_LOADING_AND_MIPS_READY"
        ):
            raise ValueError("Diagnostic frame native loading/mip readiness failed")
        state = row.get("surface_visibility", {})
        if state.get("support_visible") != (
            row["diagnostic_mode"] != "support-hidden"
        ) or state.get("landscape_visible") != (
            row["diagnostic_mode"] != "local-landscape-hidden"
        ):
            raise ValueError("Diagnostic frame surface visibility differs")
    return {
        "status": "SHOULDER_CONTACT_EVIDENCE_VERIFIED",
        "exact_sha": exact_sha,
        "frame_count": 12,
        "rendered_owner": "PENDING_PAIRED_VISUAL_REVIEW",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify",))
    parser.add_argument("--root", required=True)
    parser.add_argument("--exact-sha", required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.root, args.exact_sha), indent=2))


if __name__ == "__main__":
    main()

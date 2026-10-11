"""Bounded, read-only surface-owner evidence for Issue #459 / hairpin 0081."""

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
# FRAME_IDS also selects the existing 68-frame road material plan. Keep it
# unchanged: the optional hairpin diagnostic reuses two of that plan's poses.
HAIRPIN_FRAME_IDS = ("window-0081-forward-00008", "window-0081-reverse-00004")
MODES = ("baseline", "support-hidden", "local-landscape-hidden")
SURVEY_FILE = "docs/experiments/sa-calobra-tpp-survey-20261008/frames.csv"
SURVEY_SHA256 = "15e0a2350c613bf52bfb1354192043ca0c6cd785493c59e7721305b67de099a3"
# The immutable target CUT manifest covers these inclusive 0.5 m source cells.
CUT_FILE = f"Network/{WINDOW}.json"
CUT_SHA256 = "e49baa2073514c6f4df881daa022a158604a319f99c83932f0dd0ecd47c02506"
CUT_BOUNDS_CM = (55550.0, 50550.0, 60300.0, 54000.0)
HAIRPIN_CUT_FILE = "ma2141-cut-patch.json"
HAIRPIN_CUT_SHA256 = "5ccfd9ece2c8cdf8140b47b4a771e5a530d7aa4835554771824bf9fd1d23404f"
HAIRPIN_CUT_SIZE = 1749
MATERIAL_VIEW_PLAN_SHA256 = "3fac9564e4c96c0eee237c2103cc4833af93b8bc493b4334e0b88e1e70d37559"
MATERIAL_VIEW_PLAN_SIZE = 40501
MAP_SHA256 = "276d1621fa083850f6d603b6d115b01b74c9a92c182254d15302e786abfbf29c"


def target_spec(target="window0112"):
    if target == "window0112":
        return {"target": target, "window_id": WINDOW, "frame_ids": FRAME_IDS,
                "section_count": 110, "mesh_counts": (4050, 6208),
                "cut_file": CUT_FILE, "cut_sha256": CUT_SHA256,
                "output_name": "shoulder-contact", "retained_file_count": 26}
    if target == "hairpin0081":
        return {"target": target, "window_id": "accepted-hairpin", "frame_ids": HAIRPIN_FRAME_IDS,
                "section_count": 2401, "mesh_counts": (79785, 132218),
                "cut_file": HAIRPIN_CUT_FILE, "cut_sha256": HAIRPIN_CUT_SHA256,
                "output_name": "shoulder-contact-0081", "retained_file_count": 15}
    raise ValueError("Unknown bounded shoulder-contact target")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cut_bounds(raw, *, target="window0112"):
    """Read the immutable CUT footprint, never infer it from pavement bounds."""
    spec = target_spec(target)
    if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != spec["cut_sha256"]:
        raise ValueError("Target CUT footprint source differs")
    if target == "window0112":
        return CUT_BOUNDS_CM
    if len(raw) != HAIRPIN_CUT_SIZE:
        raise ValueError("Hairpin CUT footprint byte inventory differs")
    value = json.loads(raw.decode("utf-8-sig"))
    rect = value.get("rect", {})
    if (value.get("operation") != "CUT_ONLY" or value.get("grid_step_m") != 0.5
            or any(type(rect.get(key)) is not int for key in ("min_x", "min_y", "max_x", "max_y", "width", "height"))
            or not 0 <= rect["min_x"] < rect["max_x"] <= 4032
            or not 0 <= rect["min_y"] < rect["max_y"] <= 4032
            or rect["width"] != rect["max_x"] - rect["min_x"] + 1
            or rect["height"] != rect["max_y"] - rect["min_y"] + 1):
        raise ValueError("Hairpin CUT source grid/rectangle differs")
    return tuple(float(rect[key]) * 50.0 for key in ("min_x", "min_y", "max_x", "max_y"))


def diagnostic_plan(source, exact_sha, csv_path, *, target="window0112", view_plan_path=None):
    """Prove original source cameras; hairpin also requires the fixed GPU plan."""
    spec = target_spec(target)
    frame_ids, window = spec["frame_ids"], spec["window_id"]
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
        row["frame_id"]: row for row in plan["frames"] if row["frame_id"] in frame_ids
    }
    if set(poses) != set(frame_ids):
        raise ValueError("Exact original " + target + " camera poses unavailable")
    for frame_id in frame_ids:
        row, old = poses[frame_id], original[frame_id]
        if row["window_id"] != window or old["window_id"] != window:
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
    if target == "hairpin0081":
        if view_plan_path is None:
            raise ValueError("Hairpin diagnostic requires the authenticated 68-frame material view plan")
        raw = Path(view_plan_path).read_bytes()
        if (len(raw) != MATERIAL_VIEW_PLAN_SIZE
                or hashlib.sha256(raw).hexdigest() != MATERIAL_VIEW_PLAN_SHA256):
            raise ValueError("Fixed material camera plan bytes differ")
        material_plan = json.loads(raw.decode("utf-8-sig"))
        material_frames = material_plan.get("frames", [])
        if (material_plan.get("frame_count") != 68 or len(material_frames) != 68
                or len({row["frame_id"] for row in material_frames}) != 68
                or material_plan.get("survey_sha256") != SURVEY_SHA256):
            raise ValueError("Fixed material camera inventory differs")
        selected = {row["frame_id"]: row for row in material_frames if row["frame_id"] in frame_ids}
        if set(selected) != set(frame_ids):
            raise ValueError("Selected hairpin poses are absent from the fixed material plan")
        for frame_id, row in selected.items():
            source_row = poses[frame_id]
            for field in ("road_position_cm", "camera_location_cm", "target_cm"):
                if math.dist(row[field], source_row[field]) > 1e-5:
                    raise ValueError("Hairpin material camera differs from its source pose")
            if (row["window_id"] != window or row["direction"] != source_row["direction"]
                    or abs(row["station_m"] - source_row["station_m"]) > 1e-8
                    or row["fov_deg"] != source_row["fov_deg"]):
                raise ValueError("Hairpin material camera station/direction differs")
            # Use those exact retained GPU camera values, without recomputing
            # or confusing reverse sample indices with forward stations.
            poses[frame_id] = dict(source_row, **row)
    steps = []
    for frame_id in frame_ids:
        for mode in MODES:
            row = dict(poses[frame_id], source_frame_id=frame_id, diagnostic_mode=mode)
            row["frame_id"] = f"{frame_id}-{mode}"
            row["file"] = f"frames/{row['frame_id']}.png"
            steps.append(row)
    result = {
        "frames": steps,
        "frame_count": len(steps),
        "source_poses": list(frame_ids),
        "original_survey_csv_sha256": SURVEY_SHA256,
    }
    if target == "hairpin0081":
        result.update(diagnostic_target=target, material_view_plan_sha256=MATERIAL_VIEW_PLAN_SHA256)
    return result


def interior_top_triangles(sections, *, target="window0112"):
    """Address saved support top faces using unchanged road points, not a builder.

    The archived support has 27 points per section: shoulder, 25 pavement points,
    shoulder. Its source top order is two triangles per adjacent pair. Only the
    24 interior pairs are reconstructed; the outer shoulders are read natively.
    """
    count = target_spec(target)["section_count"]
    if len(sections) != count or any(len(row) != 25 for row in sections):
        raise ValueError(f"Target frozen {count}x25 pavement section inventory differs")
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


def require_captured(report):
    """Keep an initialization error visible when no survey was ever created."""
    if report.get("status") != "SHOULDER_CONTACT_CAPTURED":
        detail = str(report.get("error") or report.get("status") or "missing native status")
        raise ValueError("Shoulder-contact native capture failed: " + detail[:16384])


def verify(root, exact_sha, *, target="window0112"):
    root = Path(root)
    spec = target_spec(target)
    report = json.loads((root / "shoulder-contact.json").read_text(encoding="utf-8"))
    require_captured(report)
    capture = root / "capture"
    survey = json.loads((capture / "survey.json").read_text(encoding="utf-8"))
    if (
        report.get("status") != "SHOULDER_CONTACT_CAPTURED"
        or report.get("exact_sha") != exact_sha
        or report.get("source_road_sha") != FROZEN_SHA
        or report.get("window_id") != spec["window_id"]
        or report.get("restoration", {}).get("status") != "RESTORED"
        or report.get("geometry_mutated") is not False
        or report.get("saved_to_map") is not False
        or report.get("rendered_owner") != "PENDING_PAIRED_VISUAL_REVIEW"
        or survey.get("status") != "CAPTURED"
    ):
        raise ValueError("Shoulder-contact capture/cleanup contract failed")
    support = report.get("support", {})
    components = report.get("landscape", {}).get("components", [])
    bounds = CUT_BOUNDS_CM
    if target == "hairpin0081":
        bounds = cut_bounds((root / "source-cut-manifest.json").read_bytes(), target=target)
        if (tuple(report.get("cut_footprint_cm", [])) != bounds
                or report.get("plan", {}).get("material_view_plan_sha256") != MATERIAL_VIEW_PLAN_SHA256):
            raise ValueError("Hairpin source CUT/camera evidence differs")
    if (
        support.get("interior_top_triangles_compared") != (spec["section_count"] - 1) * 48
        or not 0 <= support.get("max_coordinate_delta_cm", float("inf")) <= 0.0001
        or not support.get("triangle_sha256")
        or report["restoration"].get("support_triangle_sha256")
        != support["triangle_sha256"]
        or report["restoration"].get("map_sha256") != MAP_SHA256
        or report.get("cut_manifest_sha256") != spec["cut_sha256"]
        or not 1 <= len(components) <= 16
        or any(not overlaps(c["bounds_cm"], bounds) for c in components)
        or (target == "hairpin0081" and (support.get("vertices"), support.get("triangles")) != spec["mesh_counts"])
    ):
        raise ValueError("Source ownership or native geometry conservation failed")
    expected = {(frame, mode) for frame in spec["frame_ids"] for mode in MODES}
    rows = survey.get("frames", [])
    if (
        len(rows) != len(expected)
        or {(r["source_frame_id"], r["diagnostic_mode"]) for r in rows} != expected
    ):
        raise ValueError("Incomplete or duplicate paired diagnostic frame inventory")
    planned = {r["frame_id"]: r for r in report["plan"]["frames"]}
    for row in rows:
        if row["window_id"] != spec["window_id"] or row["frame_id"] not in planned:
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
        "frame_count": len(expected),
        "rendered_owner": "PENDING_PAIRED_VISUAL_REVIEW",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify",))
    parser.add_argument("--root", required=True)
    parser.add_argument("--exact-sha", required=True)
    parser.add_argument("--target", choices=("window0112", "hairpin0081"), default="window0112")
    args = parser.parse_args()
    print(json.dumps(verify(args.root, args.exact_sha, target=args.target), indent=2))


if __name__ == "__main__":
    main()

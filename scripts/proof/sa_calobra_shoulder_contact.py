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
# Keep MODES for historical 12-frame receipts and the unchanged 6-frame hairpin.
WINDOW_MODES = (*MODES, "support022-hidden")
DIAGNOSTIC_SCHEMA_VERSION = 2
SUPPORT022_LABEL = "YACS_PERSIST_SUPPORT_022"
SUPPORT022_WINDOW = "VIAL_TR70190001272-1-interval-25-tile-0"
SUPPORT022_SECTION_COUNT = 153
SUPPORT022_MESH_COUNTS = (5555, 8616)
SUPPORT022_TOP_COUNT = 7904
SUPPORT022_TOP_SHA256 = "d745f170865e9cdf76e1c760798fb10ab29abd32763691617f147cd7f0636dcf"
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
HAIRPIN_WALL_ROWS = (1560, 1880)  # Inclusive source rows; 320 edge0 segments.
WALL_EVIDENCE_LIMIT = 1024 * 1024
WALL_TOLERANCE_CM = 0.0001
NATIVE_TRIANGLE_COLUMNS = ["tid", "p0_x_cm", "p0_y_cm", "p0_z_cm", "p1_x_cm", "p1_y_cm", "p1_z_cm", "p2_x_cm", "p2_y_cm", "p2_z_cm"]
CUT_NODE_COLUMNS = ["grid_x", "grid_y", "byte_offset", "raw4_hex", "world_x_cm", "world_y_cm", "source_world_z_cm"]


def target_spec(target="window0112"):
    if target == "window0112":
        return {"target": target, "window_id": WINDOW, "frame_ids": FRAME_IDS,
                "section_count": 110, "mesh_counts": (4050, 6208),
                "cut_file": CUT_FILE, "cut_sha256": CUT_SHA256,
                "output_name": "shoulder-contact", "retained_file_count": 34}
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
        for mode in WINDOW_MODES if target == "window0112" else MODES:
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
    else:
        result["diagnostic_schema_version"] = DIAGNOSTIC_SCHEMA_VERSION
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


def _wall_require(condition, message):
    if not condition:
        raise ValueError("Hairpin wall/CUT evidence: " + message)


def _wall_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _wall_triangle_rows(positions, ids):
    return [[tid, *(v for point in positions[tid] for v in point)] for tid in ids]


def _wall_positions(rows):
    _wall_require(isinstance(rows, list) and len(rows) <= 1280, "triangle rows unbounded")
    result = {}
    for row in rows:
        _wall_require(isinstance(row, list) and len(row) == 10
                      and type(row[0]) is int and 0 <= row[0] < 132218
                      and row[0] not in result
                      and all(type(v) in (int, float) and math.isfinite(v) for v in row[1:]),
                      "invalid native triangle ID/corners")
        result[row[0]] = tuple(tuple(row[k:k + 3]) for k in (1, 4, 7))
    return result


def _wall_segments(positions, source_edges):
    """Bind actual outer faces to the already compared source pavement edge0.

    No shoulder builder is executed. The two native outer-top faces must share
    their inner corners with the source core; their actual outer corners define
    the segment being inspected. Conditional perimeter TIDs are never inferred.
    """
    first, last = HAIRPIN_WALL_ROWS
    _wall_require(isinstance(source_edges, list) and len(source_edges) == last - first + 1,
                  "source row inventory differs")
    for i, row in enumerate(source_edges, first):
        _wall_require(isinstance(row, list) and len(row) == 4 and type(row[0]) is int
                      and row[0] == i and all(type(v) in (int, float) and math.isfinite(v)
                                           for v in row[1:]), "source edge row differs")
    segments, previous = {}, None
    for i in range(first, last):
        a, b = positions[i * 52], positions[i * 52 + 1]
        p, q = (tuple(row[1:3]) + (row[3] - 8.0,)
                for row in source_edges[i - first:i - first + 2])
        _wall_require(triangle_delta((a[1], b[0], b[1]), (p, p, q)) <= WALL_TOLERANCE_CM
                      and a[2] == b[2] and (previous is None or a[0] == previous),
                      "native outer top is not bound to consecutive source edge0 rows")
        _wall_require(math.dist(a[0][:2], a[2][:2]) > WALL_TOLERANCE_CM,
                      "native outer segment has no XY span")
        segments[i], previous = (a[0], a[2]), a[2]
    return segments


def _wall_parameters(points, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    values = [((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (length * length)
              for p in points]
    eps = WALL_TOLERANCE_CM
    if (max(values) - min(values) <= eps / length
            or any(t < -eps / length or t > 1 + eps / length
                   or math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy) > eps
                   for t, p in zip(values, points, strict=True))):
        return None
    return values


def _select_wall_faces(positions, segments):
    top_count = (target_spec("hairpin0081")["section_count"] - 1) * 52
    selected = {i: [] for i in segments}
    for tid in sorted(positions):
        if tid < top_count:
            continue
        points = positions[tid]
        owners = []
        for i, (a, b) in segments.items():
            if any(min(p[axis] for p in points) < min(a[axis], b[axis]) - WALL_TOLERANCE_CM
                   or max(p[axis] for p in points) > max(a[axis], b[axis]) + WALL_TOLERANCE_CM
                   for axis in (0, 1)):
                continue
            if _wall_parameters(points, a, b) is not None:
                owners.append(i)
        _wall_require(len(owners) <= 1, "native wall has ambiguous source-segment ownership")
        if owners:
            selected[owners[0]].append(tid)
    for i, ids in selected.items():
        if not ids:
            continue
        _wall_require(len(ids) <= 2, "multiple native walls overlap one source segment")
        a, b = segments[i]
        anchored = False
        for tid in ids:
            parameters = _wall_parameters(positions[tid], a, b)
            tops = [t for p, t in zip(positions[tid], parameters, strict=True)
                    if abs(p[2] - (a[2] + t * (b[2] - a[2]))) <= WALL_TOLERANCE_CM]
            anchored |= len(tops) >= 2 and (max(tops) - min(tops)) * math.dist(a[:2], b[:2]) > WALL_TOLERANCE_CM
        _wall_require(anchored, "native wall does not meet its actual outer top edge")
        if len(ids) == 2:
            _wall_require(len(set(positions[ids[0]]) & set(positions[ids[1]])) == 2,
                          "native wall pair is disconnected")
    _wall_require(any(selected.values()), "no native wall matched the diagnosed source AOI")
    return selected


def _wall_cut_metadata(raw):
    cut_bounds(raw, target="hairpin0081")
    value = json.loads(raw.decode("utf-8-sig"))
    _wall_require(value.get("layer_encoding") == "LANDSCAPE_TEXTURE_PATCH_WORLD_UNITS_F32_MIN"
                  and value.get("blend_mode") == "Min" and value.get("height_encoding") == "WorldUnits"
                  and value.get("zero_height_meaning") == "WorldZero"
                  and value.get("world_space_unit") == "centimeter"
                  and value.get("patch_file") == "ma2141-cut-patch.f32"
                  and value.get("patch_byte_count") == value["rect"]["width"] * value["rect"]["height"] * 4,
                  "authenticated CUT encoding/byte inventory differs")
    return value


def _wall_cut_keys(walls, cut):
    """Retain enclosing *source nodes*, not a fitted/interpolated terrain Z."""
    keys, outside = set(), []
    rect = cut["rect"]
    for row in walls:
        tid = row[1]
        for corner, k in enumerate((2, 5, 8)):
            x, y = row[k] / 50.0, row[k + 1] / 50.0
            if not rect["min_x"] <= x <= rect["max_x"] or not rect["min_y"] <= y <= rect["max_y"]:
                outside.append([tid, corner])
                continue
            keys.update((gx, gy) for gx in {math.floor(x), math.ceil(x)}
                        for gy in {math.floor(y), math.ceil(y)})
    _wall_require(len(keys) <= 4096, "CUT source node inventory unbounded")
    return sorted(keys, key=lambda p: (p[1], p[0])), outside


def hairpin_wall_contact(positions, sections, support, source_identity, cut_raw, patch_raw, patch_identity):
    """Keep a small inert subset of the full native read; never author geometry."""
    cut = _wall_cut_metadata(cut_raw)
    _wall_require(isinstance(patch_raw, bytes) and len(patch_raw) == cut["patch_byte_count"]
                  and hashlib.sha256(patch_raw).hexdigest() == cut["patch_sha256"],
                  "CUT patch bytes differ before sampling")
    _wall_require(patch_identity.get("size_bytes") == cut["patch_byte_count"]
                  and patch_identity.get("sha256_before") == patch_identity.get("sha256_after") == cut["patch_sha256"]
                  and isinstance(patch_identity.get("path"), str)
                  and patch_identity["path"].replace("\\", "/").endswith("/" + cut["patch_file"]),
                  "CUT source file changed during the read")
    spec = target_spec("hairpin0081")
    _wall_require(len(sections) == spec["section_count"] and all(len(s) == 25 for s in sections)
                  and set(positions) == set(range(spec["mesh_counts"][1])),
                  "complete native/source snapshot is required")
    first, last = HAIRPIN_WALL_ROWS
    source_edges = [[i, *(float(v) * 100.0 for v in sections[i][0])]
                    for i in range(first, last + 1)]
    segments = _wall_segments(positions, source_edges)
    selected = _select_wall_faces(positions, segments)
    walls = [[i, *row] for i, ids in selected.items() for row in _wall_triangle_rows(positions, ids)]
    keys, outside = _wall_cut_keys(walls, cut)
    nodes = []
    for gx, gy in keys:
        offset = ((gy - cut["rect"]["min_y"]) * cut["rect"]["width"] + gx - cut["rect"]["min_x"]) * 4
        raw = patch_raw[offset:offset + 4]
        z = struct.unpack("<f", raw)[0]
        _wall_require(math.isfinite(z), "nonfinite source CUT node")
        nodes.append([gx, gy, offset, raw.hex(), gx * 50.0, gy * 50.0, z])
    result = {
        "schema_version": 1, "status": "NATIVE_WALL_AND_SOURCE_CUT_OBSERVED",
        "source_window_id": "accepted-hairpin", "source_edge": 0,
        "source_rows_inclusive": list(HAIRPIN_WALL_ROWS),
        "ownership_tolerance_cm": WALL_TOLERANCE_CM,
        "source_profile_file": "ma2141-profile-candidate.json", "source_profile_sha256": cut["profile_sha256"],
        "source_recipe_sha256": source_identity["recipe_sha256"], "pavement_profile_lift_cm": 4.0,
        "support_actor_path": support["path"], "support_component_path": support["component"],
        "full_native_triangle_sha256": support["triangle_sha256"],
        "non_top_triangles_scanned": spec["mesh_counts"][1] - (spec["section_count"] - 1) * 52,
        "geometry_mutated": False, "native_vertex_ids_available": False,
        "source_patch_identity": patch_identity,
        "pavement_edge_rows_cm": source_edges,
        "native_top_columns": NATIVE_TRIANGLE_COLUMNS,
        "native_top_triangles": _wall_triangle_rows(positions, [i * 52 + k for i in segments for k in (0, 1)]),
        "wall_columns": ["source_segment_start_row", *NATIVE_TRIANGLE_COLUMNS],
        "wall_triangles": walls, "segments_without_matched_wall": [i for i, ids in selected.items() if not ids],
        "cut_source": {
            "manifest_sha256": HAIRPIN_CUT_SHA256, "patch_file": cut["patch_file"],
            "patch_sha256": cut["patch_sha256"], "patch_size_bytes": len(patch_raw),
            "encoding": "little_endian_float32_row_major_y_x_world_z_cm",
            "node_selection": "floor_ceil_source_grid_nodes_at_native_wall_corner_xy",
            "sample_status": "SOURCE_NODES_RETAINED" if keys else "NO_NODES_IN_SOURCE_FOOTPRINT",
            "final_native_landscape_height_observed": False, "height_interpolation_performed": False,
            "node_columns": CUT_NODE_COLUMNS,
            "nodes": nodes, "corners_outside_source_patch": outside,
        },
    }
    result["payload_sha256"] = _wall_hash(result)
    _wall_require(len(json.dumps(result, indent=4, allow_nan=False).encode()) <= WALL_EVIDENCE_LIMIT,
                  "retained wall/CUT field exceeds 1MiB")
    return result


def verify_wall_contact(value, report, cut_raw):
    """Check the optional new data without changing historical 4258 checks."""
    _wall_require(isinstance(value, dict) and value.get("status") == "NATIVE_WALL_AND_SOURCE_CUT_OBSERVED"
                  and value.get("schema_version") == 1,
                  "new native observation failed: " + str(value.get("error") if isinstance(value, dict) else value))
    _wall_require(len(json.dumps(value, indent=4, allow_nan=False).encode()) <= WALL_EVIDENCE_LIMIT,
                  "retained field exceeds 1MiB")
    _wall_require(value.get("payload_sha256") == _wall_hash({k: v for k, v in value.items() if k != "payload_sha256"}),
                  "payload hash differs")
    cut, support = _wall_cut_metadata(cut_raw), report["support"]
    _wall_require(support.get("label") == "YACS_PERSIST_SUPPORT_185"
                  and value.get("source_window_id") == "accepted-hairpin" and value.get("source_edge") == 0
                  and value.get("source_rows_inclusive") == list(HAIRPIN_WALL_ROWS)
                  and value.get("ownership_tolerance_cm") == WALL_TOLERANCE_CM
                  and value.get("source_profile_file") == "ma2141-profile-candidate.json"
                  and value.get("source_profile_sha256") == cut["profile_sha256"]
                  and value.get("source_recipe_sha256") == report["source_identity"]["recipe_sha256"]
                  and value.get("support_actor_path") == support.get("path")
                  and value.get("support_component_path") == support.get("component")
                  and value.get("full_native_triangle_sha256") == support["triangle_sha256"]
                  and value.get("pavement_profile_lift_cm") == 4.0
                  and report["source_identity"].get("hairpin_pavement_lift_m") == 0.04
                  and value.get("non_top_triangles_scanned") == 7418
                  and value.get("native_top_columns") == NATIVE_TRIANGLE_COLUMNS
                  and value.get("wall_columns") == ["source_segment_start_row", *NATIVE_TRIANGLE_COLUMNS]
                  and value.get("geometry_mutated") is False and value.get("native_vertex_ids_available") is False,
                  "source/native wall identity differs")
    tops = _wall_positions(value.get("native_top_triangles"))
    first, last = HAIRPIN_WALL_ROWS
    _wall_require(set(tops) == {i * 52 + k for i in range(first, last) for k in (0, 1)},
                  "native top face inventory differs")
    walls = value.get("wall_triangles", [])
    _wall_require(isinstance(walls, list) and 0 < len(walls) <= 2 * (last - first)
                  and all(isinstance(row, list) and len(row) == 11 and type(row[0]) is int for row in walls), "wall inventory differs")
    wall_positions = _wall_positions([row[1:] for row in walls])
    _wall_require(all(tid >= 124800 for tid in wall_positions), "top face passed as a wall")
    segments = _wall_segments(tops, value.get("pavement_edge_rows_cm"))
    selected = _select_wall_faces(wall_positions, segments)
    _wall_require(walls == [[i, *row] for i, ids in selected.items() for row in _wall_triangle_rows(wall_positions, ids)]
                  and value.get("segments_without_matched_wall") == [i for i, ids in selected.items() if not ids],
                  "retained source/wall correspondence differs")
    source = value.get("cut_source", {})
    _wall_require(source.get("manifest_sha256") == HAIRPIN_CUT_SHA256
                  and source.get("patch_file") == cut["patch_file"]
                  and source.get("patch_sha256") == cut["patch_sha256"]
                  and source.get("patch_size_bytes") == cut["patch_byte_count"]
                  and source.get("encoding") == "little_endian_float32_row_major_y_x_world_z_cm"
                  and source.get("node_selection") == "floor_ceil_source_grid_nodes_at_native_wall_corner_xy"
                  and source.get("node_columns") == CUT_NODE_COLUMNS
                  and source.get("final_native_landscape_height_observed") is False
                  and source.get("height_interpolation_performed") is False
                  and value.get("source_patch_identity", {}).get("size_bytes") == cut["patch_byte_count"]
                  and value.get("source_patch_identity", {}).get("sha256_before") == cut["patch_sha256"]
                  and value.get("source_patch_identity", {}).get("sha256_after") == cut["patch_sha256"]
                  and isinstance(value.get("source_patch_identity", {}).get("path"), str)
                  and value["source_patch_identity"]["path"].replace("\\", "/").endswith("/" + cut["patch_file"]),
                  "CUT source identity/measurement scope differs")
    keys, outside = _wall_cut_keys(walls, cut)
    nodes = source.get("nodes", [])
    _wall_require(isinstance(nodes, list) and len(nodes) == len(keys)
                  and source.get("sample_status") == ("SOURCE_NODES_RETAINED" if keys else "NO_NODES_IN_SOURCE_FOOTPRINT")
                  and source.get("corners_outside_source_patch") == outside,
                  "CUT source node inventory differs")
    for node, (gx, gy) in zip(nodes, keys, strict=True):
        offset = ((gy - cut["rect"]["min_y"]) * cut["rect"]["width"] + gx - cut["rect"]["min_x"]) * 4
        _wall_require(isinstance(node, list) and len(node) == 7
                      and all(type(v) is int for v in node[:3])
                      and node[:3] == [gx, gy, offset] and isinstance(node[3], str) and len(node[3]) == 8,
                      "CUT source byte address differs")
        z = struct.unpack("<f", bytes.fromhex(node[3]))[0]
        _wall_require(math.isfinite(z) and node[4:] == [gx * 50.0, gy * 50.0, z],
                      "CUT raw4/position/height differs")


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


def verify_support022(report):
    """Bound the additional owner to its existing source tops and full readback."""
    row = report.get("support022", {})
    primary = report.get("support", {})
    components = report.get("landscape", {}).get("components", [])
    path, component = row.get("path"), row.get("component")
    sha = row.get("triangle_sha256")
    original = row.get("original_visibility")
    recipe = report.get("source_identity", {}).get("recipe_sha256")
    restore = report.get("restoration", {})
    if (
        row.get("label") != SUPPORT022_LABEL
        or row.get("source_window_id") != SUPPORT022_WINDOW
        or row.get("source_section_count") != SUPPORT022_SECTION_COUNT
        or (row.get("vertices"), row.get("triangles")) != SUPPORT022_MESH_COUNTS
        or row.get("source_top_triangles_compared") != SUPPORT022_TOP_COUNT
        or row.get("source_top_triangle_sha256") != SUPPORT022_TOP_SHA256
        or not isinstance(recipe, str) or len(recipe) != 64
        or row.get("source_recipe_sha256") != recipe
        or not 0 <= row.get("max_coordinate_delta_cm", float("inf")) <= 0.0001
        or row.get("native_query") != "YacsLandscapeMeshDiagnosticLibrary.ReadWindow0112SupportTriangles"
        or row.get("native_triangle_ids_dense") is not True
        or row.get("native_triangle_ids_in_digest") is not True
        or row.get("native_vertex_ids_observed") is not False
        or not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha)
        or restore.get("support022_triangle_sha256") != sha
        or not isinstance(path, str)
        or not path.startswith("/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004.")
        or not isinstance(component, str) or not component.startswith(path + ".")
        or not isinstance(row.get("mesh_path"), str) or not row["mesh_path"]
        or primary.get("label") != "YACS_PERSIST_SUPPORT_112"
        or path == primary.get("path") or component == primary.get("component")
        or component in [c.get("path") for c in components]
        or row.get("location_cm") != [0.0, 0.0, 0.0]
        or row.get("rotation_deg") != [0.0, 0.0, 0.0]
        or row.get("scale") != [1.0, 1.0, 1.0]
        or not isinstance(original, list) or len(original) != 2
        or any(type(v) is not bool for v in original) or original[0] is not True
        or restore.get("support022_visibility") != original
    ):
        raise ValueError("Support022 source/native identity or full restoration failed")


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
    # Absence keeps the historical 4258 contract exactly as it was. A present
    # optional observation must pass completely; FAILED/PENDING is never ignored.
    if "support_wall_contact" in report:
        _wall_require(target == "hairpin0081", "wall observation supplied for a different target")
        verify_wall_contact(report["support_wall_contact"], report,
                            (root / "source-cut-manifest.json").read_bytes())
    plan = report["plan"]
    extended = "diagnostic_schema_version" in plan
    if extended:
        if (target != "window0112" or type(plan["diagnostic_schema_version"]) is not int
                or plan["diagnostic_schema_version"] != DIAGNOSTIC_SCHEMA_VERSION):
            raise ValueError("Unexpected shoulder-contact diagnostic plan version")
        verify_support022(report)
    elif "support022" in report:
        raise ValueError("Support022 observation requires the current diagnostic plan version")
    modes = WINDOW_MODES if extended else MODES
    expected_order = [(frame, mode) for frame in spec["frame_ids"] for mode in modes]
    expected = set(expected_order)
    rows = survey.get("frames", [])
    if (
        len(rows) != len(expected)
        or {(r["source_frame_id"], r["diagnostic_mode"]) for r in rows} != expected
    ):
        raise ValueError("Incomplete or duplicate paired diagnostic frame inventory")
    if extended:
        if (plan.get("frame_count") != 16 or len(plan["frames"]) != 16
                or plan.get("source_poses") != list(FRAME_IDS)
                or plan.get("original_survey_csv_sha256") != SURVEY_SHA256
                or [(r["source_frame_id"], r["diagnostic_mode"]) for r in plan["frames"]] != expected_order
                or [(r["source_frame_id"], r["diagnostic_mode"]) for r in rows] != expected_order
                or any(r["frame_id"] != f'{r["source_frame_id"]}-{r["diagnostic_mode"]}'
                       or r["file"] != f'frames/{r["frame_id"]}.png' for r in (*plan["frames"], *rows))):
            raise ValueError("Current support022 diagnostic requires the exact 16-frame plan")
        for first in range(0, 16, 4):
            baseline = plan["frames"][first]
            if any(row[key] != baseline[key] for row in plan["frames"][first:first + 4]
                   for key in ("road_position_cm", "camera_location_cm", "target_cm",
                               "ball_location_cm", "station_m", "fov_deg")):
                raise ValueError("Support022 control changed an original source camera pose")
    planned = {r["frame_id"]: r for r in plan["frames"]}
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
        if extended and (
            type(state.get("support022_visible")) is not bool
            or state["support022_visible"] != (row["diagnostic_mode"] != "support022-hidden")
            or state.get("support022_component") != report["support022"]["component"]
            or state.get("support_component") != support.get("component")
            or state.get("landscape_components") != [c["path"] for c in components]
            or state.get("hidden_shadow_disabled_on_hidden_surfaces") is not True
        ):
            raise ValueError("Support022 diagnostic frame visibility/owner differs")
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

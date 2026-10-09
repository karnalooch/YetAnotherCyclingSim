"""Bounded shared shoulder endpoints; never change pavement or infer road links.

Only coincident complete 25-point pavement cross-sections establish a join.
Nearby ends, crossings, protected structures and unknown terrain are not welded.
Native terrain/contact and visual validation remain separate requirements.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from collections import Counter
from itertools import combinations

MATCH_M = 1e-6
SHOULDER_M = 0.5
EXTENT_MAX_M = 0.51
MAX_MOVE_M = 0.025


def fingerprint(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _validate(windows, supports):
    require(isinstance(windows, list) and windows, "Missing road windows")
    ids = [w.get("id") for w in windows]
    require(
        all(isinstance(x, str) and x for x in ids)
        and len(ids) == len(set(ids))
        and set(ids) == set(supports),
        "Window/support identity mismatch",
    )
    for window in windows:
        rows = window.get("sections")
        require(isinstance(rows, list) and len(rows) >= 3, "Missing road sections")
        require(len(supports[window["id"]]) == len(rows), "Support length mismatch")
        for row, support in zip(rows, supports[window["id"]], strict=True):
            require(len(row) == 25 and len(support) == 27, "Section shape mismatch")
            for point in (*row, *support):
                require(
                    len(point) == 3
                    and all(type(v) in (float, int) and math.isfinite(v) for v in point),
                    "Nonfinite or malformed section point",
                )
            require(
                all(
                    p[0] == q[0] and p[1] == q[1] and abs(p[2] - .08 - q[2]) < 1e-9
                    for p, q in zip(row, support[1:-1], strict=True)
                ),
                "Support interior differs from fixed pavement underside",
            )
            require(math.dist(row[0][:2], row[-1][:2]) > MATCH_M, "Zero-width road")


def _endpoints(windows):
    ends = []
    for window in sorted(windows, key=lambda w: w["id"]):
        for end in (0, -1):
            row = window["sections"][end]
            ends.append({
                "window_id": window["id"], "end": end, "row": row,
                "neighbor": window["sections"][1 if end == 0 else -2],
                "center": [(row[0][k] + row[-1][k]) / 2 for k in range(3)],
            })
    return ends


def _opposed_continuation(a, b):
    vectors = []
    for ep in (a, b):
        neighbor = ep["neighbor"]
        v = [(neighbor[0][k] + neighbor[-1][k]) / 2 - ep["center"][k]
             for k in (0, 1)]
        length = math.hypot(*v)
        if length <= MATCH_M:
            return False
        vectors.append([x / length for x in v])
    return sum(x * y for x, y in zip(*vectors, strict=True)) < 0


def _normal(endpoint, side):
    point = endpoint["row"][side]
    neighbor = endpoint["neighbor"][side]
    dx, dy = neighbor[0] - point[0], neighbor[1] - point[1]
    length = math.hypot(dx, dy)
    require(length > MATCH_M, "Degenerate boundary segment")
    normal = [-dy / length, dx / length]
    outward = [point[k] - endpoint["center"][k] for k in (0, 1)]
    alignment = sum(a * b for a, b in zip(normal, outward, strict=True))
    require(abs(alignment) > MATCH_M, "Degenerate transverse direction")
    if alignment < 0:
        normal = [-x for x in normal]
    return normal


def _height(row, xy):
    a, b = row[0], row[-1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    ratio = ((xy[0] - a[0]) * dx + (xy[1] - a[1]) * dy) / (dx * dx + dy * dy)
    return a[2] + ratio * (b[2] - a[2]) - .08


def _shared_point(a, b, side_a, side_b):
    p = a["row"][side_a]
    na, nb = _normal(a, side_a), _normal(b, side_b)
    nx, ny = na[0] + nb[0], na[1] + nb[1]
    length = math.hypot(nx, ny)
    require(length > MATCH_M, "Opposed boundary normals")
    nx, ny = nx / length, ny / length
    denominator = nx * na[0] + ny * na[1]
    require(denominator > .1, "Unbounded joint miter")
    extent = SHOULDER_M / denominator
    require(extent <= EXTENT_MAX_M + 1e-9, "Joint exceeds existing shoulder envelope")
    xy = [p[0] + nx * extent, p[1] + ny * extent]
    z = _height(a["row"], xy)
    require(abs(z - _height(b["row"], xy)) <= MATCH_M, "Crossfall mismatch")
    for ep, side, normal in ((a, side_a, na), (b, side_b, nb)):
        delta = [xy[k] - ep["row"][side][k] for k in (0, 1)]
        distance = sum(x * y for x, y in zip(delta, normal, strict=True))
        require(abs(distance - SHOULDER_M) <= MATCH_M, "Shoulder width mismatch")
    return [*xy, z]


def _winding_ok(rows, end):
    a, b = (rows[0], rows[1]) if end == 0 else (rows[-2], rows[-1])
    for j in (0, 25):
        for p, q, r in ((a[j], a[j + 1], b[j]), (a[j + 1], b[j + 1], b[j])):
            area = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
            if area >= -1e-9:
                return False
    return True


def repair_shoulder_joints(windows, supports, *, protected_ids=()):
    """Return copied candidates and explicit audit; do not mutate caller data.

    The caller must trace the NEW outer points on the actual post-CUT Landscape
    before building their walls. This function never reuses old terrain heights.
    """
    _validate(windows, supports)
    protected = set(protected_ids)
    require(protected <= set(supports), "Unknown protected window")
    before = fingerprint(windows)
    result = {name: [list(map(list, row)) for row in rows]
              for name, rows in supports.items()}
    ends = _endpoints(windows)
    pairs = []
    for ia, ib in combinations(range(len(ends)), 2):
        a, b = ends[ia], ends[ib]
        if a["window_id"] == b["window_id"] or math.dist(a["center"], b["center"]) > MATCH_M:
            continue
        direct = max(math.dist(p, q) for p, q in zip(a["row"], b["row"], strict=True))
        reverse = max(math.dist(p, q) for p, q in zip(a["row"], b["row"][::-1], strict=True))
        if min(direct, reverse) <= MATCH_M:
            pairs.append((ia, ib, reverse < direct))
    counts = Counter(i for ia, ib, _ in pairs for i in (ia, ib))
    ambiguous = {i for i, count in counts.items() if count > 1}
    records = []
    for ia, ib, reverse in pairs:
        a, b = ends[ia], ends[ib]
        side_pairs = ((0, -1), (-1, 0)) if reverse else ((0, 0), (-1, -1))
        gaps = [math.dist(supports[a["window_id"]][a["end"]][sa],
                          supports[b["window_id"]][b["end"]][sb]) for sa, sb in side_pairs]
        row = {
            "a": [a["window_id"], a["end"]], "b": [b["window_id"], b["end"]],
            "reversed_cross_section": reverse, "center_local_m": a["center"],
            "before_gap_max_m": max(gaps), "after_gap_max_m": max(gaps),
            "changed_outer_vertices": 0, "max_move_m": 0.0,
        }
        if ia in ambiguous or ib in ambiguous:
            row.update(status="REVIEW_REQUIRED", reason="Ambiguous junction")
        elif a["window_id"] in protected or b["window_id"] in protected:
            row.update(status="PROTECTED_UNCHANGED", reason="Protected geometry interface")
        elif not _opposed_continuation(a, b):
            row.update(status="REVIEW_REQUIRED", reason="Coincident ends are not a continuation")
        elif max(gaps) <= 1e-9:
            row.update(status="ALREADY_CONTINUOUS")
        else:
            try:
                proposals = []
                for sa, sb in side_pairs:
                    shared = _shared_point(a, b, sa, sb)
                    for ep, side in ((a, sa), (b, sb)):
                        old = supports[ep["window_id"]][ep["end"]][side]
                        shift = math.dist(old, shared)
                        require(shift <= MAX_MOVE_M + 1e-9, "Joint exceeds 2.5 cm repair budget")
                        proposals.append((ep, side, shared, shift))
                candidate_rows = {}
                for ep, side, shared, _ in proposals:
                    name = ep["window_id"]
                    if name not in candidate_rows:
                        candidate_rows[name] = copy.deepcopy(result[name])
                    candidate_rows[name][ep["end"]][side] = shared[:]
                require(
                    all(_winding_ok(candidate_rows[ep["window_id"]], ep["end"])
                        for ep in (a, b)),
                    "Joint creates folded or degenerate shoulder triangles",
                )
                result.update(candidate_rows)
                row.update(
                    status="CANDIDATE_REPAIRED", after_gap_max_m=0.0,
                    changed_outer_vertices=sum(s > 1e-12 for _, _, _, s in proposals),
                    max_move_m=max(s for _, _, _, s in proposals),
                )
            except ValueError as exc:
                row.update(status="REVIEW_REQUIRED", reason=str(exc))
        records.append(row)
    require(fingerprint(windows) == before, "Source pavement changed")
    _validate(windows, result)
    return result, {
        "schema_version": 1, "recipe_id": "shared-shoulder-endpoints-v1",
        "status": "CANDIDATE_REQUIRES_NATIVE_CONTACT_AND_VISUAL_PROOF",
        "window_count": len(windows), "joint_count": len(records),
        "source_pavement_sha256": before,
        "support_before_sha256": fingerprint(supports),
        "support_after_sha256": fingerprint(result),
        "source_pavement_changed": False,
        "limits_m": {"match": MATCH_M, "shoulder": SHOULDER_M,
                     "extent": EXTENT_MAX_M, "max_endpoint_move": MAX_MOVE_M},
        "protected_ids": sorted(protected), "joints": records,
        "unmatched_endpoints": [[ep["window_id"], ep["end"]]
                                for i, ep in enumerate(ends) if i not in counts],
        "unmatched_semantics": "Open boundary or unmapped continuation, not a proven gap",
        "native_contact_verified": False, "visual_acceptance": "PENDING",
    }

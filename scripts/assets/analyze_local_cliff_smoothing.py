"""Independently audit a native single-surface cliff presentation diagnostic."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path


def audit(plan: dict, evidence: dict) -> dict:
    cells = plan["skin_cells"]
    if len(cells) != 1017:
        raise ValueError("Expected 1017 authoritative cells")
    quads = set()
    for cell in cells:
        if (
            cell["protected_samples"] != 0
            or cell["row1"] - cell["row0"] != 2
            or cell["col1"] - cell["col0"] != 2
        ):
            raise ValueError("Invalid authoritative cell")
        for r in range(cell["row0"], cell["row1"]):
            for c in range(cell["col0"], cell["col1"]):
                if (c, r) in quads:
                    raise ValueError("Overlapping authoritative cells")
                quads.add((c, r))

    rows = evidence["vertices_cm"]
    if len({row[0] for row in rows}) != len(rows):
        raise ValueError("Duplicate vertex ID")
    source = {int(row[0]): tuple(row[1:4]) for row in rows}
    candidate = {int(row[0]): tuple(row[4:7]) for row in rows}
    if any(len(row) != 8 or not all(math.isfinite(v) for v in row) for row in rows):
        raise ValueError("Invalid vertex evidence")
    if any(
        abs(p[k] / 50 - round(p[k] / 50)) > 1e-6
        for p in source.values()
        for k in (0, 1)
    ):
        raise ValueError("Source differs from native grid")

    def signed_area(points):
        a, b, c = points
        return ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2

    edges = Counter()
    faces = set()
    locked = set()
    source_area = candidate_area = 0.0
    allowed_count = 0
    for face in evidence["triangles"]:
        if len(face) != 3 or len(set(face)) != 3 or any(i not in source for i in face):
            raise ValueError("Invalid triangle")
        key = tuple(sorted(face))
        if key in faces:
            raise ValueError("Duplicate triangle")
        faces.add(key)
        before = [source[i] for i in face]
        after = [candidate[i] for i in face]
        old_area, new_area = signed_area(before), signed_area(after)
        if abs(old_area) < 1e-8 or old_area * new_area <= 0:
            raise ValueError("Folded or degenerate triangle")
        if abs(new_area) < abs(old_area) * 0.1 - 1e-7:
            raise ValueError("Collapsed presentation triangle")
        tile = tuple(math.floor(sum(p[k] for p in before) / 150) for k in (0, 1))
        if tile in quads:
            allowed_count += 1
            source_area += abs(old_area)
            candidate_area += abs(new_area)
        else:
            locked.update(face)
        for a, b in zip(face, face[1:] + face[:1]):
            edges[tuple(sorted((a, b)))] += 1
    if any(n > 2 for n in edges.values()):
        raise ValueError("Nonmanifold edge")
    for edge, count in edges.items():
        if count == 1:
            locked.update(edge)
    if allowed_count != 8136 or abs(source_area / 10000 - 1017) > 1e-6:
        raise ValueError("Native source does not cover exact cliff footprint")
    if abs(candidate_area - source_area) > 1e-3:
        raise ValueError("Presentation footprint area changed")
    if any(math.dist(source[v], candidate[v]) > 1e-8 for v in locked):
        raise ValueError("Unselected terrain or footprint interface moved")
    displacement = {v: math.dist(source[v], candidate[v]) for v in source}
    if max(displacement.values()) > 50.000001:
        raise ValueError("Presentation displacement exceeds 50 cm")
    changed = [v for v, d in displacement.items() if d > 1e-6]
    if not changed:
        raise ValueError("No local geometry change")
    return {
        "status": "PASS",
        "vertices": len(source),
        "triangles": len(faces),
        "selected_native_triangles": allowed_count,
        "source_area_m2": source_area / 10000,
        "candidate_area_m2": candidate_area / 10000,
        "changed_vertices": len(changed),
        "locked_vertices": len(locked),
        "max_displacement_cm": max(displacement.values()),
        "nonmanifold_edges": 0,
        "folded_xy_triangles": 0,
        "scope": "LOCAL_GEOMETRY_AUDIT_NOT_VISUAL_ACCEPTANCE",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(json.loads(args.plan.read_text()), json.loads(args.mesh.read_text()))
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()

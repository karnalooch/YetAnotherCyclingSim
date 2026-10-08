"""Independently audit a native single-surface cliff presentation diagnostic."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path


def original_surface_evidence(reference: dict, derived: dict) -> dict:
    """Recover the original native surface, never the previously smoothed candidate."""
    originals = {tuple(row[1:3]): row[1:4] for row in reference["vertices_cm"]}
    if len(originals) != len(reference["vertices_cm"]):
        raise ValueError("Ambiguous original vertex correspondence")
    rows = []
    for row in derived["vertices_cm"]:
        original = originals.get(tuple(row[1:3]))
        if original is None:
            raise ValueError("Missing original vertex correspondence")
        if math.dist(original, row[1:4]) > 150.000001:
            raise ValueError("Terrain stage exceeds reserved 150 cm")
        if math.dist(row[1:4], row[4:7]) > 50.000001:
            raise ValueError("Mesh stage exceeds reserved 50 cm")
        rows.append([row[0], *original, *row[4:]])
    return dict(derived, vertices_cm=rows, source_reference="original-before-erosion")


def audit(plan: dict, evidence: dict, *, limit_cm=100.0, rounding_domain=False) -> dict:
    if limit_cm not in (50.0, 100.0, 200.0):
        raise ValueError("Unsupported displacement envelope")
    cells = plan["skin_cells"]
    if len(cells) != 1017:
        raise ValueError("Expected 1017 authoritative cells")
    if rounding_domain:
        contract = plan.get('rounding_domain_contract', {})
        cells = plan.get('rounding_cells', [])
        if (contract.get('method') != 'source-cliff-six-metre-crown-apron-v1'
                or contract.get('radius_m') != 6 or contract.get('classifier_unchanged') is not True
                or contract.get('hard_protected_samples') != 0
                or contract.get('cell_count') != len(cells) or contract.get('area_m2') != len(cells)
                or not 1017 <= len(cells) <= 3969
                or not {(c['col0'], c['row0']) for c in plan['skin_cells']} <=
                       {(c['col0'], c['row0']) for c in cells}):
            raise ValueError('Invalid separate rounded presentation domain')
    quads = set()
    for cell in cells:
        if (
            cell["protected_samples"] != 0
            or cell["row1"] - cell["row0"] != 2
            or cell["col1"] - cell["col0"] != 2
            or (rounding_domain and not 882 <= cell['row0'] < cell['row1'] <= 1008)
            or (rounding_domain and not 756 <= cell['col0'] < cell['col1'] <= 882)
        ):
            raise ValueError("Invalid authoritative cell")
        for r in range(cell["row0"], cell["row1"]):
            for c in range(cell["col0"], cell["col1"]):
                if (c, r) in quads:
                    raise ValueError("Overlapping authoritative cells")
                quads.add((c, r))

    refinement = evidence.get("refinement", "native")
    if refinement not in (
        "native",
        "Epic FSelectiveTessellate red-green level 1 on cliff triangles only",
    ):
        raise ValueError("Unknown source refinement")
    grid_step = 50 if refinement == "native" else 25
    expected_selected = 8136 if refinement == "native" else 32544
    rows = evidence["vertices_cm"]
    if len({row[0] for row in rows}) != len(rows):
        raise ValueError("Duplicate vertex ID")
    source = {int(row[0]): tuple(row[1:4]) for row in rows}
    candidate = {int(row[0]): tuple(row[4:7]) for row in rows}
    if any(len(row) != 8 or not all(math.isfinite(v) for v in row) for row in rows):
        raise ValueError("Invalid vertex evidence")
    if any(
        abs(p[k] / grid_step - round(p[k] / grid_step)) > 1e-6
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
    quad_areas = Counter()
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
            quad_areas[tile] += abs(old_area)
        else:
            locked.update(face)
        for a, b in zip(face, face[1:] + face[:1]):
            edges[tuple(sorted((a, b)))] += 1
    if len(faces) > 60000:
        raise ValueError("Unchanged per-mesh triangle budget exceeded")
    if any(n > 2 for n in edges.values()):
        raise ValueError("Nonmanifold edge")
    for edge, count in edges.items():
        if count == 1:
            locked.update(edge)
    if ((not rounding_domain and allowed_count != expected_selected)
            or abs(source_area / 10000 - len(cells)) > 1e-6
            or set(quad_areas) != quads
            or any(abs(area - 2500) > 1e-6 for area in quad_areas.values())):
        raise ValueError("Native source does not cover exact cliff footprint")
    if abs(candidate_area - source_area) > 1e-3:
        raise ValueError("Presentation footprint area changed")
    if any(math.dist(source[v], candidate[v]) > 1e-8 for v in locked):
        raise ValueError("Unselected terrain or footprint interface moved")
    displacement = {v: math.dist(source[v], candidate[v]) for v in source}
    if max(displacement.values()) > limit_cm + 0.000001:
        raise ValueError(f"Presentation displacement exceeds {limit_cm:g} cm")
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
        "displacement_limit_cm": limit_cm,
        "nonmanifold_edges": 0,
        "folded_xy_triangles": 0,
        "scope": "LOCAL_ROUNDED_DOMAIN_AUDIT_NOT_VISUAL_ACCEPTANCE" if rounding_domain else "LOCAL_GEOMETRY_AUDIT_NOT_VISUAL_ACCEPTANCE",
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

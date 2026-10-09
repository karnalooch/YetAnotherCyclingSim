#!/usr/bin/env python3
"""Independent structural audit for Phase 2C PCGEx cliff topology.

The commandlet is responsible for generating presentation topology. This tool
independently verifies the serialized mesh against the unchanged YACS Phase 2B
skin-cell authority. It never reads or modifies Unreal assets.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _cell_bounds(plan: dict) -> tuple[list[tuple[float, float, float, float]], float]:
    pixel = float(plan["grid"]["pixel_size_m"])
    bounds = []
    for cell in plan["skin_cells"]:
        x0 = float(cell["col0"]) * pixel
        x1 = float(cell["col1"]) * pixel
        y0 = float(cell["row0"]) * pixel
        y1 = float(cell["row1"]) * pixel
        if not (x1 > x0 and y1 > y0):
            raise ValueError("invalid skin cell bounds")
        bounds.append((x0, y0, x1, y1))
    return bounds, pixel


def _edge_connected_cell_components(plan: dict) -> int:
    """Count physical polygon islands using shared-edge connectivity.

    Phase 2B semantic clusters use 8-neighbour connectivity so diagonal source
    evidence can stay in one logical cliff cluster. A triangulated polygon mesh,
    however, is connected only when cells share a non-zero-length edge. Derive
    that relation from authoritative row/column bounds rather than auxiliary
    grid_rc metadata so the audit contract is self-contained.
    """
    cells = [
        (
            int(cell["row0"]),
            int(cell["row1"]),
            int(cell["col0"]),
            int(cell["col1"]),
        )
        for cell in plan["skin_cells"]
    ]
    adjacency: list[list[int]] = [[] for _ in cells]
    for left in range(len(cells)):
        ar0, ar1, ac0, ac1 = cells[left]
        for right in range(left + 1, len(cells)):
            br0, br1, bc0, bc1 = cells[right]
            vertical_overlap = max(ar0, br0) < min(ar1, br1)
            horizontal_overlap = max(ac0, bc0) < min(ac1, bc1)
            shares_vertical_edge = (
                (ac1 == bc0 or bc1 == ac0) and vertical_overlap
            )
            shares_horizontal_edge = (
                (ar1 == br0 or br1 == ar0) and horizontal_overlap
            )
            if shares_vertical_edge or shares_horizontal_edge:
                adjacency[left].append(right)
                adjacency[right].append(left)

    seen: set[int] = set()
    components = 0
    for seed in range(len(cells)):
        if seed in seen:
            continue
        components += 1
        stack = [seed]
        seen.add(seed)
        while stack:
            current = stack.pop()
            for neighbour in adjacency[current]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
    return components

def _spatial_index(
    bounds: list[tuple[float, float, float, float]],
    step_m: float,
) -> tuple[dict[tuple[int, int], list[int]], float, float]:
    if not bounds:
        raise ValueError("no admitted skin cells")
    ox = min(row[0] for row in bounds)
    oy = min(row[1] for row in bounds)
    index: dict[tuple[int, int], list[int]] = {}
    for i, (x0, y0, x1, y1) in enumerate(bounds):
        ix0 = math.floor((x0 - ox) / step_m)
        ix1 = math.floor((x1 - ox - 1e-12) / step_m)
        iy0 = math.floor((y0 - oy) / step_m)
        iy1 = math.floor((y1 - oy - 1e-12) / step_m)
        for iy in range(iy0, iy1 + 1):
            for ix in range(ix0, ix1 + 1):
                index.setdefault((ix, iy), []).append(i)
    return index, ox, oy


def _inside(
    x: float,
    y: float,
    bounds: list[tuple[float, float, float, float]],
    index: dict[tuple[int, int], list[int]],
    ox: float,
    oy: float,
    step_m: float,
    tolerance_m: float,
) -> bool:
    ix = math.floor((x - ox) / step_m)
    iy = math.floor((y - oy) / step_m)
    for by in range(iy - 1, iy + 2):
        for bx in range(ix - 1, ix + 2):
            for cell_index in index.get((bx, by), ()):
                x0, y0, x1, y1 = bounds[cell_index]
                if (
                    x0 - tolerance_m <= x <= x1 + tolerance_m
                    and y0 - tolerance_m <= y <= y1 + tolerance_m
                ):
                    return True
    return False


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


def _triangle_quality(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> tuple[float, float, float]:
    ab = math.dist(a, b)
    bc = math.dist(b, c)
    ca = math.dist(c, a)
    longest = max(ab, bc, ca)
    area2 = abs(
        (b[0] - a[0]) * (c[1] - a[1])
        - (b[1] - a[1]) * (c[0] - a[0])
    )
    area = area2 * 0.5
    if min(ab, bc, ca) <= 1e-12 or area <= 1e-12:
        return area, longest, 0.0

    sides = (ab, bc, ca)
    angles = []
    for opposite, left, right in (
        (bc, ab, ca),
        (ca, ab, bc),
        (ab, bc, ca),
    ):
        cosine = (left * left + right * right - opposite * opposite) / (
            2.0 * left * right
        )
        angles.append(math.degrees(math.acos(max(-1.0, min(1.0, cosine)))))
    return area, longest, min(angles)


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    rows = sorted(values)
    position = (len(rows) - 1) * q
    lo = math.floor(position)
    hi = math.ceil(position)
    if lo == hi:
        return rows[lo]
    alpha = position - lo
    return rows[lo] * (1.0 - alpha) + rows[hi] * alpha


def analyze(
    plan: dict,
    mesh_receipt: dict,
    *,
    tolerance_m: float = 1e-4,
    min_area_retention: float = 0.90,
) -> dict:
    if plan.get("status") != "COMPONENT230_CLIFF_VISUAL_PLAN":
        raise ValueError("invalid Phase 2B plan")
    if mesh_receipt.get("status") != "YACS_SA_CALOBRA_PCGEX_CLIFF_MESH_PASS":
        raise ValueError("invalid Phase 2C mesh receipt")

    bounds, _pixel = _cell_bounds(plan)
    step_m = float(plan["skin_contract"]["source_grid_step_m"])
    spatial, ox, oy = _spatial_index(bounds, step_m)
    semantic_clusters = int(plan["counts"]["skin_cluster_count"])
    expected_components = _edge_connected_cell_components(plan)
    expected_cells = int(plan["counts"]["skin_cell_count"])

    if int(mesh_receipt["source_skin_cell_count"]) != expected_cells:
        raise ValueError("mesh receipt source cell count drift")

    total_vertices = 0
    total_triangles = 0
    total_area = 0.0
    max_edge = 0.0
    min_angles: list[float] = []
    outside_vertices = 0
    outside_centroids = 0
    degenerate = 0
    nonmanifold = 0
    component_count = 0
    boundary_edges = 0

    for mesh in mesh_receipt["meshes"]:
        vertices = [
            (float(row[0]) / 100.0, float(row[1]) / 100.0)
            for row in mesh["vertices_cm"]
        ]
        triangles = [
            tuple(int(value) for value in row)
            for row in mesh["triangles"]
        ]
        total_vertices += len(vertices)
        total_triangles += len(triangles)

        for x, y in vertices:
            if not _inside(
                x, y, bounds, spatial, ox, oy, step_m, tolerance_m
            ):
                outside_vertices += 1

        uf = _UnionFind(len(vertices))
        used_vertices: set[int] = set()
        edge_counts: dict[tuple[int, int], int] = {}
        for triangle in triangles:
            if len(triangle) != 3:
                raise ValueError("triangle does not have three indices")
            a_i, b_i, c_i = triangle
            if (
                min(a_i, b_i, c_i) < 0
                or max(a_i, b_i, c_i) >= len(vertices)
                or len({a_i, b_i, c_i}) != 3
            ):
                degenerate += 1
                continue

            a, b, c = vertices[a_i], vertices[b_i], vertices[c_i]
            area, longest, min_angle = _triangle_quality(a, b, c)
            if area <= 1e-10:
                degenerate += 1
                continue
            total_area += area
            max_edge = max(max_edge, longest)
            min_angles.append(min_angle)

            centroid = (
                (a[0] + b[0] + c[0]) / 3.0,
                (a[1] + b[1] + c[1]) / 3.0,
            )
            if not _inside(
                centroid[0],
                centroid[1],
                bounds,
                spatial,
                ox,
                oy,
                step_m,
                tolerance_m,
            ):
                outside_centroids += 1

            used_vertices.update((a_i, b_i, c_i))
            uf.union(a_i, b_i)
            uf.union(b_i, c_i)
            uf.union(c_i, a_i)
            for left, right in ((a_i, b_i), (b_i, c_i), (c_i, a_i)):
                edge = (min(left, right), max(left, right))
                edge_counts[edge] = edge_counts.get(edge, 0) + 1

        roots = {uf.find(index) for index in used_vertices}
        component_count += len(roots)
        boundary_edges += sum(count == 1 for count in edge_counts.values())
        nonmanifold += sum(count > 2 for count in edge_counts.values())

    source_area = sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in bounds)
    retention = total_area / source_area if source_area else 0.0
    failures = []
    if outside_vertices:
        failures.append(f"{outside_vertices} mesh vertices outside YACS admitted footprint")
    if outside_centroids:
        failures.append(
            f"{outside_centroids} triangle centroids outside YACS admitted footprint"
        )
    if degenerate:
        failures.append(f"{degenerate} degenerate/invalid triangles")
    if nonmanifold:
        failures.append(f"{nonmanifold} non-manifold edges")
    if component_count != expected_components:
        failures.append(
            f"connected components {component_count} != expected {expected_components}"
        )
    if retention < min_area_retention:
        failures.append(
            f"area retention {retention:.6f} < required {min_area_retention:.6f}"
        )
    if retention > 1.001:
        failures.append(f"mesh area exceeds admitted footprint: {retention:.6f}")

    report = {
        "schema_version": 1,
        "status": "PASS" if not failures else "FAIL",
        "authority": "unchanged Phase 2B YACS skin-cell footprint",
        "source": {
            "skin_cell_count": expected_cells,
            "semantic_cluster_count": semantic_clusters,
            "edge_connected_component_count": expected_components,
            "area_m2": source_area,
        },
        "mesh": {
            "mesh_count": len(mesh_receipt["meshes"]),
            "vertex_count": total_vertices,
            "triangle_count": total_triangles,
            "connected_components": component_count,
            "boundary_edges": boundary_edges,
            "nonmanifold_edges": nonmanifold,
            "degenerate_triangles": degenerate,
            "outside_vertices": outside_vertices,
            "outside_triangle_centroids": outside_centroids,
            "area_m2": total_area,
            "area_retention": retention,
            "max_edge_m": max_edge,
            "min_angle_deg": {
                "minimum": min(min_angles) if min_angles else 0.0,
                "p01": _percentile(min_angles, 0.01),
                "p05": _percentile(min_angles, 0.05),
                "median": _percentile(min_angles, 0.50),
            },
        },
        "gate": {
            "tolerance_m": tolerance_m,
            "min_area_retention": min_area_retention,
            "max_area_ratio": 1.001,
            "expected_connected_components": expected_components,
            "semantic_cluster_count": semantic_clusters,
        },
        "failures": failures,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--mesh", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--min-area-retention", type=float, default=0.90)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    mesh = json.loads(args.mesh.read_text(encoding="utf-8-sig"))
    report = analyze(
        plan,
        mesh,
        min_area_retention=args.min_area_retention,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

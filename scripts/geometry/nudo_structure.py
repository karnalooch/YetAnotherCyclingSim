"""An open arch under the upper ribbon, with explicit SI design dimensions."""

import math

from scripts.geometry.bob_vertical_support import build_vertical_support
from scripts.geometry.network_pavement import pavement_slab


def bridge_parapets(sections, station_start, design):
    """Two 0.30 m thick, 0.65 m high parapets within the upper bridge domain."""
    station = station_start
    selected = []
    for i, row in enumerate(sections):
        if i:
            station += math.dist(row[13][:2], sections[i - 1][13][:2])
        if station <= design["upper_domain_station_m"]:
            selected.append(row)
    if len(selected) < 3:
        return [], []
    vertices, triangles = [], []
    for outer, inner in ((0, 1), (-1, -2)):
        rows = []
        for section in selected:
            a, b = section[outer], section[inner]
            length = math.dist(a[:2], b[:2])
            row = [
                [
                    a[0] + (b[0] - a[0]) * j / 24 * 0.3 / length,
                    a[1] + (b[1] - a[1]) * j / 24 * 0.3 / length,
                    a[2] + 0.65,
                ]
                for j in range(25)
            ]
            rows.append(row if outer == 0 else list(reversed(row)))
        v, t = pavement_slab(rows)
        for p in v[len(v) // 2 :]:
            p[2] -= 0.57
        offset = len(vertices)
        vertices.extend(v)
        triangles.extend(tuple(i + offset for i in face) for face in t)
    return vertices, triangles


def arch_height(point, design):
    dx = point[0] - design["center_xy_m"][0]
    dy = point[1] - design["center_xy_m"][1]
    tx, ty = design["lower_direction_xy"]
    across = -ty * dx + tx * dy
    radius = design["opening_half_width_m"]
    if abs(across) >= radius:
        return None
    return (
        design["lower_height_m"]
        + design["spring_height_m"]
        + design["arch_rise_m"] * math.sqrt(1 - (across / radius) ** 2)
    )


def build_nudo_support(sections, ground, station_start, design):
    """Replace upper-road solid walls by the arch intrados; never fill the tunnel.

    Terrain remains the ground owner. The underside only spans the opening;
    outside it the existing support perimeter terminates at traced Landscape.
    """
    floors = []
    station = station_start
    minimum_thickness = math.inf
    arch_rows = []
    for i, (row, heights) in enumerate(zip(sections, ground, strict=True)):
        if i:
            station += math.dist(row[13][:2], sections[i - 1][13][:2])
        floor = []
        active = []
        span = math.dist(row[0][:2], row[-1][:2])
        for point in row:
            ratio = math.dist(row[0][:2], point[:2]) / span
            base = heights[0] + ratio * (heights[1] - heights[0])
            arch = (
                arch_height(point, design)
                if station < design["upper_domain_station_m"]
                else None
            )
            if arch is not None:
                minimum_thickness = min(minimum_thickness, point[2] - arch)
            floor.append(
                [point[0], point[1], max(base, arch) if arch is not None else base]
            )
            active.append(arch is not None and arch > base)
        floors.append(floor)
        arch_rows.append(active)
    if minimum_thickness < 0.4:
        raise ValueError("Nudo arch leaves less than 0.4 m structural depth")
    vertices, triangles, proof = build_vertical_support(
        sections, [[r[0][2], r[-1][2]] for r in floors]
    )
    # Downward facing soffit. Side faces from the support builder end at this
    # same sampled intrados, rather than extending through the lower road.
    offset = len(vertices)
    vertices.extend(p for row in floors for p in row)
    soffit_count = 0
    for i in range(len(sections) - 1):
        for j in range(26):
            if not any(
                (
                    arch_rows[i][j],
                    arch_rows[i][j + 1],
                    arch_rows[i + 1][j],
                    arch_rows[i + 1][j + 1],
                )
            ):
                continue
            a = offset + i * 27 + j
            triangles.extend(((a + 27, a + 1, a), (a + 27, a + 28, a + 1)))
            soffit_count += 2
    proof.update(
        recipe_id="nudo-open-arch-v1",
        arch_soffit_triangle_count=soffit_count,
        minimum_arch_depth_m=None
        if math.isinf(minimum_thickness)
        else minimum_thickness,
        vertex_count=len(vertices),
        triangle_count=len(triangles),
    )
    return vertices, triangles, proof


def inspect_underpass(vertices, triangles, design):
    """Vertical clearance of the actual triangulated arch across the 5 m road."""
    tx, ty = design["lower_direction_xy"]
    cx, cy = design["center_xy_m"]
    minimum = math.inf
    covered = 0
    for across_index in range(21):
        across = -2.5 + across_index * 0.25
        for along_index in range(17):
            along = -4.0 + along_index * 0.5
            x, y = cx + tx * along - ty * across, cy + ty * along + tx * across
            heights = []
            for face in triangles:
                a, b, c = [vertices[i] for i in face]
                if not (
                    min(a[0], b[0], c[0]) - 1e-8 <= x <= max(a[0], b[0], c[0]) + 1e-8
                    and min(a[1], b[1], c[1]) - 1e-8
                    <= y
                    <= max(a[1], b[1], c[1]) + 1e-8
                ):
                    continue
                det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
                if abs(det) < 1e-10:
                    continue
                u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / det
                v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / det
                if min(u, v, 1 - u - v) >= -1e-8:
                    heights.append(u * a[2] + v * b[2] + (1 - u - v) * c[2])
            if heights:
                covered += 1
                # Allow the lower profile's measured longitudinal variation.
                minimum = min(
                    minimum,
                    min(heights)
                    - design["lower_height_m"]
                    - design.get("lower_profile_variation_m", 0.0),
                )
    if covered < 200 or minimum < 4.5:
        raise ValueError(
            f"Nudo triangulated underpass clearance failed: {covered} samples, {minimum} m"
        )
    return {
        "sample_count": covered,
        "minimum_clearance_m": minimum,
        "required_clearance_m": 4.5,
        "status": "PASS",
    }

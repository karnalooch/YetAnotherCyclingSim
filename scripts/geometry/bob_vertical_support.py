"""Simple inferred road support: 0.5 m shoulders and vertical boundary walls.

The road stays fixed. This is visual construction geometry, not a wall survey,
Landscape replacement, collision surface or road admission.
"""

from __future__ import annotations

import math

from scripts.geometry.smooth_road_ribbon import (
    BURIAL_M,
    build_smooth_road_ribbon,
)

SHOULDER_M = 0.5


def support_sections(profile, shoulder_m=SHOULDER_M):
    """Return left/right outer support tops in local metres, below the slab."""
    build_smooth_road_ribbon(profile)  # Reuse input and road fold validation.
    if not math.isfinite(shoulder_m) or shoulder_m <= 0:
        raise ValueError("Support shoulder must be positive and finite")
    sections = []
    for row in profile["stations"]:
        left, right = row["xy_local_m"][0], row["xy_local_m"][-1]
        lz, rz = row["candidate_ground_m"][0], row["candidate_ground_m"][-1]
        dx, dy = right[0] - left[0], right[1] - left[1]
        width = math.hypot(dx, dy)
        if width <= 0:
            raise ValueError("Support section has zero width")
        ux, uy, slope = dx / width, dy / width, (rz - lz) / width
        sections.append(
            (
                (
                    left[0] - ux * shoulder_m,
                    left[1] - uy * shoulder_m,
                    lz - BURIAL_M - slope * shoulder_m,
                ),
                *(
                    (x, y, z - BURIAL_M)
                    for (x, y), z in zip(
                        row["xy_local_m"], row["candidate_ground_m"], strict=True
                    )
                ),
                (
                    right[0] + ux * shoulder_m,
                    right[1] + uy * shoulder_m,
                    rz - BURIAL_M + slope * shoulder_m,
                ),
            )
        )
    # Offset the pavement boundary itself, rather than the centreline normal:
    # varying pavement widths otherwise fold the shoulder at the hairpin.
    for side, outer, inner, sign in ((0, 0, 1, -1), (-1, -1, -2, 1)):
        boundary = [row["xy_local_m"][side] for row in profile["stations"]]
        for i, point in enumerate(boundary):
            normals = []
            for a, b in (
                (boundary[max(0, i - 1)], point),
                (point, boundary[min(len(boundary) - 1, i + 1)]),
            ):
                dx, dy = b[0] - a[0], b[1] - a[1]
                length = math.hypot(dx, dy)
                if length > 1e-9:
                    normals.append((-dy / length * sign, dx / length * sign))
            nx, ny = map(sum, zip(*normals))
            length = math.hypot(nx, ny)
            if length <= 1e-9:
                raise ValueError("Pavement boundary reverses direction")
            nx, ny = nx / length, ny / length
            denominator = nx * normals[0][0] + ny * normals[0][1]
            if denominator <= 0.1:
                raise ValueError("Pavement shoulder miter is unbounded")
            offset = shoulder_m / denominator
            x, y = point[0] + nx * offset, point[1] + ny * offset
            row = profile["stations"][i]
            left, right = row["xy_local_m"][0], row["xy_local_m"][-1]
            dx, dy = right[0] - left[0], right[1] - left[1]
            ratio = ((x - left[0]) * dx + (y - left[1]) * dy) / (dx * dx + dy * dy)
            z = (
                row["candidate_ground_m"][0]
                + ratio * (row["candidate_ground_m"][-1] - row["candidate_ground_m"][0])
                - BURIAL_M
            )
            section = list(sections[i])
            section[outer] = (x, y, z)
            sections[i] = tuple(section)
    # At a tight concave corner a constant-width offset crosses itself. Taper
    # only that local shoulder; asphalt remains byte-for-byte unchanged.
    for _ in range(16):
        narrow = set()
        for i in range(len(sections) - 1):
            for j, outer, inner in ((0, 0, 1), (25, 26, 25)):
                a, b, c, d = (
                    sections[i][j],
                    sections[i][j + 1],
                    sections[i + 1][j],
                    sections[i + 1][j + 1],
                )
                if any(
                    (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
                    >= -1e-9
                    for p, q, r in ((a, b, c), (b, d, c))
                ):
                    narrow.update(((i, outer, inner), (i + 1, outer, inner)))
        if not narrow:
            break
        for i, outer, inner in sorted(narrow):
            section = list(sections[i])
            section[outer] = tuple(
                (a + b) * 0.5 for a, b in zip(section[outer], section[inner])
            )
            sections[i] = tuple(section)
    else:
        raise ValueError("Shoulder cannot be tapered without folding")
    return sections


def build_vertical_support(sections, ground_heights):
    """Build top and vertical perimeter down to sampled ground; no bottom plane.

    Each section has 25 road samples and two outer shoulder points. Ground heights come from actual Landscape
    traces at those endpoints. Walls terminate exactly where ground crosses their
    upper edge. Uphill terrain remains the CUT recipe's responsibility.
    """
    if len(sections) < 3 or len(ground_heights) != len(sections):
        raise ValueError("Support needs matching ordered sections and ground")
    width = 27
    for section, heights in zip(sections, ground_heights, strict=True):
        if (
            len(section) != width
            or len(heights) != 2
            or any(len(point) != 3 for point in section)
        ):
            raise ValueError("Support section shape mismatch")
        if not all(math.isfinite(v) for p in section for v in p) or not all(
            isinstance(v, (int, float)) and math.isfinite(v) for v in heights
        ):
            raise ValueError("Missing or nonfinite support ground")
    vertices = [tuple(p) for section in sections for p in section]
    triangles = []
    for i in range(len(sections) - 1):
        faces = []
        for j in range(width - 1):
            a, b, c, d = (
                i * width + j,
                i * width + j + 1,
                (i + 1) * width + j,
                (i + 1) * width + j + 1,
            )
            faces.extend(((a, b, c), (b, d, c)))
        for face in faces:
            p, q, r = [vertices[j] for j in face]
            area = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
            if area >= -1e-9:
                raise ValueError("Extended shoulder folded or inverted in XY")
            triangles.append(face)
    top_triangle_count = len(triangles)
    flat_ground = []
    for section, (left, right) in zip(sections, ground_heights, strict=True):
        span = math.dist(section[0][:2], section[-1][:2])
        flat_ground.extend(
            left + (right - left) * math.dist(section[0][:2], p[:2]) / span
            for p in section
        )
    # Directed top perimeter; reverse winding for the outward wall face.
    last = (len(sections) - 1) * width
    perimeter = [(j, j + 1) for j in range(width - 1)]
    perimeter += [(last + j + 1, last + j) for j in range(width - 1)]
    perimeter += [((i + 1) * width, i * width) for i in range(len(sections) - 1)]
    perimeter += [
        (i * width + width - 1, (i + 1) * width + width - 1)
        for i in range(len(sections) - 1)
    ]
    wall_count = 0
    for u, v in perimeter:
        a, b = vertices[u], vertices[v]
        ga, gb = flat_ground[u], flat_ground[v]
        ha, hb = a[2] - ga, b[2] - gb
        if ha <= 0 and hb <= 0:
            continue
        if ha < 0 or hb < 0:
            t = ha / (ha - hb)
            crossing = tuple(x + (y - x) * t for x, y in zip(a, b))
            if ha < 0:
                a, ga = crossing, crossing[2]
            else:
                b, gb = crossing, crossing[2]
        points = [b, a, (a[0], a[1], ga), (b[0], b[1], gb)]
        # Drop coincident corners at a ground/top crossing.
        polygon = []
        for point in points:
            if not polygon or math.dist(point, polygon[-1]) > 1e-9:
                polygon.append(point)
        if len(polygon) > 1 and math.dist(polygon[0], polygon[-1]) <= 1e-9:
            polygon.pop()
        if len(polygon) < 3:
            continue
        offset = len(vertices)
        vertices.extend(polygon)
        triangles.extend(
            (offset, offset + j, offset + j + 1) for j in range(1, len(polygon) - 1)
        )
        wall_count += 1
    return (
        vertices,
        triangles,
        {
            "recipe_id": "bob-vertical-support-v1",
            "status": "GEOMETRY_BUILT_VISUAL_REVIEW_PENDING",
            "station_count": len(sections),
            "min_shoulder_extent_m": min(
                math.dist(s[a][:2], s[b][:2])
                for s in sections
                for a, b in ((0, 1), (-1, -2))
            ),
            "max_shoulder_extent_m": max(
                math.dist(s[a][:2], s[b][:2])
                for s in sections
                for a, b in ((0, 1), (-1, -2))
            ),
            "top_triangle_count": top_triangle_count,
            "wall_segment_count": wall_count,
            "vertex_count": len(vertices),
            "triangle_count": len(triangles),
            "max_wall_height_m": max(
                max(0, p[2] - g)
                for section, heights in zip(sections, ground_heights)
                for p, g in zip((section[0], section[-1]), heights)
            ),
            "ground_trace_count": 2 * len(sections),
            "road_admitted": False,
            "collision_proven": False,
            "continuous_support_proven": False,
            "human_visual": "PENDING",
        },
    )

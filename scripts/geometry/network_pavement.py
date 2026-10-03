"""Shared SI geometry for bounded network previews and shoulder admission."""

import math


def pavement_slab(sections):
    """Close the 8 cm asphalt slab with consistent perimeter winding."""
    top = [list(p) for row in sections for p in row]
    count = len(top)
    vertices = top + [[x, y, z - 0.08] for x, y, z in top]
    triangles = []
    for i in range(len(sections) - 1):
        for j in range(24):
            a = i * 25 + j
            b, c, d = a + 1, a + 25, a + 26
            triangles.extend(((a, b, c), (b, d, c)))
            triangles.extend(
                ((c + count, b + count, a + count), (c + count, d + count, b + count))
            )
    last = (len(sections) - 1) * 25
    edges = [(j, j + 1) for j in range(24)]
    edges += [(last + j + 1, last + j) for j in range(24)]
    edges += [((i + 1) * 25, i * 25) for i in range(len(sections) - 1)]
    edges += [(i * 25 + 24, (i + 1) * 25 + 24) for i in range(len(sections) - 1)]
    for a, b in edges:
        triangles.extend(((b, a, a + count), (b, a + count, b + count)))
    return vertices, triangles


def shoulder_sections(sections):
    """Offset each actual pavement boundary by 0.5 m without shoulder taper."""
    result = [[None, *[[x, y, z - 0.08] for x, y, z in row], None] for row in sections]
    for side, outer, sign in ((0, 0, -1), (-1, -1, 1)):
        boundary = [row[side] for row in sections]
        for i, p in enumerate(boundary):
            normals = []
            for a, b in (
                (boundary[max(0, i - 1)], p),
                (p, boundary[min(len(boundary) - 1, i + 1)]),
            ):
                dx, dy = b[0] - a[0], b[1] - a[1]
                length = math.hypot(dx, dy)
                if length > 1e-9:
                    normals.append((-dy / length * sign, dx / length * sign))
            nx, ny = map(sum, zip(*normals))
            length = math.hypot(nx, ny)
            if length <= 1e-9:
                raise ValueError("Shoulder boundary reverses")
            nx, ny = nx / length, ny / length
            denominator = nx * normals[0][0] + ny * normals[0][1]
            if denominator <= 0.1:
                raise ValueError("Shoulder miter unbounded")
            x, y = p[0] + nx * 0.5 / denominator, p[1] + ny * 0.5 / denominator
            a, b = sections[i][0], sections[i][-1]
            dx, dy = b[0] - a[0], b[1] - a[1]
            ratio = ((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy)
            result[i][outer] = [x, y, a[2] + ratio * (b[2] - a[2]) - 0.08]
    return result

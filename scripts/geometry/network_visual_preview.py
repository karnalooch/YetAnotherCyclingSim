"""Complete source-location markers and rejected-road visual evidence in SI units.

Markers show where source lines run; their height is ground plus a declared
visual offset, never road-deck evidence or a grade-separation solution.
"""

import hashlib
import json
import math

MARKER_WIDTH_M = 0.15
MARKER_GROUND_OFFSET_M = 0.2


def preview_fingerprint(preview):
    return hashlib.sha256(
        json.dumps(
            preview, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def validate_full_preview(preview, source_length_m):
    """Independently account for every clipped source part and diagnostic span."""
    if (
        preview.get("schema_version") != 1
        or preview.get("role") != "VISUAL_REVIEW_ONLY"
        or preview.get("road_admitted") is not False
        or preview.get("height_change_applied") is not False
        or preview.get("terrain_change_applied") is not False
    ):
        raise ValueError("Full preview authority mismatch")
    markers = preview.get("source_markers")
    rejected = preview.get("rejected_surfaces")
    if not isinstance(markers, list) or not markers or not isinstance(rejected, list):
        raise ValueError("Full preview geometry missing")
    ids = set()
    total = 0.0
    for marker in markers:
        ident = marker["id"]
        if ident in ids:
            raise ValueError("Duplicate source marker")
        ids.add(ident)
        points = marker["xy_local_m"]
        if len(points) < 2 or any(
            len(p) != 2 or not all(math.isfinite(v) for v in p) for p in points
        ):
            raise ValueError("Invalid source marker coordinates")
        ground = marker.get("ground_m")
        if (
            not isinstance(ground, list)
            or len(ground) != len(points)
            or not all(math.isfinite(v) for v in ground)
        ):
            raise ValueError("Invalid source marker ground probes")
        lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
        if min(lengths) <= 0 or max(lengths) > 2.000001:
            raise ValueError("Source marker spacing invalid")
        measured = math.fsum(lengths)
        if abs(measured - marker["length_m"]) > 1e-6:
            raise ValueError("Source marker length mismatch")
        total += measured
    if not math.isfinite(source_length_m) or abs(total - source_length_m) > 1e-5:
        raise ValueError("Incomplete full-source preview coverage")
    rejected_ids = set()
    for item in rejected:
        if item["id"] in rejected_ids or item.get("road_admitted") is not False:
            raise ValueError("Rejected preview authority/identity mismatch")
        rejected_ids.add(item["id"])
        rows = item["sections"]
        if len(rows) < 3 or any(
            len(row) != 25
            or any(len(p) != 3 or not all(math.isfinite(v) for v in p) for p in row)
            for row in rows
        ):
            raise ValueError("Invalid rejected surface coordinates")
        if not item.get("reason"):
            raise ValueError("Rejected surface reason missing")
    return {
        "status": "FULL_SOURCE_CONTEXT_REVIEW_REQUIRED",
        "source_marker_count": len(markers),
        "source_marker_length_m": total,
        "source_coverage_residual_m": total - source_length_m,
        "rejected_surface_count": len(rejected),
        "fingerprint": preview_fingerprint(preview),
        "road_admitted": False,
    }


def source_marker_mesh(points):
    """A narrow 1 cm annotation slab, not a pavement or support mesh."""
    vertices, triangles = [], []
    for a, b in zip(points, points[1:]):
        if any(len(p) != 3 or not all(math.isfinite(v) for v in p) for p in (a, b)):
            raise ValueError("Nonfinite source marker")
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length <= 0:
            raise ValueError("Degenerate source marker")
        nx, ny = -dy / length * MARKER_WIDTH_M / 2, dx / length * MARKER_WIDTH_M / 2
        start = len(vertices)
        top = [
            [p[0] + sign * nx, p[1] + sign * ny, p[2]]
            for p in (a, b)
            for sign in (-1, 1)
        ]
        vertices.extend(top + [[x, y, z - 0.01] for x, y, z in top])
        # Separate top/bottom vertices avoid cancelling normals on coincident
        # reverse-wound triangles when the native mesh recomputes vertex normals.
        faces = [(0, 1, 2), (1, 3, 2), (6, 5, 4), (6, 7, 5)]
        for u, v in ((0, 1), (1, 3), (3, 2), (2, 0)):
            faces.extend(((v, u, u + 4), (v, u + 4, v + 4)))
        triangles.extend(tuple(start + i for i in face) for face in faces)
    return vertices, triangles


def overview_camera(preview, horizontal_fov_degrees=74.0, aspect_ratio=16 / 9):
    """Fit all source markers into a top-down camera with a 10% frame margin."""
    points = [p for marker in preview["source_markers"] for p in marker["xy_local_m"]]
    ground = [v for marker in preview["source_markers"] for v in marker["ground_m"]]
    minx, maxx = min(p[0] for p in points), max(p[0] for p in points)
    miny, maxy = min(p[1] for p in points), max(p[1] for p in points)
    tangent = math.tan(math.radians(horizontal_fov_degrees) / 2)
    height = (
        max(
            (maxx - minx) / (2 * tangent),
            (maxy - miny) * aspect_ratio / (2 * tangent),
            50,
        )
        * 1.1
    )
    center = [(minx + maxx) / 2, (miny + maxy) / 2]
    return {
        "location_m": [*center, max(ground) + height],
        "target_m": [*center, min(ground)],
        "frame_margin": 1.1,
    }

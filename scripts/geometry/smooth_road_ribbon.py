"""Build the owner-visible smooth Ma-2141 asphalt ribbon.

This module deliberately does not own terrain, route or physics truth. It turns
the already BOB-inspected regularized profile candidate into a smooth transient
presentation slab. Native-facet contact evidence remains a separate mesh.
"""

from __future__ import annotations

from collections import Counter
import math
from scripts.geometry.curved_road_plan import profile_plan_valid


PAVEMENT_THICKNESS_M = 0.08
BURIAL_M = 0.04
SECTION_POINTS = 25
_EPSILON = 1e-9


def _finite(value):
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _signed_xy_area2(a, b, c):
    return (
        (b[0] - a[0]) * (c[1] - a[1])
        - (b[1] - a[1]) * (c[0] - a[0])
    )


def build_smooth_road_ribbon(profile):
    """Return a closed presentation slab from the regularized profile candidate."""
    if (
        profile.get("region_id") != "sa_calobra"
        or profile.get("status") != "REVIEW_REQUIRED"
        or not profile_plan_valid(profile)
        or profile.get("terrain_modified") is not False
        or profile.get("road_earthworks_modified") is not False
        or profile.get("earthworks_authoring_permitted") is not False
        or profile.get("authoritative_physics") is not False
        or profile.get("geographic_width_admitted") is not False
        or profile.get("road_admitted") is not False
    ):
        raise ValueError("Unadmitted profile candidate for smooth road ribbon")

    rows = profile.get("stations")
    if not isinstance(rows, list) or len(rows) < 3:
        raise ValueError("Smooth road ribbon needs ordered profile stations")

    station_values = [row.get("station_m") for row in rows]
    if (
        not all(_finite(value) for value in station_values)
        or any(
            float(right) <= float(left)
            for left, right in zip(station_values, station_values[1:])
        )
    ):
        raise ValueError("Invalid smooth road station order")

    top = []
    center_z = []
    for row in rows:
        xy = row.get("xy_local_m")
        candidate = row.get("candidate_ground_m")
        lateral = row.get("lateral_m")
        if (
            not isinstance(xy, list)
            or not isinstance(candidate, list)
            or not isinstance(lateral, list)
            or len(xy) != SECTION_POINTS
            or len(candidate) != SECTION_POINTS
            or len(lateral) != SECTION_POINTS
        ):
            raise ValueError("Smooth road cross-section contract mismatch")
        if not all(
            isinstance(point, list)
            and len(point) == 2
            and _finite(point[0])
            and _finite(point[1])
            for point in xy
        ):
            raise ValueError("Nonfinite smooth road XY")
        if not all(_finite(value) for value in candidate + lateral):
            raise ValueError("Nonfinite smooth road profile")
        if any(
            float(right) <= float(left)
            for left, right in zip(lateral, lateral[1:])
        ):
            raise ValueError("Smooth road lateral order is not increasing")

        for point, height in zip(xy, candidate):
            top.append(
                [
                    float(point[0]),
                    float(point[1]),
                    float(height) + PAVEMENT_THICKNESS_M - BURIAL_M,
                ]
            )
        center_z.append(
            float(candidate[len(candidate) // 2])
            + PAVEMENT_THICKNESS_M
            - BURIAL_M
        )

    faces = []
    for station_index in range(len(rows) - 1):
        row = station_index * SECTION_POINTS
        next_row = (station_index + 1) * SECTION_POINTS
        for lateral_index in range(SECTION_POINTS - 1):
            a = row + lateral_index
            b = a + 1
            c = next_row + lateral_index
            d = c + 1
            first = (a, b, c)
            second = (b, d, c)
            for face in (first, second):
                if _signed_xy_area2(*(top[index] for index in face)) >= -_EPSILON:
                    raise ValueError(
                        "Smooth road ribbon folded or inverted in XY"
                    )
                faces.append(face)

    n = len(top)
    bottom = [
        [x, y, z - PAVEMENT_THICKNESS_M]
        for x, y, z in top
    ]
    triangles = list(faces)
    triangles.extend((a + n, c + n, b + n) for a, b, c in faces)

    counts = Counter(
        tuple(sorted(edge))
        for a, b, c in faces
        for edge in ((a, b), (b, c), (c, a))
    )
    if any(count > 2 for count in counts.values()):
        raise ValueError("Smooth road ribbon top is nonmanifold")
    for a, b, c in faces:
        for u, v in ((a, b), (b, c), (c, a)):
            if counts[tuple(sorted((u, v)))] == 1:
                triangles.extend(((v, u, u + n), (v, u + n, v + n)))

    widths = []
    for station_index in range(len(rows)):
        first = top[station_index * SECTION_POINTS]
        last = top[(station_index + 1) * SECTION_POINTS - 1]
        widths.append(math.hypot(last[0] - first[0], last[1] - first[1]))

    second_difference_rms = 0.0
    if len(center_z) >= 3:
        second = [
            center_z[index + 1] - 2 * center_z[index] + center_z[index - 1]
            for index in range(1, len(center_z) - 1)
        ]
        second_difference_rms = math.sqrt(
            sum(value * value for value in second) / len(second)
        )

    metadata = {
        "role": "PRESENTATION_ONLY_SMOOTH_RIBBON",
        "contact_authority": False,
        "physics_authority": False,
        "road_admitted": False,
        "station_count": len(rows),
        "cross_section_point_count": SECTION_POINTS,
        "top_vertex_count": len(top),
        "top_triangle_count": len(faces),
        "min_width_m": min(widths),
        "max_width_m": max(widths),
        "center_second_difference_rms_m": second_difference_rms,
        "height_source": "BOB-inspected regularized candidate_ground_m",
    }
    return top + bottom, triangles, metadata

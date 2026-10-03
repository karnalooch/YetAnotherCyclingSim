"""Physical boundary identity, travel side, bend role and terrain role.

XY uses Unreal's horizontal X/Y frame (Y is right for a forward X tangent).
Edge indices remain stable when travel reverses; semantic roles are independent.
"""

from __future__ import annotations

import math

TERRAIN_ROLES = {"CLIFF", "MOUNTAIN", "UNKNOWN"}


def edge_roles(
    curvature_per_m, terrain_roles=("UNKNOWN", "UNKNOWN"), travel_direction=1
):
    if (
        not math.isfinite(curvature_per_m)
        or isinstance(travel_direction, bool)
        or travel_direction not in (-1, 1)
        or len(terrain_roles) != 2
        or any(role not in TERRAIN_ROLES for role in terrain_roles)
    ):
        raise ValueError("Invalid road edge role inputs")
    inner = None if abs(curvature_per_m) < 1e-4 else (1 if curvature_per_m > 0 else 0)
    return [
        {
            "edge_index": edge,
            "travel_side": ("LEFT" if edge == 0 else "RIGHT")
            if travel_direction == 1
            else ("RIGHT" if edge == 0 else "LEFT"),
            "bend_role": "STRAIGHT"
            if inner is None
            else ("INNER" if edge == inner else "OUTER"),
            "terrain_role": terrain_roles[edge],
        }
        for edge in (0, 1)
    ]


def terrain_roles_at(spans, station):
    roles = ("UNKNOWN", "UNKNOWN")
    previous_end = -math.inf
    for span in spans:
        start, end = span["start_station_m"], span["end_station_m"]
        current = span["roles"]
        if (
            not all(math.isfinite(v) for v in (start, end))
            or start < previous_end
            or start >= end
            or len(current) != 2
            or any(v not in TERRAIN_ROLES for v in current)
            or not span.get("evidence")
        ):
            raise ValueError("Ambiguous or unevidenced terrain side span")
        previous_end = end
        if start <= station < end:
            roles = tuple(current)
    return roles


def anchored_edges(anchor, tangent, width_m, anchor_edge):
    """Exact cross-section width normal to the one authoritative boundary.

    Width is horizontal, measured in the boundary's normal frame. With varying
    width the derived pavement midpoint tangent may differ from this frame.
    """
    if (
        isinstance(anchor_edge, bool)
        or anchor_edge not in (0, 1)
        or not math.isfinite(width_m)
        or not 2 <= width_m <= 12
    ):
        raise ValueError("Invalid anchor side or intended pavement width")
    if (
        len(anchor) != 2
        or len(tangent) != 2
        or not all(math.isfinite(v) for v in (*anchor, *tangent))
    ):
        raise ValueError("Nonfinite road boundary frame")
    speed = math.hypot(*tangent)
    if speed <= 1e-9:
        raise ValueError("Authoritative boundary stops")
    sign = 1 if anchor_edge == 0 else -1
    normal = [-tangent[1] / speed, tangent[0] / speed]
    derived = [anchor[k] + sign * width_m * normal[k] for k in range(2)]
    return [list(anchor), derived] if anchor_edge == 0 else [derived, list(anchor)]

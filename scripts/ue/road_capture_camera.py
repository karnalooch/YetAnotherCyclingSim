"""Pure route-local rider-camera contract for the terrain diagnostic.

A long chord across a hairpin can point behind the rider. Keep the sampled
road position and eye height fixed and use the local forward tangent instead.
This controls only proof presentation, never route or physics geometry.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def _vector(value: Sequence[float], name: str) -> tuple[float, float, float]:
    if len(value) != 3:
        raise ValueError(f"{name} must contain exactly three coordinates")
    if any(isinstance(v, bool) for v in value):
        raise ValueError(f"{name} must not contain booleans")
    result = tuple(float(v) for v in value)
    if not all(math.isfinite(v) for v in result):
        raise ValueError(f"{name} must be finite")
    return result


def rider_capture_frame(
    road_position_cm: Sequence[float],
    road_forward: Sequence[float],
    legacy_target_cm: Sequence[float],
    eye_height_cm: float,
) -> dict[str, object]:
    """Return a forward-facing frame plus the rejected chord for audit.

    Coordinates are world-space cm; forward is a direction, not an endpoint.
    No collision-derived camera lift, lateral move or terrain edit is allowed.
    The one-metre direction ray computes rotation only, not route look-ahead.
    """
    road = _vector(road_position_cm, "road_position_cm")
    forward = _vector(road_forward, "road_forward")
    legacy = _vector(legacy_target_cm, "legacy_target_cm")
    if isinstance(eye_height_cm, bool) or not math.isfinite(eye_height_cm):
        raise ValueError("eye_height_cm must be finite and positive")
    if eye_height_cm <= 0:
        raise ValueError("eye_height_cm must be finite and positive")
    length = math.hypot(*forward)
    horizontal = math.hypot(forward[0], forward[1])
    if length <= 1e-12 or horizontal <= 1e-12:
        raise ValueError("road_forward must have a nonzero horizontal direction")
    unit = tuple(v / length for v in forward)
    eye = (road[0], road[1], road[2] + eye_height_cm)
    target = tuple(eye[i] + 100.0 * unit[i] for i in range(3))
    chord = tuple(legacy[i] - eye[i] for i in range(3))
    chord_horizontal = math.hypot(chord[0], chord[1])
    if chord_horizontal <= 1e-12:
        legacy_alignment = None
        legacy_angle = None
    else:
        legacy_alignment = max(
            -1.0,
            min(
                1.0,
                (forward[0] * chord[0] + forward[1] * chord[1])
                / (horizontal * chord_horizontal),
            ),
        )
        legacy_angle = math.degrees(math.acos(legacy_alignment))
    return {
        "policy": "route_local_forward_tangent",
        "road_position_cm": list(road),
        "eye_height_cm": eye_height_cm,
        "camera_location_cm": list(eye),
        "target_cm": list(target),
        "road_forward_unit": list(unit),
        "legacy_target_cm": list(legacy),
        "legacy_chord_horizontal_alignment": legacy_alignment,
        "legacy_chord_angle_deg": legacy_angle,
        "position_adjusted_for_visibility": False,
        "route_or_terrain_modified": False,
    }

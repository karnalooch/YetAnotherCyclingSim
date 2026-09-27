"""Deterministic corner context derived from the canonical Road Physics Profile.

Stage 4B-A is intentionally policy-light. Callers provide the curvature
threshold, scan step and look-ahead distances explicitly; no hidden road-design
or grip coefficients live in this module.

Road-physics curvature follows the Unreal route geometry convention:
positive signed curvature turns toward +D (the rider's right), negative signed
curvature turns toward -D (the rider's left).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .cornering import (
    CORNER_PHASE_APEX,
    CORNER_PHASE_APPROACH,
    CORNER_PHASE_ENTRY,
    CORNER_PHASE_EXIT,
    CORNER_PHASE_OUTSIDE,
)
from .road_physics import RoadPhysicsProfile, RoadPhysicsState
from .validation import _finite, _non_negative, _positive

__all__ = [
    "CORNER_DIRECTION_STRAIGHT",
    "CORNER_DIRECTION_LEFT",
    "CORNER_DIRECTION_RIGHT",
    "CornerContextSettings",
    "CornerContext",
    "corner_context_at",
]

CORNER_DIRECTION_STRAIGHT = "straight"
CORNER_DIRECTION_LEFT = "left"
CORNER_DIRECTION_RIGHT = "right"


@dataclass(frozen=True, slots=True)
class CornerContextSettings:
    """Explicit deterministic scanning policy for route-derived corner context."""

    min_abs_curvature_per_m: float
    scan_step_m: float
    look_ahead_m: float
    approach_length_m: float

    def __post_init__(self):
        object.__setattr__(
            self,
            "min_abs_curvature_per_m",
            _positive(self.min_abs_curvature_per_m, "min_abs_curvature_per_m"),
        )
        object.__setattr__(self, "scan_step_m", _positive(self.scan_step_m, "scan_step_m"))
        object.__setattr__(
            self, "look_ahead_m", _non_negative(self.look_ahead_m, "look_ahead_m")
        )
        object.__setattr__(
            self,
            "approach_length_m",
            _positive(self.approach_length_m, "approach_length_m"),
        )


@dataclass(frozen=True, slots=True)
class CornerContext:
    """Road-derived context for one fixed-step simulation query."""

    distance_m: float
    lateral_position_m: float
    phase: str
    has_corner: bool
    corner_start_m: float
    corner_end_m: float
    distance_to_corner_start_m: float
    apex_distance_m: float
    direction: str
    signed_curvature_per_m: float
    centerline_radius_m: float
    effective_radius_m: float
    road_width_m: float
    left_margin_m: float
    right_margin_m: float
    cross_slope_angle_rad: float
    surface_id: str
    wetness: float
    roughness: float


def _is_corner(state: RoadPhysicsState, threshold: float) -> bool:
    return abs(state.horizontal_curvature_per_m) >= threshold


def _phase_at(distance: float, start: float, end: float, approach: float) -> str:
    if distance < start:
        return (
            CORNER_PHASE_APPROACH
            if distance >= max(0.0, start - approach)
            else CORNER_PHASE_OUTSIDE
        )
    length = end - start
    if length <= 0.0:
        return CORNER_PHASE_OUTSIDE
    if distance < start + 0.25 * length:
        return CORNER_PHASE_ENTRY
    if distance < start + 0.75 * length:
        return CORNER_PHASE_APEX
    if distance < end:
        return CORNER_PHASE_EXIT
    return CORNER_PHASE_OUTSIDE


def _radius_context(curvature: float, lateral: float) -> tuple[str, float, float]:
    if curvature == 0.0:
        return CORNER_DIRECTION_STRAIGHT, math.inf, math.inf

    signed_centerline_radius = 1.0 / curvature
    effective_signed_radius = signed_centerline_radius - lateral
    if not math.isfinite(effective_signed_radius) or effective_signed_radius == 0.0:
        raise ValueError(
            "lateral_position_m collapses the effective corner radius at the queried curvature"
        )

    direction = (
        CORNER_DIRECTION_RIGHT if curvature > 0.0 else CORNER_DIRECTION_LEFT
    )
    return direction, abs(signed_centerline_radius), abs(effective_signed_radius)


def corner_context_at(
    profile: RoadPhysicsProfile,
    distance_m: float,
    lateral_position_m: float,
    settings: CornerContextSettings,
) -> CornerContext:
    """Return deterministic route-derived corner context at S/D.

    The scan detects a contiguous region whose absolute horizontal curvature
    meets the caller-provided threshold. Boundaries are quantized to a
    scan_step_m grid anchored at route origin S=0. This makes a physical
    corner's detected start/end stable as the rider advances by substeps.

    No friction coefficient or tyre/grip policy is resolved here. Surface,
    wetness and roughness are passed through for the next Stage 4B/4C layer.
    """

    if not isinstance(profile, RoadPhysicsProfile):
        raise ValueError(
            f"profile must be a RoadPhysicsProfile, got {type(profile).__name__}"
        )
    if not isinstance(settings, CornerContextSettings):
        raise ValueError(
            f"settings must be a CornerContextSettings, got {type(settings).__name__}"
        )

    distance = _finite(distance_m, "distance_m")
    lateral = _finite(lateral_position_m, "lateral_position_m")
    current = profile.state_at(distance, lateral)
    threshold = settings.min_abs_curvature_per_m
    step = settings.scan_step_m
    route_end = profile.total_length_m

    # Stage 4C runtime episodes require the same physical corner to keep the
    # same interval while S advances by fixed substeps. Anchor all detection
    # probes to the route origin rather than to the current query distance.
    #
    # The grid-defined corner state at S is the state of the floor grid point.
    # A transition inside a grid cell therefore becomes active at the next
    # global scan point, which is deterministic and independent of frame/substep
    # query positions.
    grid_index = math.floor(distance / step)
    floor_probe = min(route_end, grid_index * step)
    floor_state = profile.state_at(floor_probe, lateral)
    found = _is_corner(floor_state, threshold)
    corner_start = floor_probe

    if found:
        while corner_start > 0.0:
            previous = max(0.0, corner_start - step)
            previous_state = profile.state_at(previous, lateral)
            if not _is_corner(previous_state, threshold):
                break
            corner_start = previous
            if previous == 0.0:
                break
    else:
        max_distance = min(route_end, distance + settings.look_ahead_m)
        probe_index = grid_index + 1
        while True:
            probe = probe_index * step
            if probe > route_end:
                probe = route_end
            if probe > max_distance:
                break

            probe_state = profile.state_at(probe, lateral)
            if _is_corner(probe_state, threshold):
                found = True
                corner_start = probe
                break

            if probe == route_end:
                break
            probe_index += 1

    if not found:
        left_margin = lateral - current.left_edge_m
        right_margin = current.right_edge_m - lateral
        return CornerContext(
            distance_m=distance,
            lateral_position_m=lateral,
            phase=CORNER_PHASE_OUTSIDE,
            has_corner=False,
            corner_start_m=distance,
            corner_end_m=distance,
            distance_to_corner_start_m=0.0,
            apex_distance_m=distance,
            direction=CORNER_DIRECTION_STRAIGHT,
            signed_curvature_per_m=current.horizontal_curvature_per_m,
            centerline_radius_m=math.inf,
            effective_radius_m=math.inf,
            road_width_m=current.road_width_m,
            left_margin_m=left_margin,
            right_margin_m=right_margin,
            cross_slope_angle_rad=current.cross_slope_angle_rad,
            surface_id=current.surface_id,
            wetness=current.wetness,
            roughness=current.roughness,
        )

    corner_end = corner_start
    while corner_end < route_end:
        next_probe = min(route_end, corner_end + step)
        probe_state = profile.state_at(next_probe, lateral)
        if not _is_corner(probe_state, threshold):
            corner_end = next_probe
            break
        corner_end = next_probe
        if next_probe == route_end:
            break

    if corner_end <= corner_start:
        corner_end = min(route_end, corner_start + step)
    if corner_end <= corner_start:
        raise ValueError("detected corner interval has zero length")

    focus_distance = distance if _is_corner(current, threshold) else corner_start
    focus = profile.state_at(focus_distance, lateral)
    direction, centerline_radius, effective_radius = _radius_context(
        focus.horizontal_curvature_per_m,
        lateral,
    )

    phase = _phase_at(
        distance,
        corner_start,
        corner_end,
        settings.approach_length_m,
    )
    left_margin = lateral - focus.left_edge_m
    right_margin = focus.right_edge_m - lateral

    return CornerContext(
        distance_m=distance,
        lateral_position_m=lateral,
        phase=phase,
        has_corner=True,
        corner_start_m=corner_start,
        corner_end_m=corner_end,
        distance_to_corner_start_m=max(0.0, corner_start - distance),
        apex_distance_m=corner_start + 0.5 * (corner_end - corner_start),
        direction=direction,
        signed_curvature_per_m=focus.horizontal_curvature_per_m,
        centerline_radius_m=centerline_radius,
        effective_radius_m=effective_radius,
        road_width_m=focus.road_width_m,
        left_margin_m=left_margin,
        right_margin_m=right_margin,
        cross_slope_angle_rad=focus.cross_slope_angle_rad,
        surface_id=focus.surface_id,
        wetness=focus.wetness,
        roughness=focus.roughness,
    )

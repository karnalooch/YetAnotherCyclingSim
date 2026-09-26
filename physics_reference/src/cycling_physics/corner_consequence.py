"""Geometry-derived Stage 4C-C corner consequences.

This module deliberately replaces the Stage 4A placeholder consequence
thresholds for the Stage 4C path. It consumes the real road-derived
CornerContext and the real Stage 4C CornerGripDemand.

When lateral demand exceeds the physical limit, the first consequence is to
use a larger-radius line toward the outside of the turn. Because the current
route convention changes effective radius one-for-one with lateral offset,
the required outward shift is derived directly from the required radius.

If the available outside road margin cannot provide that radius, the rider
uses all available outside margin and the remaining excess becomes a
controlled-slip speed consequence. The target speed is the minimum reduction
required to fit the maximum feasible radius at the existing lateral
acceleration limit.

No arbitrary grip thresholds or crash outcome are used here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .corner_context import (
    CORNER_DIRECTION_LEFT,
    CORNER_DIRECTION_RIGHT,
    CornerContext,
)
from .corner_grip_demand import CornerGripDemand
from .cornering import (
    CORNER_PHASE_APEX,
    CORNER_PHASE_ENTRY,
    CORNER_PHASE_EXIT,
)
from .validation import _non_negative

__all__ = [
    "CORNER_GEOMETRY_OUTCOME_CLEAN",
    "CORNER_GEOMETRY_OUTCOME_WIDE_LINE",
    "CORNER_GEOMETRY_OUTCOME_CONTROLLED_SLIP",
    "CornerGeometryConsequence",
    "resolve_corner_geometry_consequence",
]

CORNER_GEOMETRY_OUTCOME_CLEAN = "clean"
CORNER_GEOMETRY_OUTCOME_WIDE_LINE = "wide_line"
CORNER_GEOMETRY_OUTCOME_CONTROLLED_SLIP = "controlled_slip"


@dataclass(frozen=True, slots=True)
class CornerGeometryConsequence:
    """One deterministic geometry-derived consequence for an active corner."""

    outcome: str
    minimum_required_radius_m: float
    maximum_feasible_radius_m: float
    required_outward_shift_m: float
    applied_outward_shift_m: float
    line_deviation_ratio: float
    target_lateral_position_m: float
    target_speed_mps: float
    exit_speed_multiplier: float

    def __post_init__(self):
        if self.outcome not in (
            CORNER_GEOMETRY_OUTCOME_CLEAN,
            CORNER_GEOMETRY_OUTCOME_WIDE_LINE,
            CORNER_GEOMETRY_OUTCOME_CONTROLLED_SLIP,
        ):
            raise ValueError(f"unsupported corner geometry outcome {self.outcome!r}")
        for name in (
            "minimum_required_radius_m",
            "maximum_feasible_radius_m",
            "required_outward_shift_m",
            "applied_outward_shift_m",
            "line_deviation_ratio",
            "target_speed_mps",
            "exit_speed_multiplier",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative, got {value}")
        if not math.isfinite(self.target_lateral_position_m):
            raise ValueError("target_lateral_position_m must be finite")
        if self.line_deviation_ratio > 1.0:
            raise ValueError("line_deviation_ratio must not exceed 1")
        if self.exit_speed_multiplier > 1.0:
            raise ValueError("exit_speed_multiplier must not exceed 1")


def resolve_corner_geometry_consequence(
    context: CornerContext,
    demand: CornerGripDemand,
) -> CornerGeometryConsequence:
    """Resolve wide-line/slip consequences without arbitrary usage thresholds.

    Only active corner phases (entry/apex/exit) are valid. A lateral usage at
    or below 1 is clean.

    For lateral usage above 1:
      minimum_required_radius = effective_radius * lateral_usage

    The outside margin is left_margin for a right turn and right_margin for a
    left turn. Moving toward that outside edge increases the effective radius
    one-for-one under the current Road Physics Profile convention.

    If the required radius fits, the result is a wide line with unchanged
    speed. Otherwise the result is controlled slip: all available outside
    margin is consumed and target speed is reduced by

      sqrt(maximum_feasible_radius / minimum_required_radius)

    which is exactly the speed needed to bring lateral acceleration back to
    the physical limit at the widest feasible line.
    """

    if not isinstance(context, CornerContext):
        raise ValueError(
            f"context must be a CornerContext, got {type(context).__name__}"
        )
    if not isinstance(demand, CornerGripDemand):
        raise ValueError(
            f"demand must be a CornerGripDemand, got {type(demand).__name__}"
        )
    if not context.has_corner:
        raise ValueError("corner geometry consequence requires an active corner")
    if context.phase not in (CORNER_PHASE_ENTRY, CORNER_PHASE_APEX, CORNER_PHASE_EXIT):
        raise ValueError(
            "corner geometry consequence requires entry, apex or exit phase"
        )
    if (
        not math.isfinite(context.effective_radius_m)
        or context.effective_radius_m <= 0.0
    ):
        raise ValueError("context effective_radius_m must be finite and positive")
    if not math.isfinite(context.lateral_position_m):
        raise ValueError("context lateral_position_m must be finite")
    if context.direction == CORNER_DIRECTION_RIGHT:
        outside_margin = _non_negative(context.left_margin_m, "left_margin_m")
        direction_sign = -1.0
    elif context.direction == CORNER_DIRECTION_LEFT:
        outside_margin = _non_negative(context.right_margin_m, "right_margin_m")
        direction_sign = 1.0
    else:
        raise ValueError("active corner must have left or right direction")

    speed = _non_negative(demand.speed_mps, "speed_mps")
    lateral_usage = _non_negative(demand.lateral_usage, "lateral_usage")
    radius = context.effective_radius_m

    minimum_required_radius = radius * lateral_usage
    required_outward_shift = max(0.0, minimum_required_radius - radius)
    maximum_feasible_radius = radius + outside_margin

    if required_outward_shift <= 0.0:
        return CornerGeometryConsequence(
            outcome=CORNER_GEOMETRY_OUTCOME_CLEAN,
            minimum_required_radius_m=minimum_required_radius,
            maximum_feasible_radius_m=maximum_feasible_radius,
            required_outward_shift_m=0.0,
            applied_outward_shift_m=0.0,
            line_deviation_ratio=0.0,
            target_lateral_position_m=context.lateral_position_m,
            target_speed_mps=speed,
            exit_speed_multiplier=1.0,
        )

    applied_outward_shift = min(required_outward_shift, outside_margin)
    target_lateral_position = (
        context.lateral_position_m + direction_sign * applied_outward_shift
    )
    line_deviation_ratio = (
        applied_outward_shift / outside_margin if outside_margin > 0.0 else 0.0
    )

    if required_outward_shift <= outside_margin:
        return CornerGeometryConsequence(
            outcome=CORNER_GEOMETRY_OUTCOME_WIDE_LINE,
            minimum_required_radius_m=minimum_required_radius,
            maximum_feasible_radius_m=maximum_feasible_radius,
            required_outward_shift_m=required_outward_shift,
            applied_outward_shift_m=applied_outward_shift,
            line_deviation_ratio=line_deviation_ratio,
            target_lateral_position_m=target_lateral_position,
            target_speed_mps=speed,
            exit_speed_multiplier=1.0,
        )

    # This branch implies lateral_usage > 1 and therefore speed > 0 for a
    # physically derived CornerGripDemand. Keep validation fail-closed anyway.
    if minimum_required_radius <= 0.0:
        raise ValueError("minimum required radius must be positive during slip")

    exit_speed_multiplier = math.sqrt(
        maximum_feasible_radius / minimum_required_radius
    )
    target_speed = speed * exit_speed_multiplier

    return CornerGeometryConsequence(
        outcome=CORNER_GEOMETRY_OUTCOME_CONTROLLED_SLIP,
        minimum_required_radius_m=minimum_required_radius,
        maximum_feasible_radius_m=maximum_feasible_radius,
        required_outward_shift_m=required_outward_shift,
        applied_outward_shift_m=applied_outward_shift,
        line_deviation_ratio=line_deviation_ratio,
        target_lateral_position_m=target_lateral_position,
        target_speed_mps=target_speed,
        exit_speed_multiplier=exit_speed_multiplier,
    )

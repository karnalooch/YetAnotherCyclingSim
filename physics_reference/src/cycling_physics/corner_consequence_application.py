"""Authoritative Stage 4C-C3 application of geometry consequences.

The ordinary longitudinal force/braking integrator runs first. This module
then projects only the consequence that C1 physically requires:

- clean and wide-line outcomes preserve integrated forward speed/distance;
- controlled slip may only reduce speed, never increase it;
- when slip reduces the post-step speed, longitudinal distance is recomputed
  with the same trapezoidal convention used by the base integrator;
- route-local lateral position D moves toward the C1 target continuously over
  the remaining physical corner distance instead of teleporting.

The lateral projection is an MVP route-line model, not detailed steering or
front/rear tyre dynamics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .corner_consequence import (
    CORNER_GEOMETRY_OUTCOME_CONTROLLED_SLIP,
    CornerGeometryConsequence,
)
from .corner_context import CornerContext
from .model import SimulationState

__all__ = [
    "CornerConsequenceApplication",
    "apply_corner_geometry_consequence",
]


@dataclass(frozen=True, slots=True)
class CornerConsequenceApplication:
    """One deterministic post-integrator C3 consequence application."""

    state: SimulationState
    applied_speed_loss_mps: float
    applied_lateral_shift_m: float


def apply_corner_geometry_consequence(
    pre_step_state: SimulationState,
    integrated_state: SimulationState,
    context: CornerContext,
    consequence: CornerGeometryConsequence,
) -> CornerConsequenceApplication:
    """Project one C1 consequence onto authoritative route state.

    context and consequence must have been resolved from pre_step_state.
    The function is deterministic and has no rendering/frame-time inputs.
    """

    if not isinstance(pre_step_state, SimulationState):
        raise ValueError(
            "pre_step_state must be a SimulationState, "
            f"got {type(pre_step_state).__name__}"
        )
    if not isinstance(integrated_state, SimulationState):
        raise ValueError(
            "integrated_state must be a SimulationState, "
            f"got {type(integrated_state).__name__}"
        )
    if not isinstance(context, CornerContext):
        raise ValueError(
            f"context must be a CornerContext, got {type(context).__name__}"
        )
    if not isinstance(consequence, CornerGeometryConsequence):
        raise ValueError(
            "consequence must be a CornerGeometryConsequence, "
            f"got {type(consequence).__name__}"
        )
    if not context.has_corner:
        raise ValueError("consequence application requires an active corner")
    if context.lateral_position_m != pre_step_state.lateral_position_m:
        raise ValueError(
            "context lateral_position_m must match authoritative pre-step D"
        )
    if integrated_state.elapsed_time_s <= pre_step_state.elapsed_time_s:
        raise ValueError("integrated elapsed time must advance")
    if integrated_state.distance_m < pre_step_state.distance_m:
        raise ValueError("integrated distance must not move backwards")
    if context.corner_end_m <= pre_step_state.distance_m:
        raise ValueError("corner_end_m must be ahead of the pre-step distance")

    left_edge_m = context.lateral_position_m - context.left_margin_m
    right_edge_m = context.lateral_position_m + context.right_margin_m
    target_d = consequence.target_lateral_position_m
    if not math.isfinite(left_edge_m) or not math.isfinite(right_edge_m):
        raise ValueError("derived road edges must be finite")
    if left_edge_m > right_edge_m:
        raise ValueError("derived road edges are inverted")
    if target_d < left_edge_m or target_d > right_edge_m:
        raise ValueError("target_lateral_position_m lies outside road bounds")

    applied_speed = integrated_state.speed_mps
    projected_distance = integrated_state.distance_m

    if consequence.outcome == CORNER_GEOMETRY_OUTCOME_CONTROLLED_SLIP:
        applied_speed = min(
            integrated_state.speed_mps,
            consequence.target_speed_mps,
        )
        if applied_speed < integrated_state.speed_mps:
            dt_s = (
                integrated_state.elapsed_time_s
                - pre_step_state.elapsed_time_s
            )
            longitudinal_delta_m = (
                0.5
                * (pre_step_state.speed_mps + applied_speed)
                * dt_s
            )
            projected_distance = (
                pre_step_state.distance_m + longitudinal_delta_m
            )

    longitudinal_step_m = projected_distance - pre_step_state.distance_m
    if longitudinal_step_m < 0.0 or not math.isfinite(longitudinal_step_m):
        raise ValueError("projected longitudinal step must be finite and non-negative")

    remaining_corner_m = context.corner_end_m - pre_step_state.distance_m
    if longitudinal_step_m <= 0.0:
        alpha = 0.0
    else:
        remaining_transition_m = max(
            remaining_corner_m,
            longitudinal_step_m,
        )
        alpha = min(1.0, longitudinal_step_m / remaining_transition_m)

    next_d = pre_step_state.lateral_position_m + alpha * (
        target_d - pre_step_state.lateral_position_m
    )
    if next_d < left_edge_m or next_d > right_edge_m:
        raise ValueError("projected lateral position lies outside road bounds")

    candidate = SimulationState(
        speed_mps=applied_speed,
        distance_m=projected_distance,
        elapsed_time_s=integrated_state.elapsed_time_s,
        lateral_position_m=next_d,
    )
    return CornerConsequenceApplication(
        state=candidate,
        applied_speed_loss_mps=integrated_state.speed_mps - applied_speed,
        applied_lateral_shift_m=next_d - pre_step_state.lateral_position_m,
    )

"""Bridge Stage 4B corner limits into the Stage 4C shared grip budget.

Stage 4C-B2 interprets the explicit rider brake command as normalized
longitudinal grip usage and derives normalized lateral usage from the actual
cornering acceleration demand:

    lateral_acceleration = speed**2 / effective_radius
    lateral_usage = lateral_acceleration / lateral_acceleration_limit

The two normalized demands then share the Stage 4C-A unit friction circle.

This layer still does not apply braking force to forward speed. That force
integration remains a separate fixed-step step so no brake-hardware constant
or tyre-force model is smuggled into the demand contract.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .corner_context import CornerContext
from .corner_limit import CornerLateralLimit
from .grip_budget import SharedGripBudget, shared_grip_budget
from .validation import _closed_unit_interval, _non_negative

__all__ = ["CornerGripDemand", "corner_grip_demand"]


@dataclass(frozen=True, slots=True)
class CornerGripDemand:
    speed_mps: float
    lateral_acceleration_demand_mps2: float
    longitudinal_usage: float
    lateral_usage: float
    budget: SharedGripBudget


def corner_grip_demand(
    context: CornerContext,
    lateral_limit: CornerLateralLimit,
    speed_mps: float,
    brake_ratio: float,
) -> CornerGripDemand:
    """Resolve normalized longitudinal+lateral grip demand for one corner state."""

    if not isinstance(context, CornerContext):
        raise ValueError(
            f"context must be a CornerContext, got {type(context).__name__}"
        )
    if not isinstance(lateral_limit, CornerLateralLimit):
        raise ValueError(
            "lateral_limit must be a CornerLateralLimit, "
            f"got {type(lateral_limit).__name__}"
        )
    if not context.has_corner:
        raise ValueError("corner grip demand requires a context with a corner")
    if not math.isfinite(context.effective_radius_m) or context.effective_radius_m <= 0.0:
        raise ValueError(
            "context effective_radius_m must be finite and greater than zero"
        )
    if (
        not math.isfinite(lateral_limit.lateral_acceleration_limit_mps2)
        or lateral_limit.lateral_acceleration_limit_mps2 <= 0.0
    ):
        raise ValueError(
            "lateral_limit lateral_acceleration_limit_mps2 must be finite and positive"
        )

    speed = _non_negative(speed_mps, "speed_mps")
    brake = _closed_unit_interval(brake_ratio, "brake_ratio")

    if lateral_limit.surface_id != context.surface_id:
        raise ValueError("lateral_limit surface_id does not match corner context")
    if lateral_limit.wetness != context.wetness:
        raise ValueError("lateral_limit wetness does not match corner context")

    turn_sign = 1.0 if context.signed_curvature_per_m > 0.0 else -1.0
    expected_support_angle = -turn_sign * context.cross_slope_angle_rad
    if not math.isclose(
        lateral_limit.bank_support_angle_rad,
        expected_support_angle,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("lateral_limit bank support angle does not match corner context")

    lateral_acceleration = speed * speed / context.effective_radius_m
    lateral_usage = (
        lateral_acceleration / lateral_limit.lateral_acceleration_limit_mps2
    )
    budget = shared_grip_budget(brake, lateral_usage)

    return CornerGripDemand(
        speed_mps=speed,
        lateral_acceleration_demand_mps2=lateral_acceleration,
        longitudinal_usage=brake,
        lateral_usage=lateral_usage,
        budget=budget,
    )

"""Shared longitudinal + lateral grip budget for Stage 4C-A.

This module is deliberately input-source agnostic. It consumes normalized
axis usage fractions:
- longitudinal_usage: absolute longitudinal tyre-force demand / available
  longitudinal grip;
- lateral_usage: absolute lateral tyre-force demand / available lateral grip.

The MVP kernel uses a unit friction circle:

    combined_usage = sqrt(longitudinal_usage**2 + lateral_usage**2)

A result <= 1 is inside the shared budget; > 1 exceeds it. No braking control,
force split, tyre coefficient, safety factor or consequence policy is hidden
here. A later 4C-B layer maps actual fixed-step braking/deceleration and the
4B lateral limit into these normalized demands.

The function is stateless and can be evaluated for a simplified whole-bike
model or independently per tyre/axle in a future split model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .validation import _non_negative

__all__ = ["SharedGripBudget", "shared_grip_budget"]


@dataclass(frozen=True, slots=True)
class SharedGripBudget:
    longitudinal_usage: float
    lateral_usage: float
    combined_usage: float
    remaining_longitudinal_capacity: float
    remaining_lateral_capacity: float
    exceeded: bool


def shared_grip_budget(
    longitudinal_usage: float,
    lateral_usage: float,
) -> SharedGripBudget:
    """Resolve a deterministic unit friction-circle budget.

    Inputs are non-negative normalized usage fractions. They are intentionally
    not clamped: values above 1 remain observable and make the budget exceed.

    remaining_longitudinal_capacity is the maximum normalized longitudinal
    usage still compatible with the current lateral usage; the analogous
    lateral value is derived from the current longitudinal usage.
    """

    longitudinal = _non_negative(longitudinal_usage, "longitudinal_usage")
    lateral = _non_negative(lateral_usage, "lateral_usage")

    combined = math.hypot(longitudinal, lateral)
    remaining_longitudinal = math.sqrt(max(0.0, 1.0 - lateral * lateral))
    remaining_lateral = math.sqrt(max(0.0, 1.0 - longitudinal * longitudinal))

    return SharedGripBudget(
        longitudinal_usage=longitudinal,
        lateral_usage=lateral,
        combined_usage=combined,
        remaining_longitudinal_capacity=remaining_longitudinal,
        remaining_lateral_capacity=remaining_lateral,
        exceeded=combined > 1.0,
    )

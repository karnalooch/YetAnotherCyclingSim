"""Deterministic tyre-limited braking force resolver for Stage 4C-B3a.

This layer converts the explicit normalized brake command into a physical
longitudinal tyre force without introducing a hardware-specific "maximum
brake force" constant.

Standalone longitudinal capacity is derived from the caller-owned effective
tyre-road friction coefficient and the static gravity-normal load of the road
surface:

    normal_load = mass * g * cos(road_angle) * cos(cross_slope)
    longitudinal_force_capacity = mu_effective * normal_load

The Stage 4C-A shared budget limits how much of that longitudinal capacity
remains after lateral demand. If a rider requests more braking than remains,
the applied no-slip force is capped while the requested shared budget stays
observable as exceeded.

Dynamic load transfer, front/rear split, wheel lock, ABS and tyre relaxation
are deliberately outside the MVP resolver.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .grip_budget import SharedGripBudget, shared_grip_budget
from .model import STANDARD_GRAVITY_MPS2, RiderParameters, road_angle_rad
from .validation import _closed_unit_interval, _finite, _non_negative, _positive

__all__ = ["BrakingForceDemand", "braking_force_demand"]


@dataclass(frozen=True, slots=True)
class BrakingForceDemand:
    brake_ratio_requested: float
    lateral_usage: float
    requested_budget: SharedGripBudget
    applied_longitudinal_usage: float
    saturated_by_shared_budget: bool
    effective_friction_coefficient: float
    static_normal_load_n: float
    standalone_longitudinal_force_capacity_n: float
    applied_brake_force_n: float
    applied_brake_acceleration_mps2: float


def braking_force_demand(
    rider: RiderParameters,
    grade_decimal: float,
    cross_slope_angle_rad: float,
    effective_friction_coefficient: float,
    brake_ratio: float,
    lateral_usage: float,
) -> BrakingForceDemand:
    """Resolve no-slip longitudinal braking force under the shared grip budget."""

    if not isinstance(rider, RiderParameters):
        raise ValueError(
            f"rider must be RiderParameters, got {type(rider).__name__}"
        )

    grade = _finite(grade_decimal, "grade_decimal")
    cross_slope = _finite(cross_slope_angle_rad, "cross_slope_angle_rad")
    if not -0.5 * math.pi < cross_slope < 0.5 * math.pi:
        raise ValueError(
            "cross_slope_angle_rad must lie strictly inside (-pi/2, pi/2)"
        )

    friction = _positive(
        effective_friction_coefficient,
        "effective_friction_coefficient",
    )
    brake = _closed_unit_interval(brake_ratio, "brake_ratio")
    lateral = _non_negative(lateral_usage, "lateral_usage")

    budget = shared_grip_budget(brake, lateral)
    applied_usage = min(brake, budget.remaining_longitudinal_capacity)

    longitudinal_angle = road_angle_rad(grade)
    normal_load = (
        rider.total_mass_kg
        * STANDARD_GRAVITY_MPS2
        * math.cos(longitudinal_angle)
        * math.cos(cross_slope)
    )
    if not math.isfinite(normal_load) or normal_load <= 0.0:
        raise ValueError("derived static normal load must be finite and positive")

    force_capacity = friction * normal_load
    if not math.isfinite(force_capacity) or force_capacity <= 0.0:
        raise ValueError(
            "derived standalone longitudinal force capacity must be finite and positive"
        )

    brake_force = applied_usage * force_capacity
    brake_acceleration = brake_force / rider.total_mass_kg

    return BrakingForceDemand(
        brake_ratio_requested=brake,
        lateral_usage=lateral,
        requested_budget=budget,
        applied_longitudinal_usage=applied_usage,
        saturated_by_shared_budget=applied_usage < brake,
        effective_friction_coefficient=friction,
        static_normal_load_n=normal_load,
        standalone_longitudinal_force_capacity_n=force_capacity,
        applied_brake_force_n=brake_force,
        applied_brake_acceleration_mps2=brake_acceleration,
    )

"""Per-fixed-step corner + braking orchestration for Stage 4C-B3c.

This module composes the already-reviewed road, corner, surface-grip, shared
friction-budget and braking-force kernels. It does not introduce another tyre
coefficient or a hardware brake-force limit.

A look-ahead corner may describe road ahead of the rider. Longitudinal braking
capacity therefore always uses the current RoadPhysicsState under the tyres.
Lateral grip demand is consumed only while the rider is physically in entry,
apex or exit; approach metadata is guidance, not lateral tyre demand.
"""

from __future__ import annotations

from dataclasses import dataclass

from .braking import BrakingForceDemand, braking_force_demand
from .corner_context import CornerContext, CornerContextSettings, corner_context_at
from .corner_grip_demand import CornerGripDemand, corner_grip_demand
from .corner_limit import CornerLateralLimit, corner_lateral_limit
from .cornering import (
    CORNER_PHASE_APEX,
    CORNER_PHASE_ENTRY,
    CORNER_PHASE_EXIT,
    effective_friction_coefficient,
)
from .grip_policy import SurfaceGripPolicy
from .model import (
    Environment,
    RiderInput,
    RiderParameters,
    SimulationState,
    step_simulation_with_brake_force,
)
from .road_physics import RoadPhysicsProfile, RoadPhysicsState

__all__ = [
    "CornerBrakingStepResolution",
    "CornerBrakingStepResult",
    "resolve_corner_braking_step",
    "step_simulation_with_corner_braking",
]


_ACTIVE_LATERAL_PHASES = {
    CORNER_PHASE_ENTRY,
    CORNER_PHASE_APEX,
    CORNER_PHASE_EXIT,
}


@dataclass(frozen=True, slots=True)
class CornerBrakingStepResolution:
    """Resolved tyre/grip state for one authoritative fixed substep."""

    current_road_state: RoadPhysicsState
    corner_context: CornerContext
    lateral_limit: CornerLateralLimit | None
    grip_demand: CornerGripDemand | None
    braking_force_demand: BrakingForceDemand

    @property
    def has_active_lateral_demand(self) -> bool:
        return self.grip_demand is not None


@dataclass(frozen=True, slots=True)
class CornerBrakingStepResult:
    """Simulation state plus the B3c resolution that produced it."""

    state: SimulationState
    resolution: CornerBrakingStepResolution


def resolve_corner_braking_step(
    road_profile: RoadPhysicsProfile,
    corner_settings: CornerContextSettings,
    grip_policy: SurfaceGripPolicy,
    base_friction_coefficient: float,
    lateral_position_m: float,
    rider: RiderParameters,
    rider_input: RiderInput,
    state: SimulationState,
) -> CornerBrakingStepResolution:
    """Resolve shared corner/braking grip for one pre-step state.

    Current surface, wetness, grade and cross-slope come from the current
    RoadPhysicsState at the rider's S/D. A look-ahead CornerContext may point
    at a future corner, but it never changes current longitudinal tyre
    capacity.

    Lateral usage is resolved only in entry/apex/exit. During approach the
    corner remains visible to guidance while braking retains the full
    longitudinal budget available on the current road.
    """

    if not isinstance(road_profile, RoadPhysicsProfile):
        raise ValueError(
            f"road_profile must be RoadPhysicsProfile, got "
            f"{type(road_profile).__name__}"
        )
    if not isinstance(corner_settings, CornerContextSettings):
        raise ValueError(
            f"corner_settings must be CornerContextSettings, got "
            f"{type(corner_settings).__name__}"
        )
    if not isinstance(grip_policy, SurfaceGripPolicy):
        raise ValueError(
            f"grip_policy must be SurfaceGripPolicy, got "
            f"{type(grip_policy).__name__}"
        )
    if not isinstance(rider, RiderParameters):
        raise ValueError(f"rider must be RiderParameters, got {type(rider).__name__}")
    if not isinstance(rider_input, RiderInput):
        raise ValueError(
            f"rider_input must be RiderInput, got {type(rider_input).__name__}"
        )
    if not isinstance(state, SimulationState):
        raise ValueError(
            f"state must be SimulationState, got {type(state).__name__}"
        )

    current_road = road_profile.state_at(state.distance_m, lateral_position_m)
    context = corner_context_at(
        road_profile,
        state.distance_m,
        lateral_position_m,
        corner_settings,
    )

    current_surface_grip = grip_policy.resolve(
        current_road.surface_id,
        current_road.wetness,
    )
    current_effective_friction = effective_friction_coefficient(
        base_friction_coefficient,
        current_surface_grip.grip_multiplier,
    )

    lateral_limit = None
    grip_demand = None
    lateral_usage = 0.0

    if context.has_corner and context.phase in _ACTIVE_LATERAL_PHASES:
        lateral_limit = corner_lateral_limit(
            context,
            grip_policy,
            base_friction_coefficient,
        )
        grip_demand = corner_grip_demand(
            context,
            lateral_limit,
            state.speed_mps,
            rider_input.brake_ratio,
        )
        lateral_usage = grip_demand.lateral_usage

    brake_force = braking_force_demand(
        rider,
        grade_decimal=current_road.grade_decimal,
        cross_slope_angle_rad=current_road.cross_slope_angle_rad,
        effective_friction_coefficient=current_effective_friction,
        brake_ratio=rider_input.brake_ratio,
        lateral_usage=lateral_usage,
    )

    return CornerBrakingStepResolution(
        current_road_state=current_road,
        corner_context=context,
        lateral_limit=lateral_limit,
        grip_demand=grip_demand,
        braking_force_demand=brake_force,
    )


def step_simulation_with_corner_braking(
    road_profile: RoadPhysicsProfile,
    corner_settings: CornerContextSettings,
    grip_policy: SurfaceGripPolicy,
    base_friction_coefficient: float,
    lateral_position_m: float,
    rider: RiderParameters,
    environment: Environment,
    rider_input: RiderInput,
    state: SimulationState,
    dt_s: float,
) -> CornerBrakingStepResult:
    """Resolve B3c grip and advance one deterministic simulation substep."""

    resolution = resolve_corner_braking_step(
        road_profile,
        corner_settings,
        grip_policy,
        base_friction_coefficient,
        lateral_position_m,
        rider,
        rider_input,
        state,
    )
    next_state = step_simulation_with_brake_force(
        rider,
        environment,
        rider_input,
        state,
        dt_s,
        resolution.braking_force_demand.applied_brake_force_n,
    )
    return CornerBrakingStepResult(
        state=next_state,
        resolution=resolution,
    )

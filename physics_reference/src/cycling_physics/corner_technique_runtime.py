"""Stage 4C-C3 runtime collection for route-derived technique scoring.

The tracker is an immutable value object so a fixed-step runner can stage all
episode changes locally and commit them transactionally only after the whole
advance succeeds.

A technique episode starts when the real CornerContext first exposes one of
Approach/Entry/Apex/Exit for a corner interval. Every fixed substep records
the power/cadence actually consumed by that substep. Physical C1 consequences
are aggregated conservatively as maximum line deviation and minimum retained
speed.

When the authoritative post-step distance reaches the corner end, a complete
episode is finalized through the reviewed Stage 4C-C2 scoring API. Truncated
episodes or zero Approach baselines are skipped deterministically instead of
failing the physics simulation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .corner_consequence import (
    CORNER_GEOMETRY_OUTCOME_CLEAN,
    CORNER_GEOMETRY_OUTCOME_CONTROLLED_SLIP,
    CORNER_GEOMETRY_OUTCOME_WIDE_LINE,
    CornerGeometryConsequence,
)
from .corner_context import CornerContext
from .corner_technique import (
    RouteCornerTechniqueObservation,
    RouteCornerTechniqueScore,
    score_route_corner_technique,
    summarize_route_corner_technique,
)
from .cornering import (
    CORNER_PHASE_APEX,
    CORNER_PHASE_APPROACH,
    CORNER_PHASE_ENTRY,
    CORNER_PHASE_EXIT,
)
from .model import RiderInput, SimulationState

__all__ = [
    "CompletedRouteCornerTechniqueScore",
    "CornerTechniqueRuntimeState",
    "observe_corner_technique_step",
]

_SCORABLE_PHASES = (
    CORNER_PHASE_APPROACH,
    CORNER_PHASE_ENTRY,
    CORNER_PHASE_APEX,
    CORNER_PHASE_EXIT,
)


@dataclass(frozen=True, slots=True)
class CompletedRouteCornerTechniqueScore:
    """One finalized route-corner score with its deterministic route interval."""

    corner_start_m: float
    corner_end_m: float
    score: RouteCornerTechniqueScore

    def __post_init__(self):
        if not math.isfinite(self.corner_start_m) or self.corner_start_m < 0.0:
            raise ValueError("corner_start_m must be finite and non-negative")
        if not math.isfinite(self.corner_end_m) or self.corner_end_m <= self.corner_start_m:
            raise ValueError("corner_end_m must be finite and greater than corner_start_m")
        if not isinstance(self.score, RouteCornerTechniqueScore):
            raise ValueError("score must be a RouteCornerTechniqueScore")


@dataclass(frozen=True, slots=True)
class CornerTechniqueRuntimeState:
    """Transactional fixed-step technique episode state."""

    active_corner_start_m: float | None = None
    active_corner_end_m: float | None = None
    observations: tuple[RouteCornerTechniqueObservation, ...] = ()
    max_line_deviation_ratio: float = 0.0
    min_exit_speed_multiplier: float = 1.0
    completed_scores: tuple[CompletedRouteCornerTechniqueScore, ...] = ()
    skipped_episode_count: int = 0

    def __post_init__(self):
        active = self.active_corner_start_m is not None
        if active != (self.active_corner_end_m is not None):
            raise ValueError("active corner start/end must both be set or both be None")
        if active:
            if (
                not math.isfinite(self.active_corner_start_m)
                or self.active_corner_start_m < 0.0
            ):
                raise ValueError("active_corner_start_m must be finite and non-negative")
            if (
                not math.isfinite(self.active_corner_end_m)
                or self.active_corner_end_m <= self.active_corner_start_m
            ):
                raise ValueError(
                    "active_corner_end_m must be finite and greater than start"
                )
        if not 0.0 <= self.max_line_deviation_ratio <= 1.0:
            raise ValueError("max_line_deviation_ratio must lie in [0, 1]")
        if not 0.0 <= self.min_exit_speed_multiplier <= 1.0:
            raise ValueError("min_exit_speed_multiplier must lie in [0, 1]")
        if isinstance(self.skipped_episode_count, bool) or self.skipped_episode_count < 0:
            raise ValueError("skipped_episode_count must be a non-negative integer")


def _aggregate_consequence(
    max_line_deviation_ratio: float,
    min_exit_speed_multiplier: float,
) -> CornerGeometryConsequence:
    if min_exit_speed_multiplier < 1.0:
        outcome = CORNER_GEOMETRY_OUTCOME_CONTROLLED_SLIP
    elif max_line_deviation_ratio > 0.0:
        outcome = CORNER_GEOMETRY_OUTCOME_WIDE_LINE
    else:
        outcome = CORNER_GEOMETRY_OUTCOME_CLEAN

    # Stage 4C-C2 consumes only line_deviation_ratio and
    # exit_speed_multiplier. The remaining fields are explicit neutral
    # placeholders rather than re-deriving fake geometry.
    return CornerGeometryConsequence(
        outcome=outcome,
        minimum_required_radius_m=0.0,
        maximum_feasible_radius_m=0.0,
        required_outward_shift_m=0.0,
        applied_outward_shift_m=0.0,
        line_deviation_ratio=max_line_deviation_ratio,
        target_lateral_position_m=0.0,
        target_speed_mps=0.0,
        exit_speed_multiplier=min_exit_speed_multiplier,
    )


def _has_all_phases(
    observations: tuple[RouteCornerTechniqueObservation, ...],
) -> bool:
    present = {observation.phase for observation in observations}
    return all(phase in present for phase in _SCORABLE_PHASES)


def _finalize_episode(
    state: CornerTechniqueRuntimeState,
) -> CornerTechniqueRuntimeState:
    observations = state.observations
    completed = state.completed_scores
    skipped = state.skipped_episode_count

    if not _has_all_phases(observations):
        skipped += 1
    else:
        summary = summarize_route_corner_technique(observations)
        if summary.approach_power_w <= 0.0 or summary.approach_cadence_rpm <= 0.0:
            skipped += 1
        else:
            aggregate = _aggregate_consequence(
                state.max_line_deviation_ratio,
                state.min_exit_speed_multiplier,
            )
            score = score_route_corner_technique(summary, aggregate)
            completed = completed + (
                CompletedRouteCornerTechniqueScore(
                    corner_start_m=state.active_corner_start_m,
                    corner_end_m=state.active_corner_end_m,
                    score=score,
                ),
            )

    return CornerTechniqueRuntimeState(
        completed_scores=completed,
        skipped_episode_count=skipped,
    )


def observe_corner_technique_step(
    runtime_state: CornerTechniqueRuntimeState,
    context: CornerContext,
    rider_input: RiderInput,
    consequence: CornerGeometryConsequence | None,
    post_step_state: SimulationState,
) -> CornerTechniqueRuntimeState:
    """Observe one successfully integrated fixed substep.

    The supplied context is the pre-step route-derived context and
    post_step_state is the authoritative state after C3 consequence
    application.
    """

    if not isinstance(runtime_state, CornerTechniqueRuntimeState):
        raise ValueError("runtime_state must be a CornerTechniqueRuntimeState")
    if not isinstance(context, CornerContext):
        raise ValueError("context must be a CornerContext")
    if not isinstance(rider_input, RiderInput):
        raise ValueError("rider_input must be a RiderInput")
    if consequence is not None and not isinstance(consequence, CornerGeometryConsequence):
        raise ValueError("consequence must be a CornerGeometryConsequence or None")
    if not isinstance(post_step_state, SimulationState):
        raise ValueError("post_step_state must be a SimulationState")

    if not context.has_corner or context.phase not in _SCORABLE_PHASES:
        if (
            runtime_state.active_corner_end_m is not None
            and post_step_state.distance_m >= runtime_state.active_corner_end_m
        ):
            return _finalize_episode(runtime_state)
        return runtime_state

    if (
        not math.isfinite(context.corner_start_m)
        or context.corner_start_m < 0.0
        or not math.isfinite(context.corner_end_m)
        or context.corner_end_m <= context.corner_start_m
    ):
        raise ValueError("corner context interval must be finite and ordered")

    state = runtime_state
    if state.active_corner_start_m is None:
        state = CornerTechniqueRuntimeState(
            active_corner_start_m=context.corner_start_m,
            active_corner_end_m=context.corner_end_m,
            observations=(),
            max_line_deviation_ratio=0.0,
            min_exit_speed_multiplier=1.0,
            completed_scores=state.completed_scores,
            skipped_episode_count=state.skipped_episode_count,
        )
    elif (
        context.corner_start_m != state.active_corner_start_m
        or context.corner_end_m != state.active_corner_end_m
    ):
        raise ValueError(
            "corner context changed interval before active technique episode completed"
        )

    observations = state.observations + (
        RouteCornerTechniqueObservation(
            phase=context.phase,
            power_w=rider_input.power_w,
            cadence_rpm=rider_input.cadence_rpm,
        ),
    )
    max_line = state.max_line_deviation_ratio
    min_speed = state.min_exit_speed_multiplier
    if consequence is not None:
        max_line = max(max_line, consequence.line_deviation_ratio)
        min_speed = min(min_speed, consequence.exit_speed_multiplier)

    state = CornerTechniqueRuntimeState(
        active_corner_start_m=state.active_corner_start_m,
        active_corner_end_m=state.active_corner_end_m,
        observations=observations,
        max_line_deviation_ratio=max_line,
        min_exit_speed_multiplier=min_speed,
        completed_scores=state.completed_scores,
        skipped_episode_count=state.skipped_episode_count,
    )

    if post_step_state.distance_m >= state.active_corner_end_m:
        return _finalize_episode(state)
    return state

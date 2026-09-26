"""Stage 4C-C2 route-derived power/cadence technique scoring.

This module is the authoritative Stage 4C MVP technique-score path. It keeps
the Stage 4A ratio/threshold assessment intact for regression parity, but does
not reuse those hard-coded score thresholds.

Observations are tagged with the real route-derived CornerContext phase.
Approach averages are the rider's reference effort. Entry and apex are scored
continuously toward released effort; exit is scored continuously toward
recovered approach effort. The geometry-derived Stage 4C-C1 consequence adds
line-retention and speed-retention components.

All eight components are explicit, continuous and equally weighted in the
arithmetic mean. This score never changes physics state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .corner_consequence import CornerGeometryConsequence
from .cornering import (
    CORNER_PHASE_APEX,
    CORNER_PHASE_APPROACH,
    CORNER_PHASE_ENTRY,
    CORNER_PHASE_EXIT,
)
from .validation import _non_negative

__all__ = [
    "RouteCornerTechniqueObservation",
    "RouteCornerTechniqueSummary",
    "RouteCornerTechniqueScore",
    "summarize_route_corner_technique",
    "score_route_corner_technique",
]

_SCORABLE_PHASES = (
    CORNER_PHASE_APPROACH,
    CORNER_PHASE_ENTRY,
    CORNER_PHASE_APEX,
    CORNER_PHASE_EXIT,
)


@dataclass(frozen=True, slots=True)
class RouteCornerTechniqueObservation:
    """One power/cadence observation tagged with a route-derived corner phase."""

    phase: str
    power_w: float
    cadence_rpm: float

    def __post_init__(self):
        if self.phase not in _SCORABLE_PHASES:
            raise ValueError(
                "phase must be approach, entry, apex or exit, "
                f"got {self.phase!r}"
            )
        object.__setattr__(self, "power_w", _non_negative(self.power_w, "power_w"))
        object.__setattr__(
            self,
            "cadence_rpm",
            _non_negative(self.cadence_rpm, "cadence_rpm"),
        )


@dataclass(frozen=True, slots=True)
class RouteCornerTechniqueSummary:
    """Phase-mean rider effort from the real Stage 4B/4C corner context."""

    approach_power_w: float
    entry_power_w: float
    apex_power_w: float
    exit_power_w: float
    approach_cadence_rpm: float
    entry_cadence_rpm: float
    apex_cadence_rpm: float
    exit_cadence_rpm: float

    def __post_init__(self):
        for name in (
            "approach_power_w",
            "entry_power_w",
            "apex_power_w",
            "exit_power_w",
            "approach_cadence_rpm",
            "entry_cadence_rpm",
            "apex_cadence_rpm",
            "exit_cadence_rpm",
        ):
            object.__setattr__(
                self,
                name,
                _non_negative(getattr(self, name), name),
            )


@dataclass(frozen=True, slots=True)
class RouteCornerTechniqueScore:
    """Explicit continuous Stage 4C-C2 technique score components."""

    score: float
    entry_power_release_score: float
    apex_power_release_score: float
    exit_power_recovery_score: float
    entry_cadence_release_score: float
    apex_cadence_release_score: float
    exit_cadence_recovery_score: float
    line_retention_score: float
    speed_retention_score: float

    def __post_init__(self):
        for name in (
            "score",
            "entry_power_release_score",
            "apex_power_release_score",
            "exit_power_recovery_score",
            "entry_cadence_release_score",
            "apex_cadence_release_score",
            "exit_cadence_recovery_score",
            "line_retention_score",
            "speed_retention_score",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0.0 <= value <= 100.0:
                raise ValueError(f"{name} must be finite and lie in [0, 100]")


def summarize_route_corner_technique(
    observations: tuple[RouteCornerTechniqueObservation, ...],
) -> RouteCornerTechniqueSummary:
    """Average power and cadence for each real route-derived corner phase."""

    if not isinstance(observations, tuple):
        raise ValueError(
            f"observations must be a tuple, got {type(observations).__name__}"
        )
    if not observations:
        raise ValueError("observations must not be empty")

    power = {phase: [] for phase in _SCORABLE_PHASES}
    cadence = {phase: [] for phase in _SCORABLE_PHASES}

    for index, observation in enumerate(observations):
        if not isinstance(observation, RouteCornerTechniqueObservation):
            raise ValueError(
                f"observations[{index}] must be a RouteCornerTechniqueObservation, "
                f"got {type(observation).__name__}"
            )
        power[observation.phase].append(observation.power_w)
        cadence[observation.phase].append(observation.cadence_rpm)

    missing = [phase for phase in _SCORABLE_PHASES if not power[phase]]
    if missing:
        raise ValueError(
            "missing observations for corner phase(s): " + ", ".join(missing)
        )

    def mean(values: list[float]) -> float:
        return sum(values) / len(values)

    return RouteCornerTechniqueSummary(
        approach_power_w=mean(power[CORNER_PHASE_APPROACH]),
        entry_power_w=mean(power[CORNER_PHASE_ENTRY]),
        apex_power_w=mean(power[CORNER_PHASE_APEX]),
        exit_power_w=mean(power[CORNER_PHASE_EXIT]),
        approach_cadence_rpm=mean(cadence[CORNER_PHASE_APPROACH]),
        entry_cadence_rpm=mean(cadence[CORNER_PHASE_ENTRY]),
        apex_cadence_rpm=mean(cadence[CORNER_PHASE_APEX]),
        exit_cadence_rpm=mean(cadence[CORNER_PHASE_EXIT]),
    )


def _release_score(value: float, baseline: float) -> float:
    ratio = value / baseline
    return 100.0 * (1.0 - min(1.0, max(0.0, ratio)))


def _recovery_score(value: float, baseline: float) -> float:
    ratio = value / baseline
    return 100.0 * min(1.0, max(0.0, ratio))


def score_route_corner_technique(
    summary: RouteCornerTechniqueSummary,
    consequence: CornerGeometryConsequence,
) -> RouteCornerTechniqueScore:
    """Score power/cadence timing plus physical line/speed retention.

    The approach phase is the explicit rider-effort baseline and must contain
    positive power and cadence. Entry/apex release components score 100 at
    zero effort and fall linearly to 0 at the approach baseline. Exit recovery
    scores rise linearly from 0 to 100 at the approach baseline.

    Line retention is 100 * (1 - line_deviation_ratio). Speed retention is
    100 * exit_speed_multiplier. The overall score is the arithmetic mean of
    all eight explicit components, so there are no hidden weights or rating
    thresholds.
    """

    if not isinstance(summary, RouteCornerTechniqueSummary):
        raise ValueError(
            "summary must be a RouteCornerTechniqueSummary, "
            f"got {type(summary).__name__}"
        )
    if not isinstance(consequence, CornerGeometryConsequence):
        raise ValueError(
            "consequence must be a CornerGeometryConsequence, "
            f"got {type(consequence).__name__}"
        )
    if summary.approach_power_w <= 0.0:
        raise ValueError("approach_power_w must be positive for technique scoring")
    if summary.approach_cadence_rpm <= 0.0:
        raise ValueError("approach_cadence_rpm must be positive for technique scoring")

    line_deviation = _non_negative(
        consequence.line_deviation_ratio,
        "line_deviation_ratio",
    )
    speed_multiplier = _non_negative(
        consequence.exit_speed_multiplier,
        "exit_speed_multiplier",
    )
    if line_deviation > 1.0:
        raise ValueError("line_deviation_ratio must not exceed 1")
    if speed_multiplier > 1.0:
        raise ValueError("exit_speed_multiplier must not exceed 1")

    components = (
        _release_score(summary.entry_power_w, summary.approach_power_w),
        _release_score(summary.apex_power_w, summary.approach_power_w),
        _recovery_score(summary.exit_power_w, summary.approach_power_w),
        _release_score(
            summary.entry_cadence_rpm,
            summary.approach_cadence_rpm,
        ),
        _release_score(
            summary.apex_cadence_rpm,
            summary.approach_cadence_rpm,
        ),
        _recovery_score(
            summary.exit_cadence_rpm,
            summary.approach_cadence_rpm,
        ),
        100.0 * (1.0 - line_deviation),
        100.0 * speed_multiplier,
    )

    return RouteCornerTechniqueScore(
        score=sum(components) / len(components),
        entry_power_release_score=components[0],
        apex_power_release_score=components[1],
        exit_power_recovery_score=components[2],
        entry_cadence_release_score=components[3],
        apex_cadence_release_score=components[4],
        exit_cadence_recovery_score=components[5],
        line_retention_score=components[6],
        speed_retention_score=components[7],
    )

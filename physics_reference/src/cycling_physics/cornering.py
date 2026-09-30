"""Cornering geometry and grip-based speed limits for the reference physics.

This module defines the data contract for a single corner and the functions
that derive the maximum cornering speed from the available grip. It is an
independent physics module: it does not yet integrate with step_simulation,
the route, technique scoring, slip, braking or crashes.
"""

import math
from dataclasses import dataclass

from .model import STANDARD_GRAVITY_MPS2
from .validation import (
    _clean_name,
    _closed_unit_interval,
    _finite,
    _non_negative,
    _positive,
    _positive_at_most_one,
)

__all__ = [
    "Corner",
    "CornerProfile",
    "CORNER_PHASE_OUTSIDE",
    "CORNER_PHASE_APPROACH",
    "CORNER_PHASE_ENTRY",
    "CORNER_PHASE_APEX",
    "CORNER_PHASE_EXIT",
    "CornerTechniqueSample",
    "CornerTechniqueSummary",
    "effective_friction_coefficient",
    "maximum_corner_speed_mps",
    "corner_grip_usage",
    "classify_corner_grip_usage",
    "corner_phase_at_distance",
    "distance_to_corner_start_m",
    "summarize_corner_technique",
    "CornerTechniqueAssessment",
    "assess_corner_technique",
    "CornerConsequence",
    "corner_consequence_from_grip_usage",
    "apply_corner_exit_speed_mps",
]

CORNER_PHASE_OUTSIDE = "outside"
"""Phase returned for distances outside any corner phase."""

CORNER_PHASE_APPROACH = "approach"
"""Phase covering the road just before the corner start."""

CORNER_PHASE_ENTRY = "entry"
"""Phase covering the first 25 % of the corner."""

CORNER_PHASE_APEX = "apex"
"""Phase covering the middle 50 % of the corner."""

CORNER_PHASE_EXIT = "exit"
"""Phase covering the last 25 % of the corner."""


@dataclass(frozen=True, slots=True)
class Corner:
    """One corner placed along a route, with constant radius.

    start_distance_m is the position of the corner start along the route from
    the beginning, length_m its extent along the road and radius_m the corner
    radius of curvature, all in metres. All distances and the radius must be
    finite and greater than zero where applicable. The name is stored
    stripped of surrounding whitespace and must not be empty.
    """

    name: str
    """Corner name. Must be non-empty after stripping whitespace."""

    start_distance_m: float
    """Distance of the corner start along the route in metres (m). Must be finite and non-negative."""

    length_m: float
    """Corner extent along the road in metres (m). Must be finite and greater than zero."""

    radius_m: float
    """Corner radius of curvature in metres (m). Must be finite and greater than zero."""

    def __post_init__(self):
        object.__setattr__(self, "name", _clean_name(self.name, "name"))
        object.__setattr__(self, "start_distance_m", _non_negative(self.start_distance_m, "start_distance_m"))
        object.__setattr__(self, "length_m", _positive(self.length_m, "length_m"))
        object.__setattr__(self, "radius_m", _positive(self.radius_m, "radius_m"))

    @property
    def end_distance_m(self) -> float:
        """Distance of the corner end along the route in metres (m)."""
        return self.start_distance_m + self.length_m


@dataclass(frozen=True, slots=True)
class CornerProfile:
    """An ordered set of corners placed along a route.

    total_length_m is the length of the route in metres (m) and must be
    greater than zero. Corners must be provided as a tuple and are sorted by
    start distance: each corner lies on the closed-open interval
    [start_distance_m, end_distance_m) and corners must not overlap,
    although touching (end of one equal to the start of the next) is
    allowed. No corner end may exceed total_length_m. The profile may be
    empty.
    """

    name: str
    """Corner profile name. Must be non-empty after stripping whitespace."""

    total_length_m: float
    """Route length covered by the profile in metres (m). Must be finite and greater than zero."""

    corners: tuple[Corner, ...]
    """Corners sorted by start distance. Must be a tuple; may be empty. Corners must not overlap and must fit inside the profile."""

    def __post_init__(self):
        object.__setattr__(self, "name", _clean_name(self.name, "name"))
        object.__setattr__(self, "total_length_m", _positive(self.total_length_m, "total_length_m"))
        if not isinstance(self.corners, tuple):
            raise ValueError(
                f"corners must be a tuple, got {type(self.corners).__name__}"
            )
        for index, corner in enumerate(self.corners):
            if not isinstance(corner, Corner):
                raise ValueError(
                    f"corners[{index}] must be a Corner, got {type(corner).__name__}"
                )
            if corner.end_distance_m > self.total_length_m:
                raise ValueError(
                    f"corners[{index}] end distance ({corner.end_distance_m} m) "
                    f"must not exceed the total profile length ({self.total_length_m} m)"
                )
        for index in range(1, len(self.corners)):
            previous = self.corners[index - 1]
            current = self.corners[index]
            if current.start_distance_m < previous.start_distance_m:
                raise ValueError(
                    "corners must be ordered by ascending start distance; "
                    f"got start {current.start_distance_m} m after "
                    f"{previous.start_distance_m} m"
                )
            if current.start_distance_m < previous.end_distance_m:
                raise ValueError(
                    "corners must not overlap; "
                    f"corners[{index - 1}] ends at {previous.end_distance_m} m "
                    f"while corners[{index}] starts at {current.start_distance_m} m"
                )

    def corner_at_distance(self, distance_m: float) -> Corner | None:
        """Return the Corner containing a distance, or None outside any corner.

        distance_m is the position along the route in metres (m) and must be
        finite and lie in the closed interval [0, total_length_m]. Each corner
        covers the closed-open interval [start_distance_m, end_distance_m): its
        exact start belongs to the corner, its exact end does not. A distance
        of exactly total_length_m returns None, as does any distance between
        corners.
        """
        distance = _finite(distance_m, "distance_m")
        if distance < 0.0:
            raise ValueError(f"distance_m must not be negative, got {distance}")
        if distance > self.total_length_m:
            raise ValueError(
                f"distance_m must not exceed the total profile length "
                f"({self.total_length_m} m), got {distance}"
            )
        for corner in self.corners:
            if corner.start_distance_m <= distance < corner.end_distance_m:
                return corner
        return None


def effective_friction_coefficient(
    base_friction_coefficient: float,
    grip_multiplier: float,
) -> float:
    """Return the effective friction coefficient (unitless).

    base_friction_coefficient is the friction coefficient of the tyre-road
    pair on a dry surface and must be greater than zero; grip_multiplier is
    the dimensionless grip multiplier in the interval (0, 1] (1.0 base grip,
    smaller values reduced grip, e.g. on wet road). The result is their
    product.
    """
    base = _positive(base_friction_coefficient, "base_friction_coefficient")
    grip = _positive_at_most_one(grip_multiplier, "grip_multiplier")
    return base * grip


def maximum_corner_speed_mps(
    radius_m: float,
    base_friction_coefficient: float,
    grip_multiplier: float,
) -> float:
    """Return the maximum flat-corner speed in metres per second (m/s).

    radius_m is the corner radius in metres (m) and must be greater than
    zero; base_friction_coefficient must be greater than zero and
    grip_multiplier must lie in (0, 1]. The result follows from the balance
    of centripetal acceleration and the effective friction:
    v_max = sqrt(mu_effective * g * radius_m). No artificial speed limit is
    applied.
    """
    radius = _positive(radius_m, "radius_m")
    friction = effective_friction_coefficient(base_friction_coefficient, grip_multiplier)
    return math.sqrt(friction * STANDARD_GRAVITY_MPS2 * radius)


def corner_grip_usage(
    speed_mps: float,
    radius_m: float,
    base_friction_coefficient: float,
    grip_multiplier: float,
) -> float:
    """Return the fraction of available grip used while cornering (unitless).

    speed_mps is the forward speed in metres per second (m/s) and must be
    finite and non-negative; radius_m, base_friction_coefficient and
    grip_multiplier are validated as in maximum_corner_speed_mps. The result
    is speed_mps**2 / (mu_effective * g * radius_m): below 1.0 there is a
    grip reserve, exactly 1.0 is the physical limit and above 1.0 the
    available grip is exceeded.
    """
    speed = _non_negative(speed_mps, "speed_mps")
    radius = _positive(radius_m, "radius_m")
    friction = effective_friction_coefficient(base_friction_coefficient, grip_multiplier)
    return speed * speed / (friction * STANDARD_GRAVITY_MPS2 * radius)


def classify_corner_grip_usage(grip_usage: float) -> str:
    """Classify a corner grip usage value into one of three statuses.

    grip_usage is the dimensionless fraction of available grip used, as
    returned by corner_grip_usage, and must be finite and non-negative. A
    value below 0.85 returns "safe", a value from 0.85 to 1.0 inclusive
    returns "near_limit" and a value above 1.0 returns "grip_exceeded".
    """
    usage = _non_negative(grip_usage, "grip_usage")
    if usage < 0.85:
        return "safe"
    if usage <= 1.0:
        return "near_limit"
    return "grip_exceeded"


def corner_phase_at_distance(
    corner: Corner,
    distance_m: float,
    approach_length_m: float = 100.0,
) -> str:
    """Return the cornering phase for a distance along the route.

    corner must be a Corner record, distance_m the position along the route
    in metres (m), which must be finite and non-negative, and
    approach_length_m the length of the approach zone in metres (m), which
    must be finite and greater than zero.

    The approach zone starts at
    max(0.0, corner.start_distance_m - approach_length_m). The phases are:
    - "approach": [approach_start, start);
    - "entry": [start, start + 0.25 * length);
    - "apex": [start + 0.25 * length, start + 0.75 * length);
    - "exit": [start + 0.75 * length, end);
    - "outside": every other valid distance.
    The exact corner end distance returns "outside". The distance is never
    rounded.
    """
    if not isinstance(corner, Corner):
        raise ValueError(
            f"corner must be a Corner, got {type(corner).__name__}"
        )
    distance = _non_negative(distance_m, "distance_m")
    approach_length = _positive(approach_length_m, "approach_length_m")

    start = corner.start_distance_m
    length = corner.length_m
    end = corner.end_distance_m
    approach_start = max(0.0, start - approach_length)

    if distance < start:
        if distance >= approach_start:
            return CORNER_PHASE_APPROACH
        return CORNER_PHASE_OUTSIDE
    if distance < start + 0.25 * length:
        return CORNER_PHASE_ENTRY
    if distance < start + 0.75 * length:
        return CORNER_PHASE_APEX
    if distance < end:
        return CORNER_PHASE_EXIT
    return CORNER_PHASE_OUTSIDE


def distance_to_corner_start_m(corner: Corner, distance_m: float) -> float:
    """Return the distance to the start of a corner in metres (m).

    corner must be a Corner record and distance_m the position along the
    route in metres (m), which must be finite and non-negative. Before the
    corner the result is the positive distance to its start; exactly at the
    start, inside the corner and after it the result is 0.0. This will later
    feed HUD messages such as "corner in X m".
    """
    if not isinstance(corner, Corner):
        raise ValueError(
            f"corner must be a Corner, got {type(corner).__name__}"
        )
    distance = _non_negative(distance_m, "distance_m")
    if distance < corner.start_distance_m:
        return corner.start_distance_m - distance
    return 0.0


@dataclass(frozen=True, slots=True)
class CornerTechniqueSample:
    """One technique sample taken while approaching or riding a corner.

    distance_m is the position along the route in metres (m); power_w is the
    rider power in watts (W); cadence_rpm is the cadence in revolutions per
    minute (rpm); grip_usage is the dimensionless grip usage from
    corner_grip_usage. All fields must be finite and non-negative.
    """

    distance_m: float
    """Sample position along the route in metres (m). Must be finite and non-negative."""

    power_w: float
    """Rider power in watts (W). Must be finite and non-negative."""

    cadence_rpm: float
    """Cadence in revolutions per minute (rpm). Must be finite and non-negative."""

    grip_usage: float
    """Dimensionless grip usage. Must be finite and non-negative."""

    def __post_init__(self):
        object.__setattr__(self, "distance_m", _non_negative(self.distance_m, "distance_m"))
        object.__setattr__(self, "power_w", _non_negative(self.power_w, "power_w"))
        object.__setattr__(self, "cadence_rpm", _non_negative(self.cadence_rpm, "cadence_rpm"))
        object.__setattr__(self, "grip_usage", _non_negative(self.grip_usage, "grip_usage"))


@dataclass(frozen=True, slots=True)
class CornerTechniqueSummary:
    """Summary of power and cadence behaviour across the corner phases.

    The four phase averages use watts (W) for power and revolutions per
    minute (rpm) for cadence; max_grip_usage is dimensionless. All stored
    fields must be finite and non-negative. Derived ratio properties may
    return math.inf when the corresponding approach baseline is zero and the
    numerator is positive.
    """

    approach_power_w: float
    """Mean power in the approach phase in watts (W)."""

    entry_power_w: float
    """Mean power in the entry phase in watts (W)."""

    apex_power_w: float
    """Mean power in the apex phase in watts (W)."""

    exit_power_w: float
    """Mean power in the exit phase in watts (W)."""

    approach_cadence_rpm: float
    """Mean cadence in the approach phase in revolutions per minute (rpm)."""

    entry_cadence_rpm: float
    """Mean cadence in the entry phase in revolutions per minute (rpm)."""

    apex_cadence_rpm: float
    """Mean cadence in the apex phase in revolutions per minute (rpm)."""

    exit_cadence_rpm: float
    """Mean cadence in the exit phase in revolutions per minute (rpm)."""

    max_grip_usage: float
    """Maximum dimensionless grip usage over the corner phases entry, apex and exit (approach is excluded)."""

    def __post_init__(self):
        for field_name in (
            "approach_power_w",
            "entry_power_w",
            "apex_power_w",
            "exit_power_w",
            "approach_cadence_rpm",
            "entry_cadence_rpm",
            "apex_cadence_rpm",
            "exit_cadence_rpm",
            "max_grip_usage",
        ):
            object.__setattr__(
                self,
                field_name,
                _non_negative(getattr(self, field_name), field_name),
            )

    @property
    def entry_power_ratio(self) -> float:
        """Entry power divided by approach power (unitless)."""
        return _baseline_ratio(self.entry_power_w, self.approach_power_w)

    @property
    def apex_power_ratio(self) -> float:
        """Apex power divided by approach power (unitless)."""
        return _baseline_ratio(self.apex_power_w, self.approach_power_w)

    @property
    def exit_power_ratio(self) -> float:
        """Exit power divided by approach power (unitless)."""
        return _baseline_ratio(self.exit_power_w, self.approach_power_w)

    @property
    def entry_cadence_ratio(self) -> float:
        """Entry cadence divided by approach cadence (unitless)."""
        return _baseline_ratio(self.entry_cadence_rpm, self.approach_cadence_rpm)

    @property
    def apex_cadence_ratio(self) -> float:
        """Apex cadence divided by approach cadence (unitless)."""
        return _baseline_ratio(self.apex_cadence_rpm, self.approach_cadence_rpm)

    @property
    def exit_cadence_ratio(self) -> float:
        """Exit cadence divided by approach cadence (unitless)."""
        return _baseline_ratio(self.exit_cadence_rpm, self.approach_cadence_rpm)


def _baseline_ratio(numerator: float, baseline: float) -> float:
    """Return numerator / baseline, with defined zero-baseline behaviour."""
    if baseline == 0.0:
        if numerator == 0.0:
            return 0.0
        return math.inf
    return numerator / baseline


def summarize_corner_technique(
    corner: Corner,
    samples: tuple[CornerTechniqueSample, ...],
    approach_length_m: float = 100.0,
) -> CornerTechniqueSummary:
    """Summarize technique samples over the four corner phases.

    corner must be a Corner record and samples a non-empty tuple of
    CornerTechniqueSample records ordered by non-decreasing distance_m;
    approach_length_m is validated as in corner_phase_at_distance. Each
    sample is assigned to a phase with corner_phase_at_distance; samples in
    the outside phase are ignored. For every phase among approach, entry,
    apex and exit the plain arithmetic mean of power and cadence is
    computed. max_grip_usage is the maximum grip usage over the corner
    phases only (entry, apex and exit); approach samples never influence
    it. A missing phase raises ValueError naming the missing phase. The
    input data is not modified.
    """
    if not isinstance(corner, Corner):
        raise ValueError(
            f"corner must be a Corner, got {type(corner).__name__}"
        )
    if not isinstance(samples, tuple):
        raise ValueError(
            f"samples must be a tuple, got {type(samples).__name__}"
        )
    if not samples:
        raise ValueError("samples must contain at least one CornerTechniqueSample")
    for index, sample in enumerate(samples):
        if not isinstance(sample, CornerTechniqueSample):
            raise ValueError(
                f"samples[{index}] must be a CornerTechniqueSample, "
                f"got {type(sample).__name__}"
            )
        if index > 0 and sample.distance_m < samples[index - 1].distance_m:
            raise ValueError(
                "samples must be ordered by non-decreasing distance_m; "
                f"got {sample.distance_m} m after "
                f"{samples[index - 1].distance_m} m"
            )

    phases = {
        CORNER_PHASE_APPROACH: {"power": [], "cadence": []},
        CORNER_PHASE_ENTRY: {"power": [], "cadence": []},
        CORNER_PHASE_APEX: {"power": [], "cadence": []},
        CORNER_PHASE_EXIT: {"power": [], "cadence": []},
    }
    corner_phases = {CORNER_PHASE_ENTRY, CORNER_PHASE_APEX, CORNER_PHASE_EXIT}
    max_grip_usage = 0.0
    for sample in samples:
        phase = corner_phase_at_distance(corner, sample.distance_m, approach_length_m)
        if phase == CORNER_PHASE_OUTSIDE:
            continue
        phases[phase]["power"].append(sample.power_w)
        phases[phase]["cadence"].append(sample.cadence_rpm)
        if phase in corner_phases:
            max_grip_usage = max(max_grip_usage, sample.grip_usage)

    def mean(values):
        return sum(values) / len(values)

    missing = [phase for phase in phases if not phases[phase]["power"]]
    if missing:
        raise ValueError(
            f"missing samples for corner phase(s): {', '.join(missing)}"
        )

    return CornerTechniqueSummary(
        approach_power_w=mean(phases[CORNER_PHASE_APPROACH]["power"]),
        entry_power_w=mean(phases[CORNER_PHASE_ENTRY]["power"]),
        apex_power_w=mean(phases[CORNER_PHASE_APEX]["power"]),
        exit_power_w=mean(phases[CORNER_PHASE_EXIT]["power"]),
        approach_cadence_rpm=mean(phases[CORNER_PHASE_APPROACH]["cadence"]),
        entry_cadence_rpm=mean(phases[CORNER_PHASE_ENTRY]["cadence"]),
        apex_cadence_rpm=mean(phases[CORNER_PHASE_APEX]["cadence"]),
        exit_cadence_rpm=mean(phases[CORNER_PHASE_EXIT]["cadence"]),
        max_grip_usage=max_grip_usage,
    )


def _lower_is_better_factor(value: float, full_at: float, zero_at: float) -> float:
    """Return a 0..1 factor where lower values score better."""
    if value <= full_at:
        return 1.0
    if value >= zero_at:
        return 0.0
    return (zero_at - value) / (zero_at - full_at)


def _higher_is_better_factor(value: float, zero_at: float, full_at: float) -> float:
    """Return a 0..1 factor where higher values score better."""
    if value <= zero_at:
        return 0.0
    if value >= full_at:
        return 1.0
    return (value - zero_at) / (full_at - zero_at)


def _grip_factor(grip_usage: float) -> float:
    """Return the grip factor in [0, 1] for a given grip usage."""
    if grip_usage <= 0.85:
        return 1.0
    if grip_usage <= 1.0:
        return 1.0 - (grip_usage - 0.85) / 0.15 * 0.5
    if grip_usage < 1.25:
        return 0.5 - (grip_usage - 1.0) / 0.25 * 0.5
    return 0.0


ASSESSMENT_RATINGS = ("excellent", "good", "needs_improvement", "poor")
ASSESSMENT_FEEDBACKS = (
    "good_technique",
    "reduce_speed",
    "release_earlier",
    "stay_off_power_at_apex",
    "accelerate_on_exit",
)
ASSESSMENT_GRIP_STATUSES = ("safe", "near_limit", "grip_exceeded")


@dataclass(frozen=True, slots=True)
class CornerTechniqueAssessment:
    """Deterministic 0-100 corner technique assessment.

    score lies in [0, 100]; rating and feedback are fixed text labels and
    grip_status is one of the classify_corner_grip_usage results.
    """

    score: float
    """Technique score in points (unitless), clamped to [0, 100]."""

    rating: str
    """Rating label: one of excellent, good, needs_improvement, poor."""

    feedback: str
    """Primary feedback label: one of the fixed feedback strings."""

    grip_status: str
    """Grip status from classify_corner_grip_usage."""

    def __post_init__(self):
        score = _finite(self.score, "score")
        if not 0.0 <= score <= 100.0:
            raise ValueError(f"score must be in the interval [0, 100], got {score}")
        object.__setattr__(self, "score", score)
        if self.rating not in ASSESSMENT_RATINGS:
            raise ValueError(
                f"rating must be one of {ASSESSMENT_RATINGS}, got {self.rating!r}"
            )
        if self.feedback not in ASSESSMENT_FEEDBACKS:
            raise ValueError(
                f"feedback must be one of {ASSESSMENT_FEEDBACKS}, got {self.feedback!r}"
            )
        if self.grip_status not in ASSESSMENT_GRIP_STATUSES:
            raise ValueError(
                f"grip_status must be one of {ASSESSMENT_GRIP_STATUSES}, got {self.grip_status!r}"
            )


def assess_corner_technique(summary: CornerTechniqueSummary) -> CornerTechniqueAssessment:
    """Assess a CornerTechniqueSummary into a deterministic 0-100 score.

    summary must be a CornerTechniqueSummary. The total of 100 points is
    split into grip (40), entry power (15), entry cadence (5), apex power
    (10), apex cadence (5), exit power (15) and exit cadence (10). Each
    component uses the documented ratio thresholds through
    lower_is_better/higher_is_better factors; the grip factor drops linearly
    from 1.0 at usage 0.85 to 0.5 at usage 1.0 and to 0.0 at usage 1.25.
    The final score is clamped to [0, 100] and not rounded. The rating and
    feedback follow the documented deterministic rules; grip_status comes
    from classify_corner_grip_usage(summary.max_grip_usage).
    """
    if not isinstance(summary, CornerTechniqueSummary):
        raise ValueError(
            f"summary must be a CornerTechniqueSummary, got {type(summary).__name__}"
        )

    grip_score = 40.0 * _grip_factor(summary.max_grip_usage)
    entry_power_score = 15.0 * _lower_is_better_factor(summary.entry_power_ratio, 0.60, 1.00)
    entry_cadence_score = 5.0 * _lower_is_better_factor(summary.entry_cadence_ratio, 0.85, 1.05)
    apex_power_score = 10.0 * _lower_is_better_factor(summary.apex_power_ratio, 0.35, 0.85)
    apex_cadence_score = 5.0 * _lower_is_better_factor(summary.apex_cadence_ratio, 0.70, 1.00)
    exit_power_score = 15.0 * _higher_is_better_factor(summary.exit_power_ratio, 0.40, 0.90)
    exit_cadence_score = 10.0 * _higher_is_better_factor(summary.exit_cadence_ratio, 0.50, 0.90)

    raw_score = (
        grip_score
        + entry_power_score
        + entry_cadence_score
        + apex_power_score
        + apex_cadence_score
        + exit_power_score
        + exit_cadence_score
    )
    score = max(0.0, min(100.0, raw_score))

    if score >= 90.0:
        rating = "excellent"
    elif score >= 75.0:
        rating = "good"
    elif score >= 50.0:
        rating = "needs_improvement"
    else:
        rating = "poor"

    if summary.max_grip_usage > 1.0:
        feedback = "reduce_speed"
    elif summary.entry_power_ratio > 0.60 or summary.entry_cadence_ratio > 0.85:
        feedback = "release_earlier"
    elif summary.apex_power_ratio > 0.35 or summary.apex_cadence_ratio > 0.70:
        feedback = "stay_off_power_at_apex"
    elif summary.exit_power_ratio < 0.90 or summary.exit_cadence_ratio < 0.90:
        feedback = "accelerate_on_exit"
    else:
        feedback = "good_technique"

    return CornerTechniqueAssessment(
        score=score,
        rating=rating,
        feedback=feedback,
        grip_status=classify_corner_grip_usage(summary.max_grip_usage),
    )


CORNER_OUTCOMES = ("clean", "wide_line", "controlled_slip")
CORNER_HUD_FEEDBACKS = ("clean_corner", "wider_slower_line", "rear_wheel_slip")


@dataclass(frozen=True, slots=True)
class CornerConsequence:
    """Deterministic consequence of corner grip usage, without a crash.

    outcome is one of clean, wide_line, controlled_slip. exit_speed_multiplier
    scales the corner exit speed and lies in [0, 1]; line_deviation_ratio is
    the normalized line deviation in [0, 1] where 0.0 is the ideal line and
    1.0 uses the full available lane width (it is a normalized value, not a
    metric). hud_feedback is one of the fixed HUD strings.
    """

    outcome: str
    """Corner outcome: one of clean, wide_line, controlled_slip."""

    exit_speed_multiplier: float
    """Exit speed multiplier (unitless), in [0, 1]. Scales the speed leaving the corner."""

    line_deviation_ratio: float
    """Normalized line deviation (unitless), in [0, 1]: 0.0 ideal line, 1.0 full lane width."""

    hud_feedback: str
    """HUD feedback string: one of clean_corner, wider_slower_line, rear_wheel_slip."""

    def __post_init__(self):
        object.__setattr__(
            self,
            "exit_speed_multiplier",
            _closed_unit_interval(self.exit_speed_multiplier, "exit_speed_multiplier"),
        )
        object.__setattr__(
            self,
            "line_deviation_ratio",
            _closed_unit_interval(self.line_deviation_ratio, "line_deviation_ratio"),
        )
        if self.outcome not in CORNER_OUTCOMES:
            raise ValueError(
                f"outcome must be one of {CORNER_OUTCOMES}, got {self.outcome!r}"
            )
        if self.hud_feedback not in CORNER_HUD_FEEDBACKS:
            raise ValueError(
                f"hud_feedback must be one of {CORNER_HUD_FEEDBACKS}, "
                f"got {self.hud_feedback!r}"
            )


def corner_consequence_from_grip_usage(grip_usage: float) -> CornerConsequence:
    """Return the deterministic CornerConsequence for a grip usage value.

    grip_usage is the dimensionless grip usage and must be finite and
    non-negative. At or below 1.0 the corner is clean. Between 1.0 and 1.15
    the outcome is wide_line with the exit speed multiplier and line
    deviation interpolating linearly to 0.85 and 0.5. Above 1.15 the outcome
    is controlled_slip; the exit speed multiplier interpolates from 0.85 to
    0.60 and the line deviation from 0.5 to 1.0 as grip usage grows from 1.15
    to 1.50, after which the values stay at 0.60 and 1.0. There is never a
    crash.
    """
    usage = _non_negative(grip_usage, "grip_usage")
    if usage <= 1.0:
        return CornerConsequence(
            outcome="clean",
            exit_speed_multiplier=1.0,
            line_deviation_ratio=0.0,
            hud_feedback="clean_corner",
        )
    if usage <= 1.15:
        progress = (usage - 1.0) / 0.15
        return CornerConsequence(
            outcome="wide_line",
            exit_speed_multiplier=1.0 - progress * 0.15,
            line_deviation_ratio=progress * 0.5,
            hud_feedback="wider_slower_line",
        )
    progress = min(1.0, max(0.0, (usage - 1.15) / 0.35))
    return CornerConsequence(
        outcome="controlled_slip",
        exit_speed_multiplier=0.85 - progress * 0.25,
        line_deviation_ratio=0.5 + progress * 0.5,
        hud_feedback="rear_wheel_slip",
    )


def apply_corner_exit_speed_mps(
    speed_mps: float,
    consequence: CornerConsequence,
) -> float:
    """Return the corner exit speed in metres per second (m/s).

    speed_mps is the speed entering the corner application in m/s and must be
    finite and non-negative; consequence must be a CornerConsequence. The
    result is speed_mps * consequence.exit_speed_multiplier and is never
    negative. No object is modified.
    """
    if not isinstance(consequence, CornerConsequence):
        raise ValueError(
            f"consequence must be a CornerConsequence, got {type(consequence).__name__}"
        )
    speed = _non_negative(speed_mps, "speed_mps")
    return speed * consequence.exit_speed_multiplier

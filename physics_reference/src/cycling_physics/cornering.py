"""Cornering geometry and grip-based speed limits for the reference physics.

This module defines the data contract for a single corner and the functions
that derive the maximum cornering speed from the available grip. It is an
independent physics module: it does not yet integrate with step_simulation,
the route, technique scoring, slip, braking or crashes.
"""

import math
from dataclasses import dataclass

from .model import STANDARD_GRAVITY_MPS2
from .validation import _clean_name, _finite, _non_negative, _positive, _positive_at_most_one

__all__ = [
    "Corner",
    "CornerProfile",
    "effective_friction_coefficient",
    "maximum_corner_speed_mps",
    "corner_grip_usage",
    "classify_corner_grip_usage",
]


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

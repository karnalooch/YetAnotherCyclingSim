"""Cornering geometry and grip-based speed limits for the reference physics.

This module defines the data contract for a single corner and the functions
that derive the maximum cornering speed from the available grip. It is an
independent physics module: it does not yet integrate with step_simulation,
the route, technique scoring, slip, braking or crashes.
"""

import math
from dataclasses import dataclass

from .model import STANDARD_GRAVITY_MPS2
from .validation import _clean_name, _non_negative, _positive, _positive_at_most_one

__all__ = [
    "Corner",
    "effective_friction_coefficient",
    "maximum_corner_speed_mps",
    "corner_grip_usage",
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

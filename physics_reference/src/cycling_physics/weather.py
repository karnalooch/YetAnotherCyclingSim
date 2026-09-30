"""Distance-based planned weather data contracts for the reference physics.

A weather profile is a sequence of keyframes placed along the route. Between
two neighbouring keyframes every weather parameter is interpolated linearly
by distance. This module contains no randomness, graphics or sound.
"""

from dataclasses import dataclass

from .model import Environment
from .validation import (
    _clean_name,
    _closed_unit_interval,
    _finite,
    _non_negative,
    _positive,
    _positive_at_most_one,
)

__all__ = ["WeatherKeyframe", "WeatherProfile"]


@dataclass(frozen=True, slots=True)
class WeatherKeyframe:
    """Exact weather state at one distance along the route.

    distance_m is the position along the route from the start, in metres.
    Wind speed may be negative (tailwind). Air density must be greater than
    zero; wetness lies in [0, 1]; the rolling resistance multiplier must be
    greater than zero; grip lies in (0, 1].
    """

    distance_m: float
    """Position along the route from the start in metres (m). Must be finite and non-negative."""

    wind_speed_mps: float
    """Wind speed in metres per second (m/s). Positive values are headwinds; negative values are tailwinds. Must be finite."""

    air_density_kg_m3: float
    """Air density in kilograms per cubic metre (kg/m^3). Must be greater than zero."""

    surface_wetness: float
    """Road wetness (unitless): 0.0 dry, 1.0 fully wet. Must be in the interval [0, 1]."""

    rolling_resistance_multiplier: float
    """Dimensionless multiplier on the base rolling resistance coefficient Crr. Must be greater than zero."""

    grip_multiplier: float
    """Dimensionless grip multiplier (unitless): 1.0 base grip, smaller values limited grip. Must be in the interval (0, 1]."""

    def __post_init__(self):
        object.__setattr__(self, "distance_m", _non_negative(self.distance_m, "distance_m"))
        object.__setattr__(self, "wind_speed_mps", _finite(self.wind_speed_mps, "wind_speed_mps"))
        object.__setattr__(self, "air_density_kg_m3", _positive(self.air_density_kg_m3, "air_density_kg_m3"))
        object.__setattr__(self, "surface_wetness", _closed_unit_interval(self.surface_wetness, "surface_wetness"))
        object.__setattr__(self, "rolling_resistance_multiplier", _positive(self.rolling_resistance_multiplier, "rolling_resistance_multiplier"))
        object.__setattr__(self, "grip_multiplier", _positive_at_most_one(self.grip_multiplier, "grip_multiplier"))


@dataclass(frozen=True, slots=True)
class WeatherProfile:
    """A distance-keyed weather profile for a route.

    Keyframes are ordered by distance: the first keyframe must lie at
    distance 0.0 and distances must be strictly increasing. The last
    keyframe defines the profile length. Between neighbouring keyframes all
    weather parameters are interpolated linearly by distance; at an exact
    keyframe distance the exact keyframe values are returned.
    """

    name: str
    """Weather profile name. Must be non-empty after stripping whitespace."""

    keyframes: tuple[WeatherKeyframe, ...]
    """Ordered weather keyframes. Must be a tuple with at least two entries, first at distance 0.0 and strictly increasing distances."""

    def __post_init__(self):
        object.__setattr__(self, "name", _clean_name(self.name, "name"))
        if not isinstance(self.keyframes, tuple):
            raise ValueError(
                f"keyframes must be a tuple, got {type(self.keyframes).__name__}"
            )
        if len(self.keyframes) < 2:
            raise ValueError("keyframes must contain at least two WeatherKeyframe entries")
        for index, keyframe in enumerate(self.keyframes):
            if not isinstance(keyframe, WeatherKeyframe):
                raise ValueError(
                    f"keyframes[{index}] must be a WeatherKeyframe, "
                    f"got {type(keyframe).__name__}"
                )
        first_distance = self.keyframes[0].distance_m
        if first_distance != 0.0:
            raise ValueError(f"the first keyframe distance must be 0.0, got {first_distance}")
        for index in range(1, len(self.keyframes)):
            previous = self.keyframes[index - 1].distance_m
            current = self.keyframes[index].distance_m
            if current <= previous:
                raise ValueError(
                    "keyframe distances must be strictly increasing; "
                    f"got {current} after {previous}"
                )

    @property
    def total_length_m(self) -> float:
        """Total profile length in metres (m), defined by the last keyframe."""
        return self.keyframes[-1].distance_m

    def environment_at_distance(self, distance_m: float, grade_decimal: float) -> Environment:
        """Return the interpolated Environment at a distance along the route.

        distance_m is the position along the route from the start in metres
        (m) and grade_decimal the road grade (rise over run, unitless) passed
        through to the returned Environment. Both must be finite. distance_m
        must lie in the closed interval [0, total_length_m]; values outside
        raise ValueError.

        The two neighbouring keyframes around distance_m are found and every
        weather parameter is interpolated linearly between them. A distance
        of 0.0 returns the first keyframe values exactly, a distance exactly
        equal to a keyframe returns that keyframe's values exactly and the
        exact profile end returns the last keyframe values. The result is
        not rounded.
        """
        distance = _finite(distance_m, "distance_m")
        grade = _finite(grade_decimal, "grade_decimal")
        total_length = self.total_length_m
        if distance < 0.0:
            raise ValueError(f"distance_m must not be negative, got {distance}")
        if distance > total_length:
            raise ValueError(
                f"distance_m must not exceed the total profile length "
                f"({total_length} m), got {distance}"
            )

        lower_index = 0
        for index, keyframe in enumerate(self.keyframes):
            if keyframe.distance_m <= distance:
                lower_index = index
            else:
                break

        lower = self.keyframes[lower_index]
        if distance == lower.distance_m:
            return self._build_environment(lower, grade)

        upper = self.keyframes[lower_index + 1]
        span = upper.distance_m - lower.distance_m
        fraction = (distance - lower.distance_m) / span
        wind_speed_mps = lower.wind_speed_mps + (upper.wind_speed_mps - lower.wind_speed_mps) * fraction
        air_density_kg_m3 = lower.air_density_kg_m3 + (upper.air_density_kg_m3 - lower.air_density_kg_m3) * fraction
        surface_wetness = lower.surface_wetness + (upper.surface_wetness - lower.surface_wetness) * fraction
        rolling_resistance_multiplier = (
            lower.rolling_resistance_multiplier
            + (upper.rolling_resistance_multiplier - lower.rolling_resistance_multiplier) * fraction
        )
        grip_multiplier = lower.grip_multiplier + (upper.grip_multiplier - lower.grip_multiplier) * fraction
        return Environment(
            grade_decimal=grade,
            wind_speed_mps=wind_speed_mps,
            air_density_kg_m3=air_density_kg_m3,
            surface_wetness=surface_wetness,
            rolling_resistance_multiplier=rolling_resistance_multiplier,
            grip_multiplier=grip_multiplier,
        )

    def _build_environment(self, keyframe: WeatherKeyframe, grade_decimal: float) -> Environment:
        """Build an Environment with the exact values of a WeatherKeyframe."""
        return Environment(
            grade_decimal=grade_decimal,
            wind_speed_mps=keyframe.wind_speed_mps,
            air_density_kg_m3=keyframe.air_density_kg_m3,
            surface_wetness=keyframe.surface_wetness,
            rolling_resistance_multiplier=keyframe.rolling_resistance_multiplier,
            grip_multiplier=keyframe.grip_multiplier,
        )

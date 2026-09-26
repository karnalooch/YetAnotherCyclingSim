"""Canonical road-physics profile for route-local queries.

This module is deliberately independent from Unreal rendering, terrain and PCG.
It represents the physical road in route-local coordinates:

- S: distance along the route;
- D: lateral displacement from the route reference line.

Continuous numeric fields are linearly interpolated between ordered samples.
Surface identifiers use left-closed/right-open semantics: the surface from the
sample at the beginning of an interval applies until the next exact sample.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .validation import (
    _clean_name,
    _closed_unit_interval,
    _finite,
    _non_negative,
    _positive,
)

__all__ = [
    "RoadPhysicsSample",
    "RoadPhysicsState",
    "RoadPhysicsTransitionLimits",
    "RoadPhysicsProfile",
]


@dataclass(frozen=True, slots=True)
class RoadPhysicsSample:
    """One authoritative road-physics sample at route distance S."""

    distance_m: float
    elevation_m: float
    grade_decimal: float
    horizontal_curvature_per_m: float
    vertical_curvature_per_m: float
    road_width_m: float
    bank_angle_rad: float
    surface_id: str
    wetness: float = 0.0
    roughness: float = 0.0

    def __post_init__(self):
        object.__setattr__(self, "distance_m", _non_negative(self.distance_m, "distance_m"))
        object.__setattr__(self, "elevation_m", _finite(self.elevation_m, "elevation_m"))
        object.__setattr__(self, "grade_decimal", _finite(self.grade_decimal, "grade_decimal"))
        object.__setattr__(
            self,
            "horizontal_curvature_per_m",
            _finite(self.horizontal_curvature_per_m, "horizontal_curvature_per_m"),
        )
        object.__setattr__(
            self,
            "vertical_curvature_per_m",
            _finite(self.vertical_curvature_per_m, "vertical_curvature_per_m"),
        )
        object.__setattr__(self, "road_width_m", _positive(self.road_width_m, "road_width_m"))
        bank = _finite(self.bank_angle_rad, "bank_angle_rad")
        if not -0.5 * math.pi < bank < 0.5 * math.pi:
            raise ValueError(
                f"bank_angle_rad must be strictly between -pi/2 and pi/2, got {bank}"
            )
        object.__setattr__(self, "bank_angle_rad", bank)
        object.__setattr__(self, "surface_id", _clean_name(self.surface_id, "surface_id"))
        object.__setattr__(self, "wetness", _closed_unit_interval(self.wetness, "wetness"))
        object.__setattr__(self, "roughness", _non_negative(self.roughness, "roughness"))


@dataclass(frozen=True, slots=True)
class RoadPhysicsState:
    """Interpolated physical-road state at route-local coordinates S/D."""

    distance_m: float
    lateral_position_m: float
    elevation_m: float
    grade_decimal: float
    horizontal_curvature_per_m: float
    vertical_curvature_per_m: float
    road_width_m: float
    bank_angle_rad: float
    surface_id: str
    wetness: float
    roughness: float

    @property
    def left_edge_m(self) -> float:
        return -0.5 * self.road_width_m

    @property
    def right_edge_m(self) -> float:
        return 0.5 * self.road_width_m


@dataclass(frozen=True, slots=True)
class RoadPhysicsTransitionLimits:
    """Explicit validation limits for rates of change along S.

    No hidden road-design thresholds live in RoadPhysicsProfile. A caller that
    wants authoring-quality continuity validation provides these limits.
    """

    max_abs_grade_change_per_m: float
    max_abs_horizontal_curvature_change_per_m2: float
    max_abs_bank_angle_change_rad_per_m: float

    def __post_init__(self):
        object.__setattr__(
            self,
            "max_abs_grade_change_per_m",
            _positive(self.max_abs_grade_change_per_m, "max_abs_grade_change_per_m"),
        )
        object.__setattr__(
            self,
            "max_abs_horizontal_curvature_change_per_m2",
            _positive(
                self.max_abs_horizontal_curvature_change_per_m2,
                "max_abs_horizontal_curvature_change_per_m2",
            ),
        )
        object.__setattr__(
            self,
            "max_abs_bank_angle_change_rad_per_m",
            _positive(
                self.max_abs_bank_angle_change_rad_per_m,
                "max_abs_bank_angle_change_rad_per_m",
            ),
        )


@dataclass(frozen=True, slots=True)
class RoadPhysicsProfile:
    """Ordered, deterministic physical-road samples covering one route."""

    name: str
    samples: tuple[RoadPhysicsSample, ...]

    def __post_init__(self):
        object.__setattr__(self, "name", _clean_name(self.name, "name"))
        if not isinstance(self.samples, tuple):
            raise ValueError(
                f"samples must be a tuple, got {type(self.samples).__name__}"
            )
        if len(self.samples) < 2:
            raise ValueError("samples must contain at least two RoadPhysicsSample values")
        for index, sample in enumerate(self.samples):
            if not isinstance(sample, RoadPhysicsSample):
                raise ValueError(
                    f"samples[{index}] must be a RoadPhysicsSample, "
                    f"got {type(sample).__name__}"
                )
        if self.samples[0].distance_m != 0.0:
            raise ValueError(
                f"samples[0].distance_m must be exactly 0.0, got "
                f"{self.samples[0].distance_m}"
            )
        for index in range(1, len(self.samples)):
            previous = self.samples[index - 1]
            current = self.samples[index]
            if current.distance_m <= previous.distance_m:
                raise ValueError(
                    "sample distances must be strictly increasing; "
                    f"samples[{index - 1}]={previous.distance_m}, "
                    f"samples[{index}]={current.distance_m}"
                )

    @property
    def total_length_m(self) -> float:
        return self.samples[-1].distance_m

    def state_at(
        self,
        distance_m: float,
        lateral_position_m: float = 0.0,
    ) -> RoadPhysicsState:
        """Return deterministic road state at S/D.

        distance_m must lie in [0, total_length_m]. lateral_position_m must lie
        inside the interpolated road width, inclusive of both road edges.
        """
        distance = _finite(distance_m, "distance_m")
        lateral = _finite(lateral_position_m, "lateral_position_m")
        if distance < 0.0:
            raise ValueError(f"distance_m must not be negative, got {distance}")
        if distance > self.total_length_m:
            raise ValueError(
                f"distance_m must not exceed total_length_m "
                f"({self.total_length_m}), got {distance}"
            )

        if distance == self.total_length_m:
            left = right = self.samples[-1]
            alpha = 0.0
        else:
            left = self.samples[0]
            right = self.samples[1]
            for index in range(1, len(self.samples)):
                candidate = self.samples[index]
                if distance < candidate.distance_m:
                    left = self.samples[index - 1]
                    right = candidate
                    break
                if distance == candidate.distance_m:
                    left = candidate
                    if index + 1 < len(self.samples):
                        right = self.samples[index + 1]
                    else:
                        right = candidate
                    break
            if left is right:
                alpha = 0.0
            else:
                alpha = (distance - left.distance_m) / (
                    right.distance_m - left.distance_m
                )

        def lerp(a: float, b: float) -> float:
            return a + (b - a) * alpha

        width = lerp(left.road_width_m, right.road_width_m)
        half_width = 0.5 * width
        if lateral < -half_width or lateral > half_width:
            raise ValueError(
                f"lateral_position_m {lateral} lies outside road bounds "
                f"[-{half_width}, {half_width}] at distance {distance}"
            )

        return RoadPhysicsState(
            distance_m=distance,
            lateral_position_m=lateral,
            elevation_m=lerp(left.elevation_m, right.elevation_m),
            grade_decimal=lerp(left.grade_decimal, right.grade_decimal),
            horizontal_curvature_per_m=lerp(
                left.horizontal_curvature_per_m,
                right.horizontal_curvature_per_m,
            ),
            vertical_curvature_per_m=lerp(
                left.vertical_curvature_per_m,
                right.vertical_curvature_per_m,
            ),
            road_width_m=width,
            bank_angle_rad=lerp(left.bank_angle_rad, right.bank_angle_rad),
            surface_id=left.surface_id,
            wetness=lerp(left.wetness, right.wetness),
            roughness=lerp(left.roughness, right.roughness),
        )

    def state_ahead(
        self,
        distance_m: float,
        look_ahead_m: float,
        lateral_position_m: float = 0.0,
    ) -> RoadPhysicsState:
        """Return state look_ahead_m ahead, clamped to the route end."""
        distance = _finite(distance_m, "distance_m")
        look_ahead = _non_negative(look_ahead_m, "look_ahead_m")
        if distance < 0.0 or distance > self.total_length_m:
            raise ValueError(
                f"distance_m must lie in [0, {self.total_length_m}], got {distance}"
            )
        target = min(self.total_length_m, distance + look_ahead)
        return self.state_at(target, lateral_position_m)

    def validate_transition_rates(
        self,
        limits: RoadPhysicsTransitionLimits,
    ) -> None:
        """Validate explicit authoring continuity limits.

        Raises ValueError on the first transition that exceeds a configured
        rate. Structural validity is already guaranteed by construction.
        """
        if not isinstance(limits, RoadPhysicsTransitionLimits):
            raise ValueError(
                "limits must be a RoadPhysicsTransitionLimits, got "
                f"{type(limits).__name__}"
            )
        for index in range(1, len(self.samples)):
            previous = self.samples[index - 1]
            current = self.samples[index]
            delta_s = current.distance_m - previous.distance_m

            grade_rate = abs(current.grade_decimal - previous.grade_decimal) / delta_s
            if grade_rate > limits.max_abs_grade_change_per_m:
                raise ValueError(
                    f"grade change rate exceeds limit between samples "
                    f"{index - 1} and {index}: {grade_rate}"
                )

            curvature_rate = abs(
                current.horizontal_curvature_per_m
                - previous.horizontal_curvature_per_m
            ) / delta_s
            if (
                curvature_rate
                > limits.max_abs_horizontal_curvature_change_per_m2
            ):
                raise ValueError(
                    f"horizontal curvature change rate exceeds limit between "
                    f"samples {index - 1} and {index}: {curvature_rate}"
                )

            bank_rate = abs(current.bank_angle_rad - previous.bank_angle_rad) / delta_s
            if bank_rate > limits.max_abs_bank_angle_change_rad_per_m:
                raise ValueError(
                    f"bank angle change rate exceeds limit between samples "
                    f"{index - 1} and {index}: {bank_rate}"
                )

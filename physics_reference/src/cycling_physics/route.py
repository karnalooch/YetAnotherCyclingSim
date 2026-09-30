"""Segmented route data contracts for the reference cycling physics.

A route is represented as an ordered sequence of straight road segments.
Each segment has a length measured along the road and a constant grade.
The route module does not yet integrate with step_simulation and contains
no GPX, UI or weather logic.
"""

import math
from dataclasses import dataclass

from .validation import _clean_name, _finite, _positive

__all__ = ["RouteSegment", "RouteProfile"]


@dataclass(frozen=True, slots=True)
class RouteSegment:
    """One straight road segment with a constant grade.

    length_m is the segment length measured along the road surface, not the
    horizontal distance. grade_decimal is the slope as rise over run and may
    be any finite value (no arbitrary grade limits). The name is stored
    stripped of surrounding whitespace and must not be empty.
    """

    name: str
    """Segment name. Must be non-empty after stripping whitespace."""

    length_m: float
    """Segment length along the road in metres (m). Must be finite and greater than zero."""

    grade_decimal: float
    """Segment grade as a decimal fraction of rise over run (unitless). Positive values climb; negative values descend. Must be finite."""

    def __post_init__(self):
        object.__setattr__(self, "name", _clean_name(self.name, "name"))
        object.__setattr__(self, "length_m", _positive(self.length_m, "length_m"))
        object.__setattr__(self, "grade_decimal", _finite(self.grade_decimal, "grade_decimal"))

    @property
    def elevation_change_m(self) -> float:
        """Vertical elevation change over the segment in metres (m).

        The value is length_m * sin(atan(grade_decimal)): positive for an
        ascent, negative for a descent and zero for a flat segment.
        """
        angle = math.atan(self.grade_decimal)
        return self.length_m * math.sin(angle)


@dataclass(frozen=True, slots=True)
class RouteProfile:
    """An ordered route made of at least one RouteSegment.

    Segments must be provided as a tuple and are traversed in order. The
    name is stored stripped of surrounding whitespace and must not be empty.
    """

    name: str
    """Route name. Must be non-empty after stripping whitespace."""

    segments: tuple[RouteSegment, ...]
    """Ordered route segments. Must contain at least one RouteSegment."""

    def __post_init__(self):
        object.__setattr__(self, "name", _clean_name(self.name, "name"))
        if not isinstance(self.segments, tuple):
            raise ValueError(
                f"segments must be a tuple, got {type(self.segments).__name__}"
            )
        if not self.segments:
            raise ValueError("segments must contain at least one RouteSegment")
        for index, segment in enumerate(self.segments):
            if not isinstance(segment, RouteSegment):
                raise ValueError(
                    f"segments[{index}] must be a RouteSegment, "
                    f"got {type(segment).__name__}"
                )

    @property
    def total_length_m(self) -> float:
        """Total route length along the road in metres (m)."""
        return sum(segment.length_m for segment in self.segments)

    @property
    def total_elevation_change_m(self) -> float:
        """Net elevation change over the whole route in metres (m)."""
        return sum(segment.elevation_change_m for segment in self.segments)

    @property
    def total_ascent_m(self) -> float:
        """Total climbed elevation in metres (m), summed over positive changes only."""
        return sum(
            segment.elevation_change_m
            for segment in self.segments
            if segment.elevation_change_m > 0.0
        )

    @property
    def total_descent_m(self) -> float:
        """Total descended elevation in metres (m), as a positive magnitude."""
        return sum(
            -segment.elevation_change_m
            for segment in self.segments
            if segment.elevation_change_m < 0.0
        )

    def segment_at_distance(self, distance_m: float) -> RouteSegment:
        """Return the RouteSegment containing a distance along the route.

        distance_m is the distance measured along the road from the start in
        metres (m). It must be finite and lie in the closed interval
        [0, total_length_m]; values outside raise ValueError.

        Boundary behaviour is exact: a distance of 0.0 returns the first
        segment, a distance exactly equal to the end of a segment returns the
        next segment, and a distance exactly equal to total_length_m returns
        the last segment.
        """
        distance = _finite(distance_m, "distance_m")
        if distance < 0.0:
            raise ValueError(f"distance_m must not be negative, got {distance}")
        total_length = self.total_length_m
        if distance > total_length:
            raise ValueError(
                f"distance_m must not exceed the total route length "
                f"({total_length} m), got {distance}"
            )
        running_length = 0.0
        for segment in self.segments:
            running_length += segment.length_m
            if distance < running_length:
                return segment
        return self.segments[-1]

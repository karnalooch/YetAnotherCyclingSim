"""Sample route data for the reference cycling physics.

Defines the first example route as a RouteProfile built from RouteSegment
records. The sample route is deterministic and contains no weather, GPX or
UI logic.
"""

from .route import RouteProfile, RouteSegment

__all__ = ["ALPINE_JOURNEY"]

ALPINE_JOURNEY = RouteProfile(
    name="Alpine Journey",
    segments=(
        RouteSegment(name="Village Start", length_m=1000.0, grade_decimal=0.005),
        RouteSegment(name="River Descent", length_m=1200.0, grade_decimal=-0.015),
        RouteSegment(name="Meadow Rollers", length_m=1500.0, grade_decimal=0.015),
        RouteSegment(name="Forest Approach", length_m=1000.0, grade_decimal=0.025),
        RouteSegment(name="Challenge Climb", length_m=1500.0, grade_decimal=0.065),
        RouteSegment(name="Mountain Shelf", length_m=1000.0, grade_decimal=-0.010),
        RouteSegment(name="High Valley Descent", length_m=1500.0, grade_decimal=-0.030),
        RouteSegment(name="Lakeside Finish", length_m=1300.0, grade_decimal=0.005),
    ),
)

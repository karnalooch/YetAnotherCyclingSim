"""Sample route data for the reference cycling physics.

Defines the first example route as a RouteProfile built from RouteSegment
records. The sample route is deterministic and contains no weather, GPX or
UI logic.
"""

from .route import RouteProfile, RouteSegment
from .weather import WeatherKeyframe, WeatherProfile

__all__ = ["ALPINE_JOURNEY", "ALPINE_WEATHER"]

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

ALPINE_WEATHER = WeatherProfile(
    name="Alpine Journey Scripted Weather",
    keyframes=(
        WeatherKeyframe(
            distance_m=0.0,
            wind_speed_mps=-0.5,
            air_density_kg_m3=1.225,
            surface_wetness=0.0,
            rolling_resistance_multiplier=1.00,
            grip_multiplier=1.00,
        ),
        WeatherKeyframe(
            distance_m=2200.0,
            wind_speed_mps=0.5,
            air_density_kg_m3=1.220,
            surface_wetness=0.0,
            rolling_resistance_multiplier=1.00,
            grip_multiplier=1.00,
        ),
        WeatherKeyframe(
            distance_m=3700.0,
            wind_speed_mps=1.5,
            air_density_kg_m3=1.215,
            surface_wetness=0.2,
            rolling_resistance_multiplier=1.02,
            grip_multiplier=0.95,
        ),
        WeatherKeyframe(
            distance_m=4700.0,
            wind_speed_mps=2.5,
            air_density_kg_m3=1.200,
            surface_wetness=0.8,
            rolling_resistance_multiplier=1.08,
            grip_multiplier=0.80,
        ),
        WeatherKeyframe(
            distance_m=6200.0,
            wind_speed_mps=2.0,
            air_density_kg_m3=1.180,
            surface_wetness=1.0,
            rolling_resistance_multiplier=1.12,
            grip_multiplier=0.75,
        ),
        WeatherKeyframe(
            distance_m=7200.0,
            wind_speed_mps=-1.0,
            air_density_kg_m3=1.170,
            surface_wetness=0.6,
            rolling_resistance_multiplier=1.06,
            grip_multiplier=0.85,
        ),
        WeatherKeyframe(
            distance_m=8700.0,
            wind_speed_mps=-2.0,
            air_density_kg_m3=1.160,
            surface_wetness=0.2,
            rolling_resistance_multiplier=1.02,
            grip_multiplier=0.95,
        ),
        WeatherKeyframe(
            distance_m=10000.0,
            wind_speed_mps=-1.0,
            air_density_kg_m3=1.150,
            surface_wetness=0.0,
            rolling_resistance_multiplier=1.00,
            grip_multiplier=1.00,
        ),
    ),
)

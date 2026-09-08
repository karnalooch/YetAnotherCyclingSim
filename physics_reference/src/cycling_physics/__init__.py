"""Reference cycling physics package for the YetAnotherCyclingSim project."""

from .cornering import (
    Corner,
    CornerProfile,
    corner_grip_usage,
    effective_friction_coefficient,
    maximum_corner_speed_mps,
)
from .model import (
    STANDARD_GRAVITY_MPS2,
    Environment,
    RiderInput,
    RiderParameters,
    SimulationState,
    aerodynamic_force_n,
    gravitational_force_n,
    road_angle_rad,
    rolling_resistance_force_n,
    step_simulation,
    total_resistance_force_n,
)
from .route import RouteProfile, RouteSegment
from .sample_routes import ALPINE_CORNERS, ALPINE_JOURNEY, ALPINE_WEATHER
from .weather import WeatherKeyframe, WeatherProfile

__all__ = [
    "STANDARD_GRAVITY_MPS2",
    "RiderParameters",
    "Environment",
    "RiderInput",
    "SimulationState",
    "RouteSegment",
    "RouteProfile",
    "WeatherKeyframe",
    "WeatherProfile",
    "ALPINE_JOURNEY",
    "ALPINE_WEATHER",
    "ALPINE_CORNERS",
    "Corner",
    "CornerProfile",
    "effective_friction_coefficient",
    "maximum_corner_speed_mps",
    "corner_grip_usage",
    "road_angle_rad",
    "gravitational_force_n",
    "rolling_resistance_force_n",
    "aerodynamic_force_n",
    "total_resistance_force_n",
    "step_simulation",
]

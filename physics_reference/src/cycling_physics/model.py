"""Deterministic reference cycling physics model.

This module defines the data contracts of the reference cycling physics:
immutable input and output records expressed in SI units. The equations of
motion are not implemented yet. Reference results are verified here in
Python before being ported to the Unreal Engine 5 C++ implementation.
"""

import math
from dataclasses import dataclass

STANDARD_GRAVITY_MPS2 = 9.80665
"""Standard gravitational acceleration on Earth in metres per second squared (m/s^2)."""

__all__ = [
    "STANDARD_GRAVITY_MPS2",
    "RiderParameters",
    "Environment",
    "RiderInput",
    "SimulationState",
    "road_angle_rad",
    "gravitational_force_n",
    "rolling_resistance_force_n",
    "aerodynamic_force_n",
]


def _require_real_number(value, field_name):
    """Return value as a float, rejecting non-real or non-numeric values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            f"{field_name} must be a real number, got {value!r} "
            f"of type {type(value).__name__}"
        )
    return float(value)


def _finite(value, field_name):
    """Return value as a finite float."""
    result = _require_real_number(value, field_name)
    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be a finite number, got {result}")
    return result


def _positive(value, field_name):
    """Return a validated float strictly greater than zero."""
    result = _finite(value, field_name)
    if result <= 0.0:
        raise ValueError(f"{field_name} must be greater than zero, got {result}")
    return result


def _non_negative(value, field_name):
    """Return a validated float greater than or equal to zero."""
    result = _finite(value, field_name)
    if result < 0.0:
        raise ValueError(f"{field_name} must not be negative, got {result}")
    return result


def _efficiency(value, field_name):
    """Return a validated float inside the open-closed interval (0, 1]."""
    result = _finite(value, field_name)
    if not 0.0 < result <= 1.0:
        raise ValueError(f"{field_name} must be in the interval (0, 1], got {result}")
    return result


@dataclass(frozen=True, slots=True)
class RiderParameters:
    """Rider and bicycle parameters used by the physics model.

    All fields are stored as floats in SI units and must be finite. Masses,
    drag area and efficiency bounds are validated at construction time.
    """

    rider_mass_kg: float
    """Total mass of the rider in kilograms (kg). Must be greater than zero."""

    bike_mass_kg: float
    """Total mass of the bicycle in kilograms (kg). Must be greater than zero."""

    cda_m2: float
    """Aerodynamic drag area (CdA, C_d times frontal area A) in square metres (m^2). Must be greater than zero."""

    rolling_resistance_coefficient: float
    """Dimensionless rolling resistance coefficient (Crr). Must not be negative; zero is allowed."""

    drivetrain_efficiency: float
    """Dimensionless drivetrain efficiency fraction. Must be in the interval (0, 1]."""

    def __post_init__(self):
        object.__setattr__(self, "rider_mass_kg", _positive(self.rider_mass_kg, "rider_mass_kg"))
        object.__setattr__(self, "bike_mass_kg", _positive(self.bike_mass_kg, "bike_mass_kg"))
        object.__setattr__(self, "cda_m2", _positive(self.cda_m2, "cda_m2"))
        object.__setattr__(
            self,
            "rolling_resistance_coefficient",
            _non_negative(self.rolling_resistance_coefficient, "rolling_resistance_coefficient"),
        )
        object.__setattr__(self, "drivetrain_efficiency", _efficiency(self.drivetrain_efficiency, "drivetrain_efficiency"))

    @property
    def total_mass_kg(self):
        """Combined mass of the rider and the bicycle in kilograms (kg)."""
        return self.rider_mass_kg + self.bike_mass_kg


@dataclass(frozen=True, slots=True)
class Environment:
    """Environmental conditions along the route, in SI units.

    All fields are stored as floats and must be finite. Grade and wind may be
    negative; air density must be greater than zero.
    """

    grade_decimal: float
    """Road grade as a decimal fraction of the slope (unitless), e.g. 0.08 means 8 %. Positive values are ascents; negative values are descents."""

    wind_speed_mps: float
    """Wind speed in metres per second (m/s) relative to the ground along the direction of travel. Positive values are headwinds (oppose motion); negative values are tailwinds (assist motion)."""

    air_density_kg_m3: float
    """Air density in kilograms per cubic metre (kg/m^3). Must be greater than zero."""

    def __post_init__(self):
        object.__setattr__(self, "grade_decimal", _finite(self.grade_decimal, "grade_decimal"))
        object.__setattr__(self, "wind_speed_mps", _finite(self.wind_speed_mps, "wind_speed_mps"))
        object.__setattr__(self, "air_density_kg_m3", _positive(self.air_density_kg_m3, "air_density_kg_m3"))


@dataclass(frozen=True, slots=True)
class RiderInput:
    """Rider control input for one simulation step.

    Both fields are stored as floats and must be finite and non-negative.
    """

    power_w: float
    """Mechanical power delivered by the rider to the drivetrain in watts (W). Must not be negative; zero is allowed."""

    cadence_rpm: float
    """Pedalling cadence in revolutions per minute (rpm). Must not be negative; zero is allowed."""

    def __post_init__(self):
        object.__setattr__(self, "power_w", _non_negative(self.power_w, "power_w"))
        object.__setattr__(self, "cadence_rpm", _non_negative(self.cadence_rpm, "cadence_rpm"))


@dataclass(frozen=True, slots=True)
class SimulationState:
    """Simulation output state, in SI units.

    All fields are stored as floats and must be finite and non-negative.
    """

    speed_mps: float
    """Forward ground speed in metres per second (m/s). Must not be negative; zero is allowed."""

    distance_m: float
    """Distance travelled along the route in metres (m). Must not be negative; zero is allowed."""

    elapsed_time_s: float
    """Elapsed simulation time in seconds (s). Must not be negative; zero is allowed."""

    def __post_init__(self):
        object.__setattr__(self, "speed_mps", _non_negative(self.speed_mps, "speed_mps"))
        object.__setattr__(self, "distance_m", _non_negative(self.distance_m, "distance_m"))
        object.__setattr__(self, "elapsed_time_s", _non_negative(self.elapsed_time_s, "elapsed_time_s"))


def road_angle_rad(grade_decimal):
    """Convert a road grade to the road angle in radians (rad).

    grade_decimal is the road slope as a decimal fraction of rise over run
    (unitless), e.g. 0.08 means an 8 % gradient. The returned angle is
    arctan(grade_decimal): positive for ascents, negative for descents and
    zero for a flat road.
    """
    grade = _finite(grade_decimal, "grade_decimal")
    return math.atan(grade)


def gravitational_force_n(rider, environment):
    """Compute the gravitational force component along the road, in newtons (N).

    rider must be a RiderParameters record and environment an Environment
    record. The force uses the combined rider and bicycle mass and the road
    angle derived from environment.grade_decimal. A positive value opposes
    forward motion on an ascent, a negative value assists forward motion on
    a descent and the value is zero on a flat road.
    """
    angle = road_angle_rad(environment.grade_decimal)
    return rider.total_mass_kg * STANDARD_GRAVITY_MPS2 * math.sin(angle)


def rolling_resistance_force_n(rider, environment):
    """Compute the rolling resistance force, in newtons (N).

    rider must be a RiderParameters record and environment an Environment
    record. The force uses rider.rolling_resistance_coefficient, the
    combined mass and the component of weight perpendicular to the road
    (standard gravity times cos of the road angle). The result is always
    non-negative and opposes forward motion.
    """
    angle = road_angle_rad(environment.grade_decimal)
    normal_load = rider.total_mass_kg * STANDARD_GRAVITY_MPS2 * math.cos(angle)
    return rider.rolling_resistance_coefficient * normal_load


def aerodynamic_force_n(rider, environment, speed_mps):
    """Compute the aerodynamic drag force, in newtons (N).

    rider must be a RiderParameters record, environment an Environment
    record and speed_mps the forward ground speed in metres per second
    (m/s), which must be finite and non-negative. The relative air speed
    along the direction of travel is speed_mps + environment.wind_speed_mps,
    where a positive wind_speed_mps is a headwind and a negative value is a
    tailwind. The signed drag force is
    0.5 * rho * CdA * relative_air_speed * abs(relative_air_speed). A
    positive result opposes forward motion; a negative result means that a
    strong tailwind pushes the rider forward.
    """
    speed = _non_negative(speed_mps, "speed_mps")
    relative_air_speed = speed + environment.wind_speed_mps
    return (
        0.5
        * environment.air_density_kg_m3
        * rider.cda_m2
        * relative_air_speed
        * abs(relative_air_speed)
    )

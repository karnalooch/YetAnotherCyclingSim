"""Deterministic reference cycling physics model.

This module defines the data contracts of the reference cycling physics:
immutable input and output records expressed in SI units. The equations of
motion are not implemented yet. Reference results are verified here in
Python before being ported to the Unreal Engine 5 C++ implementation.
"""

import math
from dataclasses import dataclass

from .validation import (
    _efficiency,
    _finite,
    _non_negative,
    _positive,
)

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
    "total_resistance_force_n",
    "step_simulation",
]


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
    def total_mass_kg(self) -> float:
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


def road_angle_rad(grade_decimal: float) -> float:
    """Convert a road grade to the road angle in radians (rad).

    grade_decimal is the road slope as a decimal fraction of rise over run
    (unitless), e.g. 0.08 means an 8 % gradient. The returned angle is
    arctan(grade_decimal): positive for ascents, negative for descents and
    zero for a flat road.
    """
    grade = _finite(grade_decimal, "grade_decimal")
    return math.atan(grade)


def gravitational_force_n(rider: RiderParameters, environment: Environment) -> float:
    """Compute the gravitational force component along the road, in newtons (N).

    rider must be a RiderParameters record and environment an Environment
    record. The force uses the combined rider and bicycle mass and the road
    angle derived from environment.grade_decimal. A positive value opposes
    forward motion on an ascent, a negative value assists forward motion on
    a descent and the value is zero on a flat road.
    """
    angle = road_angle_rad(environment.grade_decimal)
    return rider.total_mass_kg * STANDARD_GRAVITY_MPS2 * math.sin(angle)


def rolling_resistance_force_n(rider: RiderParameters, environment: Environment) -> float:
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


def aerodynamic_force_n(
    rider: RiderParameters,
    environment: Environment,
    speed_mps: float,
) -> float:
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


def total_resistance_force_n(
    rider: RiderParameters,
    environment: Environment,
    speed_mps: float,
) -> float:
    """Compute the total resistive force along the road, in newtons (N).

    rider must be a RiderParameters record, environment an Environment
    record and speed_mps the forward ground speed in metres per second
    (m/s), which must be finite and non-negative. The result is the sum of
    the gravitational force, the rolling resistance force and the
    aerodynamic drag force. A positive value opposes forward motion; a
    negative value propels the rider forward, for example on a steep
    descent or with a very strong tailwind. The result is never clamped to
    zero.
    """
    return (
        gravitational_force_n(rider, environment)
        + rolling_resistance_force_n(rider, environment)
        + aerodynamic_force_n(rider, environment, speed_mps)
    )


def step_simulation(
    rider: RiderParameters,
    environment: Environment,
    rider_input: RiderInput,
    state: SimulationState,
    dt_s: float,
) -> SimulationState:
    """Advance the simulation by one deterministic step using an energy balance.

    rider defines the rider and bicycle parameters, environment the
    environmental conditions, rider_input the control input for the step,
    state the current simulation state and dt_s the step duration in seconds
    (s), which must be a finite number greater than zero.

    The step uses an energy balance:
    - initial_energy_j = 0.5 * m * v^2 (kinetic energy);
    - drive_work_j = power_w * drivetrain_efficiency * dt_s.

    A deterministic predictor first estimates the effect of the resistance
    forces at the current speed, adds the drive energy to the predicted
    speed, then recomputes the resistance force at the average of the
    current and the predicted speed to estimate the resistance work over the
    step. Positive resistance work removes energy; negative resistance work
    (for example on a descent) adds energy. The final speed is derived from
    the remaining energy and is never negative.

    cadence_rpm is part of the rider input but does not yet affect the
    equation of motion directly; no cadence-power dependency is assumed.

    The input state is not modified; a new immutable SimulationState is
    returned.
    """
    dt = _positive(dt_s, "dt_s")
    total_mass = rider.total_mass_kg

    current_speed = state.speed_mps
    initial_energy_j = 0.5 * total_mass * current_speed ** 2
    drive_work_j = rider_input.power_w * rider.drivetrain_efficiency * dt

    resistance_force_n = total_resistance_force_n(rider, environment, current_speed)
    external_acceleration_mps2 = -resistance_force_n / total_mass
    external_predicted_speed_mps = max(0.0, current_speed + external_acceleration_mps2 * dt)
    predicted_speed_mps = math.sqrt(
        max(0.0, external_predicted_speed_mps ** 2 + 2.0 * drive_work_j / total_mass)
    )
    estimated_average_speed_mps = 0.5 * (current_speed + predicted_speed_mps)

    average_resistance_force_n = total_resistance_force_n(rider, environment, estimated_average_speed_mps)
    resistance_work_j = average_resistance_force_n * estimated_average_speed_mps * dt

    final_energy_j = max(0.0, initial_energy_j + drive_work_j - resistance_work_j)
    new_speed_mps = math.sqrt(2.0 * final_energy_j / total_mass)

    distance_delta_m = 0.5 * (current_speed + new_speed_mps) * dt
    new_state = SimulationState(
        speed_mps=new_speed_mps,
        distance_m=state.distance_m + distance_delta_m,
        elapsed_time_s=state.elapsed_time_s + dt,
    )
    return new_state

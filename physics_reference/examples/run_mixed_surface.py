"""Synthetic asphalt -> gravel -> asphalt reference exercise, not a real ride.

Every coefficient and the 300 m route below is an arbitrary test fixture, not
surveyed data, a calibrated tyre model or a production gravel preset. This
example composes existing APIs; it does not alter the integrator, implement
cornering, import roads, or activate mixed-surface riding in Unreal.

Run from the repository root with:
    PYTHONPATH=physics_reference/src python physics_reference/examples/run_mixed_surface.py
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from typing import Mapping

from cycling_physics.grip_policy import SurfaceGripPolicy, SurfaceGripRule
from cycling_physics.model import (
    Environment,
    RiderInput,
    RiderParameters,
    SimulationState,
    step_simulation,
)
from cycling_physics.road_physics import RoadPhysicsProfile, RoadPhysicsSample

FIXTURE_NOTICE = "SYNTHETIC_ONLY_NOT_CALIBRATED_NOT_A_REAL_ROUTE"
FIXED_STEP_S = 0.05


def make_profile(wetness: float = 0.0) -> RoadPhysicsProfile:
    return RoadPhysicsProfile(
        name="Synthetic mixed-surface reference",
        samples=tuple(
            RoadPhysicsSample(
                distance_m=distance,
                elevation_m=0.0,
                grade_decimal=0.0,
                horizontal_curvature_per_m=0.0,
                vertical_curvature_per_m=0.0,
                road_width_m=4.0,
                left_cross_slope_angle_rad=0.0,
                right_cross_slope_angle_rad=0.0,
                surface_id=surface,
                wetness=wetness,
            )
            for distance, surface in (
                (0.0, "asphalt"),
                (100.0, "gravel"),
                (200.0, "asphalt"),
                (300.0, "asphalt"),
            )
        ),
    )


def make_grip_policy() -> SurfaceGripPolicy:
    return SurfaceGripPolicy(
        name="Synthetic comparison only",
        rules=(
            SurfaceGripRule("asphalt", 1.0, 0.8),
            SurfaceGripRule("gravel", 0.75, 0.5),
        ),
    )


def environment_at(
    profile: RoadPhysicsProfile,
    state: SimulationState,
    ambient: Environment,
    grip_policy: SurfaceGripPolicy,
    rolling_multipliers: Mapping[str, float],
) -> tuple[str, Environment]:
    """Resolve the current contact surface, not a future look-ahead surface.

    Pass an unresolved ambient environment each time, not the previous return.
    Surface rolling resistance composes with the ambient/weather multiplier.
    Missing policy fails explicitly; unknown surface never becomes asphalt.
    Existing constructors validate wetness and positive finite multipliers.
    """
    road = profile.state_at(state.distance_m, state.lateral_position_m)
    if road.surface_id not in rolling_multipliers:
        raise ValueError(f"Missing rolling policy for surface {road.surface_id!r}")
    grip = grip_policy.resolve(road.surface_id, road.wetness)
    return road.surface_id, replace(
        ambient,
        grade_decimal=road.grade_decimal,
        surface_wetness=road.wetness,
        rolling_resistance_multiplier=(
            ambient.rolling_resistance_multiplier * rolling_multipliers[road.surface_id]
        ),
        grip_multiplier=ambient.grip_multiplier * grip.grip_multiplier,
    )


def run_reference(batch_size: int = 1) -> dict:
    """Complete the fixture using unchanged, fixed-size reference substeps.

    Batching groups substeps only; this is not a UE frame-timing benchmark.
    Surface boundaries use the existing current-S sampling convention: the
    next substep uses the newly entered surface. The final substep may pass
    the endpoint slightly; no distance or velocity is reset to disguise that.
    Grip is reported independently; this straight-line example has no corner
    or braking demand and must not claim it proves gravel cornering.
    """
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")
    profile = make_profile()
    grip_policy = make_grip_policy()
    rolling = {"asphalt": 1.0, "gravel": 2.0}
    rider = RiderParameters(75.0, 10.0, 0.4, 0.004, 0.97)
    ambient = Environment(0.0, 0.0, 1.225)
    rider_input = RiderInput(250.0, 90.0)
    state = SimulationState(6.0, 0.0, 0.0)
    states = [asdict(state)]
    transitions = []
    previous_surface = None
    steps = 0
    while state.distance_m < profile.total_length_m:
        for _ in range(batch_size):
            if state.distance_m >= profile.total_length_m:
                break
            if steps >= 20000:
                raise RuntimeError("Synthetic reference exceeded its step budget")
            surface, environment = environment_at(
                profile, state, ambient, grip_policy, rolling
            )
            if surface != previous_surface:
                transitions.append(
                    {
                        "surface_id": surface,
                        "state": asdict(state),
                        "rolling_multiplier": environment.rolling_resistance_multiplier,
                        "grip_multiplier": environment.grip_multiplier,
                    }
                )
                previous_surface = surface
            state = step_simulation(
                rider, environment, rider_input, state, FIXED_STEP_S
            )
            states.append(asdict(state))
            steps += 1
    return {
        "notice": FIXTURE_NOTICE,
        "fixed_step_s": FIXED_STEP_S,
        "route_length_m": profile.total_length_m,
        "steps": steps,
        "transitions": transitions,
        "final_state": asdict(state),
        "states": states,
    }


def main() -> None:
    report = run_reference()
    report.pop("states")
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

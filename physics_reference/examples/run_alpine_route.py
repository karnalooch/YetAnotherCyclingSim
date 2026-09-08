"""Demo ride along the sample Alpine Journey route with scripted weather.

Rides the full 10 km ALPINE_JOURNEY at 20 Hz with the sample power plan and
the ALPINE_WEATHER scripted profile. In every step the current route segment
is resolved from the travelled distance and the Environment is taken from
ALPINE_WEATHER.environment_at_distance. An entry line is printed whenever a
new segment begins and a summary is printed at the finish. Uses only the
public cycling_physics API.
"""

from cycling_physics import (
    ALPINE_JOURNEY,
    ALPINE_WEATHER,
    RiderInput,
    RiderParameters,
    SimulationState,
    step_simulation,
)

RIDER = RiderParameters(
    rider_mass_kg=75.0,
    bike_mass_kg=8.5,
    cda_m2=0.32,
    rolling_resistance_coefficient=0.004,
    drivetrain_efficiency=0.97,
)

DT_S = 0.05
MAX_TIME_S = 3600.0

POWER_PLAN = {
    "Village Start": (220.0, 90.0),
    "River Descent": (140.0, 80.0),
    "Meadow Rollers": (230.0, 90.0),
    "Forest Approach": (250.0, 88.0),
    "Challenge Climb": (300.0, 82.0),
    "Mountain Shelf": (200.0, 88.0),
    "High Valley Descent": (0.0, 0.0),
    "Lakeside Finish": (240.0, 92.0),
}


def segment_index_at(distance_m):
    """Return the profile segment index for a distance inside the route."""
    for index, segment in enumerate(ALPINE_JOURNEY.segments):
        if ALPINE_JOURNEY.segment_at_distance(distance_m) is segment:
            return index
    raise RuntimeError("distance beyond the end of the route")


def main():
    state = SimulationState(speed_mps=0.0, distance_m=0.0, elapsed_time_s=0.0)
    current_index = None

    print(
        "segment            distance_m  grade_%  speed_kmh  time_s  "
        "wind_mps  wetness  grip"
    )

    while (
        state.distance_m < ALPINE_JOURNEY.total_length_m
        and state.elapsed_time_s < MAX_TIME_S
    ):
        index = segment_index_at(state.distance_m)
        segment = ALPINE_JOURNEY.segments[index]
        environment = ALPINE_WEATHER.environment_at_distance(
            state.distance_m,
            segment.grade_decimal,
        )
        if index != current_index:
            print(
                f"{segment.name:<18s} {state.distance_m:9.1f} "
                f"{segment.grade_decimal * 100.0:7.2f} "
                f"{state.speed_mps * 3.6:8.2f} {state.elapsed_time_s:7.1f} "
                f"{environment.wind_speed_mps:8.2f} "
                f"{environment.surface_wetness:7.2f} "
                f"{environment.grip_multiplier:6.2f}"
            )
            current_index = index

        power_w, cadence_rpm = POWER_PLAN[segment.name]
        rider_input = RiderInput(power_w=power_w, cadence_rpm=cadence_rpm)
        state = step_simulation(RIDER, environment, rider_input, state, DT_S)

    if state.distance_m < ALPINE_JOURNEY.total_length_m:
        raise RuntimeError(
            f"route not finished within {MAX_TIME_S:.0f} seconds"
        )

    average_speed_kmh = state.distance_m / state.elapsed_time_s * 3.6
    print()
    print("Finish")
    print(f"  time:              {state.elapsed_time_s:8.2f} s")
    print(f"  distance:          {state.distance_m:8.1f} m")
    print(f"  average speed:     {average_speed_kmh:8.2f} km/h")
    print(f"  final speed:       {state.speed_mps * 3.6:8.2f} km/h")
    print(f"  total ascent:      {ALPINE_JOURNEY.total_ascent_m:8.1f} m")
    print(f"  total descent:     {ALPINE_JOURNEY.total_descent_m:8.1f} m")


if __name__ == "__main__":
    main()

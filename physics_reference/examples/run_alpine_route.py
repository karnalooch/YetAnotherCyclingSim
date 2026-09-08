"""Demo ride along the sample Alpine Journey route.

Rides the full 10 km ALPINE_JOURNEY at 20 Hz with the sample power plan,
prints an entry line whenever a new segment begins and prints a summary at
the finish. Uses only the public cycling_physics API.
"""

from cycling_physics import (
    ALPINE_JOURNEY,
    Environment,
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

AIR_DENSITY_KG_M3 = 1.225
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
        "segment            distance_m  grade_%  speed_kmh  time_s"
    )

    while (
        state.distance_m < ALPINE_JOURNEY.total_length_m
        and state.elapsed_time_s < MAX_TIME_S
    ):
        index = segment_index_at(state.distance_m)
        if index != current_index:
            segment = ALPINE_JOURNEY.segments[index]
            print(
                f"{segment.name:<18s} {state.distance_m:10.1f} "
                f"{segment.grade_decimal * 100.0:8.2f} "
                f"{state.speed_mps * 3.6:10.2f} {state.elapsed_time_s:7.1f}"
            )
            current_index = index

        segment = ALPINE_JOURNEY.segments[index]
        power_w, cadence_rpm = POWER_PLAN[segment.name]
        environment = Environment(
            grade_decimal=segment.grade_decimal,
            wind_speed_mps=0.0,
            air_density_kg_m3=AIR_DENSITY_KG_M3,
        )
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

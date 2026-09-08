"""Demo ride for the reference cycling physics model.

Runs a fixed 60 second ride at 20 Hz (dt = 0.05 s) through four phases and
prints the state every 5 seconds together with a final summary. Uses only
the public cycling_physics API.
"""

from cycling_physics import (
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
STEPS_PER_SECOND = int(1.0 / DT_S)
REPORT_EVERY_S = 5.0
REPORT_EVERY_STEPS = int(REPORT_EVERY_S * STEPS_PER_SECOND)

PHASES = [
    {
        "name": "Flat start",
        "duration_s": 15.0,
        "grade_decimal": 0.0,
        "wind_speed_mps": 0.0,
        "power_w": 220.0,
        "cadence_rpm": 90.0,
    },
    {
        "name": "Climb",
        "duration_s": 20.0,
        "grade_decimal": 0.06,
        "wind_speed_mps": 1.0,
        "power_w": 280.0,
        "cadence_rpm": 85.0,
    },
    {
        "name": "Descent coasting",
        "duration_s": 10.0,
        "grade_decimal": -0.05,
        "wind_speed_mps": 0.0,
        "power_w": 0.0,
        "cadence_rpm": 0.0,
    },
    {
        "name": "Descent attack",
        "duration_s": 15.0,
        "grade_decimal": -0.02,
        "wind_speed_mps": -1.0,
        "power_w": 320.0,
        "cadence_rpm": 95.0,
    },
]


def print_row(time_s, phase, power_w, cadence_rpm, grade_percent, speed_kmh, distance_m):
    print(
        f"{time_s:6.1f}  {phase:<16s} "
        f"{power_w:7.1f} {cadence_rpm:10.1f} "
        f"{grade_percent:7.2f} {speed_kmh:10.2f} {distance_m:10.1f}"
    )


def main():
    print(
        "time_s  phase             power_w  cadence_rpm  grade_%  "
        "speed_kmh  distance_m"
    )

    state = SimulationState(speed_mps=0.0, distance_m=0.0, elapsed_time_s=0.0)
    total_steps = 0

    for phase in PHASES:
        steps_in_phase = int(phase["duration_s"] * STEPS_PER_SECOND)
        environment = Environment(
            grade_decimal=phase["grade_decimal"],
            wind_speed_mps=phase["wind_speed_mps"],
            air_density_kg_m3=AIR_DENSITY_KG_M3,
        )
        rider_input = RiderInput(
            power_w=phase["power_w"],
            cadence_rpm=phase["cadence_rpm"],
        )
        for _ in range(steps_in_phase):
            state = step_simulation(RIDER, environment, rider_input, state, DT_S)
            total_steps += 1
            if total_steps % REPORT_EVERY_STEPS == 0:
                print_row(
                    time_s=state.elapsed_time_s,
                    phase=phase["name"],
                    power_w=phase["power_w"],
                    cadence_rpm=phase["cadence_rpm"],
                    grade_percent=phase["grade_decimal"] * 100.0,
                    speed_kmh=state.speed_mps * 3.6,
                    distance_m=state.distance_m,
                )

    total_time_s = state.elapsed_time_s
    average_speed_mps = state.distance_m / total_time_s
    print()
    print("Summary")
    print(f"  total time:     {total_time_s:9.2f} s")
    print(f"  total distance: {state.distance_m:9.1f} m")
    print(f"  final speed:    {state.speed_mps * 3.6:9.2f} km/h")
    print(f"  average speed:  {average_speed_mps * 3.6:9.2f} km/h  (distance / time)")


if __name__ == "__main__":
    main()

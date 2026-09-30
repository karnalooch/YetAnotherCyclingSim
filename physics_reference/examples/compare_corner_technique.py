"""Compare a baseline power plan with a corner-aware technique plan.

Rides ALPINE_JOURNEY twice with ALPINE_WEATHER at 20 Hz: once with the plain
POWER_PLAN (baseline) and once with a corner technique plan that releases
power before and during each corner and accelerates on the exit. The
technique plan modifies only the RiderInput; geometry, weather and the
simulation state are never altered directly. Both rides are deterministic.
"""

from cycling_physics import (
    ALPINE_CORNERS,
    ALPINE_JOURNEY,
    ALPINE_WEATHER,
    CORNER_PHASE_APEX,
    CORNER_PHASE_APPROACH,
    CORNER_PHASE_ENTRY,
    CORNER_PHASE_EXIT,
    CORNER_PHASE_OUTSIDE,
    CornerTechniqueSample,
    RiderInput,
    RiderParameters,
    SimulationState,
    assess_corner_technique,
    corner_grip_usage,
    corner_phase_at_distance,
    step_simulation,
    summarize_corner_technique,
)

APPROACH_LENGTH_M = 100.0
BASE_FRICTION_COEFFICIENT = 0.8
TAIL_APPROACH_DISTANCE_M = 15.0
EXIT_MIN_POWER_W = 250.0
EXIT_MIN_CADENCE_RPM = 90.0

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


def _technique_power_cadence(corner, phase, distance_m, base_power_w, base_cadence_rpm):
    """Return the technique (power_w, cadence_rpm) for a phase at a distance.

    Far approach keeps 100% of base power and cadence; the last 15 m of the
    approach drop to 20% power and 70% cadence; entry is 50%/75%; apex is
    30%/60%. On the exit the power is base_power_w * 1.15 but at least 250 W
    and the cadence is the base cadence but at least 90 rpm. The exit
    minimums apply only in the exit phase.
    """
    if phase == CORNER_PHASE_APPROACH:
        if distance_m >= corner.start_distance_m - TAIL_APPROACH_DISTANCE_M:
            return base_power_w * 0.20, base_cadence_rpm * 0.70
        return base_power_w, base_cadence_rpm
    if phase == CORNER_PHASE_ENTRY:
        return base_power_w * 0.50, base_cadence_rpm * 0.75
    if phase == CORNER_PHASE_APEX:
        return base_power_w * 0.30, base_cadence_rpm * 0.60
    if phase == CORNER_PHASE_EXIT:
        return max(base_power_w * 1.15, EXIT_MIN_POWER_W), max(
            base_cadence_rpm,
            EXIT_MIN_CADENCE_RPM,
        )
    return base_power_w, base_cadence_rpm


def _current_corner_phase(distance_m):
    """Return the (corner, phase) active at a distance, or None."""
    for corner in ALPINE_CORNERS.corners:
        phase = corner_phase_at_distance(corner, distance_m, APPROACH_LENGTH_M)
        if phase != CORNER_PHASE_OUTSIDE:
            return corner, phase
    return None


def make_rider_input(segment_name, distance_m, use_technique):
    """Build the RiderInput for a segment at a distance.

    Without use_technique the input is exactly POWER_PLAN. With the
    technique plan the base power and cadence are scaled inside the corner
    phases (approach tail 20%/70%, entry 50%/75%, apex 30%/60%, exit
    max(base*1.15, 250 W) / max(base, 90 rpm)). Only the RiderInput differs;
    nothing else is modified.
    """
    base_power_w, base_cadence_rpm = POWER_PLAN[segment_name]
    if not use_technique:
        return RiderInput(power_w=base_power_w, cadence_rpm=base_cadence_rpm)
    active = _current_corner_phase(distance_m)
    if active is None:
        return RiderInput(power_w=base_power_w, cadence_rpm=base_cadence_rpm)
    corner, phase = active
    power_w, cadence_rpm = _technique_power_cadence(
        corner,
        phase,
        distance_m,
        base_power_w,
        base_cadence_rpm,
    )
    return RiderInput(power_w=power_w, cadence_rpm=cadence_rpm)


def ride_and_assess(use_technique):
    """Ride the full route with one plan and assess all corners.

    Returns a dict with the final time/distance, the average speed, the
    assessments of the eight corners, the mean score, the rating counts and
    the maximum grip usage with its corner name.
    """
    state = SimulationState(speed_mps=0.0, distance_m=0.0, elapsed_time_s=0.0)
    samples = [[] for _ in ALPINE_CORNERS.corners]

    while (
        state.distance_m < ALPINE_JOURNEY.total_length_m
        and state.elapsed_time_s < MAX_TIME_S
    ):
        segment = ALPINE_JOURNEY.segment_at_distance(state.distance_m)
        environment = ALPINE_WEATHER.environment_at_distance(
            state.distance_m,
            segment.grade_decimal,
        )
        rider_input = make_rider_input(segment.name, state.distance_m, use_technique)

        for index, corner in enumerate(ALPINE_CORNERS.corners):
            phase = corner_phase_at_distance(
                corner,
                state.distance_m,
                APPROACH_LENGTH_M,
            )
            if phase == CORNER_PHASE_OUTSIDE:
                continue
            if phase == CORNER_PHASE_APPROACH:
                grip_usage = 0.0
            else:
                grip_usage = corner_grip_usage(
                    state.speed_mps,
                    corner.radius_m,
                    BASE_FRICTION_COEFFICIENT,
                    environment.grip_multiplier,
                )
            samples[index].append(
                CornerTechniqueSample(
                    distance_m=state.distance_m,
                    power_w=rider_input.power_w,
                    cadence_rpm=rider_input.cadence_rpm,
                    grip_usage=grip_usage,
                )
            )

        state = step_simulation(RIDER, environment, rider_input, state, DT_S)

    if state.distance_m < ALPINE_JOURNEY.total_length_m:
        raise RuntimeError(
            f"route not finished within {MAX_TIME_S:.0f} seconds"
        )

    summaries = [
        summarize_corner_technique(
            corner,
            tuple(samples[index]),
            APPROACH_LENGTH_M,
        )
        for index, corner in enumerate(ALPINE_CORNERS.corners)
    ]
    assessments = [
        assess_corner_technique(summary) for summary in summaries
    ]
    mean_score = sum(assessment.score for assessment in assessments) / len(assessments)
    rating_counts = {"excellent": 0, "good": 0, "needs_improvement": 0, "poor": 0}
    for assessment in assessments:
        rating_counts[assessment.rating] += 1

    max_grip_usage = -1.0
    max_grip_corner = ""
    for corner, summary in zip(ALPINE_CORNERS.corners, summaries):
        if summary.max_grip_usage > max_grip_usage:
            max_grip_usage = summary.max_grip_usage
            max_grip_corner = corner.name

    return {
        "state": state,
        "time_s": state.elapsed_time_s,
        "distance_m": state.distance_m,
        "avg_kmh": state.distance_m / state.elapsed_time_s * 3.6,
        "assessments": assessments,
        "mean_score": mean_score,
        "rating_counts": rating_counts,
        "max_grip_usage": max_grip_usage,
        "max_grip_corner": max_grip_corner,
    }


def main():
    baseline = ride_and_assess(use_technique=False)
    technique = ride_and_assess(use_technique=True)

    print("Ride comparison")
    print(
        f"{'plan':<10s} {'time_s':>8s} {'avg_kmh':>8s} {'mean_score':>11s} "
        f"{'excellent':>9s} {'good':>5s} {'needs_improvement':>18s} "
        f"{'poor':>5s} {'max_grip_usage':>14s} {'max_grip_corner':>19s}"
    )
    for name, result in (("BASELINE", baseline), ("TECHNIQUE", technique)):
        counts = result["rating_counts"]
        print(
            f"{name:<10s} "
            f"{result['time_s']:8.2f} "
            f"{result['avg_kmh']:8.2f} "
            f"{result['mean_score']:11.1f} "
            f"{counts['excellent']:9d} "
            f"{counts['good']:5d} "
            f"{counts['needs_improvement']:18d} "
            f"{counts['poor']:5d} "
            f"{result['max_grip_usage']:14.3f} "
            f"{result['max_grip_corner']:>19s}"
        )

    print()
    print("Corner score comparison")
    print(
        f"{'corner':<20s} {'baseline_score':>14s} {'technique_score':>15s} "
        f"{'difference':>11s} {'technique_feedback':>22s}"
    )
    for corner, base_assessment, technique_assessment in zip(
        ALPINE_CORNERS.corners,
        baseline["assessments"],
        technique["assessments"],
    ):
        difference = technique_assessment.score - base_assessment.score
        print(
            f"{corner.name:<20s} "
            f"{base_assessment.score:14.1f} "
            f"{technique_assessment.score:15.1f} "
            f"{difference:11.1f} "
            f"{technique_assessment.feedback:>22s}"
        )

    time_difference_s = technique["time_s"] - baseline["time_s"]
    print()
    print(f"Technique time vs baseline: {time_difference_s:+.2f} s")


if __name__ == "__main__":
    main()

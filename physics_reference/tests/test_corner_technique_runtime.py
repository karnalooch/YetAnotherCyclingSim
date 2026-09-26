import dataclasses
import unittest

from cycling_physics import RiderInput, SimulationState
from cycling_physics.corner_consequence import (
    CORNER_GEOMETRY_OUTCOME_CLEAN,
    CORNER_GEOMETRY_OUTCOME_CONTROLLED_SLIP,
    CORNER_GEOMETRY_OUTCOME_WIDE_LINE,
    CornerGeometryConsequence,
)
from cycling_physics.corner_context import (
    CORNER_DIRECTION_RIGHT,
    CornerContext,
)
from cycling_physics.corner_technique_runtime import (
    CornerTechniqueRuntimeState,
    observe_corner_technique_step,
)
from cycling_physics.cornering import (
    CORNER_PHASE_APEX,
    CORNER_PHASE_APPROACH,
    CORNER_PHASE_ENTRY,
    CORNER_PHASE_EXIT,
)


def _context(phase, *, start=100.0, end=140.0):
    distance = {
        CORNER_PHASE_APPROACH: 90.0,
        CORNER_PHASE_ENTRY: 105.0,
        CORNER_PHASE_APEX: 120.0,
        CORNER_PHASE_EXIT: 135.0,
    }[phase]
    return CornerContext(
        distance_m=distance,
        lateral_position_m=0.0,
        phase=phase,
        has_corner=True,
        corner_start_m=start,
        corner_end_m=end,
        distance_to_corner_start_m=max(0.0, start - distance),
        apex_distance_m=120.0,
        direction=CORNER_DIRECTION_RIGHT,
        signed_curvature_per_m=0.02,
        centerline_radius_m=50.0,
        effective_radius_m=50.0,
        road_width_m=6.0,
        left_margin_m=3.0,
        right_margin_m=3.0,
        cross_slope_angle_rad=0.0,
        surface_id="asphalt",
        wetness=0.0,
        roughness=0.0,
    )


def _consequence(
    outcome=CORNER_GEOMETRY_OUTCOME_CLEAN,
    *,
    line=0.0,
    speed=1.0,
):
    return CornerGeometryConsequence(
        outcome=outcome,
        minimum_required_radius_m=50.0,
        maximum_feasible_radius_m=53.0,
        required_outward_shift_m=0.0,
        applied_outward_shift_m=0.0,
        line_deviation_ratio=line,
        target_lateral_position_m=0.0,
        target_speed_mps=10.0 * speed,
        exit_speed_multiplier=speed,
    )


def _post(distance):
    return SimulationState(
        speed_mps=10.0,
        distance_m=distance,
        elapsed_time_s=1.0,
    )


class TestCornerTechniqueRuntime(unittest.TestCase):
    def test_complete_ideal_episode_scores_100(self):
        state = CornerTechniqueRuntimeState()
        steps = (
            (CORNER_PHASE_APPROACH, 250.0, 90.0, None, 95.0),
            (CORNER_PHASE_ENTRY, 0.0, 0.0, _consequence(), 110.0),
            (CORNER_PHASE_APEX, 0.0, 0.0, _consequence(), 130.0),
            (CORNER_PHASE_EXIT, 250.0, 90.0, _consequence(), 141.0),
        )
        for phase, power, cadence, consequence, post_distance in steps:
            state = observe_corner_technique_step(
                state,
                _context(phase),
                RiderInput(power_w=power, cadence_rpm=cadence),
                consequence,
                _post(post_distance),
            )

        self.assertEqual(len(state.completed_scores), 1)
        self.assertEqual(state.skipped_episode_count, 0)
        self.assertEqual(state.completed_scores[0].corner_start_m, 100.0)
        self.assertEqual(state.completed_scores[0].corner_end_m, 140.0)
        self.assertEqual(state.completed_scores[0].score.score, 100.0)
        self.assertIsNone(state.active_corner_start_m)
        self.assertEqual(state.observations, ())

    def test_physical_consequences_aggregate_conservatively(self):
        state = CornerTechniqueRuntimeState()
        steps = (
            (CORNER_PHASE_APPROACH, None, 95.0),
            (
                CORNER_PHASE_ENTRY,
                _consequence(
                    CORNER_GEOMETRY_OUTCOME_WIDE_LINE,
                    line=0.25,
                ),
                110.0,
            ),
            (
                CORNER_PHASE_APEX,
                _consequence(
                    CORNER_GEOMETRY_OUTCOME_CONTROLLED_SLIP,
                    line=0.75,
                    speed=0.8,
                ),
                130.0,
            ),
            (
                CORNER_PHASE_EXIT,
                _consequence(
                    CORNER_GEOMETRY_OUTCOME_WIDE_LINE,
                    line=0.5,
                    speed=1.0,
                ),
                141.0,
            ),
        )
        for phase, consequence, post_distance in steps:
            state = observe_corner_technique_step(
                state,
                _context(phase),
                RiderInput(
                    power_w=250.0 if phase in (CORNER_PHASE_APPROACH, CORNER_PHASE_EXIT) else 0.0,
                    cadence_rpm=90.0 if phase in (CORNER_PHASE_APPROACH, CORNER_PHASE_EXIT) else 0.0,
                ),
                consequence,
                _post(post_distance),
            )

        score = state.completed_scores[0].score
        self.assertEqual(score.line_retention_score, 25.0)
        self.assertEqual(score.speed_retention_score, 80.0)
        self.assertEqual(score.score, 88.125)

    def test_truncated_episode_is_skipped_not_physics_failure(self):
        state = CornerTechniqueRuntimeState()
        for phase, distance in (
            (CORNER_PHASE_ENTRY, 110.0),
            (CORNER_PHASE_APEX, 130.0),
            (CORNER_PHASE_EXIT, 141.0),
        ):
            state = observe_corner_technique_step(
                state,
                _context(phase),
                RiderInput(power_w=100.0, cadence_rpm=80.0),
                _consequence(),
                _post(distance),
            )
        self.assertEqual(state.completed_scores, ())
        self.assertEqual(state.skipped_episode_count, 1)
        self.assertIsNone(state.active_corner_start_m)

    def test_zero_approach_baseline_is_skipped(self):
        state = CornerTechniqueRuntimeState()
        for phase, distance in (
            (CORNER_PHASE_APPROACH, 95.0),
            (CORNER_PHASE_ENTRY, 110.0),
            (CORNER_PHASE_APEX, 130.0),
            (CORNER_PHASE_EXIT, 141.0),
        ):
            state = observe_corner_technique_step(
                state,
                _context(phase),
                RiderInput(
                    power_w=0.0,
                    cadence_rpm=0.0 if phase == CORNER_PHASE_APPROACH else 90.0,
                ),
                None if phase == CORNER_PHASE_APPROACH else _consequence(),
                _post(distance),
            )
        self.assertEqual(state.completed_scores, ())
        self.assertEqual(state.skipped_episode_count, 1)

    def test_multiple_observations_are_phase_averaged(self):
        state = CornerTechniqueRuntimeState()
        for power in (200.0, 300.0):
            state = observe_corner_technique_step(
                state,
                _context(CORNER_PHASE_APPROACH),
                RiderInput(power_w=power, cadence_rpm=90.0),
                None,
                _post(96.0),
            )
        for phase, power, cadence, distance in (
            (CORNER_PHASE_ENTRY, 125.0, 45.0, 110.0),
            (CORNER_PHASE_APEX, 125.0, 45.0, 130.0),
            (CORNER_PHASE_EXIT, 125.0, 45.0, 141.0),
        ):
            state = observe_corner_technique_step(
                state,
                _context(phase),
                RiderInput(power_w=power, cadence_rpm=cadence),
                _consequence(),
                _post(distance),
            )
        self.assertEqual(state.completed_scores[0].score.score, 62.5)

    def test_context_interval_change_before_completion_fails_closed(self):
        state = observe_corner_technique_step(
            CornerTechniqueRuntimeState(),
            _context(CORNER_PHASE_APPROACH),
            RiderInput(power_w=250.0, cadence_rpm=90.0),
            None,
            _post(95.0),
        )
        with self.assertRaisesRegex(ValueError, "changed interval"):
            observe_corner_technique_step(
                state,
                _context(CORNER_PHASE_ENTRY, start=101.0, end=141.0),
                RiderInput(power_w=0.0, cadence_rpm=0.0),
                _consequence(),
                _post(110.0),
            )

    def test_runtime_state_is_frozen_and_deterministic(self):
        initial = CornerTechniqueRuntimeState()
        args = (
            initial,
            _context(CORNER_PHASE_APPROACH),
            RiderInput(power_w=250.0, cadence_rpm=90.0),
            None,
            _post(95.0),
        )
        first = observe_corner_technique_step(*args)
        for _ in range(20):
            self.assertEqual(observe_corner_technique_step(*args), first)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            first.skipped_episode_count = 10


if __name__ == "__main__":
    unittest.main()

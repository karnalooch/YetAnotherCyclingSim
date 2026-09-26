import dataclasses
import unittest

from cycling_physics import (
    CORNER_PHASE_APEX,
    CORNER_PHASE_APPROACH,
    CORNER_PHASE_ENTRY,
    CORNER_PHASE_EXIT,
)
from cycling_physics.corner_consequence import (
    CORNER_GEOMETRY_OUTCOME_CLEAN,
    CORNER_GEOMETRY_OUTCOME_CONTROLLED_SLIP,
    CORNER_GEOMETRY_OUTCOME_WIDE_LINE,
    CornerGeometryConsequence,
)
from cycling_physics.corner_technique import (
    RouteCornerTechniqueObservation,
    RouteCornerTechniqueScore,
    RouteCornerTechniqueSummary,
    score_route_corner_technique,
    summarize_route_corner_technique,
)


def _consequence(
    *,
    outcome=CORNER_GEOMETRY_OUTCOME_CLEAN,
    line_deviation_ratio=0.0,
    exit_speed_multiplier=1.0,
):
    return CornerGeometryConsequence(
        outcome=outcome,
        minimum_required_radius_m=50.0,
        maximum_feasible_radius_m=53.0,
        required_outward_shift_m=0.0,
        applied_outward_shift_m=0.0,
        line_deviation_ratio=line_deviation_ratio,
        target_lateral_position_m=0.0,
        target_speed_mps=20.0 * exit_speed_multiplier,
        exit_speed_multiplier=exit_speed_multiplier,
    )


def _summary(**overrides):
    values = dict(
        approach_power_w=250.0,
        entry_power_w=0.0,
        apex_power_w=0.0,
        exit_power_w=250.0,
        approach_cadence_rpm=90.0,
        entry_cadence_rpm=0.0,
        apex_cadence_rpm=0.0,
        exit_cadence_rpm=90.0,
    )
    values.update(overrides)
    return RouteCornerTechniqueSummary(**values)


class TestRouteCornerTechniqueSummary(unittest.TestCase):
    def test_route_phases_are_averaged_without_legacy_corner_geometry(self):
        observations = (
            RouteCornerTechniqueObservation(CORNER_PHASE_APPROACH, 240.0, 88.0),
            RouteCornerTechniqueObservation(CORNER_PHASE_APPROACH, 260.0, 92.0),
            RouteCornerTechniqueObservation(CORNER_PHASE_ENTRY, 80.0, 45.0),
            RouteCornerTechniqueObservation(CORNER_PHASE_APEX, 20.0, 10.0),
            RouteCornerTechniqueObservation(CORNER_PHASE_EXIT, 200.0, 80.0),
            RouteCornerTechniqueObservation(CORNER_PHASE_EXIT, 300.0, 100.0),
        )
        summary = summarize_route_corner_technique(observations)
        self.assertEqual(summary.approach_power_w, 250.0)
        self.assertEqual(summary.approach_cadence_rpm, 90.0)
        self.assertEqual(summary.entry_power_w, 80.0)
        self.assertEqual(summary.apex_cadence_rpm, 10.0)
        self.assertEqual(summary.exit_power_w, 250.0)
        self.assertEqual(summary.exit_cadence_rpm, 90.0)

    def test_missing_phase_is_rejected(self):
        observations = (
            RouteCornerTechniqueObservation(CORNER_PHASE_APPROACH, 250.0, 90.0),
            RouteCornerTechniqueObservation(CORNER_PHASE_ENTRY, 0.0, 0.0),
            RouteCornerTechniqueObservation(CORNER_PHASE_APEX, 0.0, 0.0),
        )
        with self.assertRaisesRegex(ValueError, "exit"):
            summarize_route_corner_technique(observations)

    def test_non_route_phase_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "approach, entry, apex or exit"):
            RouteCornerTechniqueObservation("outside", 250.0, 90.0)


class TestRouteCornerTechniqueScore(unittest.TestCase):
    def test_ideal_timing_and_clean_line_scores_100(self):
        score = score_route_corner_technique(_summary(), _consequence())
        self.assertEqual(score.score, 100.0)
        for field in dataclasses.fields(score):
            self.assertEqual(getattr(score, field.name), 100.0)

    def test_equal_half_effort_phase_scores_are_continuous(self):
        score = score_route_corner_technique(
            _summary(
                entry_power_w=125.0,
                apex_power_w=125.0,
                exit_power_w=125.0,
                entry_cadence_rpm=45.0,
                apex_cadence_rpm=45.0,
                exit_cadence_rpm=45.0,
            ),
            _consequence(),
        )
        self.assertEqual(score.entry_power_release_score, 50.0)
        self.assertEqual(score.apex_power_release_score, 50.0)
        self.assertEqual(score.exit_power_recovery_score, 50.0)
        self.assertEqual(score.entry_cadence_release_score, 50.0)
        self.assertEqual(score.apex_cadence_release_score, 50.0)
        self.assertEqual(score.exit_cadence_recovery_score, 50.0)
        self.assertEqual(score.line_retention_score, 100.0)
        self.assertEqual(score.speed_retention_score, 100.0)
        self.assertEqual(score.score, 62.5)

    def test_effort_above_baseline_clamps_without_magic_thresholds(self):
        score = score_route_corner_technique(
            _summary(
                entry_power_w=500.0,
                apex_power_w=500.0,
                exit_power_w=500.0,
                entry_cadence_rpm=180.0,
                apex_cadence_rpm=180.0,
                exit_cadence_rpm=180.0,
            ),
            _consequence(),
        )
        self.assertEqual(score.entry_power_release_score, 0.0)
        self.assertEqual(score.apex_power_release_score, 0.0)
        self.assertEqual(score.exit_power_recovery_score, 100.0)
        self.assertEqual(score.entry_cadence_release_score, 0.0)
        self.assertEqual(score.apex_cadence_release_score, 0.0)
        self.assertEqual(score.exit_cadence_recovery_score, 100.0)

    def test_wide_line_penalty_comes_directly_from_geometry_consequence(self):
        score = score_route_corner_technique(
            _summary(),
            _consequence(
                outcome=CORNER_GEOMETRY_OUTCOME_WIDE_LINE,
                line_deviation_ratio=0.5,
            ),
        )
        self.assertEqual(score.line_retention_score, 50.0)
        self.assertEqual(score.speed_retention_score, 100.0)
        self.assertEqual(score.score, 93.75)

    def test_controlled_slip_penalties_are_continuous(self):
        score = score_route_corner_technique(
            _summary(),
            _consequence(
                outcome=CORNER_GEOMETRY_OUTCOME_CONTROLLED_SLIP,
                line_deviation_ratio=1.0,
                exit_speed_multiplier=0.8,
            ),
        )
        self.assertEqual(score.line_retention_score, 0.0)
        self.assertEqual(score.speed_retention_score, 80.0)
        self.assertEqual(score.score, 85.0)

    def test_zero_approach_baseline_is_rejected_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "approach_power_w"):
            score_route_corner_technique(
                _summary(approach_power_w=0.0),
                _consequence(),
            )
        with self.assertRaisesRegex(ValueError, "approach_cadence_rpm"):
            score_route_corner_technique(
                _summary(approach_cadence_rpm=0.0),
                _consequence(),
            )

    def test_scoring_is_exactly_deterministic(self):
        summary = _summary(
            entry_power_w=73.0,
            apex_power_w=19.0,
            exit_power_w=221.0,
            entry_cadence_rpm=42.0,
            apex_cadence_rpm=11.0,
            exit_cadence_rpm=83.0,
        )
        consequence = _consequence(
            outcome=CORNER_GEOMETRY_OUTCOME_WIDE_LINE,
            line_deviation_ratio=0.37,
            exit_speed_multiplier=0.91,
        )
        first = score_route_corner_technique(summary, consequence)
        for _ in range(20):
            self.assertEqual(
                score_route_corner_technique(summary, consequence),
                first,
            )

    def test_score_record_is_frozen_and_slotted(self):
        score = score_route_corner_technique(_summary(), _consequence())
        with self.assertRaises(dataclasses.FrozenInstanceError):
            score.score = 0.0
        self.assertFalse(hasattr(score, "__dict__"))


if __name__ == "__main__":
    unittest.main()

import math
import unittest

from cycling_physics import SimulationState
from cycling_physics.corner_consequence import (
    CORNER_GEOMETRY_OUTCOME_CLEAN,
    CORNER_GEOMETRY_OUTCOME_CONTROLLED_SLIP,
    CORNER_GEOMETRY_OUTCOME_WIDE_LINE,
    CornerGeometryConsequence,
)
from cycling_physics.corner_consequence_application import (
    apply_corner_geometry_consequence,
)
from cycling_physics.corner_context import (
    CORNER_DIRECTION_RIGHT,
    CornerContext,
)
from cycling_physics.cornering import CORNER_PHASE_ENTRY


def _context(*, lateral_position_m=0.0, corner_end_m=130.0):
    return CornerContext(
        distance_m=110.0,
        lateral_position_m=lateral_position_m,
        phase=CORNER_PHASE_ENTRY,
        has_corner=True,
        corner_start_m=100.0,
        corner_end_m=corner_end_m,
        distance_to_corner_start_m=0.0,
        apex_distance_m=115.0,
        direction=CORNER_DIRECTION_RIGHT,
        signed_curvature_per_m=0.02,
        centerline_radius_m=50.0,
        effective_radius_m=50.0 - lateral_position_m,
        road_width_m=6.0,
        left_margin_m=3.0 + lateral_position_m,
        right_margin_m=3.0 - lateral_position_m,
        cross_slope_angle_rad=0.0,
        surface_id="asphalt",
        wetness=0.0,
        roughness=0.0,
    )


def _consequence(
    outcome,
    *,
    target_d=0.0,
    target_speed=10.0,
    multiplier=1.0,
    deviation=0.0,
):
    return CornerGeometryConsequence(
        outcome=outcome,
        minimum_required_radius_m=50.0,
        maximum_feasible_radius_m=53.0,
        required_outward_shift_m=abs(target_d),
        applied_outward_shift_m=abs(target_d),
        line_deviation_ratio=deviation,
        target_lateral_position_m=target_d,
        target_speed_mps=target_speed,
        exit_speed_multiplier=multiplier,
    )


class TestCornerConsequenceApplication(unittest.TestCase):
    def pre(self, *, speed=10.0, distance=110.0, time=1.0, d=0.0):
        return SimulationState(
            speed_mps=speed,
            distance_m=distance,
            elapsed_time_s=time,
            lateral_position_m=d,
        )

    def integrated(
        self,
        *,
        speed=10.0,
        distance=111.0,
        time=1.1,
        d=0.0,
    ):
        return SimulationState(
            speed_mps=speed,
            distance_m=distance,
            elapsed_time_s=time,
            lateral_position_m=d,
        )

    def test_clean_preserves_integrated_longitudinal_state_exactly(self):
        integrated = self.integrated(speed=10.6, distance=111.03)
        result = apply_corner_geometry_consequence(
            self.pre(),
            integrated,
            _context(),
            _consequence(
                CORNER_GEOMETRY_OUTCOME_CLEAN,
                target_speed=10.0,
            ),
        )
        self.assertEqual(result.state.speed_mps, integrated.speed_mps)
        self.assertEqual(result.state.distance_m, integrated.distance_m)
        self.assertEqual(result.state.elapsed_time_s, integrated.elapsed_time_s)
        self.assertEqual(result.state.lateral_position_m, 0.0)
        self.assertEqual(result.applied_speed_loss_mps, 0.0)

    def test_wide_line_does_not_suppress_normal_acceleration(self):
        integrated = self.integrated(speed=10.6, distance=111.03)
        result = apply_corner_geometry_consequence(
            self.pre(),
            integrated,
            _context(),
            _consequence(
                CORNER_GEOMETRY_OUTCOME_WIDE_LINE,
                target_d=-2.0,
                target_speed=10.0,
                deviation=2.0 / 3.0,
            ),
        )
        self.assertEqual(result.state.speed_mps, 10.6)
        self.assertEqual(result.state.distance_m, 111.03)
        self.assertLess(result.state.lateral_position_m, 0.0)
        self.assertGreater(result.state.lateral_position_m, -2.0)

    def test_wide_line_moves_by_remaining_corner_distance_not_teleport(self):
        result = apply_corner_geometry_consequence(
            self.pre(),
            self.integrated(distance=111.0),
            _context(),
            _consequence(
                CORNER_GEOMETRY_OUTCOME_WIDE_LINE,
                target_d=-2.0,
                deviation=2.0 / 3.0,
            ),
        )
        self.assertAlmostEqual(result.state.lateral_position_m, -0.1, places=12)
        self.assertAlmostEqual(result.applied_lateral_shift_m, -0.1, places=12)

    def test_controlled_slip_projects_speed_down_and_recomputes_distance(self):
        result = apply_corner_geometry_consequence(
            self.pre(speed=10.0),
            self.integrated(speed=10.0, distance=111.0, time=1.1),
            _context(),
            _consequence(
                CORNER_GEOMETRY_OUTCOME_CONTROLLED_SLIP,
                target_d=-3.0,
                target_speed=8.0,
                multiplier=0.8,
                deviation=1.0,
            ),
        )
        self.assertEqual(result.state.speed_mps, 8.0)
        self.assertAlmostEqual(result.state.distance_m, 110.9, places=12)
        self.assertAlmostEqual(result.applied_speed_loss_mps, 2.0, places=12)
        self.assertAlmostEqual(
            result.state.lateral_position_m,
            -3.0 * (0.9 / 20.0),
            places=12,
        )

    def test_controlled_slip_never_increases_or_rewrites_already_slower_step(self):
        integrated = self.integrated(speed=7.5, distance=110.875)
        result = apply_corner_geometry_consequence(
            self.pre(speed=10.0),
            integrated,
            _context(),
            _consequence(
                CORNER_GEOMETRY_OUTCOME_CONTROLLED_SLIP,
                target_d=-3.0,
                target_speed=8.0,
                multiplier=0.8,
                deviation=1.0,
            ),
        )
        self.assertEqual(result.state.speed_mps, 7.5)
        self.assertEqual(result.state.distance_m, integrated.distance_m)
        self.assertEqual(result.applied_speed_loss_mps, 0.0)

    def test_zero_longitudinal_progress_means_zero_lateral_progress(self):
        result = apply_corner_geometry_consequence(
            self.pre(speed=0.0),
            self.integrated(speed=0.0, distance=110.0),
            _context(),
            _consequence(
                CORNER_GEOMETRY_OUTCOME_WIDE_LINE,
                target_d=-2.0,
                deviation=2.0 / 3.0,
            ),
        )
        self.assertEqual(result.state.lateral_position_m, 0.0)
        self.assertEqual(result.applied_lateral_shift_m, 0.0)

    def test_step_crossing_corner_end_reaches_target_without_overshoot(self):
        result = apply_corner_geometry_consequence(
            self.pre(distance=110.0),
            self.integrated(distance=131.0),
            _context(corner_end_m=130.0),
            _consequence(
                CORNER_GEOMETRY_OUTCOME_WIDE_LINE,
                target_d=-2.0,
                deviation=2.0 / 3.0,
            ),
        )
        self.assertEqual(result.state.lateral_position_m, -2.0)

    def test_signed_authoritative_d_is_supported(self):
        context = _context(lateral_position_m=-0.5)
        pre = self.pre(d=-0.5)
        integrated = self.integrated(d=-0.5)
        consequence = _consequence(
            CORNER_GEOMETRY_OUTCOME_CLEAN,
            target_d=-0.5,
        )
        result = apply_corner_geometry_consequence(
            pre,
            integrated,
            context,
            consequence,
        )
        self.assertEqual(result.state.lateral_position_m, -0.5)

    def test_context_must_match_authoritative_pre_step_d(self):
        with self.assertRaisesRegex(ValueError, "authoritative pre-step D"):
            apply_corner_geometry_consequence(
                self.pre(d=0.25),
                self.integrated(d=0.25),
                _context(lateral_position_m=0.0),
                _consequence(CORNER_GEOMETRY_OUTCOME_CLEAN),
            )

    def test_target_outside_road_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "outside road bounds"):
            apply_corner_geometry_consequence(
                self.pre(),
                self.integrated(),
                _context(),
                _consequence(
                    CORNER_GEOMETRY_OUTCOME_WIDE_LINE,
                    target_d=-3.1,
                    deviation=1.0,
                ),
            )

    def test_non_finite_lateral_state_is_rejected(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "lateral_position_m"):
                    SimulationState(
                        speed_mps=10.0,
                        distance_m=110.0,
                        elapsed_time_s=1.0,
                        lateral_position_m=value,
                    )

    def test_application_is_exactly_deterministic(self):
        args = (
            self.pre(speed=14.0, d=0.0),
            self.integrated(speed=13.5, distance=111.375, d=0.0),
            _context(),
            _consequence(
                CORNER_GEOMETRY_OUTCOME_CONTROLLED_SLIP,
                target_d=-2.5,
                target_speed=12.0,
                multiplier=12.0 / 14.0,
                deviation=0.9,
            ),
        )
        first = apply_corner_geometry_consequence(*args)
        for _ in range(20):
            self.assertEqual(apply_corner_geometry_consequence(*args), first)


if __name__ == "__main__":
    unittest.main()

import math
import unittest

from cycling_physics import (
    CORNER_DIRECTION_LEFT,
    CORNER_DIRECTION_RIGHT,
    CORNER_PHASE_APEX,
    CORNER_PHASE_APPROACH,
    CornerContext,
    CornerGripDemand,
    shared_grip_budget,
)
from cycling_physics.corner_consequence import (
    CORNER_GEOMETRY_OUTCOME_CLEAN,
    CORNER_GEOMETRY_OUTCOME_CONTROLLED_SLIP,
    CORNER_GEOMETRY_OUTCOME_WIDE_LINE,
    resolve_corner_geometry_consequence,
)


def _context(
    *,
    direction=CORNER_DIRECTION_RIGHT,
    lateral_position_m=0.0,
    effective_radius_m=50.0,
    left_margin_m=3.0,
    right_margin_m=3.0,
    phase=CORNER_PHASE_APEX,
):
    curvature = 1.0 / effective_radius_m
    if direction == CORNER_DIRECTION_LEFT:
        curvature = -curvature
    return CornerContext(
        distance_m=100.0,
        lateral_position_m=lateral_position_m,
        phase=phase,
        has_corner=True,
        corner_start_m=80.0,
        corner_end_m=120.0,
        distance_to_corner_start_m=0.0,
        apex_distance_m=100.0,
        direction=direction,
        signed_curvature_per_m=curvature,
        centerline_radius_m=effective_radius_m,
        effective_radius_m=effective_radius_m,
        road_width_m=left_margin_m + right_margin_m,
        left_margin_m=left_margin_m,
        right_margin_m=right_margin_m,
        cross_slope_angle_rad=0.0,
        surface_id="asphalt",
        wetness=0.0,
        roughness=0.0,
    )


def _demand(*, speed_mps=20.0, lateral_usage=1.0):
    return CornerGripDemand(
        speed_mps=speed_mps,
        lateral_acceleration_demand_mps2=0.0,
        longitudinal_usage=0.0,
        lateral_usage=lateral_usage,
        budget=shared_grip_budget(0.0, lateral_usage),
    )


class TestCornerGeometryConsequence(unittest.TestCase):
    def test_within_lateral_limit_is_clean(self):
        result = resolve_corner_geometry_consequence(
            _context(),
            _demand(lateral_usage=0.8),
        )
        self.assertEqual(result.outcome, CORNER_GEOMETRY_OUTCOME_CLEAN)
        self.assertEqual(result.required_outward_shift_m, 0.0)
        self.assertEqual(result.applied_outward_shift_m, 0.0)
        self.assertEqual(result.line_deviation_ratio, 0.0)
        self.assertEqual(result.target_lateral_position_m, 0.0)
        self.assertEqual(result.target_speed_mps, 20.0)
        self.assertEqual(result.exit_speed_multiplier, 1.0)

    def test_right_turn_uses_left_margin_for_wider_radius(self):
        # 4% lateral over-demand at a 50 m radius requires 52 m: a 2 m
        # outward shift, which fits inside the 3 m left/outside margin.
        result = resolve_corner_geometry_consequence(
            _context(direction=CORNER_DIRECTION_RIGHT),
            _demand(lateral_usage=1.04),
        )
        self.assertEqual(result.outcome, CORNER_GEOMETRY_OUTCOME_WIDE_LINE)
        self.assertAlmostEqual(result.minimum_required_radius_m, 52.0)
        self.assertAlmostEqual(result.required_outward_shift_m, 2.0)
        self.assertAlmostEqual(result.applied_outward_shift_m, 2.0)
        self.assertAlmostEqual(result.target_lateral_position_m, -2.0)
        self.assertAlmostEqual(result.line_deviation_ratio, 2.0 / 3.0)
        self.assertEqual(result.exit_speed_multiplier, 1.0)

    def test_left_turn_mirrors_right_turn_geometry(self):
        result = resolve_corner_geometry_consequence(
            _context(direction=CORNER_DIRECTION_LEFT),
            _demand(lateral_usage=1.04),
        )
        self.assertEqual(result.outcome, CORNER_GEOMETRY_OUTCOME_WIDE_LINE)
        self.assertAlmostEqual(result.target_lateral_position_m, 2.0)
        self.assertAlmostEqual(result.applied_outward_shift_m, 2.0)
        self.assertAlmostEqual(result.line_deviation_ratio, 2.0 / 3.0)

    def test_insufficient_road_width_becomes_controlled_slip(self):
        # 20% over-demand at 50 m requires 60 m, but only 3 m of outside
        # margin exists. The widest feasible radius is 53 m.
        result = resolve_corner_geometry_consequence(
            _context(left_margin_m=3.0),
            _demand(speed_mps=20.0, lateral_usage=1.2),
        )
        expected_multiplier = math.sqrt(53.0 / 60.0)
        self.assertEqual(
            result.outcome,
            CORNER_GEOMETRY_OUTCOME_CONTROLLED_SLIP,
        )
        self.assertAlmostEqual(result.maximum_feasible_radius_m, 53.0)
        self.assertAlmostEqual(result.required_outward_shift_m, 10.0)
        self.assertAlmostEqual(result.applied_outward_shift_m, 3.0)
        self.assertAlmostEqual(result.line_deviation_ratio, 1.0)
        self.assertAlmostEqual(result.target_lateral_position_m, -3.0)
        self.assertAlmostEqual(result.exit_speed_multiplier, expected_multiplier)
        self.assertAlmostEqual(result.target_speed_mps, 20.0 * expected_multiplier)

    def test_no_outside_margin_reduces_speed_at_current_radius(self):
        result = resolve_corner_geometry_consequence(
            _context(left_margin_m=0.0),
            _demand(speed_mps=15.0, lateral_usage=1.44),
        )
        self.assertEqual(
            result.outcome,
            CORNER_GEOMETRY_OUTCOME_CONTROLLED_SLIP,
        )
        self.assertEqual(result.applied_outward_shift_m, 0.0)
        self.assertEqual(result.line_deviation_ratio, 0.0)
        self.assertAlmostEqual(result.exit_speed_multiplier, 1.0 / 1.2)
        self.assertAlmostEqual(result.target_speed_mps, 12.5)

    def test_approach_phase_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "entry, apex or exit"):
            resolve_corner_geometry_consequence(
                _context(phase=CORNER_PHASE_APPROACH),
                _demand(lateral_usage=1.1),
            )

    def test_resolution_is_exactly_deterministic(self):
        context = _context(left_margin_m=2.5, lateral_position_m=-0.25)
        demand = _demand(speed_mps=17.25, lateral_usage=1.12)
        first = resolve_corner_geometry_consequence(context, demand)
        for _ in range(20):
            self.assertEqual(
                resolve_corner_geometry_consequence(context, demand),
                first,
            )


if __name__ == "__main__":
    unittest.main()

import copy
import unittest

import numpy as np

from scripts.geometry.road_surface_profile import (
    design_profile,
    inspect_surface,
    surface_proof_valid,
)
from scripts.geometry.road_transition import evaluate, quintic, verify_join_proof


class RoadTransitionTests(unittest.TestCase):
    def test_endpoint_value_grade_and_curvature_are_preserved(self):
        c = quintic(10, 0.1, 0.01, 15, 0.2, -0.01, 40)
        for at, expected in [(0, (10, 0.1, 0.01)), (40, (15, 0.2, -0.01))]:
            for derivative, value in enumerate(expected):
                self.assertAlmostEqual(evaluate(c, at, 40, derivative), value)

    def test_g2_join_rejects_curvature_break_or_missing_receipt(self):
        span = {"start_station_m": 127.5, "end_station_m": 135.0}
        proof = {**span, "joins": [{"position_error_m": 0.0, "unit_tangent_error": 0.0, "curvature_error_per_m": 0.0} for _ in range(2)]}
        verify_join_proof([proof], [span])
        proof["joins"][1]["curvature_error_per_m"] = 0.01
        with self.assertRaisesRegex(ValueError, "join"):
            verify_join_proof([proof], [span])
        with self.assertRaises(ValueError):
            verify_join_proof(None, [span])

    def test_invalid_transition_is_rejected(self):
        for length in (0, -1, float("nan")):
            with self.assertRaises(ValueError):
                quintic(0, 0, 0, 1, 0, 0, length)


class RoadSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.stations = np.arange(2401) * 0.125
        self.lateral = np.tile(np.linspace(-3, 3, 25), (2401, 1))
        self.xy = np.stack((np.broadcast_to(self.stations[:, None], self.lateral.shape), self.lateral), axis=2)
        self.center = 600 + self.stations * 0.02
        self.crossfall = np.zeros(2401)
        self.crossfall[(self.stations > 120) & (self.stations < 160)] = -0.16

    def rows(self, center, crossfall):
        return [{"station_m": float(s), "xy_local_m": self.xy[i].tolist(),
                 "candidate_ground_m": (center[i] + crossfall[i] * self.lateral[i]).tolist()}
                for i, s in enumerate(self.stations)]

    def test_hillside_bank_is_rejected_by_surface_gate(self):
        self.assertEqual(inspect_surface(self.rows(self.center, self.crossfall))["status"], "FAIL")

    def test_design_preserves_approaches_and_reference_apex_for_both_sides(self):
        for reference_edge, inner_edge in ((0, 1), (1, 0)):
            z, q, meta = design_profile(self.stations, self.xy, self.center, self.crossfall,
                                       reference_edge=reference_edge, inner_edge=inner_edge)
            outside = (self.stations < 110) | (self.stations > 165)
            np.testing.assert_array_equal(z[outside], self.center[outside])
            np.testing.assert_array_equal(q[outside], self.crossfall[outside])
            offset = -3 if reference_edge == 0 else 3
            apex = int(145 / 0.125)
            self.assertAlmostEqual(z[apex] + q[apex] * offset,
                                   self.center[apex] + self.crossfall[apex] * offset)
            self.assertAlmostEqual(abs(q[apex]), 0.02)
            self.assertFalse(meta["engineering_admitted"])
            self.assertEqual(inspect_surface(self.rows(z, q))["status"], "PASS")

    def test_new_height_crease_cannot_reuse_a_passing_report(self):
        z, q, _ = design_profile(self.stations, self.xy, self.center, self.crossfall)
        rows = self.rows(z, q)
        profile = {"stations": rows, "surface_inspection": inspect_surface(rows)}
        self.assertTrue(surface_proof_valid(profile))
        altered = copy.deepcopy(profile)
        altered["stations"][1160]["candidate_ground_m"][12] += 0.5
        self.assertFalse(surface_proof_valid(altered))

    def test_stale_receipt_rejects_even_a_change_outside_metric_window(self):
        z, q, _ = design_profile(self.stations, self.xy, self.center, self.crossfall)
        rows = self.rows(z, q)
        profile = {"stations": rows, "surface_inspection": inspect_surface(rows)}
        profile["stations"][10]["candidate_ground_m"][12] += 0.001
        self.assertFalse(surface_proof_valid(profile))

    def test_nonfinite_surface_fails(self):
        rows = self.rows(self.center, self.crossfall)
        rows[1160]["candidate_ground_m"][0] = float("nan")
        with self.assertRaises(ValueError):
            inspect_surface(rows)

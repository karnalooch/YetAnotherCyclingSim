"""Regression gates for the owner's reverse-turn nose and approach width."""

import copy
import math
import unittest

from scripts.geometry.road_single_bend import (
    DOMAIN,
    MAIN_BEND,
    METHOD,
    RECIPE,
    inspect,
    profile_proof_valid,
)


class SingleBendTests(unittest.TestCase):
    def setUp(self):
        self.spec = {"method": METHOD, "domain_m": list(DOMAIN),
                     "main_bend_m": list(MAIN_BEND), "turn_sign": 1,
                     "base_width_m": 5.0, "widening_m": 0.0}
        self.rows = []
        for i in range(421):
            theta = math.pi*i/420
            self.rows.append({"station_m": DOMAIN[0]+i*0.125,
                              "edges_xy_m": [[r*math.cos(theta), r*math.sin(theta)]
                                             for r in (15, 10)]})

    def test_both_turn_directions_and_physical_edge_order_are_supported(self):
        for sign in (-1, 1):
            for reverse_edges in (False, True):
                rows = copy.deepcopy(self.rows)
                for row in rows:
                    for p in row["edges_xy_m"]:
                        p[1] *= sign
                    if reverse_edges:
                        row["edges_xy_m"].reverse()
                result = inspect(rows, dict(self.spec, turn_sign=sign))
                self.assertEqual(result["status"], "PASS")
                for curve in result["curves"]:
                    self.assertEqual(curve["counter_turn_intervals"], 0)
                    self.assertGreater(curve["heading_change_deg"], 175)

    def test_constant_width_does_not_excuse_reverse_turn_nose(self):
        for row in self.rows:
            s = row["station_m"]
            bump = 2*math.exp(-((s-130)/1.2)**2)
            for edge in row["edges_xy_m"]:
                edge[0] += bump
        with self.assertRaisesRegex(ValueError, "counter-turn"):
            inspect(self.rows, self.spec)

    def test_approach_bulge_and_unproved_widening_are_rejected(self):
        self.rows[20]["edges_xy_m"][1][0] -= 0.1
        with self.assertRaisesRegex(ValueError, "width varies"):
            inspect(self.rows, self.spec)
        with self.assertRaisesRegex(ValueError, "unsupported"):
            inspect(self.rows, dict(self.spec, widening_m=1.0))

    def test_wrong_turn_sign_missing_domain_and_nonfinite_fail(self):
        with self.assertRaisesRegex(ValueError, "counter-turn"):
            inspect(self.rows, dict(self.spec, turn_sign=-1))
        with self.assertRaisesRegex(ValueError, "domain"):
            inspect(self.rows[:-1], self.spec)
        self.rows[20]["edges_xy_m"][1][0] = float("nan")
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            inspect(self.rows, self.spec)

    def test_consumer_recomputes_shape_and_rejects_stale_or_missing_receipt(self):
        profile = {"presentation_plan": {"recipe": RECIPE,
                   "controlled_width": {"single_bend": self.spec},
                   "single_bend_inspection": inspect(self.rows, self.spec)},
                   "stations": [{"station_m": r["station_m"],
                                 "xy_local_m": r["edges_xy_m"]}
                                for r in self.rows]}
        self.assertTrue(profile_proof_valid(profile))
        for mutation in ("coordinate", "receipt", "contract"):
            altered = copy.deepcopy(profile)
            if mutation == "coordinate":
                altered["stations"][200]["xy_local_m"][0][0] += 0.1
            elif mutation == "receipt":
                del altered["presentation_plan"]["single_bend_inspection"]
            else:
                del altered["presentation_plan"]["controlled_width"]["single_bend"]
            self.assertFalse(profile_proof_valid(altered))


if __name__ == "__main__":
    unittest.main()

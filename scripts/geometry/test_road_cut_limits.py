import unittest

from scripts.geometry.road_cut_limits import (
    cut_limits,
    inspection_within_cut_limits,
    receipt_within_cut_limits,
)


class RoadCutLimitsTests(unittest.TestCase):
    def setUp(self):
        self.policy = {
            "strategies": {
                "native_blend": {"max_ground_adjustment_m": 1.0},
                "retaining_or_cliff": {"max_ground_adjustment_m": 4.0},
            },
            "thresholds": {"retaining_cut_fill_m": 4.0},
        }
        self.plan = {
            "recipe": "native-cliff-edge-width-v3",
            "controlled_width": {"edge_constraint": {"terrain_spans": [{
                "start_station_m": 125.0, "end_station_m": 165.0,
                "roles": ["CLIFF", "MOUNTAIN"],
            }]}},
        }

    def allowed(self, station, depth, plan=None):
        return inspection_within_cut_limits(
            {"station_summaries": [{"station_m": station, "max_cut_required_m": depth}]},
            cut_limits(self.plan if plan is None else plan, self.policy),
        )

    def test_cliff_depth_is_local_and_half_open(self):
        self.assertTrue(self.allowed(125.0, 3.5))
        self.assertFalse(self.allowed(124.75, 3.5))
        self.assertFalse(self.allowed(165.0, 3.5))
        self.assertFalse(self.allowed(140.0, 4.01))

    def test_legacy_or_unknown_terrain_cannot_extend_cut(self):
        self.assertFalse(self.allowed(140.0, 3.5, {}))
        self.plan["controlled_width"]["edge_constraint"]["terrain_spans"][0]["roles"] = ["UNKNOWN", "UNKNOWN"]
        self.assertFalse(self.allowed(140.0, 3.5))

    def test_missing_native_station_evidence_fails(self):
        self.assertFalse(inspection_within_cut_limits({}, cut_limits(self.plan, self.policy)))

    def test_receipt_cannot_supply_its_own_ceiling(self):
        receipt = {"patch_max_cut_m": 3.5, "patch_cut_limits": cut_limits(self.plan, self.policy)}
        self.assertTrue(receipt_within_cut_limits(self.plan, receipt, self.policy))
        receipt["patch_cut_limits"]["cliff_m"] = 6.0
        self.assertFalse(receipt_within_cut_limits(self.plan, receipt, self.policy))
        receipt["patch_cut_limits"] = cut_limits(self.plan, self.policy)
        receipt["patch_max_cut_m"] = 4.01
        self.assertFalse(receipt_within_cut_limits(self.plan, receipt, self.policy))

    def test_structure_threshold_remains_a_bound(self):
        self.policy["strategies"]["retaining_or_cliff"]["max_ground_adjustment_m"] = 6.0
        self.assertFalse(self.allowed(140.0, 4.01))


if __name__ == "__main__":
    unittest.main()

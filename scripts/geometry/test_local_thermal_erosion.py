import unittest

from scripts.geometry.local_thermal_erosion import erode


class ThermalErosionTests(unittest.TestCase):
    def fixture(self):
        field = dict(
            size=7, origin_col=0, origin_row=0, height_unit_cm=0.5, heights=[32768] * 49
        )
        plan = {
            "skin_cells": [dict(row0=0, row1=6, col0=0, col1=6, protected_samples=0)]
        }
        return field, plan

    def test_peak_moves_downhill_conserves_mass_and_locks_border(self):
        source, plan = self.fixture()
        source["heights"][24] += 600
        result, receipt = erode(source, plan)
        self.assertLess(result["heights"][24], source["heights"][24])
        self.assertGreater(result["heights"][23], source["heights"][23])
        self.assertEqual(receipt["height_sum_delta_units"], 0)
        self.assertEqual(receipt["fixed_samples_changed"], 0)
        self.assertLessEqual(receipt["max_abs_change_cm"], 100)
        self.assertEqual(source["heights"][24], 33368)
        self.assertEqual(erode(source, plan), (result, receipt))

    def test_flat_surface_is_unchanged(self):
        source, plan = self.fixture()
        result, receipt = erode(source, plan)
        self.assertEqual(result, source)
        self.assertEqual(receipt["transfers"], 0)

    def test_excluded_gap_is_unchanged(self):
        source, plan = self.fixture()
        plan["skin_cells"][0]["col1"] = 3
        source["heights"][24] += 600
        result, _ = erode(source, plan)
        self.assertEqual(result["heights"][24], source["heights"][24])

    def test_protected_cell_rejected(self):
        source, plan = self.fixture()
        plan["skin_cells"][0]["protected_samples"] = 1
        with self.assertRaises(ValueError):
            erode(source, plan)

    def test_invalid_height_rejected(self):
        source, plan = self.fixture()
        source["heights"][24] = float("nan")
        with self.assertRaises(ValueError):
            erode(source, plan)


if __name__ == "__main__":
    unittest.main()

"""Meaningful CPU-only boundary fixtures; no asset/native proof."""

import unittest
from dataclasses import replace
import numpy as np
from sa_calobra_world_graph_candidates import (
    LatticeRecipe,
    candidates,
    candidate_id,
    derived_random,
)
from read_sa_calobra_pcg_masks import evaluate


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.arrays = [
            np.ones((3, 11, 11), dtype=np.uint8),
            np.full((11, 11), 20.0),
            np.ones((3, 11, 11)),
            np.zeros((11, 11), dtype=np.uint16),
        ]
        self.recipe = LatticeRecipe(2, 36501, 0.3, 0.2, (2, 0, 1))

    def run_case(self, recipe=None):
        return candidates(*self.arrays, recipe or self.recipe)

    def center(self, result):
        return next(r for r in result["candidates"] if r["source_cell"] == [4, 4])

    def test_repeat_seed_and_named_streams(self):
        a, b = self.run_case(), self.run_case()
        self.assertEqual(a, b)
        changed = self.run_case(replace(self.recipe, seed=7))
        self.assertEqual(
            [r["candidate_id"] for r in a["candidates"]],
            [r["candidate_id"] for r in changed["candidates"]],
        )
        self.assertNotEqual(
            self.center(a)["point_seed"], self.center(changed)["point_seed"]
        )
        identity = candidate_id(4, 4)
        self.assertNotEqual(
            derived_random(identity, 1, "density"),
            derived_random(identity, 1, "variant"),
        )

    def test_local_change_preserves_unaffected_inventory(self):
        before = self.run_case()
        self.arrays[0][:, 4, 5] = 255
        after = self.run_case()
        for a, b in zip(before["candidates"], after["candidates"]):
            row, col = a["source_cell"]
            if abs(row - 4) > 1 or abs(col - 5) > 1:
                self.assertEqual(a, b)
        self.assertEqual(self.center(after)["reason"], "footprint_semantic_or_unknown")

    def test_full_footprint_exclusion_and_nodata(self):
        for array, value, reason in [
            (self.arrays[3], 65535, "footprint_exclusion_or_unknown"),
            (self.arrays[1], -32767, "footprint_unknown_clearance"),
        ]:
            old = array[4, 5]
            array[4, 5] = value
            self.assertEqual(self.center(self.run_case())["reason"], reason)
            array[4, 5] = old
        self.arrays[2][2, 4, 5] = np.nan
        self.assertEqual(
            self.center(self.run_case())["reason"], "footprint_unknown_weight"
        )

    def test_overlap_and_no_fallback(self):
        self.assertEqual(self.center(self.run_case())["band"], 2)
        self.arrays[0][2, 4, 5] = 0
        self.assertFalse(self.center(self.run_case())["selected"])

    def test_reader_parity_units_and_exclusion(self):
        self.arrays[1][4, 4] = 0.4
        result = self.center(self.run_case())
        reference = evaluate(self.arrays[0], self.arrays[1], 200, 200, 2, 0.3, 0.2)
        for key, value in reference.items():
            self.assertEqual(result[key], value)
        self.assertEqual(result["world_xy_cm"], [200, 200])
        self.assertEqual(
            self.run_case()["candidates"][0]["reason"], "asset_footprint_outside_aoi"
        )

    def test_density_only_thins(self):
        self.arrays[2][:] = 0
        self.assertEqual(self.center(self.run_case())["reason"], "density_thinned")
        self.assertFalse(any(r["selected"] for r in self.run_case()["candidates"]))

    def test_invalid_recipe_and_shapes(self):
        for recipe in [
            replace(self.recipe, radius_m=True),
            replace(self.recipe, seed=True),
            replace(self.recipe, clearance_m=-1),
            replace(self.recipe, band_priority=(0, 0, 1)),
            replace(self.recipe, spacing_cells=True),
            replace(self.recipe, radius_m=float("inf")),
        ]:
            with self.assertRaises(ValueError):
                self.run_case(recipe)
        self.arrays[1] = np.ones(11)
        with self.assertRaises(ValueError):
            self.run_case()


if __name__ == "__main__":
    unittest.main()

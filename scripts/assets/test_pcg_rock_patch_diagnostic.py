"""Analytic source cap and full clearance footprint regression cases."""

import copy
import unittest

from pcg_rock_patch_diagnostic import (
    diagnose,
    inside_patch,
    inside_validated_patch,
    patch_loops,
)


def fixture():
    rows = [
        dict(
            local_xy_cm=[x, y],
            bottom_z_cm=0,
            top_z_cm=10,
            ground_z_cm=0,
            ground_slope_deg=0,
        )
        for x, y in [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    ]
    rows += [
        dict(
            local_xy_cm=[x, y],
            bottom_z_cm=8,
            top_z_cm=10,
            ground_z_cm=0,
            ground_slope_deg=0,
        )
        for x, y in [(-2, 0), (2, 0), (0, -2), (0, 2)]
    ]
    declaration = dict(
        height_cm=10,
        source_sha256="1" * 64,
        basecut_source_sha256="2" * 64,
        topology_verified=True,
        cap_z_cm=0,
        cap_tolerance_cm=0.01,
        cap_xy_polygon=[[-1, -1], [1, -1], [1, 1], [-1, 1]],
        com_xy_cm=[0, 0],
        expected_full_ray_count=8,
        expected_cap_ray_count=4,
    )
    return rows, declaration


class PatchTests(unittest.TestCase):
    def test_disjoint_outer_union_fits_both_feet_and_preserves_coverage(self):
        _, d = fixture()
        loops = [
            [[-3, -1], [-1, -1], [-1, 1], [-3, 1]],
            [[1, -1], [3, -1], [3, 1], [1, 1]],
        ]
        d.update(
            cap_xy_polygon=loops[0],
            cap_xy_loops=loops,
            cap_loop_mode="DISJOINT_OUTER_UNION_V1",
            expected_full_ray_count=8,
            expected_cap_ray_count=8,
        )
        rows = [
            dict(
                local_xy_cm=p,
                bottom_z_cm=0,
                top_z_cm=10,
                ground_z_cm=0 if p[0] < 0 else 0.1,
                ground_slope_deg=0,
            )
            for loop in loops
            for p in loop
        ]
        result = self.final(rows, d)
        self.assertEqual(result["status"], "DIAGNOSTIC_SUPPORT_PATCH_ONLY")
        self.assertEqual(result["coverage"]["cap_valid"], 8)
        self.assertAlmostEqual(result["full_embedding_cm"], 0.1)
        self.assertFalse(inside_patch([0, 0], d))
        self.assertTrue(inside_patch([2, 0], d))
        self.assertTrue(
            inside_validated_patch([2, 0], patch_loops(d), d["cap_loop_mode"])
        )
        self.assertFalse(result["placement"])
        rows[-1]["ground_z_cm"] = None
        self.assertIn(
            "INCOMPLETE_FULL_FOOTPRINT_GROUND", self.final(rows, d)["reasons"]
        )

    def test_union_touching_nested_and_unknown_modes_reject(self):
        rows, d = fixture()
        d["cap_loop_mode"] = "DISJOINT_OUTER_UNION_V1"
        for second in (
            [[0, 0], [1, 0], [1, 0.5], [0, 0.5]],
            [[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]],
        ):
            d["cap_xy_loops"] = [d["cap_xy_polygon"], second]
            self.assertEqual(self.final(rows, d)["status"], "REJECTED_DIAGNOSTIC")
            with self.assertRaises(ValueError):
                inside_patch([0, 0], d)
        d.pop("cap_xy_loops")
        d["cap_loop_mode"] = "GUESS"
        self.assertIn("UNKNOWN_CAP_LOOP_MODE", self.final(rows, d)["reasons"])

    def test_ring_patch_excludes_hole_but_com_hull_is_not_force_proof(self):
        rows, d = fixture()
        d["cap_xy_polygon"] = [[-3, -3], [3, -3], [3, 3], [-3, 3]]
        hole = [[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]]
        d["cap_xy_loops"] = [d["cap_xy_polygon"], hole]
        for row in rows:
            row["bottom_z_cm"] = 0
        rows.append(
            dict(
                local_xy_cm=[0, 0],
                bottom_z_cm=3,
                top_z_cm=10,
                ground_z_cm=0,
                ground_slope_deg=0,
            )
        )
        d.update(expected_full_ray_count=9, expected_cap_ray_count=8)
        self.assertTrue(inside_patch([3, 0], d))
        self.assertFalse(inside_patch([0, 0], d))
        self.assertFalse(inside_patch([0.5, 0], d))
        loops = patch_loops(d)
        self.assertIsInstance(loops, tuple)
        for point in ([3, 0], [0, 0], [0.5, 0], [2, 2], [4, 4]):
            self.assertEqual(
                inside_validated_patch(point, loops), inside_patch(point, d)
            )
        result = self.final(rows, d)
        self.assertEqual(result["coverage"]["cap_valid"], 8)
        self.assertTrue(result["com_inside_support_hull"])
        self.assertEqual(result["status"], "DIAGNOSTIC_SUPPORT_PATCH_ONLY")
        self.assertFalse(result["full_qualification"])
        self.assertFalse(result["continuous_support_verified"])
        rows[-1]["ground_z_cm"] = None
        self.assertIn(
            "INCOMPLETE_FULL_FOOTPRINT_GROUND", self.final(rows, d)["reasons"]
        )

    def test_ambiguous_patch_loops_reject(self):
        rows, d = fixture()
        cases = [
            [[[2, 2], [3, 2], [3, 3], [2, 3]]],  # disjoint outer
            [[[0, 0], [1, 0], [1, 0.5], [0, 0.5]]],  # touches outer
            [[[0, 0], [2, 0], [2, 0.5], [0, 0.5]]],  # crosses outer
            [
                [[-0.8, -0.8], [0.8, -0.8], [0.8, 0.8], [-0.8, 0.8]],
                [[-0.2, -0.2], [0.2, -0.2], [0.2, 0.2], [-0.2, 0.2]],
            ],
            [
                [[-0.8, -0.8], [0, -0.8], [0, 0], [-0.8, 0]],
                [[0, -0.5], [0.5, -0.5], [0.5, 0.5], [0, 0.5]],
            ],
        ]
        for holes in cases:
            with self.subTest(holes=holes):
                altered = copy.deepcopy(d)
                altered["cap_xy_loops"] = [altered["cap_xy_polygon"]] + holes
                self.assertEqual(
                    self.final(rows, altered)["status"], "REJECTED_DIAGNOSTIC"
                )
                with self.assertRaises(ValueError):
                    inside_patch([0, 0], altered)

    def final(self, rows, d):
        return diagnose(rows, d, {"root_delta_cm": 0.1, "embedding_delta_cm": 0.1})

    def test_rounded_overhang_is_not_forced_into_ground(self):
        rows, d = fixture()
        result = self.final(rows, d)
        self.assertEqual(result["status"], "DIAGNOSTIC_SUPPORT_PATCH_ONLY")
        self.assertEqual(result["root_z_cm"], 0)
        self.assertEqual(result["fit"]["root_zero_sampled_air_cm"], 0)
        self.assertEqual(result["full_embedding_cm"], 0)
        self.assertEqual(result["remaining_positive_overhang_gap_cm"], 8)
        self.assertEqual(result["coverage"]["cap_valid"], 4)
        self.assertFalse(result["full_qualification"])
        self.assertFalse(result["placement"])
        self.assertEqual(diagnose(rows, d)["status"], "DIAGNOSTIC_AWAITING_REFINEMENT")

    def test_slope_fits_source_cap_without_terrain_selected_subset(self):
        rows, d = fixture()
        for row in rows:
            row["ground_z_cm"] = 0.1 * row["local_xy_cm"][0]
        result = self.final(rows, d)
        self.assertEqual(result["status"], "DIAGNOSTIC_SUPPORT_PATCH_ONLY")
        self.assertAlmostEqual(result["root_z_cm"], -0.1)
        self.assertAlmostEqual(result["full_embedding_cm"], 0.2)
        self.assertEqual(sum(r["cap_support"] for r in result["samples"]), 4)

    def test_declared_plant_consumes_embedding_and_exposure(self):
        rows, d = fixture()
        original = self.final(rows, d)
        d["planting_depth_fraction"] = 0.05
        planted = self.final(rows, d)
        self.assertEqual(planted["unplanted_root_z_cm"], original["root_z_cm"])
        self.assertEqual(planted["planting_depth_cm"], 0.5)
        self.assertEqual(planted["planting_depth_fraction"], 0.05)
        self.assertEqual(planted["root_z_cm"], -0.5)
        self.assertEqual(planted["full_embedding_cm"], 0.5)
        self.assertEqual(planted["fit"]["exposure_max_cm"], 9.5)
        self.assertEqual(planted["remaining_positive_overhang_gap_cm"], 7.5)
        self.assertEqual(planted["status"], "DIAGNOSTIC_SUPPORT_PATCH_ONLY")
        for flag in (
            "placement",
            "full_qualification",
            "regional_production_qualified",
        ):
            self.assertFalse(planted[flag])
        self.assertEqual(original["planting_depth_cm"], 0)
        d["planting_depth_fraction"] = 0
        self.assertEqual(self.final(rows, d), original)

    def test_plant_has_no_extra_twenty_percent_burial_budget(self):
        rows, d = fixture()
        rows[0]["ground_z_cm"] = -1.75
        unplanted = self.final(rows, d)
        self.assertEqual(unplanted["status"], "DIAGNOSTIC_SUPPORT_PATCH_ONLY")
        d["planting_depth_fraction"] = 0.05
        planted = self.final(rows, d)
        self.assertEqual(planted["full_embedding_cm"], 2.25)
        self.assertIn("EXCESSIVE_FULL_GEOMETRY_EMBEDDING", planted["reasons"])
        self.assertLess(
            planted["fit"]["exposure_max_cm"], unplanted["fit"]["exposure_max_cm"]
        )
        self.assertEqual(planted["status"], "REJECTED_DIAGNOSTIC")

    def test_invalid_plant_fraction_rejects_closed(self):
        rows, d = fixture()
        for value in (
            -0.05,
            0.01,
            0.0500001,
            1,
            True,
            None,
            "0.05",
            float("nan"),
            float("inf"),
        ):
            with self.subTest(value=value):
                d["planting_depth_fraction"] = value
                result = self.final(rows, d)
                self.assertEqual(result["status"], "REJECTED_DIAGNOSTIC")
                self.assertFalse(result["placement"])

    def test_missing_ground_in_cap_or_overhang_rejects_full_coverage(self):
        for index in (0, 7):
            rows, d = fixture()
            rows[index]["ground_z_cm"] = None
            with self.subTest(index=index):
                result = self.final(rows, d)
                self.assertIn("INCOMPLETE_FULL_FOOTPRINT_GROUND", result["reasons"])
        rows, d = fixture()
        rows[0]["bottom_z_cm"] = None
        self.assertIn("MISSING_DECLARED_CAP_BOTTOM", self.final(rows, d)["reasons"])
        rows, d = fixture()
        rows.pop(0)
        self.assertEqual(self.final(rows, d)["status"], "REJECTED_DIAGNOSTIC")

    def test_cap_hole_and_one_sided_com_reject(self):
        rows, d = fixture()
        rows[0]["bottom_z_cm"] = 0.02
        self.assertIn("INCOMPLETE_DECLARED_CAP_SUPPORT", self.final(rows, d)["reasons"])
        rows, d = fixture()
        d["com_xy_cm"] = [1.1, 0]
        self.assertIn("COM_OUTSIDE_SUPPORT_HULL", self.final(rows, d)["reasons"])

    def test_nonfinite_unknown_and_degenerate_reject(self):
        rows, d = fixture()
        for field, value in [
            ("topology_verified", False),
            ("source_sha256", "bad"),
            ("cap_tolerance_cm", 0.02),
            ("cap_xy_polygon", [[0, 0], [1, 0], [2, 0]]),
        ]:
            altered = copy.deepcopy(d)
            altered[field] = value
            self.assertEqual(self.final(rows, altered)["status"], "REJECTED_DIAGNOSTIC")
        for value in (float("nan"), float("inf"), True):
            altered = copy.deepcopy(rows)
            altered[0]["top_z_cm"] = value
            self.assertEqual(self.final(altered, d)["status"], "REJECTED_DIAGNOSTIC")
        self.assertEqual(diagnose(None, {}, None)["status"], "REJECTED_DIAGNOSTIC")

    def test_convergence_and_excessive_burial_reject(self):
        rows, d = fixture()
        rows[0]["ground_slope_deg"] = 10.001
        self.assertIn("EXCESSIVE_LOCAL_SLOPE", self.final(rows, d)["reasons"])
        rows[0]["ground_slope_deg"] = 0
        self.assertIn(
            "SAMPLE_REFINEMENT_NOT_CONVERGED",
            diagnose(rows, d, {"root_delta_cm": 0.10001, "embedding_delta_cm": 0})[
                "reasons"
            ],
        )
        rows[0]["ground_z_cm"] = -5
        self.assertIn(
            "EXCESSIVE_FULL_GEOMETRY_EMBEDDING", self.final(rows, d)["reasons"]
        )

    def test_simple_concave_polygon_with_disjoint_collinear_edges(self):
        _, d = fixture()
        d.update(
            cap_xy_polygon=[
                [0, 0],
                [1, 0],
                [1, 1],
                [2, 1],
                [2, 0],
                [3, 0],
                [3, 2],
                [0, 2],
            ],
            com_xy_cm=[1.5, 1.5],
            expected_full_ray_count=4,
            expected_cap_ray_count=4,
        )
        rows = [
            dict(
                local_xy_cm=[x, y],
                bottom_z_cm=0,
                top_z_cm=10,
                ground_z_cm=0,
                ground_slope_deg=0,
            )
            for x, y in [(0.5, 0.5), (0.5, 1.5), (2.5, 0.5), (2.5, 1.5)]
        ]
        self.assertEqual(self.final(rows, d)["status"], "DIAGNOSTIC_SUPPORT_PATCH_ONLY")
        d["cap_xy_polygon"] = [[0, 0], [3, 2], [0, 2], [3, 0]]
        self.assertIn("SELF_INTERSECTING_CAP_POLYGON", self.final(rows, d)["reasons"])


if __name__ == "__main__":
    unittest.main()

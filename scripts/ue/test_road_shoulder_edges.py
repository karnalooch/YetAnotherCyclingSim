"""Metric edge-field and fail-closed rollback regressions; no native PASS claim."""

from copy import deepcopy
import math
from types import SimpleNamespace
import unittest

from scripts.ue import road_shoulder_edges as edges
from scripts.ue.test_road_shoulder_network import Harness


def owner_fixture():
    return {"material_target": True, "kind": "ordinary",
            "sections_cm": [[(-50.0, y, 0.0), *[(20.0 * j, y, 0.0) for j in range(25)], (530.0, y, 0.0)]
                            for y in (0.0, 100.0, 200.0)],
            "selected_triangle_ids": [i * 52 + j * 2 + side for i in range(2) for j in (0, 25) for side in (0, 1)]}


class EdgeFieldTests(unittest.TestCase):
    def test_metric_distance_both_sides_and_nonzero_uv_area_without_source_edits(self):
        owner = owner_fixture()
        before = deepcopy(owner)
        rows = edges.triangle_coordinates(owner)
        self.assertEqual(owner, before)
        self.assertEqual([tid for tid, _ in rows], owner["selected_triangle_ids"])
        self.assertEqual(rows[0][1], ((50, 0), (0, 0), (50, 100)))
        self.assertEqual(rows[2][1], ((0, 0), (50, 0), (0, 100)))
        for _, (a, b, c) in rows:
            self.assertGreater(abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])), 1)

    def test_rotation_translation_grade_and_height_do_not_change_horizontal_centimetres(self):
        owner = owner_fixture()
        expected = edges.triangle_coordinates(owner)
        angle = 0.723
        owner["sections_cm"] = [[(12345 + x * math.cos(angle) - y * math.sin(angle),
                                 -43210 + x * math.sin(angle) + y * math.cos(angle), 300 + y * 0.3)
                                 for x, y, _ in row] for row in owner["sections_cm"]]
        actual = edges.triangle_coordinates(owner)
        for (_, want), (_, got) in zip(expected, actual, strict=True):
            for pair_a, pair_b in zip(want, got, strict=True):
                for a, b in zip(pair_a, pair_b, strict=True):
                    self.assertAlmostEqual(a, b, places=4)

    def test_tapered_skew_quad_keeps_true_perpendicular_distance_and_affine_interpolation(self):
        owner = owner_fixture()
        owner["sections_cm"][1] = [(x + 20, y, z) for x, y, z in owner["sections_cm"][1]]
        owner["sections_cm"][1][0] = (-10, 100, 0)
        triangle = edges.triangle_coordinates(owner)[0][1]
        self.assertAlmostEqual(triangle[0][0], 50 / math.sqrt(1.04), places=4)
        self.assertEqual(triangle[1][0], 0)
        self.assertAlmostEqual(triangle[2][0], 30 / math.sqrt(1.04), places=4)
        # Equal barycentric weights must give the true distance of the source
        # triangle centroid from its pavement edge, not a normalized strip UV.
        centroid = (-20.0, 100.0 / 3.0)
        expected = abs(20 * centroid[1] - 100 * centroid[0]) / math.hypot(20, 100)
        self.assertAlmostEqual(sum(uv[0] for uv in triangle) / 3, expected, places=4)

    def test_invalid_source_ownership_nonfinite_fold_or_degenerate_chart_fails(self):
        for change in ("parapet", "selection", "shape", "nan", "zero_length", "fold", "width"):
            owner = owner_fixture()
            if change == "parapet":
                owner["material_target"] = False
            elif change == "selection":
                owner["selected_triangle_ids"][1] = 2
            elif change == "shape":
                owner["sections_cm"][0].pop()
            elif change == "nan":
                owner["sections_cm"][0][0] = (float("nan"), 0, 0)
            elif change == "zero_length":
                owner["sections_cm"][1][1] = owner["sections_cm"][0][1]
            elif change == "fold":
                owner["sections_cm"][1][0] = (10, 100, 0)
            else:
                owner["sections_cm"][0][0] = (-101, 0, 0)
            with self.subTest(change=change), self.assertRaises(ValueError):
                edges.triangle_coordinates(owner)

    def test_native_witness_rejects_missing_or_foreign_triangles_coords_and_prefix(self):
        harness = Harness()
        component, owner = harness.components[0], harness.plan["owners"][0]
        before = harness.snapshot(component)["summary"]
        edges.apply(harness.api, component, edges.triangle_coordinates(owner), 0)
        snapshot = harness.snapshot(component, preserved_uv_set_count=0)
        proof = edges.verify_native(before, snapshot, owner)
        self.assertTrue(proof["unset_nonselected_triangles"])
        for change in ("prefix", "missing", "wall", "coordinate", "hash", "reordered"):
            changed = deepcopy(snapshot)
            witness = changed["material_uv"]
            if change == "prefix":
                witness["preserved_triangle_corner_normals_uv_blake3"] = "0" * 64
            elif change == "missing":
                witness["triangles"].pop()
            elif change == "wall":
                witness["triangles"][-1][0] = owner["top_triangle_count"]
            elif change == "coordinate":
                witness["triangles"][0][1] += 0.01
            elif change == "hash":
                witness["uv_blake3"] = "x" * 64
            else:
                witness["triangles"] = witness["triangles"][::-1]
            with self.subTest(change=change), self.assertRaises(ValueError):
                edges.verify_native(before, changed, owner)

    def test_probe_rejects_a_minimum_one_channel_clamp_and_proves_true_one_to_zero(self):
        for minimum in (0, 1):
            mesh = SimpleNamespace(count=0)
            mesh.get_num_uv_sets = lambda: mesh.count

            def setter(target, count):
                target.count = max(minimum, count)
                return target

            api = SimpleNamespace(GeometryScript_UVs=SimpleNamespace(set_num_uv_sets=setter))
            if minimum:
                with self.assertRaisesRegex(ValueError, "clamps/rejects zero"):
                    edges.verify_zero_uv_round_trip(api, mesh)
            else:
                proof = edges.verify_zero_uv_round_trip(api, mesh)
                self.assertEqual(proof["observed_counts"], [1, 0])
                self.assertTrue(proof["zero_channels_restored"])
                self.assertFalse(proof["consumer_mesh_mutated"])

    def test_rollback_refuses_to_delete_a_second_unowned_channel(self):
        harness = Harness()
        component = harness.components[0]
        component.mesh.uv_layers[:] = [{}, {}]
        with self.assertRaisesRegex(ValueError, "unowned channel"):
            edges.rollback(harness.api, component, 0)
        self.assertEqual(len(component.mesh.uv_layers), 2)
        self.assertEqual(harness.events, [])


if __name__ == "__main__":
    unittest.main()

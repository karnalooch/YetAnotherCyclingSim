"""Reject unsafe edits independently of the Unreal smoothing implementation."""

import copy
import unittest

from scripts.assets.analyze_local_cliff_smoothing import audit


class LocalCliffAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = {
            "skin_cells": [
                dict(
                    row0=r * 2,
                    row1=r * 2 + 2,
                    col0=c * 2,
                    col1=c * 2 + 2,
                    protected_samples=0,
                )
                for r in range(20)
                for c in range(51)
                if (c, r) not in {(0, 0), (1, 0), (2, 0)}
            ]
        }
        width, height = 105, 43
        vertices = [
            [y * width + x, x * 50 - 50, y * 50 - 50, 0, x * 50 - 50, y * 50 - 50, 0, 1]
            for y in range(height)
            for x in range(width)
        ]
        faces = []
        for y in range(height - 1):
            for x in range(width - 1):
                a = y * width + x
                faces.extend([[a, a + 1, a + width + 1], [a, a + width + 1, a + width]])
        cls.changed_vertex = 10 * width + 10
        vertices[cls.changed_vertex][6] = 5
        cls.evidence = {"vertices_cm": vertices, "triangles": faces}

    def test_local_edit_preserves_exact_domain(self):
        result = audit(self.plan, self.evidence)
        self.assertEqual(result["candidate_area_m2"], 1017)
        self.assertEqual(result["changed_vertices"], 1)

    def test_interface_edit_rejected_even_if_marked_movable(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["vertices_cm"][0][6] = 1
        with self.assertRaisesRegex(ValueError, "interface moved"):
            audit(self.plan, evidence)

    def test_fold_rejected(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["vertices_cm"][self.changed_vertex][4] = 9999
        with self.assertRaisesRegex(ValueError, "Folded"):
            audit(self.plan, evidence)

    def test_excess_displacement_rejected(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["vertices_cm"][self.changed_vertex][6] = 101
        with self.assertRaisesRegex(ValueError, "exceeds"):
            audit(self.plan, evidence)

    def test_owner_approved_one_metre_envelope(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["vertices_cm"][self.changed_vertex][6] = 100
        result = audit(self.plan, evidence)
        self.assertEqual(result["max_displacement_cm"], 100)
        self.assertEqual(result["displacement_limit_cm"], 100)

    def test_limit_is_total_distance_not_per_axis(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["vertices_cm"][self.changed_vertex][4] += 10
        evidence["vertices_cm"][self.changed_vertex][6] = 100
        with self.assertRaisesRegex(ValueError, "exceeds"):
            audit(self.plan, evidence)

    def test_duplicate_triangle_rejected(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["triangles"].append(evidence["triangles"][0])
        with self.assertRaisesRegex(ValueError, "Duplicate triangle"):
            audit(self.plan, evidence)


if __name__ == "__main__":
    unittest.main()

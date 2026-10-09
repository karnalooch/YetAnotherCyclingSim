"""Reject unsafe edits independently of the Unreal smoothing implementation."""

import copy
import unittest

from scripts.assets.analyze_local_cliff_smoothing import (
    audit,
    original_surface_evidence,
    source_only_surface_evidence,
)


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

    def test_separate_rounding_domain_preserves_original_classifier_and_locks(self):
        plan = copy.deepcopy(self.plan)
        evidence = copy.deepcopy(self.evidence)
        for c in plan['skin_cells']:
            c['col0'] += 756
            c['col1'] += 756
            c['row0'] += 882
            c['row1'] += 882
        for v in evidence['vertices_cm']:
            for k in (1, 4):
                v[k] += 37800
            for k in (2, 5):
                v[k] += 44100
        plan['rounding_cells'] = copy.deepcopy(plan['skin_cells']) + [
            dict(col0=756, col1=758, row0=882, row1=884, protected_samples=0)]
        plan['rounding_domain_contract'] = dict(method='source-cliff-six-metre-crown-apron-v1',
            radius_m=6, classifier_unchanged=True, hard_protected_samples=0,
            cell_count=1018, area_m2=1018)
        self.assertEqual(audit(plan, evidence, rounding_domain=True)['source_area_m2'], 1018)
        self.assertEqual(audit(plan, evidence)['source_area_m2'], 1017)
        evidence['vertices_cm'][0][6] = 1
        with self.assertRaisesRegex(ValueError, 'interface moved'):
            audit(plan, evidence, rounding_domain=True)

    def test_rounding_cannot_claim_changed_classifier_or_protected_cells(self):
        plan = copy.deepcopy(self.plan)
        plan['rounding_cells'] = plan['skin_cells']
        plan['rounding_domain_contract'] = dict(method='source-cliff-six-metre-crown-apron-v1',
            radius_m=6, classifier_unchanged=False, hard_protected_samples=0,
            cell_count=1017, area_m2=1017)
        with self.assertRaisesRegex(ValueError, 'separate rounded'):
            audit(plan, self.evidence, rounding_domain=True)

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

    def test_combined_budget_uses_original_surface(self):
        derived = copy.deepcopy(self.evidence)
        row = derived["vertices_cm"][self.changed_vertex]
        row[3], row[6] = 150, 200
        combined = original_surface_evidence(self.evidence, derived)
        self.assertEqual(combined["vertices_cm"][self.changed_vertex][3], 0)
        self.assertEqual(
            audit(self.plan, combined, limit_cm=200)["max_displacement_cm"], 200
        )
        row[6] = 201
        with self.assertRaisesRegex(ValueError, "Mesh stage"):
            original_surface_evidence(self.evidence, derived)
        row[3], row[6] = 151, 190
        with self.assertRaisesRegex(ValueError, "Terrain stage"):
            original_surface_evidence(self.evidence, derived)

    def test_source_only_comparison_uses_control_source_not_smoothed_positions(self):
        reference = copy.deepcopy(self.evidence)
        reference["vertices_cm"][self.changed_vertex][6] = 100
        candidate = source_only_surface_evidence(reference, self.evidence)
        self.assertEqual(candidate["vertices_cm"][self.changed_vertex][3], 0)
        result = audit(self.plan, candidate, limit_cm=50)
        self.assertEqual(result["max_displacement_cm"], 5)
        self.assertEqual(result["source_reference"], "original-before-reshaping")
        self.assertEqual(result["source_reference_vertices"], len(reference["vertices_cm"]))
        self.assertEqual(result["source_reference_vertices"], result["vertices"])
        self.assertTrue(result["source_reference_topology_unchanged"])

    def test_source_only_audit_rejects_inconsistent_proof_metadata(self):
        verified = source_only_surface_evidence(self.evidence, self.evidence)
        for key, value in (("source_reference_vertices", len(self.evidence["vertices_cm"]) - 1),
                           ("source_reference_topology_unchanged", False),
                           ("source_reference", "candidate-after-smoothing")):
            candidate = dict(verified, **{key: value})
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, "original source correspondence proof"):
                    audit(self.plan, candidate, limit_cm=50)

    def test_source_only_comparison_rejects_changed_before_coordinates(self):
        derived = copy.deepcopy(self.evidence)
        derived["vertices_cm"][self.changed_vertex][3] = 1
        with self.assertRaisesRegex(ValueError, "source differs from original"):
            source_only_surface_evidence(self.evidence, derived)

    def test_source_only_comparison_requires_complete_original_source(self):
        derived = copy.deepcopy(self.evidence)
        derived["vertices_cm"].pop()
        with self.assertRaisesRegex(ValueError, "Incomplete original source"):
            source_only_surface_evidence(self.evidence, derived)

    def test_source_only_comparison_rejects_changed_connectivity_or_winding(self):
        derived = copy.deepcopy(self.evidence)
        derived["triangles"].pop()
        with self.assertRaisesRegex(ValueError, "source topology"):
            source_only_surface_evidence(self.evidence, derived)
        derived = copy.deepcopy(self.evidence)
        derived["triangles"][0].reverse()
        with self.assertRaisesRegex(ValueError, "source topology"):
            source_only_surface_evidence(self.evidence, derived)

    def test_source_only_comparison_allows_vertex_id_permutation(self):
        derived = copy.deepcopy(self.evidence)
        for row in derived["vertices_cm"]:
            row[0] += 10000
        derived["triangles"] = [[v + 10000 for v in face] for face in derived["triangles"]]
        candidate = source_only_surface_evidence(self.evidence, derived)
        self.assertEqual(audit(self.plan, candidate, limit_cm=50)["changed_vertices"], 1)

    def test_duplicate_triangle_rejected(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["triangles"].append(evidence["triangles"][0])
        with self.assertRaisesRegex(ValueError, "Duplicate triangle"):
            audit(self.plan, evidence)


if __name__ == "__main__":
    unittest.main()

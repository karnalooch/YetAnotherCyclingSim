import unittest

from scripts.assets.analyze_sa_calobra_component230_pcgex_topology import analyze


def plan():
    return {
        "status": "COMPONENT230_CLIFF_VISUAL_PLAN",
        "grid": {"pixel_size_m": 0.5},
        "skin_contract": {"source_grid_step_m": 1.0},
        "counts": {"skin_cluster_count": 2, "skin_cell_count": 2},
        "skin_cells": [
            {"row0": 0, "row1": 2, "col0": 0, "col1": 2},
            {"row0": 0, "row1": 2, "col0": 4, "col1": 6},
        ],
    }


def mesh_receipt(second_x=2.0):
    # Two independent unit squares, each represented by two triangles.
    vertices = [
        [0, 0, 0], [100, 0, 0], [100, 100, 0], [0, 100, 0],
        [second_x * 100, 0, 0], [(second_x + 1) * 100, 0, 0],
        [(second_x + 1) * 100, 100, 0], [second_x * 100, 100, 0],
    ]
    return {
        "status": "YACS_SA_CALOBRA_PCGEX_CLIFF_MESH_PASS",
        "source_skin_cell_count": 2,
        "meshes": [{
            "vertices_cm": vertices,
            "triangles": [
                [0, 1, 2], [0, 2, 3],
                [4, 5, 6], [4, 6, 7],
            ],
        }],
    }


class Phase2CTopologyAuditTests(unittest.TestCase):
    def test_accepts_two_exact_disconnected_cells(self):
        report = analyze(plan(), mesh_receipt())
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["mesh"]["connected_components"], 2)
        self.assertEqual(report["mesh"]["outside_vertices"], 0)
        self.assertAlmostEqual(report["mesh"]["area_retention"], 1.0)

    def test_diagonal_semantic_cluster_is_two_mesh_islands(self):
        diagonal_plan = plan()
        diagonal_plan["counts"]["skin_cluster_count"] = 1
        diagonal_plan["skin_cells"] = [
            {"grid_rc": [0, 0], "row0": 0, "row1": 2, "col0": 0, "col1": 2},
            {"grid_rc": [1, 1], "row0": 2, "row1": 4, "col0": 2, "col1": 4},
        ]
        receipt = {
            "status": "YACS_SA_CALOBRA_PCGEX_CLIFF_MESH_PASS",
            "source_skin_cell_count": 2,
            "meshes": [{
                "vertices_cm": [
                    [0, 0, 0], [100, 0, 0], [100, 100, 0], [0, 100, 0],
                    [100, 100, 0], [200, 100, 0], [200, 200, 0], [100, 200, 0],
                ],
                "triangles": [
                    [0, 1, 2], [0, 2, 3],
                    [4, 5, 6], [4, 6, 7],
                ],
            }],
        }
        report = analyze(diagonal_plan, receipt)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["source"]["semantic_cluster_count"], 1)
        self.assertEqual(report["gate"]["expected_connected_components"], 2)
        self.assertEqual(report["mesh"]["connected_components"], 2)

    def test_rejects_leakage_outside_authoritative_cells(self):
        receipt = mesh_receipt(second_x=3.0)
        report = analyze(plan(), receipt)
        self.assertEqual(report["status"], "FAIL")
        self.assertGreater(report["mesh"]["outside_vertices"], 0)
        self.assertGreater(report["mesh"]["outside_triangle_centroids"], 0)

    def test_rejects_missing_component_area(self):
        receipt = mesh_receipt()
        receipt["meshes"][0]["triangles"] = [[0, 1, 2], [0, 2, 3]]
        report = analyze(plan(), receipt)
        self.assertEqual(report["status"], "FAIL")
        self.assertLess(report["mesh"]["area_retention"], 0.90)
        self.assertNotEqual(report["mesh"]["connected_components"], 2)


if __name__ == "__main__":
    unittest.main()

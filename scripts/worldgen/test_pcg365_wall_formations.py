"""Regression tests for continuous cliff wall formations and contact verification.

Tests:
1. 8-connectivity connected components over 0.5m grid.
2. Degenerate region detection (< 3 points) without polygon bridging.
3. Batch boundary continuity (shared vertices across 512-cell batch borders).
4. Strict separation of independent physical formations.
5. Protected exclusions (bit 63, clearance >= 125cm) preserved as holes.
6. Landscape contact and 3cm vertical offset verification.
7. Data ownership configuration for PCGEx nodes (preventing IsClosed warning).
"""
from unittest.mock import MagicMock
import unittest

import numpy as np

from scripts.worldgen.pcg365_wall_formations import (
    FormationTopologyError,
    configure_pcgex_data_ownership,
    identify_formations,
    map_formations_across_batches,
    verify_landscape_contact,
)


class WallFormationTests(unittest.TestCase):
    def test_single_continuous_formation_is_identified(self):
        # 10x10 grid with a single connected 4x4 block of cliff points
        mask = np.zeros((10, 10), dtype=bool)
        mask[2:6, 2:6] = True
        labeled, report = identify_formations(mask, min_points=3)
        self.assertEqual(report["valid_formations"], 1)
        self.assertEqual(report["degenerate_formations"], 0)
        self.assertEqual(report["total_components"], 1)
        self.assertEqual(len(report["valid_formation_ids"]), 1)

    def test_distant_formations_are_strictly_separated(self):
        # Two distant cliff blocks (top-left and bottom-right)
        mask = np.zeros((20, 20), dtype=bool)
        mask[1:5, 1:5] = True
        mask[15:19, 15:19] = True
        labeled, report = identify_formations(mask, min_points=3)
        self.assertEqual(report["valid_formations"], 2)
        self.assertEqual(report["total_components"], 2)
        # Verify two different positive IDs exist
        ids = np.unique(labeled)
        self.assertEqual(set(ids[ids > 0]), {1, 2})

    def test_degenerate_regions_under_three_points_are_detected_and_reported(self):
        # 1 valid 4-point formation, 1 isolated 1-point degenerate, 1 isolated 2-point degenerate
        mask = np.zeros((15, 15), dtype=bool)
        mask[2:4, 2:4] = True  # 4 points -> valid
        mask[8, 8] = True      # 1 point -> degenerate
        mask[12, 12:14] = True  # 2 points -> degenerate

        labeled, report = identify_formations(mask, min_points=3)
        self.assertEqual(report["valid_formations"], 1)
        self.assertEqual(report["degenerate_formations"], 2)
        self.assertEqual(report["degenerate_points"], 3)
        self.assertEqual(len(report["degenerate_components"]), 2)
        sizes = [d["point_count"] for d in report["degenerate_components"]]
        self.assertIn(1, sizes)
        self.assertIn(2, sizes)

    def test_diagonal_8_connectivity_preserves_grid_edges(self):
        # Diagonal step (0,0) -> (1,1) -> (2,2) is distance sqrt(2)*50 cm ~= 70.7 cm <= max face edge
        mask = np.zeros((5, 5), dtype=bool)
        mask[0, 0] = True
        mask[1, 1] = True
        mask[2, 2] = True
        labeled, report = identify_formations(mask, min_points=3)
        self.assertEqual(report["valid_formations"], 1)
        self.assertEqual(report["total_components"], 1)

    def test_holes_and_exclusions_remain_unbridged(self):
        # Outer ring with hollow center (donut shape)
        mask = np.zeros((7, 7), dtype=bool)
        mask[1:6, 1:6] = True
        mask[2:5, 2:5] = False  # hole inside
        labeled, report = identify_formations(mask, min_points=3)
        self.assertEqual(report["valid_formations"], 1)
        # Hole center must have label 0 (background/hole)
        self.assertTrue(np.all(labeled[2:5, 2:5] == 0))

    def test_multi_batch_boundary_continuity(self):
        # Grid of 25x25 with batch cells=8 (simulating 512-cell boundary)
        # A formation spanning rows 5..12 across batch boundary row 8
        grid = np.zeros((25, 25), dtype=int)
        # Component 1 crosses row 8 (shared boundary row)
        grid[5:12, 3:7] = 1
        result = map_formations_across_batches(grid, cells_per_batch=8)
        self.assertGreaterEqual(result["active_batches_count"], 2)
        self.assertIn(1, result["multi_batch_formations"])
        # Verify boundary stitch record was logged
        self.assertGreaterEqual(result["boundary_stitch_connections"], 1)
        records = [r for r in result["boundary_stitch_records"] if 1 in r["shared_formations"]]
        self.assertTrue(len(records) > 0)
        self.assertEqual(records[0]["type"], "VERTICAL_BOUNDARY")

    def test_landscape_contact_and_3cm_diagnostic_offset(self):
        # 3 vertices on 50 cm grid at 3 cm offset
        mesh_vertices = [
            {"@Points.$Transform": {"translation": [0.0, 0.0, 103.0]}},
            {"@Points.$Transform": {"translation": [50.0, 0.0, 113.0]}},
            {"@Points.$Transform": {"translation": [50.0, 50.0, 123.0]}},
        ]
        ground_points = [
            {"@Points.$Transform": {"translation": [0.0, 0.0, 100.0]}},
            {"@Points.$Transform": {"translation": [50.0, 0.0, 110.0]}},
            {"@Points.$Transform": {"translation": [50.0, 50.0, 120.0]}},
        ]
        edge_probes = [
            {"@Points.GroundDistance": 1003.0},
            {"@Points.GroundDistance": 1003.5},
        ]
        contact = verify_landscape_contact(
            mesh_vertices=mesh_vertices,
            landscape_surface_points=ground_points,
            edge_probes=edge_probes,
            diagnostic_offset_cm=3.0,
        )
        self.assertEqual(contact["status"], "LANDSCAPE_CONTACT_VERIFIED")
        self.assertEqual(contact["diagnostic_vertical_offset_cm"], 3.0)
        self.assertEqual(contact["max_xy_grid_deviation_cm"], 0.0)

    def test_landscape_contact_rejects_grid_motion(self):
        # Vertex moved away from 50 cm grid step
        mesh_vertices = [
            {"@Points.$Transform": {"translation": [12.5, 0.0, 103.0]}},
        ]
        ground_points = [
            {"@Points.$Transform": {"translation": [12.5, 0.0, 100.0]}},
        ]
        with self.assertRaises(FormationTopologyError) as ctx:
            verify_landscape_contact(mesh_vertices, ground_points)
        self.assertIn("Source-grid XY coordinates moved", str(ctx.exception))

    def test_landscape_contact_rejects_edge_penetration(self):
        mesh_vertices = [
            {"@Points.$Transform": {"translation": [0.0, 0.0, 103.0]}},
        ]
        ground_points = [
            {"@Points.$Transform": {"translation": [0.0, 0.0, 100.0]}},
        ]
        # Probe ground distance - 1000 <= 0 implies penetration!
        edge_probes = [{"@Points.GroundDistance": 999.0}]
        with self.assertRaises(FormationTopologyError) as ctx:
            verify_landscape_contact(mesh_vertices, ground_points, edge_probes=edge_probes)
        self.assertIn("penetrates Landscape", str(ctx.exception))

    def test_configure_pcgex_data_ownership_updates_node_settings(self):
        mock_author = MagicMock()
        mock_author.state = {"nodes": {"regions_partition": "/Path/To/Node"}}
        configure_pcgex_data_ownership(mock_author, partition_node_name="regions_partition")
        mock_author.call.assert_called_once()
        call_args = mock_author.call.call_args[0]
        self.assertEqual(call_args[0], "PCGToolset.PCGToolset")
        self.assertEqual(call_args[1], "UpdateNode")
        import json
        params = json.loads(call_args[2]["jsonParams"])
        self.assertFalse(params["bCleanupConsumableAttributes"])
        self.assertIn("IsClosed", params["protectedAttributes"])


if __name__ == "__main__":
    unittest.main()

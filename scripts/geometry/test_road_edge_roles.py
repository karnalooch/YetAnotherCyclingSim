"""Mirror/reverse edge semantics and asymmetric boundary authority regressions."""

import unittest

from scripts.geometry.road_edge_roles import (
    anchored_edges,
    edge_roles,
    terrain_roles_at,
)


class RoadEdgeRoleTests(unittest.TestCase):
    def test_left_right_bends_and_reversed_travel_keep_physical_identity(self):
        for curvature, inner in ((-0.1, 0), (0.1, 1)):
            for travel in (-1, 1):
                roles = edge_roles(curvature, ("CLIFF", "MOUNTAIN"), travel)
                self.assertEqual(roles[inner]["bend_role"], "INNER")
                self.assertEqual(roles[0]["terrain_role"], "CLIFF")
                self.assertEqual(
                    roles[0]["travel_side"], "LEFT" if travel == 1 else "RIGHT"
                )
                self.assertEqual(
                    roles[1]["travel_side"], "RIGHT" if travel == 1 else "LEFT"
                )

    def test_cliff_is_independent_of_inner_outer_and_unknown_is_preserved(self):
        for curvature in (-0.1, 0.1):
            roles = edge_roles(curvature, ("UNKNOWN", "CLIFF"))
            self.assertEqual(roles[1]["terrain_role"], "CLIFF")
            self.assertEqual(roles[0]["terrain_role"], "UNKNOWN")
        self.assertEqual(edge_roles(0)[0]["bend_role"], "STRAIGHT")

    def test_anchor_side_changes_without_moving_the_authoritative_edge(self):
        self.assertEqual(anchored_edges([0, 0], [1, 0], 5, 0), [[0, 0], [0, 5]])
        self.assertEqual(anchored_edges([0, 5], [1, 0], 5, 1), [[0, 0], [0, 5]])
        # Reverse direction: storage becomes travel-left/right reversed.
        self.assertEqual(anchored_edges([0, 5], [-1, 0], 5, 0), [[0, 5], [0, 0]])

    def test_unknown_spans_and_ambiguous_evidence_fail(self):
        spans = [
            {
                "start_station_m": 10,
                "end_station_m": 20,
                "roles": ["CLIFF", "MOUNTAIN"],
                "evidence": "owner review",
            }
        ]
        self.assertEqual(terrain_roles_at(spans, 15), ("CLIFF", "MOUNTAIN"))
        self.assertEqual(terrain_roles_at(spans, 25), ("UNKNOWN", "UNKNOWN"))
        with self.assertRaises(ValueError):
            terrain_roles_at(spans + spans, 15)
        spans[0]["evidence"] = ""
        with self.assertRaises(ValueError):
            terrain_roles_at(spans, 15)


class AnchoredAdmissionTests(unittest.TestCase):
    def setUp(self):
        import math

        from scripts.geometry.test_curved_road_plan import CurvedRoadPlanTests

        fixture = CurvedRoadPlanTests()
        fixture.setUp()
        self.source, self.kwargs = fixture.source, fixture.kwargs
        self.packet = fixture.packet
        self.packet.update(
            geometry_contract="cliff-edge-width-v3",
            point_type="CurveCustomTangent",
            width_profile={
                "evidence": {"class": "Synthetic test"},
                "samples": [
                    {"station_m": s, "left_m": 4, "right_m": 4} for s in (0, 300)
                ],
            },
            edge_constraint={
                "reference_edge": 0,
                "evidence": "Synthetic test",
                "terrain_spans": [
                    {
                        "start_station_m": 100,
                        "end_station_m": 200,
                        "roles": ["CLIFF", "MOUNTAIN"],
                        "evidence": "test",
                    }
                ],
            },
        )
        for row in self.packet["stations"]:
            station = row["station_m"]
            anchor = [station, -3 + 0.1 * math.sin(station / 10)]
            tangent = [1, 0.01 * math.cos(station / 10)]
            edges = anchored_edges(anchor, tangent, 8, 0)
            row.update(
                edges_xy_m=edges,
                center_xy_m=[(edges[0][k] + edges[1][k]) / 2 for k in (0, 1)],
                anchor_xy_m=anchor,
                anchor_tangent_xy_m_per_key=tangent,
            )

        from scripts.geometry.road_width_profile import boundary_width_profile

        self.packet["width_distance_profile"], distances = boundary_width_profile(
            self.packet["width_profile"], self.packet["stations"]
        )
        for row, distance in zip(self.packet["stations"], distances):
            row["boundary_distance_m"] = distance

    def test_derived_side_may_move_but_width_and_anchor_remain_checked(self):
        from scripts.geometry.curved_road_plan import (
            edge_role_proof_valid,
            prepare_sections,
        )

        _, proof = prepare_sections(self.packet, self.source, **self.kwargs)
        self.assertEqual(proof["recipe"], "native-cliff-edge-width-v3")
        self.assertGreater(proof["edge_displacements_m"][1], 2)
        self.assertLess(proof["maximum_constrained_edge_displacement_m"], 0.11)
        self.assertTrue(edge_role_proof_valid(proof))
        proof["edge_role_samples"][500]["edges"][0]["terrain_role"] = "MOUNTAIN"
        self.assertFalse(edge_role_proof_valid(proof))

    def test_moving_the_reference_cannot_hide_inside_derived_edge_allowance(self):
        from scripts.geometry.curved_road_plan import prepare_sections

        for row in self.packet["stations"]:
            for point in row["edges_xy_m"] + [row["anchor_xy_m"], row["center_xy_m"]]:
                point[1] += 2
        with self.assertRaisesRegex(ValueError, "1 m source"):
            prepare_sections(self.packet, self.source, **self.kwargs)

    def test_width_drift_and_wrong_cliff_identity_are_rejected(self):
        import copy

        from scripts.geometry.curved_road_plan import prepare_sections

        for mutation in ("width", "cliff"):
            packet = copy.deepcopy(self.packet)
            if mutation == "width":
                packet["stations"][400]["edges_xy_m"][1][1] += 0.1
            else:
                packet["edge_constraint"]["terrain_spans"][0]["roles"] = [
                    "MOUNTAIN",
                    "CLIFF",
                ]
            with self.assertRaises(ValueError):
                prepare_sections(packet, self.source, **self.kwargs)

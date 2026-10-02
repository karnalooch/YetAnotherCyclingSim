"""Road-width regressions: intended widening, common normals and rejected drift."""

import copy
import math
import unittest

from scripts.geometry.curved_road_plan import prepare_sections
from scripts.geometry.road_width_profile import offset_edges, width_at


class RoadWidthTests(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "evidence": {"class": "Inference"},
            "samples": [
                {"station_m": s, "left_m": a, "right_m": b}
                for s, a, b in [(0, 2, 3), (100, 2, 4), (200, 2, 3), (300, 2, 3)]
            ],
        }

    def test_widening_is_bounded_asymmetric_and_returns_to_nominal(self):
        for station in range(301):
            a, b = width_at(self.profile, station)
            self.assertEqual(a, 2)
            self.assertLessEqual(b, 4)
            self.assertGreaterEqual(b, 3)
        self.assertEqual(width_at(self.profile, 100), (2, 4))
        self.assertEqual(width_at(self.profile, 300), (2, 3))
        self.assertLess(abs(width_at(self.profile, 100.01)[1] - 4), 1e-8)
        self.assertLess(abs(width_at(self.profile, 99.99)[1] - 4), 1e-8)

    def test_edges_keep_width_and_normal_on_a_circular_axis(self):
        for angle in (0, 0.5, 1, 2, 3):
            center = [10 * math.cos(angle), 10 * math.sin(angle)]
            tangent = [-math.sin(angle), math.cos(angle)]
            edges = offset_edges(center, tangent, (2, 3))
            self.assertAlmostEqual(math.dist(*edges), 5)
            self.assertAlmostEqual(math.hypot(*edges[0]), 12)
            self.assertAlmostEqual(math.hypot(*edges[1]), 7)
        with self.assertRaises(ValueError):
            offset_edges([0, 0], [0, 0], (2, 3))

    def test_missing_evidence_unordered_and_outside_domain_fail(self):
        for mutation in ("evidence", "order", "nan"):
            profile = copy.deepcopy(self.profile)
            if mutation == "evidence":
                profile["evidence"] = None
            elif mutation == "order":
                profile["samples"].reverse()
            else:
                profile["samples"][1]["left_m"] = float("nan")
            with self.assertRaises(ValueError):
                width_at(profile, 50)
        with self.assertRaises(ValueError):
            width_at(self.profile, -1)

    def test_validator_rejects_width_drift_even_inside_old_width_bounds(self):
        from scripts.geometry.test_curved_road_plan import CurvedRoadPlanTests

        fixture = CurvedRoadPlanTests()
        fixture.setUp()
        packet = fixture.packet
        packet["geometry_contract"] = "common-axis-width-v2"
        packet["point_type"] = "CurveCustomTangent"
        packet["width_profile"] = self.profile
        packet["axis_arc"] = {
            "center_xy_m": [0, 10],
            "radius_m": 10,
            "fit_start_m": 0,
            "fit_end_m": 1,
        }
        for row in packet["stations"]:
            row["center_xy_m"] = [row["station_m"], 0]
            row["tangent_xy_m_per_key"] = [1, 0]
            row["edges_xy_m"] = offset_edges(
                row["center_xy_m"], [1, 0], width_at(self.profile, row["station_m"])
            )
        packet["stations"][400]["edges_xy_m"][1][1] += 0.05
        with self.assertRaisesRegex(ValueError, "width profile"):
            prepare_sections(packet, fixture.source, **fixture.kwargs)


class CommonAxisAdmissionTests(unittest.TestCase):
    def test_valid_circle_and_width_flow_into_existing_sections(self):
        from scripts.geometry.test_curved_road_plan import CurvedRoadPlanTests

        fixture = CurvedRoadPlanTests()
        fixture.setUp()
        packet = fixture.packet
        packet.update(
            geometry_contract="common-axis-width-v2",
            point_type="CurveCustomTangent",
            width_profile={
                "evidence": {"class": "Synthetic test"},
                "samples": [
                    {"station_m": s, "left_m": 3, "right_m": 3} for s in (0, 300)
                ],
            },
            axis_arc={
                "center_xy_m": [0, 10000],
                "radius_m": 10000,
                "fit_start_m": 0,
                "fit_end_m": 300,
            },
        )
        for row in packet["stations"]:
            angle = row["station_m"] / 10000
            center = [10000 * math.sin(angle), 10000 * (1 - math.cos(angle))]
            tangent = [math.cos(angle), math.sin(angle)]
            row.update(
                center_xy_m=center,
                tangent_xy_m_per_key=tangent,
                edges_xy_m=offset_edges(center, tangent, (3, 3)),
            )
        source = [
            [
                [
                    (1 - j / 24) * r["edges_xy_m"][0][k]
                    + j / 24 * r["edges_xy_m"][1][k]
                    for k in range(2)
                ]
                for j in range(25)
            ]
            for r in packet["stations"][::4]
        ]
        _, proof = prepare_sections(packet, source, **fixture.kwargs)
        self.assertEqual(proof["recipe"], "native-common-axis-width-v2")
        self.assertLess(proof["controlled_width"]["maximum_edge_profile_error_m"], 1e-8)
        self.assertLess(proof["controlled_width"]["maximum_axis_radial_error_m"], 1e-8)


class BoundaryDistanceWidthTests(unittest.TestCase):
    def test_source_key_spacing_does_not_control_geometric_width_rate(self):
        from scripts.geometry.road_width_profile import boundary_width_profile, width_at

        profile = {
            "evidence": {"class": "test"},
            "samples": [
                {"station_m": s, "left_m": a, "right_m": 3}
                for s, a in ((0, 2), (5, 3), (10, 2))
            ],
        }
        rows = [
            {"station_m": s, "anchor_xy_m": [d, 0]}
            for s, d in ((0, 0), (2.5, 3), (5, 10), (7.5, 11), (10, 20))
        ]
        mapped, distances = boundary_width_profile(profile, rows)
        self.assertEqual(distances, [0, 3, 10, 11, 20])
        self.assertEqual(width_at(mapped, 10), (3, 3))
        self.assertEqual(width_at(mapped, 20), (2, 3))
        self.assertEqual(profile["samples"][1]["station_m"], 5)


class CircularWidthTests(unittest.TestCase):
    def test_mean_plateau_preserves_observations_and_approach_width(self):
        from scripts.geometry.road_width_profile import circular_width_profile
        raw = {"evidence": {"class": "Inference"}, "samples": [
            {"station_m": s, "left_m": w / 2, "right_m": w / 2}
            for s, w in [(0, 5), (125, 5), (135, 8), (140, 8), (145, 10), (150, 9), (155, 7), (175, 5.75), (300, 5)]
        ]}
        fitted = circular_width_profile(raw, 135, 155, 125, 175)
        self.assertEqual(fitted["evidence"]["raw_width_samples"], raw["samples"])
        for station in [135, 140, 145, 150, 155]:
            self.assertAlmostEqual(sum(width_at(fitted, station)), 8.625)
        self.assertEqual(width_at(fitted, 125), width_at(raw, 125))
        self.assertEqual(width_at(fitted, 175), width_at(raw, 175))
        self.assertEqual(sum(width_at(raw, 145)), 10)

    def test_missing_end_observation_fails(self):
        from scripts.geometry.road_width_profile import circular_width_profile
        raw = {"evidence": {"class": "Inference"}, "samples": [
            {"station_m": s, "left_m": 2.5, "right_m": 2.5} for s in [0, 300]
        ]}
        with self.assertRaisesRegex(ValueError, "endpoint"):
            circular_width_profile(raw, 135, 155, 125, 175)

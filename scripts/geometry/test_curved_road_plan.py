"""Boundary admission regressions; these do not emulate native spline execution."""

import copy
import math
import unittest

from scripts.geometry.curved_road_plan import (
    boundary_span_metrics,
    prepare_sections,
    profile_plan_valid,
)
from scripts.geometry.smooth_road_ribbon import build_smooth_road_ribbon
from scripts.worldgen.bob_profile_inspector import inspect_road_profile


class CurvedRoadPlanTests(unittest.TestCase):
    def setUp(self):
        self.source = [
            [[i * 0.25, -3 + j * 0.25] for j in range(25)] for i in range(1201)
        ]
        self.kwargs = {
            "exact_sha": "a" * 40,
            "source_sha": "b" * 64,
            "profile_sha": "c" * 64,
            "origin": [0, 0],
        }
        self.packet = {
            "exact_sha": "a" * 40,
            "source_sha256": "b" * 64,
            "profile_sha256": "c" * 64,
            "origin_epsg_m": [0, 0],
            "producer": "USplineComponent",
            "point_type": "Curve",
            "status": "NATIVE_CURVES_EXPORTED_REVIEW_REQUIRED",
            "canonical_source_modified": False,
            "map_modified": False,
            "stations": [
                {
                    "station_m": i * 0.0625,
                    "edges_xy_m": [
                        [i * 0.0625, y + 0.1 * math.sin(i * 0.0625 / 10)]
                        for y in (-3, 3)
                    ],
                }
                for i in range(4801)
            ],
        }

    def test_bounded_curves_flow_into_existing_ribbon_without_moving_source(self):
        original = copy.deepcopy(self.source)
        xy, proof = prepare_sections(self.packet, self.source, **self.kwargs)
        self.assertEqual(self.source, original)
        self.assertGreater(proof["max_corresponding_edge_displacement_m"], 0.09)
        profile = {
            "region_id": "sa_calobra",
            "status": "REVIEW_REQUIRED",
            "source_xy_preserved": False,
            "canonical_source_xy_preserved": True,
            "terrain_modified": False,
            "road_earthworks_modified": False,
            "earthworks_authoring_permitted": False,
            "authoritative_physics": False,
            "geographic_width_admitted": False,
            "road_admitted": False,
            "exact_sha": "a" * 40,
            "source_sha256": "b" * 64,
            "profile_sha256": "c" * 64,
            "presentation_plan": proof,
            "stations": [
                {
                    "station_m": i * 0.25,
                    "xy_local_m": row,
                    "source_xy_local_m": original[i],
                    "candidate_ground_m": [600.0] * 25,
                    "lateral_m": [-3 + j * 0.25 for j in range(25)],
                }
                for i, row in enumerate(xy)
            ],
        }
        self.assertTrue(profile_plan_valid(profile))
        profile.update(
            heightmap_sha256="d" * 64,
            imagery_sha256="e" * 64,
            producer_sha256="f" * 64,
            parameters={
                "station_step_m": 0.25,
                "review_delta_m": 0.5,
                "review_grade": 0.25,
                "review_crossfall": 0.12,
            },
        )
        for row in profile["stations"]:
            row.update(candidate_center_m=600.0, native_ground_m=[600.0] * 25)
        self.assertTrue(inspect_road_profile(profile)["inspection_complete"])
        profile["parameters"]["station_step_m"] = 0.5
        self.assertFalse(inspect_road_profile(profile)["inspection_complete"])
        profile["parameters"]["station_step_m"] = 0.25
        vertices, _, _ = build_smooth_road_ribbon(profile)
        self.assertEqual(vertices[250][:2], xy[10][0])
        profile["stations"][10]["xy_local_m"][0][0] += 0.1
        self.assertFalse(profile_plan_valid(profile))
        with self.assertRaises(ValueError):
            build_smooth_road_ribbon(profile)

    def test_mismatched_source_and_missing_samples_fail_closed(self):
        for mutation in ("sha", "missing", "nan"):
            packet = copy.deepcopy(self.packet)
            if mutation == "sha":
                packet["exact_sha"] = "d" * 40
            elif mutation == "missing":
                packet["stations"].pop(400)
            else:
                packet["stations"][400]["edges_xy_m"][0][0] = float("nan")
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                prepare_sections(packet, self.source, **self.kwargs)

    def test_crossed_edges_and_displaced_hairpin_arm_are_rejected(self):
        for mutation in ("crossing", "displacement"):
            packet = copy.deepcopy(self.packet)
            if mutation == "crossing":
                packet["stations"][400]["edges_xy_m"].reverse()
            else:
                for row in packet["stations"]:
                    for point in row["edges_xy_m"]:
                        point[0] += 2.0
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                prepare_sections(packet, self.source, **self.kwargs)

    def test_coarse_chord_cannot_hide_curve_between_render_stations(self):
        packet = copy.deepcopy(self.packet)
        for point in packet["stations"][402]["edges_xy_m"]:
            point[1] += 0.1
        with self.assertRaisesRegex(ValueError, "tessellation"):
            prepare_sections(packet, self.source, **self.kwargs)

    def test_legacy_false_preservation_flag_does_not_admit_curves(self):
        self.assertFalse(profile_plan_valid({"source_xy_preserved": False}))
        self.assertFalse(
            profile_plan_valid({"source_xy_preserved": True, "presentation_plan": {}})
        )

    def test_fillet_rejects_the_pinched_apex_but_accepts_a_round_boundary(self):
        spec = {
            "edge": 1,
            "start_station_m": 140,
            "end_station_m": 155,
            "minimum_radius_m": 1.5,
            "point_type": "CurveCustomTangent",
            "join_position_error_m": 0.0,
            "join_tangent_error_m_per_key": 0.0,
        }
        for radius in (0.3, 3.0):
            rows = [
                {
                    "station_m": 140 + i / 16,
                    "edges_xy_m": [
                        [0, 0],
                        [radius * math.cos(i / 240), radius * math.sin(i / 240)],
                    ],
                }
                for i in range(241)
            ]
            if radius < 1.5:
                with self.assertRaisesRegex(ValueError, "pinched"):
                    boundary_span_metrics(rows, spec)
            else:
                result = boundary_span_metrics(rows, spec)
                self.assertAlmostEqual(result["minimum_sampled_radius_m"], radius)
                for key in ("join_position_error_m", "join_tangent_error_m_per_key"):
                    with (
                        self.subTest(key=key),
                        self.assertRaisesRegex(ValueError, "join"),
                    ):
                        boundary_span_metrics(rows, dict(spec, **{key: 0.1}))


if __name__ == "__main__":
    unittest.main()

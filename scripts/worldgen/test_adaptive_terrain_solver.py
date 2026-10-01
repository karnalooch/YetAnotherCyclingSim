"""Tests for the deterministic adaptive terrain policy and case memory."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

from scripts.worldgen.adaptive_terrain_solver import (
    BOB_EXPANSION,
    BOB_NAME,
    BOB_SYSTEM_ID,
    FEATURE_SOURCE_PCGEX,
    STRATEGY_HAIRPIN_CLEARANCE,
    STRATEGY_NATIVE_BLEND,
    STRATEGY_RETAINING_OR_CLIFF,
    BobTerrainArchitect,
    TerrainFeaturePacket,
    TerrainFeatureProvenance,
    TerrainFeatures,
    TerrainParameters,
    VerifiedTerrainCase,
    choose_terrain_decision,
    decision_report,
    feature_packet_from_mapping,
    load_case_memory,
    load_policy,
    similarity_score,
)


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "worldgen/terrain/adaptive_terrain_policy.json"
CASES_PATH = ROOT / "worldgen/terrain/verified_terrain_cases.json"


def hairpin_features() -> TerrainFeatures:
    return TerrainFeatures(
        longitudinal_grade=-0.059,
        left_cross_slope=0.18,
        right_cross_slope=-0.12,
        road_to_dtm_delta_m=0.45,
        dtm_roughness_m=0.18,
        curvature_radius_m=8.15,
        nearest_branch_xy_m=9.0,
        nearest_branch_z_separation_m=0.8,
        max_cut_fill_m=3.5,
    )


class AdaptiveTerrainSolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = load_policy(POLICY_PATH)

    def test_expert_repair_rule_cannot_bypass_acceptance(self) -> None:
        import copy
        policy = copy.deepcopy(self.policy)
        policy["retaining_repair_rule"]["promotion_requires"] = ["same_exact_sha_technical_PASS"]
        with self.assertRaisesRegex(ValueError, "human visual PASS"):
            BobTerrainArchitect(policy=policy, cases=())

    def test_bob_identity_is_stable_and_policy_owned(self) -> None:
        self.assertEqual(BOB_NAME, "BOB")
        self.assertEqual(BOB_EXPANSION, "Builder Of Berms")
        self.assertEqual(BOB_SYSTEM_ID, "bob-terrain-architect-v1")
        self.assertEqual(
            self.policy["policy_id"],
            "bob-near-field-terrain-v1",
        )
        self.assertEqual(self.policy["architect"]["name"], "BOB")

    def test_bob_architect_emits_identity_in_decision_report(self) -> None:
        packet = TerrainFeaturePacket(
            corridor_id="sp638-hairpin-15460",
            exact_sha="a" * 40,
            provenance=TerrainFeatureProvenance(
                source_kind="yacs_python_analysis",
                source_artifact_sha256="b" * 64,
                source_dataset_id="hairpin-fixture",
                canonical_road_xy_preserved=True,
                authoritative_route_geometry=False,
                authoritative_physics=False,
            ),
            features=hairpin_features(),
        )
        bob = BobTerrainArchitect(policy=self.policy, cases=())
        report = bob.review(packet)
        self.assertEqual(report["architect"]["name"], "BOB")
        self.assertEqual(
            report["architect"]["expansion"],
            "Builder Of Berms",
        )
        self.assertEqual(
            report["architect"]["system_id"],
            "bob-terrain-architect-v1",
        )
        self.assertEqual(
            report["decision"]["strategy"],
            STRATEGY_HAIRPIN_CLEARANCE,
        )

    def test_empty_verified_memory_is_valid(self) -> None:
        self.assertEqual(load_case_memory(CASES_PATH), ())

    def test_minor_native_corridor_uses_native_blend(self) -> None:
        features = TerrainFeatures(
            longitudinal_grade=0.035,
            left_cross_slope=0.04,
            right_cross_slope=-0.03,
            road_to_dtm_delta_m=0.12,
            dtm_roughness_m=0.05,
            curvature_radius_m=90.0,
            nearest_branch_xy_m=None,
            nearest_branch_z_separation_m=None,
            max_cut_fill_m=0.30,
        )
        decision = choose_terrain_decision(features, self.policy, ())
        self.assertEqual(decision.strategy, STRATEGY_NATIVE_BLEND)
        self.assertFalse(decision.learning_applied)

    def test_tight_hairpin_uses_clearance_strategy(self) -> None:
        decision = choose_terrain_decision(hairpin_features(), self.policy, ())
        self.assertEqual(decision.strategy, STRATEGY_HAIRPIN_CLEARANCE)
        self.assertGreaterEqual(decision.parameters.shoulder_apron_m, 1.5)
        self.assertGreaterEqual(decision.parameters.min_asphalt_clearance_m, 0.06)

    def test_stacked_branch_escalates_out_of_heightfield(self) -> None:
        features = replace(
            hairpin_features(),
            nearest_branch_xy_m=4.0,
            nearest_branch_z_separation_m=3.0,
        )
        decision = choose_terrain_decision(features, self.policy, ())
        self.assertEqual(decision.strategy, STRATEGY_RETAINING_OR_CLIFF)
        self.assertFalse(decision.learning_applied)
        self.assertIn(
            "case memory cannot override safety escalation",
            decision.reasons,
        )

    def test_verified_similar_case_tunes_same_strategy_parameters(self) -> None:
        features = hairpin_features()
        case = VerifiedTerrainCase(
            case_id="hairpin-pass-001",
            exact_sha="a" * 40,
            technical_status="PASS",
            visual_status="PASS",
            strategy=STRATEGY_HAIRPIN_CLEARANCE,
            features=replace(features, road_to_dtm_delta_m=0.50),
            parameters=TerrainParameters(
                shoulder_apron_m=2.0,
                transition_width_m=12.0,
                max_ground_adjustment_m=5.0,
                min_asphalt_clearance_m=0.08,
            ),
        )

        decision = choose_terrain_decision(features, self.policy, (case,))
        self.assertTrue(decision.learning_applied)
        self.assertEqual(decision.contributing_case_ids, ("hairpin-pass-001",))
        self.assertGreaterEqual(decision.parameters.shoulder_apron_m, 2.0)
        self.assertGreaterEqual(decision.parameters.transition_width_m, 12.0)
        self.assertLessEqual(decision.parameters.max_ground_adjustment_m, 5.0)
        self.assertGreaterEqual(decision.parameters.min_asphalt_clearance_m, 0.08)

    def test_unverified_case_never_teaches_policy(self) -> None:
        case = VerifiedTerrainCase(
            case_id="rejected-hairpin",
            exact_sha="b" * 40,
            technical_status="PASS",
            visual_status="FAIL",
            strategy=STRATEGY_HAIRPIN_CLEARANCE,
            features=hairpin_features(),
            parameters=TerrainParameters(
                shoulder_apron_m=4.0,
                transition_width_m=20.0,
                max_ground_adjustment_m=2.0,
                min_asphalt_clearance_m=0.20,
            ),
        )
        decision = choose_terrain_decision(hairpin_features(), self.policy, (case,))
        self.assertFalse(decision.learning_applied)
        self.assertEqual(decision.contributing_case_ids, ())

    def test_dissimilar_case_is_ignored(self) -> None:
        case = VerifiedTerrainCase(
            case_id="dissimilar-hairpin",
            exact_sha="c" * 40,
            technical_status="PASS",
            visual_status="PASS",
            strategy=STRATEGY_HAIRPIN_CLEARANCE,
            features=replace(
                hairpin_features(),
                longitudinal_grade=0.25,
                road_to_dtm_delta_m=3.5,
                dtm_roughness_m=1.5,
                max_cut_fill_m=3.9,
            ),
            parameters=TerrainParameters(
                shoulder_apron_m=3.0,
                transition_width_m=18.0,
                max_ground_adjustment_m=3.0,
                min_asphalt_clearance_m=0.12,
            ),
        )
        self.assertLess(
            similarity_score(hairpin_features(), case.features, self.policy),
            float(self.policy["learning"]["minimum_similarity"]),
        )
        decision = choose_terrain_decision(hairpin_features(), self.policy, (case,))
        self.assertFalse(decision.learning_applied)


    def test_pcgex_feature_packet_preserves_authority_boundary(self) -> None:
        packet = feature_packet_from_mapping(
            {
                "schema_version": 1,
                "corridor_id": "sp638-hairpin-15460",
                "exact_sha": "d" * 40,
                "provenance": {
                    "source_kind": FEATURE_SOURCE_PCGEX,
                    "source_artifact_sha256": "e" * 64,
                    "source_dataset_id": "pcgex-center-dataset-0",
                    "canonical_road_xy_preserved": True,
                    "authoritative_route_geometry": False,
                    "authoritative_physics": False,
                    "pcgex_commit": "f" * 40,
                },
                "features": {
                    "longitudinal_grade": -0.059,
                    "left_cross_slope": 0.18,
                    "right_cross_slope": -0.12,
                    "road_to_dtm_delta_m": 0.45,
                    "dtm_roughness_m": 0.18,
                    "curvature_radius_m": 8.15,
                    "nearest_branch_xy_m": 9.0,
                    "nearest_branch_z_separation_m": 0.8,
                    "max_cut_fill_m": 3.5,
                },
            }
        )
        self.assertEqual(packet.provenance.source_kind, FEATURE_SOURCE_PCGEX)
        self.assertFalse(packet.provenance.authoritative_route_geometry)
        self.assertFalse(packet.provenance.authoritative_physics)

        decision = choose_terrain_decision(packet.features, self.policy, ())
        report = decision_report(packet, decision)
        self.assertEqual(report["corridor_id"], "sp638-hairpin-15460")
        self.assertEqual(
            report["feature_provenance"]["source_kind"],
            FEATURE_SOURCE_PCGEX,
        )
        self.assertEqual(
            report["decision"]["strategy"],
            STRATEGY_HAIRPIN_CLEARANCE,
        )

    def test_feature_packet_rejects_pcgex_route_authority(self) -> None:
        with self.assertRaisesRegex(ValueError, "route authority"):
            TerrainFeaturePacket(
                corridor_id="bad-pcgex-authority",
                exact_sha="1" * 40,
                provenance=TerrainFeatureProvenance(
                    source_kind=FEATURE_SOURCE_PCGEX,
                    source_artifact_sha256="2" * 64,
                    source_dataset_id="dataset-0",
                    canonical_road_xy_preserved=True,
                    authoritative_route_geometry=True,
                    authoritative_physics=False,
                    pcgex_commit="3" * 40,
                ),
                features=hairpin_features(),
            )

    def test_decision_is_deterministic_for_same_inputs(self) -> None:
        first = choose_terrain_decision(hairpin_features(), self.policy, ())
        second = choose_terrain_decision(hairpin_features(), self.policy, ())
        self.assertEqual(first, second)


class ExistingCorridorReviewTests(unittest.TestCase):
    def review(self, *, height_delta=0.0, xs=None, points=None, exact_sha="a" * 40):
        from scripts.geometry.sp638_local_corridor import (
            CrossSectionPoint, Vec3, build_corridor_mesh, make_constant_profiles,
        )
        from scripts.worldgen.review_sp638_terrain import review_existing_corridor

        xs = tuple(range(-20, 21)) if xs is None else xs
        ys = tuple(range(20, -21, -1))
        heights = tuple(tuple(0.10 * x + 0.20 * y for x in xs) for y in ys)
        points = points or tuple(Vec3(x, 0.0, 0.10 * x + height_delta) for x in range(-10, 11, 2))
        profile = (
            CrossSectionPoint(-4.0, 0.0, "left_shoulder"),
            CrossSectionPoint(-3.0, 0.0, "left_road_edge"),
            CrossSectionPoint(3.0, 0.0, "right_road_edge"),
            CrossSectionPoint(4.0, 0.0, "right_shoulder"),
        )
        profiles = make_constant_profiles(len(points), profile)
        mesh = build_corridor_mesh(points, profiles, tangent_half_window_stations=3)
        return review_existing_corridor(
            bob=BobTerrainArchitect.from_paths(POLICY_PATH, CASES_PATH),
            xs=xs, ys=ys, native_heights=heights, centerline=points,
            corridor_mesh=mesh, profiles=profiles, origin=Vec3(0.0, 0.0, 0.0),
            exact_sha=exact_sha, native_binary_sha256="b" * 64,
            pcgex_output_sha256="c" * 64, start_station_m=100.0,
        )

    def test_planar_native_terrain_has_zero_roughness_and_measured_cross_slopes(self):
        result = self.review()
        feature = result["decisions"][5]["features"]
        self.assertAlmostEqual(feature["longitudinal_grade"], 0.10)
        self.assertAlmostEqual(feature["left_cross_slope"], -0.20)
        self.assertAlmostEqual(feature["right_cross_slope"], 0.20)
        self.assertAlmostEqual(feature["road_to_dtm_delta_m"], 0.0)
        self.assertAlmostEqual(feature["dtm_roughness_m"], 0.0)
        self.assertAlmostEqual(feature["max_cut_fill_m"], 0.8)
        self.assertEqual(result["status"], "MEASURED")
        self.assertFalse(result["parameters_applied"])
        self.assertFalse(result["learning_case_promoted"])

    def test_escalation_measures_cut_and_fill_sides_before_proposing_repairs(self):
        fill = self.review(height_delta=5.0)["decisions"][5]
        cut = self.review(height_delta=-5.0)["decisions"][5]
        for report in (fill, cut):
            plan = report["repair_plan"]
            self.assertEqual(plan["status"], "PROPOSED_NOT_EXECUTED")
            self.assertEqual(plan["side_resolution"], "MEASURED_ROAD_LOCAL_FRAME")
            self.assertFalse(plan["learning_case_promoted"])
            self.assertFalse(plan["rule"]["threshold_override_allowed"])
            self.assertTrue(plan["rule"]["shared_ground_owner_between_branches"])
        for side in ("left", "right"):
            self.assertGreater(fill["repair_plan"]["side_candidates"][side]["required_fill_m"], 4.0)
            self.assertEqual(fill["repair_plan"]["side_candidates"][side]["required_cut_m"], 0.0)
            self.assertGreater(cut["repair_plan"]["side_candidates"][side]["required_cut_m"], 4.0)
            self.assertEqual(cut["repair_plan"]["side_candidates"][side]["required_fill_m"], 0.0)

    def test_existing_large_earthwork_is_rejected_without_policy_rewrite(self):
        result = self.review(height_delta=5.0)
        self.assertEqual(result["status"], "REQUIRES_ESCALATION")
        self.assertEqual(result["technical_acceptance"], "FAIL")
        self.assertEqual(len(result["escalation_station_indices"]), result["station_count"])
        self.assertFalse(result["learning_case_promoted"])

    def test_missing_native_coverage_is_not_clamped_or_marked_pass(self):
        result = self.review(xs=tuple(range(-3, 4)))
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertLess(result["measured_station_count"], result["station_count"])
        self.assertTrue(result["uncovered_stations"])
        self.assertNotEqual(result["technical_acceptance"], "PASS")

    def test_invalid_exact_sha_is_rejected_even_without_coverage(self):
        with self.assertRaisesRegex(ValueError, "SHA40"):
            self.review(xs=tuple(range(-3, 4)), exact_sha="missing")

    def test_repeated_review_is_deterministic(self):
        self.assertEqual(self.review(), self.review())

    def test_competing_branch_distance_and_z_come_from_the_same_segment(self):
        from scripts.geometry.sp638_local_corridor import Vec3
        from scripts.worldgen.review_sp638_terrain import _nearest_branch

        points = (Vec3(0, 0, 0), Vec3(10, 0, 0), Vec3(10, 4, 3), Vec3(-10, 4, 3))
        xy, z = _nearest_branch(points, (0.0, 10.0, 25.0, 45.0), 0, 20.0)
        self.assertAlmostEqual(xy, 4.0)
        self.assertAlmostEqual(z, 3.0)

    def test_native_sample_rejects_uncovered_positions(self):
        from scripts.worldgen.review_sp638_terrain import MissingDtmCoverage, sample_native_height

        with self.assertRaises(MissingDtmCoverage):
            sample_native_height((0, 1, 2), (2, 1, 0), ((0, 0, 0),) * 3, -0.01, 1.0)


if __name__ == "__main__":
    unittest.main()

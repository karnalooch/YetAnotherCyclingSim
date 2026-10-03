"""Tests for the deterministic adaptive terrain policy and case memory."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

from scripts.worldgen.adaptive_terrain_solver import (
    BOB_EXPANSION,
    review_pavement_contact_trial,
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





class BobContactReviewTests(unittest.TestCase):
    def test_failed_centroids_cannot_be_hidden_by_passing_native_vertices(self):
        r16 = {"floating_centroid_count":456, "penetrating_centroid_count":712,
               "triangle_centroid_count":28800, "r16_contact_status":"FAIL"}
        native = {"floating_sample_count":0, "penetrating_sample_count":0,
                  "trace_miss_count":0,"trace_sample_count":15025,
                  "native_sample_contact_status":"PASS"}
        result = review_pavement_contact_trial(r16, geographic_width_admitted=False, native_contact=native)
        self.assertEqual(result["status"], "REJECT_CONTACT")
        self.assertFalse(result["eligible_for_learning"])
        self.assertFalse(result["geometry_repair_executed"])
        self.assertIn("Road_Earthworks", " ".join(result["next_actions"]))
        self.assertIn("verify separate left/right", result["next_actions"][0])

    def test_missing_or_boolean_counts_never_become_success(self):
        result = review_pavement_contact_trial({"floating_centroid_count":False}, geographic_width_admitted=False)
        self.assertEqual(result["status"], "REVIEW_PENDING")
        self.assertFalse(result["sample_proofs_complete"])
        self.assertFalse(result["road_admitted"])

    def test_sample_pass_still_needs_continuous_contact_and_visual_review(self):
        r16 = {"floating_centroid_count":0, "penetrating_centroid_count":0,
               "triangle_centroid_count":28800, "r16_contact_status":"PASS"}
        native = {"floating_sample_count":0,"penetrating_sample_count":0,
                  "trace_miss_count":0,"trace_sample_count":15025,
                  "native_sample_contact_status":"PASS"}
        result = review_pavement_contact_trial(r16, geographic_width_admitted=True, native_contact=native)
        self.assertTrue(result["sample_proofs_complete"])
        self.assertEqual(result["status"], "REVIEW_PENDING")
        self.assertFalse(result["eligible_for_learning"])
        self.assertFalse(result["road_admitted"])


if __name__ == "__main__":
    unittest.main()

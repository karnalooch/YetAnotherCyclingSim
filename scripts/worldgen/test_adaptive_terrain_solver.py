"""Tests for the deterministic adaptive terrain policy and case memory."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

from scripts.worldgen.adaptive_terrain_solver import (
    STRATEGY_HAIRPIN_CLEARANCE,
    STRATEGY_NATIVE_BLEND,
    STRATEGY_RETAINING_OR_CLIFF,
    TerrainFeatures,
    TerrainParameters,
    VerifiedTerrainCase,
    choose_terrain_decision,
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

    def test_decision_is_deterministic_for_same_inputs(self) -> None:
        first = choose_terrain_decision(hairpin_features(), self.policy, ())
        second = choose_terrain_decision(hairpin_features(), self.policy, ())
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

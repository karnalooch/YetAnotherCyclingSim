"""Frozen boundaries and failure paths for sampled-only contact decisions."""

import copy
import unittest

from pcg_rock_contact_policy import evaluate, trial_policy


def measurement():
    return {
        "height_cm": 100,
        "uniform_scale": 1,
        "yaw_deg": 0,
        "tilt_deg": 0,
        "max_local_slope_deg": 10,
        "ground_class": "LandscapeHeightfieldCollisionComponent",
        "coverage_status": "COMPLETE_SAMPLED_MESH_FOOTPRINT",
        "sample_count": 100,
        "valid_ground_count": 100,
        "fit": {
            "required_embedding_cm": 20,
            "root_zero_sampled_air_cm": 0,
            "exposure_max_cm": 80,
            "exposed_count": 80,
            "max_positive_bottom_gap_cm": 0,
        },
        "refinement": {
            "coarse_grid": 33,
            "fine_grid": 65,
            "coarse_root_cm": 0.1,
            "fine_root_cm": 0,
            "coarse_embedding_cm": 20,
            "fine_embedding_cm": 20,
        },
    }


class ContactPolicyTests(unittest.TestCase):
    def test_exact_boundaries_pass_sampled_only(self):
        result = evaluate(measurement(), trial_policy())
        self.assertEqual(result["status"], "PASS_SAMPLED_CONTACT_ONLY")
        self.assertEqual(result["reasons"], [])
        self.assertFalse(result["full_qualification"])
        self.assertFalse(result["placement"])
        self.assertFalse(result["continuous_support_verified"])

    def test_quality_boundaries_reject(self):
        cases = [
            ("max_local_slope_deg", 10.001, "EXCESSIVE_LOCAL_SLOPE"),
            ("uniform_scale", 1.1, "UNSUPPORTED_UNIFORM_SCALE"),
            ("tilt_deg", 0.1, "UNSUPPORTED_TILT_DEG"),
            ("yaw_deg", 1, "UNSUPPORTED_YAW_DEG"),
        ]
        for key, value, reason in cases:
            m = measurement()
            m[key] = value
            with self.subTest(key=key):
                self.assertIn(reason, evaluate(m, trial_policy())["reasons"])
        for key, value, reason in [
            ("required_embedding_cm", 20.001, "EXCESSIVE_EMBEDDING"),
            ("exposure_max_cm", 79.999, "INSUFFICIENT_EXPOSED_HEIGHT"),
            ("exposed_count", 79, "INSUFFICIENT_EXPOSED_RAYS"),
            ("max_positive_bottom_gap_cm", 0.001, "POSITIVE_BOTTOM_GAP"),
        ]:
            m = measurement()
            m["fit"][key] = value
            with self.subTest(key=key):
                self.assertIn(reason, evaluate(m, trial_policy())["reasons"])

    def test_ground_coverage_and_unknowns_fail_closed(self):
        for key, value in [
            ("valid_ground_count", 99),
            ("ground_class", "StaticMeshComponent"),
            ("coverage_status", "UNKNOWN"),
        ]:
            m = measurement()
            m[key] = value
            self.assertEqual(evaluate(m, trial_policy())["status"], "REJECTED")
        for m in ({}, None, {"fit": {}}):
            self.assertEqual(evaluate(m, trial_policy())["status"], "REJECTED")

    def test_nonfinite_and_invalid_counts(self):
        for value in (float("nan"), float("inf"), True, "100", -1, 0):
            m = measurement()
            m["height_cm"] = value
            with self.subTest(value=value):
                self.assertEqual(evaluate(m, trial_policy())["status"], "REJECTED")
        for value in (0, -1, True, 1.5):
            m = measurement()
            m["sample_count"] = value
            self.assertEqual(evaluate(m, trial_policy())["status"], "REJECTED")

    def test_refinement_convergence_and_consistency(self):
        for key, value, reason in [
            ("coarse_root_cm", 0.10001, "ROOT_NOT_CONVERGED"),
            ("coarse_embedding_cm", 19.899, "EMBEDDING_NOT_CONVERGED"),
            ("fine_root_cm", 0.01, "FINE_FIT_REFINEMENT_MISMATCH"),
            ("fine_grid", 33, "INVALID_REFINEMENT_GRIDS"),
        ]:
            m = measurement()
            m["refinement"][key] = value
            with self.subTest(key=key):
                self.assertIn(reason, evaluate(m, trial_policy())["reasons"])

    def test_modified_policy_and_independent_copies(self):
        policy = trial_policy()
        independent = copy.deepcopy(policy)
        policy["max_embedding_fraction"] = 0.7
        self.assertEqual(
            evaluate(measurement(), policy)["reasons"], ["UNKNOWN_OR_MODIFIED_POLICY"]
        )
        self.assertEqual(trial_policy(), independent)
        for key, value in [("schema_version", True), ("extra_limit", 100)]:
            policy = trial_policy()
            policy[key] = value
            self.assertEqual(evaluate(measurement(), policy)["status"], "REJECTED")


if __name__ == "__main__":
    unittest.main()

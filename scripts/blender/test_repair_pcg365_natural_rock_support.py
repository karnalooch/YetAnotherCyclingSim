"""CPU-only repair contract regression tests; no Blender, Unreal or GPU."""

import copy
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location(
    "repair", HERE / "repair_pcg365_natural_rock_support.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
policy = m.asset_module("pcg_rock_contact_policy")
support = m.asset_module("pcg_boulder_support")


class RepairContract(unittest.TestCase):
    def catalog(self):
        families = sorted(m.FAMILIES)
        rows = []
        for i, family in enumerate(families):
            for variant in range(1, (3 if i < 4 else 2) + 1):
                rows.append(
                    {
                        "id": f"{family}_{variant:02d}",
                        "source_id": family,
                        "sha256": "a" * 64,
                        "bytes": 1,
                        "license": "CC0-1.0",
                        "placement": False,
                        "qualified_assets": [],
                    }
                )
        return {
            "schema_version": 1,
            "placement": False,
            "qualified_assets": [],
            "variants": rows,
        }

    def intervals(self, bottoms, tops=None):
        return [
            {"bottom_z_cm": b, "top_z_cm": t, "ground_z_cm": 0.0}
            for b, t in zip(bottoms, tops or [100.0] * len(bottoms))
        ]

    def evaluate(self, coarse, fine=None):
        return m.evaluate_ideal_plane(
            coarse, fine if fine is not None else coarse, 100.0, policy, support
        )

    def test_declared_repair_planes_are_fixed_and_separate(self):
        self.assertEqual(m.CUT_FRACTIONS, (0.20, 0.35, 0.50, 0.65))
        self.assertEqual(m.SCHEMA, "PCG365_SOURCE_RECUT_SUPPORT_V1")
        self.assertEqual(policy.trial_policy()["max_embedding_fraction"], 0.20)
        self.assertEqual(policy.trial_policy()["max_positive_bottom_gap_cm"], 0.0)

    def test_twenty_eight_family_source_contract(self):
        self.assertEqual(len(m.validate_catalog(self.catalog())), 20)
        for mutate in (
            lambda d: d.update(schema_version=True),
            lambda d: d.update(placement=True),
            lambda d: d["variants"][0].update(license="unknown"),
            lambda d: d["variants"][0].update(id="../traversal"),
            lambda d: d["variants"][0].update(qualified_assets=["rock"]),
            lambda d: d["variants"][0].update(source_id="wrong"),
        ):
            data = self.catalog()
            mutate(data)
            with self.assertRaises(ValueError):
                m.validate_catalog(data)
        data = self.catalog()
        data["variants"][1] = copy.deepcopy(data["variants"][0])
        with self.assertRaises(ValueError):
            m.validate_catalog(data)

    def test_flat_source_pass_is_explicitly_synthetic_unqualified(self):
        result = self.evaluate(self.intervals([0, 0, 0]))
        self.assertEqual(
            result["status"], "PASS_IDEAL_PLANE_SAMPLED_SOURCE_DIAGNOSTIC_ONLY"
        )
        self.assertFalse(result["native_qualification"])
        self.assertFalse(result["placement"])
        self.assertFalse(result["continuous_support_verified"])
        self.assertEqual(
            result["actual_ground_kind"], "ANALYTICAL_LOCAL_Z0_PLANE_NOT_LANDSCAPE"
        )
        self.assertFalse(
            result["policy_decision_for_synthetic_plane"]["full_qualification"]
        )

    def test_full_footprint_undercut_is_not_cap_only_pass(self):
        result = self.evaluate(self.intervals([0, 0, 90]))
        reasons = result["policy_decision_for_synthetic_plane"]["reasons"]
        self.assertEqual(result["status"], "REJECTED_SOURCE_DIAGNOSTIC")
        self.assertIn("EXCESSIVE_EMBEDDING", reasons)
        self.assertIn("INSUFFICIENT_EXPOSED_HEIGHT", reasons)

    def test_unchanged_twenty_percent_boundary_and_exposed_rays(self):
        self.assertEqual(
            self.evaluate(self.intervals([0, 20]))["status"],
            "PASS_IDEAL_PLANE_SAMPLED_SOURCE_DIAGNOSTIC_ONLY",
        )
        self.assertIn(
            "EXCESSIVE_EMBEDDING",
            self.evaluate(self.intervals([0, 20.01]))[
                "policy_decision_for_synthetic_plane"
            ]["reasons"],
        )
        result = self.evaluate(self.intervals([0, 0, 0, 0, 0], [0, 0, 100, 100, 100]))
        self.assertIn(
            "INSUFFICIENT_EXPOSED_RAYS",
            result["policy_decision_for_synthetic_plane"]["reasons"],
        )

    def test_refinement_is_not_silently_ignored(self):
        result = self.evaluate(self.intervals([0, 0]), self.intervals([0, 0.2]))
        self.assertIn(
            "ROOT_NOT_CONVERGED",
            result["policy_decision_for_synthetic_plane"]["reasons"],
        )
        self.assertIn(
            "EMBEDDING_NOT_CONVERGED",
            result["policy_decision_for_synthetic_plane"]["reasons"],
        )

    def test_missing_nonfinite_inverted_data_rejects(self):
        for data in ([], self.intervals([float("nan")]), self.intervals([2], [1])):
            with self.assertRaises(ValueError):
                self.evaluate(data)


if __name__ == "__main__":
    unittest.main()

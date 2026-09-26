from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"
UNREAL = ROOT / ".github" / "workflows" / "reusable-unreal.yml"


class ChangeClassifierWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ci = CI.read_text(encoding="utf-8")
        cls.unreal = UNREAL.read_text(encoding="utf-8")

    def test_classifier_is_single_routing_entrypoint(self):
        self.assertIn("name: Classify changes", self.ci)
        self.assertIn("scripts/ci/classify_changes.py", self.ci)
        for output in (
            "python:",
            "cpp:",
            "assets:",
            "ci:",
            "ue_code:",
            "docs_only:",
            "asset_only:",
            "security_base:",
        ):
            self.assertIn(output, self.ci)

    def test_python_lane_is_path_gated(self):
        self.assertIn(
            "needs.changes.outputs.python == 'true' || "
            "needs.changes.outputs.ci == 'true'",
            self.ci,
        )
        self.assertIn("codeql_languages_json: '[\"python\"]'", self.ci)

    def test_cpp_security_and_unreal_are_path_gated(self):
        self.assertIn(
            "needs.changes.outputs.cpp == 'true' || "
            "needs.changes.outputs.ue_code == 'true'",
            self.ci,
        )
        self.assertIn("codeql_languages_json: '[\"c-cpp\"]'", self.ci)
        self.assertIn("name: Code-only Unreal canary", self.ci)
        self.assertIn("needs.changes.outputs.ue_code == 'true'", self.ci)

    def test_asset_lane_is_lightweight_and_pointer_only(self):
        self.assertIn("name: Lightweight asset validation", self.ci)
        self.assertIn("validate_changed_assets.py", self.ci)
        self.assertIn('GIT_LFS_SKIP_SMUDGE: "1"', self.ci)
        self.assertIn("lfs: false", self.ci)

    def test_reusable_unreal_lane_never_materializes_assets(self):
        self.assertIn('GIT_LFS_SKIP_SMUDGE: "1"', self.unreal)
        self.assertIn("lfs: false", self.unreal)
        self.assertNotIn("lfs: true", self.unreal)
        self.assertIn("Test-YacsCodeOnlyCheckout.ps1", self.unreal)

    def test_aggregate_knows_every_optional_lane(self):
        for lane in (
            "python-reference",
            "security-base",
            "security-python",
            "security-cpp",
            "asset-validation",
            "unreal-code",
        ):
            self.assertIn(f"- {lane}", self.ci)
        self.assertIn("require_optional", self.ci)
        self.assertIn("expected skipped", self.ci)

    def test_docs_only_has_no_forced_runtime_lane(self):
        self.assertNotIn("needs.changes.outputs.docs_only == 'true'", self.ci)

    def test_static_schedule_does_not_force_unreal_or_assets(self):
        self.assertIn("--all-static", self.ci)
        self.assertIn('--base "ALL_STATIC"', self.ci)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "asset-full.yml"


class AssetFullWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_lane_is_manual_only_during_trusted_phase(self):
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("pull_request:", self.workflow)
        self.assertNotIn("pull_request_target:", self.workflow)
        self.assertNotIn("schedule:", self.workflow)

    def test_lane_is_self_hosted_and_read_only(self):
        self.assertIn("runs-on: [self-hosted, yacs-ue58]", self.workflow)
        self.assertIn("permissions:\n  contents: read", self.workflow)
        self.assertNotIn("contents: write", self.workflow)
        self.assertNotIn("pull-requests: write", self.workflow)

    def test_lane_resolves_and_checks_exact_main_sha(self):
        self.assertIn("refs/heads/main", self.workflow)
        self.assertIn("/branches/main", self.workflow)
        self.assertIn("expected_sha", self.workflow)
        self.assertIn("git rev-parse HEAD", self.workflow)
        self.assertIn("checkout HEAD", self.workflow)

    def test_lane_intentionally_materializes_full_lfs(self):
        self.assertIn("lfs: true", self.workflow)
        self.assertIn("git lfs fsck", self.workflow)
        self.assertNotIn('GIT_LFS_SKIP_SMUDGE: "1"', self.workflow)

    def test_modes_are_explicit_and_bounded(self):
        for mode in ("map-smoke", "visual", "package", "full"):
            self.assertIn(f"- {mode}", self.workflow)
        self.assertNotIn("\n          - cook\n", self.workflow)
        self.assertIn("package_configuration", self.workflow)
        self.assertIn("- Development", self.workflow)
        self.assertIn("- Shipping", self.workflow)

    def test_map_smoke_uses_existing_stage3_proof(self):
        self.assertIn("Invoke-YacsStage3Proof.ps1", self.workflow)
        self.assertIn("SkipPerformance", self.workflow)

    def test_visual_mode_uses_existing_rendered_proof(self):
        self.assertIn(
            "Invoke-YacsStage3VisualEnvironmentProof.ps1",
            self.workflow,
        )
        self.assertIn("SkipBuild", self.workflow)

    def test_package_mode_uses_dedicated_fail_closed_script(self):
        self.assertIn("Invoke-YacsPackageProof.ps1", self.workflow)
        self.assertIn("inputs.mode == 'package'", self.workflow)
        self.assertIn("PACKAGE_CONFIGURATION", self.workflow)

    def test_full_lane_uploads_only_proof_artifacts(self):
        for extension in ("**/*.json", "**/*.txt", "**/*.log", "**/*.png"):
            self.assertIn(extension, self.workflow)
        self.assertNotIn("Content/**/*.uasset", self.workflow)
        self.assertNotIn("Content/**/*.umap", self.workflow)

    def test_workspace_cleanup_is_unconditional(self):
        self.assertIn("if: ${{ always() }}", self.workflow)
        self.assertIn("git reset --hard", self.workflow)
        self.assertIn("git clean -ffdx", self.workflow)
        self.assertIn("workspace cleanup: PASS", self.workflow)


if __name__ == "__main__":
    unittest.main()

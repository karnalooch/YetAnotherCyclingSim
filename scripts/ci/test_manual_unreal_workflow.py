from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "manual-unreal.yml"


class ManualUnrealWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_manual_unreal_is_dispatch_only(self):
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("pull_request:", self.workflow)
        self.assertNotIn("pull_request_target:", self.workflow)
        self.assertNotIn("push:", self.workflow)
        self.assertNotIn("schedule:", self.workflow)

    def test_manual_unreal_uses_repo_scoped_self_hosted_runner(self):
        self.assertIn("runs-on: [self-hosted, yacs-ue58]", self.workflow)
        self.assertIn("contents: read", self.workflow)
        self.assertNotIn("contents: write", self.workflow)

    def test_canary_modes_are_code_only(self):
        self.assertIn(
            "inputs.mode == 'canary' || inputs.mode == 'intentional-red'",
            self.workflow,
        )
        self.assertIn("Checkout exact trusted revision without LFS payloads", self.workflow)
        self.assertIn('GIT_LFS_SKIP_SMUDGE: "1"', self.workflow)
        self.assertIn("lfs: false", self.workflow)
        self.assertIn("Test-YacsCodeOnlyCheckout.ps1", self.workflow)

    def test_stage3g_modes_use_full_lfs(self):
        self.assertIn(
            "inputs.mode == 'stage3g-author' || inputs.mode == 'stage3g-proof'",
            self.workflow,
        )
        self.assertIn("Checkout exact trusted revision with full LFS", self.workflow)
        self.assertIn("lfs: true", self.workflow)
        self.assertIn("git lfs fsck", self.workflow)

    def test_runner_provenance_records_checkout_mode(self):
        self.assertIn("CheckoutMode = $checkoutMode", self.workflow)
        self.assertIn("$checkoutMode = 'code-only'", self.workflow)
        self.assertIn("$checkoutMode = 'full-lfs'", self.workflow)

    def test_workspace_cleanup_is_unconditional(self):
        self.assertIn("if: ${{ always() }}", self.workflow)
        self.assertIn("git reset --hard", self.workflow)
        self.assertIn("git clean -ffdx", self.workflow)


if __name__ == "__main__":
    unittest.main()

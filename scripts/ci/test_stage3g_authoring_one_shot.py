from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "stage3g-authoring-one-shot.yml"
SENTINEL = ROOT / ".github" / "STAGE3G_AUTHORING_ONE_SHOT"
TARGET_SHA = "da99c0327ff023881ec7a379adf43eda9ca25829"


class Stage3GAuthoringOneShotContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.sentinel = SENTINEL.read_text(encoding="utf-8")

    def test_trigger_is_single_main_sentinel_push(self):
        self.assertIn("push:", self.workflow)
        self.assertIn("branches: [main]", self.workflow)
        self.assertIn(".github/STAGE3G_AUTHORING_ONE_SHOT", self.workflow)
        self.assertNotIn("pull_request:", self.workflow)
        self.assertNotIn("schedule:", self.workflow)

    def test_runner_is_trusted_self_hosted_and_read_only(self):
        self.assertIn("runs-on: [self-hosted, yacs-ue58]", self.workflow)
        self.assertGreaterEqual(self.workflow.count("contents: read"), 2)
        self.assertNotIn("contents: write", self.workflow)
        self.assertNotIn("git push", self.workflow)
        self.assertIn("Isolate self-hosted Git configuration", self.workflow)
        self.assertIn("$env:GIT_CONFIG_GLOBAL = $isolated", self.workflow)
        self.assertIn('"GIT_CONFIG_GLOBAL=$isolated" >> $env:GITHUB_ENV', self.workflow)

    def test_target_is_exact_stage3g_sha_with_full_lfs(self):
        self.assertIn(TARGET_SHA, self.workflow)
        self.assertIn("feat%2Fstage3g-reference-environment", self.workflow)
        self.assertIn("lfs: true", self.workflow)
        self.assertIn("git lfs install --local", self.workflow)
        self.assertIn("git lfs checkout", self.workflow)
        self.assertIn("git lfs fsck", self.workflow)
        self.assertIn("version https://git-lfs.github.com/spec/v1", self.workflow)
        self.assertIn("persist-credentials: false", self.workflow)

    def test_runs_only_stage3g_authoring_and_uploads_binary_source(self):
        self.assertIn("Invoke-YacsStage3GAuthoring.ps1", self.workflow)
        self.assertIn("Content/Prototype/Environment/Stage3G/**", self.workflow)
        self.assertIn("Content/Prototype/Maps/L_CyclingTest.umap", self.workflow)
        self.assertIn("stage3g-authored-source-", self.workflow)

    def test_cleanup_is_unconditional(self):
        self.assertIn("if: ${{ always() }}", self.workflow)
        self.assertIn("git reset --hard", self.workflow)
        self.assertIn("git clean -ffdx", self.workflow)

    def test_sentinel_records_exact_target_and_restore_requirement(self):
        self.assertIn("restore_required=true", self.sentinel)
        self.assertIn("runner=yacs-ue58", self.sentinel)
        self.assertIn(f"target_sha={TARGET_SHA}", self.sentinel)


if __name__ == "__main__":
    unittest.main()

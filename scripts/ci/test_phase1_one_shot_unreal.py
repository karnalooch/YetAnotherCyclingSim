from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "phase1-one-shot-unreal.yml"
SENTINEL = ROOT / ".github" / "PHASE1_UNREAL_CANARY_ONE_SHOT"
UNREAL_CI = ROOT / "scripts" / "ci" / "Invoke-YacsUnrealCi.ps1"


class Phase1OneShotUnrealContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.sentinel = SENTINEL.read_text(encoding="utf-8")
        cls.unreal_ci = UNREAL_CI.read_text(encoding="utf-8")

    def test_one_shot_triggers_only_on_main_sentinel_push(self):
        self.assertIn("push:", self.workflow)
        self.assertIn("branches: [main]", self.workflow)
        self.assertIn('.github/PHASE1_UNREAL_CANARY_ONE_SHOT', self.workflow)
        self.assertNotIn("pull_request:", self.workflow)
        self.assertNotIn("schedule:", self.workflow)

    def test_one_shot_uses_self_hosted_code_only_runner(self):
        self.assertIn("runs-on: [self-hosted, yacs-ue58]", self.workflow)
        self.assertIn('GIT_LFS_SKIP_SMUDGE: "1"', self.workflow)
        self.assertIn("lfs: false", self.workflow)
        self.assertIn("Test-YacsCodeOnlyCheckout.ps1", self.workflow)
        self.assertNotIn("lfs: true", self.workflow)

    def test_green_canary_runs_before_intentional_red(self):
        green = self.workflow.index("Normal green Unreal canary")
        red = self.workflow.index("Intentional-red must fail closed without rebuilding")
        self.assertLess(green, red)
        self.assertIn("Invoke-YacsUnrealCi.ps1", self.workflow)

    def test_intentional_red_reuses_build_and_must_be_zero_discovery(self):
        for token in (
            "-SkipBuild",
            "CyclingDefinitelyDoesNotExist",
            "Intentional-red proof unexpectedly passed.",
            "expected zero discovered tests",
            "intentional_red_verified.json",
            "fail-closed-verified",
        ):
            self.assertIn(token, self.workflow)

    def test_wrapper_supports_skip_build_passthrough(self):
        for token in (
            "[switch] $SkipBuild",
            "$ProofArgs['SkipBuild'] = $true",
            "SkipBuild = [bool]$SkipBuild",
        ):
            self.assertIn(token, self.unreal_ci)

    def test_sentinel_requires_restore(self):
        for token in (
            "scope=single-main-push",
            "restore_required=true",
            "runner=yacs-ue58",
        ):
            self.assertIn(token, self.sentinel)

    def test_artifacts_are_proof_only_and_cleanup_is_unconditional(self):
        self.assertIn("Saved/RuntimeProof/CI/Phase1/**/*.json", self.workflow)
        self.assertIn("Saved/RuntimeProof/CI/Phase1/**/*.txt", self.workflow)
        self.assertIn("Saved/RuntimeProof/CI/Phase1/**/*.log", self.workflow)
        self.assertNotIn("Content/**", self.workflow)
        self.assertIn("if: ${{ always() }}", self.workflow)
        self.assertIn("git reset --hard", self.workflow)
        self.assertIn("git clean -ffdx", self.workflow)


if __name__ == "__main__":
    unittest.main()

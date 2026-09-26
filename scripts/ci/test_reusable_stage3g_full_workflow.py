from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "reusable-stage3g-full.yml"
PREFLIGHT = ROOT / "scripts" / "ue" / "Preflight-YacsProof.ps1"
BASE_PROOF = ROOT / "scripts" / "ue" / "Invoke-YacsProof.ps1"
STAGE3G_PROOF = ROOT / "scripts" / "ue" / "Invoke-YacsStage3GProof.ps1"


class ReusableStage3GFullWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.preflight = PREFLIGHT.read_text(encoding="utf-8")
        cls.base_proof = BASE_PROOF.read_text(encoding="utf-8")
        cls.stage3g_proof = STAGE3G_PROOF.read_text(encoding="utf-8")

    def test_lane_is_reusable_and_self_hosted(self):
        self.assertIn("workflow_call:", self.workflow)
        self.assertIn("target_sha:", self.workflow)
        self.assertIn("runs-on: [self-hosted, yacs-ue58]", self.workflow)
        self.assertNotIn("contents: write", self.workflow)

    def test_lane_refuses_untrusted_fork_prs(self):
        self.assertIn("PR_HEAD_REPO", self.workflow)
        self.assertIn("refuses untrusted fork PRs", self.workflow)
        self.assertIn("github.event.pull_request.head.sha", self.workflow)

    def test_lane_materializes_and_verifies_full_lfs(self):
        self.assertIn("lfs: true", self.workflow)
        self.assertIn("git lfs install --local", self.workflow)
        self.assertIn("git lfs checkout", self.workflow)
        self.assertIn("git lfs fsck", self.workflow)
        self.assertIn("Stage 3G Git LFS checkout left pointer files", self.workflow)

    def test_lane_authors_then_runs_final_non_mutating_proof(self):
        self.assertIn("Invoke-YacsStage3GAuthoring.ps1", self.workflow)
        self.assertIn("Invoke-YacsStage3GProof.ps1", self.workflow)
        self.assertIn("-SkipBuild", self.workflow)

    def test_ephemeral_stage3g_dirty_allowlist_is_narrow_and_propagated(self):
        self.assertIn("AdditionalAllowedDirtyPaths", self.preflight)
        self.assertIn("AdditionalAllowedDirtyPaths", self.base_proof)
        self.assertGreaterEqual(
            self.stage3g_proof.count("AdditionalAllowedDirtyPaths"),
            2,
        )
        self.assertIn(
            "Content/Prototype/Environment/Stage3G/",
            self.stage3g_proof,
        )
        self.assertIn(
            "Content/Prototype/Maps/L_CyclingTest.umap",
            self.stage3g_proof,
        )
        self.assertNotIn(
            "AdditionalAllowedDirtyPaths = @('Content/')",
            self.stage3g_proof,
        )

    def test_stage3g_map_check_is_completion_aware_and_fail_closed(self):
        self.assertIn("function Invoke-Stage3GMapCheck", self.stage3g_proof)
        self.assertIn("Map Check did not emit a completion summary", self.stage3g_proof)
        self.assertIn("YACS MAP CHECK summary observed", self.stage3g_proof)
        self.assertIn("ForcedExitAfterSummary", self.stage3g_proof)
        self.assertIn("map_check_process.json", self.stage3g_proof)
        self.assertIn("-ExitGraceSec 10", self.stage3g_proof)
        self.assertNotIn(
            "Invoke-Stage3GEditor -LogPath $MapStdout -TimeoutSec 120",
            self.stage3g_proof,
        )

    def test_lane_uploads_only_proof_and_always_cleans(self):
        for extension in ("**/*.json", "**/*.txt", "**/*.log", "**/*.png"):
            self.assertIn(extension, self.workflow)
        self.assertNotIn("Content/**/*.uasset", self.workflow)
        self.assertNotIn("Content/**/*.umap", self.workflow)
        self.assertIn("if: ${{ always() }}", self.workflow)
        self.assertIn("git reset --hard", self.workflow)
        self.assertIn("git clean -ffdx", self.workflow)


if __name__ == "__main__":
    unittest.main()

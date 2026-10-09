from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from scripts.ci.test_sa_calobra_detail_native_workflow import parse_powershell_scripts

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

    def test_long_paths_are_enabled_in_isolated_config_before_checkout(self):
        isolate = self.workflow.split(
            "- name: Isolate self-hosted Git configuration", 1
        )[1].split("- name:", 1)[0]
        config = isolate.index("$env:GIT_CONFIG_GLOBAL = $isolated")
        enable = isolate.index("git config --global core.longpaths true")
        guard = isolate.index(
            "if ($LASTEXITCODE -ne 0) { throw 'Cannot enable long paths in isolated Git configuration.' }"
        )
        self.assertLess(config, enable)
        self.assertLess(enable, guard)
        self.assertLess(
            self.workflow.index("git config --global core.longpaths true"),
            self.workflow.index("uses: actions/checkout@"),
        )

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

    def test_compatibility_mode_runs_named_test_without_legacy_world_authoring(self):
        for step in (
            "Author deterministic Stage 3G environment",
            "Run non-mutating Stage 3G final proof",
        ):
            body = self.workflow.split("- name: " + step, 1)[1].split("- name:", 1)[0]
            self.assertIn("if: ${{ !inputs.legacy_regression_only }}", body)
        regression = self.workflow.split(
            "- name: Verify frozen prototype compatibility without world authoring", 1
        )[1].split("- name:", 1)[0]
        self.assertIn("if: ${{ inputs.legacy_regression_only }}", regression)
        self.assertIn("./scripts/ci/Invoke-YacsUnrealCi.ps1", regression)
        self.assertIn("-TestFilter 'CyclingStage3World.PrototypeTerrain'", regression)
        self.assertNotIn("-SkipBuild", regression)
        self.assertNotIn("Invoke-YacsStage3GAuthoring", regression)
        self.assertNotIn("Invoke-YacsStage3GProof", regression)
        self.assertNotIn("L_CyclingTest", regression)
        self.assertIn("$dirty = @(git status --porcelain)", regression)
        self.assertIn("current_world_admission = $false", regression)

    def test_native_work_respects_idle_host_ownership(self):
        guard = self.workflow.index(
            "Respect shared Unreal host ownership before native regression"
        )
        self.assertIn(
            "$state = ./scripts/runner/Get-YacsUnrealHostState.ps1", self.workflow
        )
        self.assertIn("if ($state.status -ne 'IDLE')", self.workflow)
        for step in (
            "Author deterministic Stage 3G environment",
            "Verify frozen prototype compatibility without world authoring",
        ):
            self.assertLess(guard, self.workflow.index(step))

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell is unavailable")
    def test_every_embedded_powershell_source_parses(self):
        sources = re.findall(
            r"        run: \|\n((?:          [^\n]*\n|\n)+)", self.workflow
        )
        self.assertGreaterEqual(len(sources), 9)
        parse_powershell_scripts(
            [
                re.sub(r"\$\{\{.*?\}\}", "parser-fixture", textwrap.dedent(source))
                for source in sources
            ]
        )

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell is unavailable")
    def test_native_receipt_gate_rejects_missing_or_different_prototype_evidence(self):
        function = re.search(
            r"          function Assert-LegacyStage3GRegression \{.*?\n          \}\n",
            self.workflow,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(function)
        head = "a" * 40
        expected_test = "CyclingStage3World.PrototypeTerrain"
        ci = {
            "Head": head,
            "ExpectedHead": head,
            "TestFilter": expected_test,
            "SkipBuild": False,
            "Discovered": 1,
            "Passed": 1,
            "Failed": 0,
            "Errors": 0,
        }
        proof = {
            "Head": head,
            "Discovered": 1,
            "Passed": 1,
            "Failed": 0,
            "Skipped": 0,
            "Errors": 0,
            "UatExitCode": 0,
        }
        test = {
            "fullTestPath": expected_test,
            "state": "Success",
            "errors": 0,
            "warnings": 2,
        }
        changes = [
            ("valid", None, None, None, True),
            ("wrong_sha", ("Head", "b" * 40), None, None, False),
            ("stale_build", ("SkipBuild", True), None, None, False),
            ("wrong_filter", ("TestFilter", "CyclingPhysics"), None, None, False),
            ("empty", ("Discovered", 0), None, None, False),
            ("skipped", None, ("Skipped", 1), None, False),
            ("wrong_test", None, None, ("fullTestPath", "CyclingPhysics.Flat"), False),
            ("failed", None, None, ("state", "Fail"), False),
            ("loose_pass", None, None, ("state", "Pass"), False),
            ("errors", None, None, ("errors", 1), False),
            ("duplicate", None, None, None, False),
        ]
        with tempfile.TemporaryDirectory(prefix="yacs-legacy-receipt-") as directory:
            root = Path(directory)
            cases = []
            for name, ci_change, proof_change, test_change, expected in changes:
                case_root = root / name
                index_path = case_root / "Proof/AutomationReport/index.json"
                index_path.parent.mkdir(parents=True)
                local_ci, local_proof, local_test = map(
                    copy.deepcopy, (ci, proof, test)
                )
                for data, change in (
                    (local_ci, ci_change),
                    (local_proof, proof_change),
                    (local_test, test_change),
                ):
                    if change:
                        data[change[0]] = change[1]
                local_proof["IndexPath"] = str(index_path)
                (case_root / "unreal_ci_summary.json").write_text(json.dumps(local_ci))
                (case_root / "Proof/summary.json").write_text(json.dumps(local_proof))
                index_path.write_text(
                    json.dumps(
                        {"tests": [local_test] * (2 if name == "duplicate" else 1)}
                    )
                )
                cases.append({"root": str(case_root), "expected": expected})
            inputs = root / "cases.json"
            inputs.write_text(json.dumps(cases), encoding="utf-8")
            command = (
                textwrap.dedent(function.group(0))
                + """
$ErrorActionPreference = 'Stop'
$cases = @(Get-Content -LiteralPath $env:YACS_LEGACY_TEST_CASES -Raw | ConvertFrom-Json)
$results = @()
foreach ($case in $cases) {
  try {
    $receipt = Assert-LegacyStage3GRegression -ReportRoot $case.root -ExpectedHead ('a' * 40)
    $results += [ordered]@{ accepted = $true; warnings = $receipt.warnings; admission = $receipt.current_world_admission }
  }
  catch { $results += [ordered]@{ accepted = $false } }
}
ConvertTo-Json -InputObject $results -Compress | Write-Output
"""
            )
            result = subprocess.run(
                [
                    shutil.which("pwsh"),
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    command,
                ],
                env=dict(os.environ, YACS_LEGACY_TEST_CASES=str(inputs)),
                stdin=subprocess.DEVNULL,
                text=True,
                capture_output=True,
                timeout=30,
                check=True,
            )
            receipts = json.loads(result.stdout.lstrip("\ufeff"))
            self.assertEqual(
                [receipt["accepted"] for receipt in receipts],
                [case["expected"] for case in cases],
            )
            self.assertEqual(receipts[0]["warnings"], 2)
            self.assertIs(receipts[0]["admission"], False)

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

    def test_lane_uses_per_run_isolated_worktree(self):
        self.assertIn(
            "STAGE3G_WORKTREE_DIR: _stage3g-full-${{ github.run_id }}-${{ github.run_attempt }}",
            self.workflow,
        )
        self.assertIn(
            "STAGE3G_BOOTSTRAP_DIR: _bootstrap-cleanup-${{ github.run_id }}-${{ github.run_attempt }}",
            self.workflow,
        )
        self.assertIn("path: ${{ env.STAGE3G_WORKTREE_DIR }}", self.workflow)
        self.assertIn("path: ${{ env.STAGE3G_BOOTSTRAP_DIR }}", self.workflow)
        self.assertNotIn("path: _stage3g-full-worktree", self.workflow)
        self.assertIn("Release-YacsUnrealWorkspaceLocks.ps1", self.workflow)

    def test_lane_uploads_only_proof_and_always_cleans(self):
        self.assertGreaterEqual(
            self.workflow.count("working-directory: ${{ env.STAGE3G_WORKTREE_DIR }}"),
            3,
        )
        self.assertIn(
            "${{ env.STAGE3G_WORKTREE_DIR }}/Saved/RuntimeProof/CI/Stage3GFull/",
            self.workflow,
        )
        for extension in ("**/*.json", "**/*.txt", "**/*.log", "**/*.png"):
            self.assertIn(extension, self.workflow)
        self.assertNotIn("Content/**/*.uasset", self.workflow)
        self.assertNotIn("Content/**/*.umap", self.workflow)
        self.assertIn("if: ${{ always() }}", self.workflow)
        self.assertIn("git reset --hard", self.workflow)
        self.assertIn("git clean -ffdx", self.workflow)
        self.assertIn(
            "Remove-Item -LiteralPath $worktree -Recurse -Force", self.workflow
        )


if __name__ == "__main__":
    unittest.main()

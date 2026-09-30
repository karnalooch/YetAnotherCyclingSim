from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "scripts" / "ue" / "Invoke-YacsStage3GForestTargetDensity.ps1"
BASE_PERF = ROOT / "scripts" / "ue" / "Invoke-YacsStage3GEnvironmentPerformance.ps1"
AUTHOR_WORKFLOW = (
    ROOT / ".github" / "workflows" / "stage3g-forest-target-density-author.yml"
)
PERF_WORKFLOW = (
    ROOT / ".github" / "workflows" / "stage3g-forest-target-density-performance.yml"
)
FULL_WORKFLOW = ROOT / ".github" / "workflows" / "reusable-stage3g-full.yml"
UNREAL_WORKFLOW = ROOT / ".github" / "workflows" / "reusable-unreal.yml"
WORKSPACE_CLEANUP = ROOT / "scripts" / "ci" / "Release-YacsUnrealWorkspaceLocks.ps1"
BASE_PROOF = ROOT / "scripts" / "ue" / "Invoke-YacsProof.ps1"
R2_FOREST = ROOT / "scripts" / "ue" / "Invoke-YacsStage3GR2PCGForest.ps1"
TARGET_AUTHOR = ROOT / "scripts" / "ue" / "Invoke-YacsStage3GForestTargetAuthor.ps1"
STAGE3G_AUTHORING = ROOT / "scripts" / "ue" / "Invoke-YacsStage3GAuthoring.ps1"
STAGE3G_PROOF = ROOT / "scripts" / "ue" / "Invoke-YacsStage3GProof.ps1"


class Stage3GForestTargetDensityContractTests(unittest.TestCase):
    def test_forest_budget_is_stricter_than_base_60fps_gate(self):
        text = HARNESS.read_text(encoding="utf-8")
        self.assertIn("[double] $ForestP95BudgetMs = 14.0", text)
        self.assertIn("FrameP95Ms -gt $ForestP95BudgetMs", text)
        self.assertIn("GpuP95Ms -gt $ForestP95BudgetMs", text)
        self.assertIn("TargetFps = 60.0", text)
        self.assertIn("AllowedOverBudgetRatio = 0.05", text)

    def test_benchmark_keeps_normal_project_shadows(self):
        harness = HARNESS.read_text(encoding="utf-8").lower()
        base = BASE_PERF.read_text(encoding="utf-8").lower()
        for forbidden in (
            "r.shadowquality=0",
            "showflag.shadows=0",
            "-noshadows",
            "r.dynamicglobalilluminationmethod=0",
        ):
            self.assertNotIn(forbidden, harness)
            self.assertNotIn(forbidden, base)
        self.assertIn(
            "normal project rendering; no shadow-disable override",
            harness,
        )

    def test_authoring_persists_only_pcg_forest(self):
        text = AUTHOR_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("runs-on: [self-hosted, yacs-ue58]", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("Release stale Unreal workspace locks", text)
        self.assertIn(
            "_bootstrap-cleanup/scripts/ci/Release-YacsUnrealWorkspaceLocks.ps1",
            text,
        )
        self.assertIn("-Workspace $env:GITHUB_WORKSPACE", text)
        self.assertIn(
            "Checkout exact trusted revision in isolated author worktree",
            text,
        )
        self.assertIn("path: _author-worktree", text)
        self.assertIn("working-directory: _author-worktree", text)
        self.assertIn("lfs: false", text)
        self.assertIn("persist-credentials: true", text)
        self.assertIn("git lfs fetch origin '${{ github.sha }}'", text)
        self.assertIn("Local LFS cache is incomplete", text)
        self.assertIn("Content/YACS/WorldGen/PCG/PCG_Forest.uasset", text)
        self.assertIn("Content/Prototype/Maps/L_CyclingTest.umap", text)
        self.assertIn(
            "_author-worktree/Saved/RuntimeProof/CI/ForestTargetDensity/Author/**",
            text,
        )
        self.assertIn("Clean isolated author worktree", text)
        self.assertIn("Invoke-YacsStage3GForestTargetAuthor.ps1", text)
        self.assertIn("Unexpected staged paths", text)
        self.assertIn("git lfs fsck", text)

    def test_workspace_cleanup_is_shared_tree_aware_and_fail_closed(self):
        for workflow in (
            AUTHOR_WORKFLOW,
            PERF_WORKFLOW,
            FULL_WORKFLOW,
            UNREAL_WORKFLOW,
        ):
            text = workflow.read_text(encoding="utf-8")
            self.assertIn(
                "_bootstrap-cleanup/scripts/ci/Release-YacsUnrealWorkspaceLocks.ps1",
                text,
            )
            self.assertIn(
                "Bootstrap cleanup helper outside persistent worktree",
                text,
            )
            self.assertIn("path: _bootstrap-cleanup", text)
            self.assertIn("lfs: false", text)
            self.assertIn("-Workspace $env:GITHUB_WORKSPACE", text)
            self.assertIn(
                "git clean -ffdx -e Saved/Logs/YetAnotherCyclingSim.log",
                text,
            )
            self.assertIn("Test-Path -LiteralPath '.git'", text)

        author_text = AUTHOR_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("path: _author-worktree", author_text)
        self.assertIn("clean: true", author_text)

        perf_text = PERF_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("path: _perf-worktree", perf_text)
        self.assertIn("clean: false", perf_text)

        full_text = FULL_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("path: _stage3g-full-worktree", full_text)
        self.assertIn("working-directory: _stage3g-full-worktree", full_text)
        self.assertIn("clean: true", full_text)

        unreal_text = UNREAL_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("path: _unreal-worktree", unreal_text)
        self.assertIn("working-directory: _unreal-worktree", unreal_text)
        self.assertIn("clean: true", unreal_text)

        helper = WORKSPACE_CLEANUP.read_text(encoding="utf-8")
        self.assertIn("Get-CimInstance Win32_Process", helper)
        self.assertIn("$env:GITHUB_WORKSPACE", helper)
        self.assertIn("taskkill.exe /PID $TargetProcessId /T /F", helper)
        self.assertIn("Get-WorkspaceUnrealProcesses |", helper)
        self.assertIn("Get-Process -Id $ProcessId -ErrorAction Stop", helper)
        self.assertIn("Test-NativeProcessAlive", helper)
        self.assertIn("$_.ProcessId -eq $TargetProcessId", helper)
        self.assertIn("deferring failure to bounded workspace verification", helper)
        self.assertNotIn(
            'Get-CimInstance Win32_Process -Filter "ProcessId = $TargetProcessId"',
            helper,
        )
        self.assertIn("CrashReportClient.exe", helper)
        self.assertIn("ShaderCompileWorker.exe", helper)
        self.assertIn("Workspace-scoped Unreal process tree remained alive", helper)
        self.assertIn("YacsFileLockProbe.RestartManager", helper)
        self.assertIn("rstrtmgr.dll", helper)
        self.assertIn("RmRegisterResources", helper)
        self.assertIn("Restart Manager locker:", helper)
        self.assertIn("Stopping known Unreal locker", helper)
        self.assertIn("Lock diagnostic candidate:", helper)
        self.assertIn("parentName={3}", helper)
        self.assertIn("nativeAlive={4}", helper)
        self.assertIn("Preserving stale locked workspace log", helper)
        self.assertIn("OnlyExitedWorkspaceUnrealLockers", helper)
        self.assertIn("Workspace log lock did not clear within", helper)

    def test_unreal_processes_use_per_run_absolute_logs(self):
        base_proof = BASE_PROOF.read_text(encoding="utf-8")
        r2_forest = R2_FOREST.read_text(encoding="utf-8")
        authoring = STAGE3G_AUTHORING.read_text(encoding="utf-8")
        stage3g_proof = STAGE3G_PROOF.read_text(encoding="utf-8")

        self.assertIn("automation_editor.log", base_proof)
        self.assertIn("('-AbsLog=' + $EditorLog)", base_proof)
        self.assertIn("$AuthorLog + '.editor.log'", r2_forest)
        self.assertIn("('-AbsLog=' + $EditorLog)", r2_forest)
        self.assertIn(
            "$EffectiveArguments += ('-AbsLog=' + ($LogPath + '.editor.log'))",
            authoring,
        )
        self.assertIn(
            "$EffectiveArguments += ('-AbsLog=' + ($LogPath + '.editor.log'))",
            stage3g_proof,
        )

    def test_v2_authoring_contract_rejects_stale_v1_bounds(self):
        r2 = R2_FOREST.read_text(encoding="utf-8")
        author = TARGET_AUTHOR.read_text(encoding="utf-8")

        for expected in (
            "forest_density - 0.84",
            "target_density_v2",
            "layer_profile_version -ne 2",
            "$ExpectedMean -lt 1850.0 -or $ExpectedMean -gt 2150.0",
            "station_spacing_m - 20.0",
            "min_lateral_offset_m - 10.0",
            "max_lateral_offset_m - 36.0",
            "min_uniform_scale - 0.95",
            "max_uniform_scale - 1.35",
        ):
            self.assertIn(expected, r2)

        for stale in (
            "forest_density - 0.78",
            "target_density_v1",
            "layer_profile_version -ne 1",
            "$ExpectedMean -lt 1000.0 -or $ExpectedMean -gt 1150.0",
            "station_spacing_m - 28.0",
            "min_lateral_offset_m - 8.0",
            "max_lateral_offset_m - 34.0",
            "min_uniform_scale - 0.84",
            "max_uniform_scale - 1.16",
        ):
            self.assertNotIn(stale, r2)

        self.assertIn("$ForestTotal -lt 1700 -or $ForestTotal -gt 2300", author)
        self.assertIn("outside [1700, 2300]", author)
        self.assertNotIn("$ForestTotal -lt 800 -or $ForestTotal -gt 1300", author)
        self.assertNotIn("outside [800, 1300]", author)

    def test_persisted_asset_triggers_reference_pc_stress_gate(self):
        text = PERF_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Content/YACS/WorldGen/PCG/PCG_Forest.uasset", text)
        self.assertIn("runs-on: [self-hosted, yacs-ue58]", text)
        self.assertIn("Invoke-YacsStage3GForestTargetDensity.ps1", text)
        self.assertIn("-ForestP95BudgetMs 14.0", text)
        self.assertIn("lfs: true", text)


if __name__ == "__main__":
    unittest.main()

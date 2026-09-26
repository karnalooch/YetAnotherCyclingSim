from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".circleci" / "config.yml"
CODE_ONLY = ROOT / "scripts" / "ci" / "Test-YacsCodeOnlyCheckout.ps1"
PREFLIGHT = ROOT / "scripts" / "ue" / "Preflight-YacsProof.ps1"
PROOF = ROOT / "scripts" / "ue" / "Invoke-YacsProof.ps1"


class CircleCiWindowsPhaseBContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = CONFIG.read_text(encoding="utf-8")
        cls.code_only = CODE_ONLY.read_text(encoding="utf-8")
        cls.preflight = PREFLIGHT.read_text(encoding="utf-8")
        cls.proof = PROOF.read_text(encoding="utf-8")

    def test_expensive_circleci_paths_are_opt_in(self):
        for parameter in ("windows_probe:", "ue_local_canary:"):
            self.assertIn(parameter, self.config)
        self.assertGreaterEqual(self.config.count("default: false"), 2)

    def test_circleci_ue_transport_is_storage_free(self):
        for forbidden in (
            "ue_cache_seed:",
            "ue_canary:",
            "ue_cache_key:",
            "persist_to_workspace:",
            "attach_workspace:",
            "save_cache:",
            "restore_cache:",
            "ue58-win64.zip",
            "C:\\YacsUe58Seed",
        ):
            self.assertNotIn(forbidden, self.config)

    def test_legacy_seed_scripts_are_not_called_by_circleci(self):
        for forbidden in (
            "Prepare-YacsUe58Seed.ps1",
            "Restore-YacsUe58Seed.ps1",
            "Test-YacsUe58SeedPayload.ps1",
        ):
            self.assertNotIn(forbidden, self.config)

    def test_local_canary_uses_self_hosted_runner(self):
        for token in (
            "ue-local-canary:",
            "machine: true",
            "ue_runner_resource_class:",
            "resource_class: << pipeline.parameters.ue_runner_resource_class >>",
            "ue_runner_working_directory:",
            "working_directory: << pipeline.parameters.ue_runner_working_directory >>",
            "karnalooch/yacs-ue58-seed",
        ):
            self.assertIn(token, self.config)

    def test_local_canary_stays_on_main_and_is_manual_parameter_only(self):
        self.assertIn("windows-ue-local-canary:", self.config)
        self.assertIn("when: << pipeline.parameters.ue_local_canary >>", self.config)
        self.assertIn('filters: pipeline.git.branch == "main"', self.config)
        self.assertNotIn("schedule:", self.config)

    def test_local_canary_keeps_project_lfs_unmaterialized(self):
        local_start = self.config.index("  ue-local-canary:")
        workflows_start = self.config.index("workflows:")
        local_block = self.config[local_start:workflows_start]
        self.assertIn('GIT_LFS_SKIP_SMUDGE: "1"', local_block)
        self.assertIn("method: blobless", local_block)
        self.assertIn("Test-YacsCodeOnlyCheckout.ps1", local_block)

    def test_local_canary_runs_real_unreal_ci_entry_point(self):
        local_start = self.config.index("  ue-local-canary:")
        workflows_start = self.config.index("workflows:")
        local_block = self.config[local_start:workflows_start]
        self.assertIn("Invoke-YacsUnrealCi.ps1", local_block)
        self.assertIn("-ExpectedHead $env:CIRCLE_SHA1", local_block)
        self.assertIn("no_output_timeout: 45m", local_block)

    def test_local_canary_keeps_scratch_on_d_drive(self):
        for token in (
            "TEMP: 'D:\\CircleCI\\YACS-Runner\\Temp'",
            "TMP: 'D:\\CircleCI\\YACS-Runner\\Temp'",
            "Self-hosted UE TEMP must stay on D:",
            "Self-hosted UE TMP must stay on D:",
        ):
            self.assertIn(token, self.config)

    def test_local_canary_publishes_only_runtime_proof(self):
        local_start = self.config.index("  ue-local-canary:")
        workflows_start = self.config.index("workflows:")
        local_block = self.config[local_start:workflows_start]
        self.assertIn("store_artifacts:", local_block)
        self.assertIn("Saved/RuntimeProof/CI/Unreal", local_block)
        for forbidden in (
            "UE58Seed",
            "ue58-win64",
            "Engine/Binaries",
            "Engine/Content",
        ):
            self.assertNotIn(forbidden, local_block)

    def test_local_canary_always_prints_final_diagnostics(self):
        local_start = self.config.index("  ue-local-canary:")
        workflows_start = self.config.index("workflows:")
        local_block = self.config[local_start:workflows_start]
        for token in (
            "name: Print local UE final diagnostics",
            "when: always",
            "Proof/phase_status.json",
            "Proof/build_editor.log",
            "Proof/automation_run.log",
            "Proof/summary.txt",
            "unreal_ci_summary.json",
            "-Tail 40",
        ):
            self.assertIn(token, local_block)

    def test_code_only_guard_accepts_lazy_lfs_but_rejects_payloads(self):
        for token in (
            "git lfs ls-files --name-only",
            "git cat-file blob",
            "git lfs pointer --check --stdin",
            "CODE-ONLY LFS LAZY",
            "Code-only checkout materialized Git LFS payload",
            "CODE-ONLY CHECKOUT PASS",
            "materialized=0",
        ):
            self.assertIn(token, self.code_only)

    def test_unreal_proof_keeps_phase_telemetry(self):
        for token in (
            "phase_status.json",
            "Write-YacsPhaseStatus",
            "YACS PHASE:",
            "Wait-YacsProcessWithHeartbeat",
            "YACS HEARTBEAT",
            "YACS LOGTAIL",
        ):
            self.assertIn(token, self.proof)

    def test_preflight_discovers_local_reference_ue(self):
        self.assertIn("'D:\\Epic Games'", self.preflight)
        self.assertIn("'D:\\UE_5.8'", self.preflight)
        self.assertIn("Get-ChildItem -LiteralPath $d -Directory", self.preflight)

    def test_probe_remains_small_and_hosted(self):
        probe_start = self.config.index("  windows-probe:")
        local_start = self.config.index("  ue-local-canary:")
        probe_block = self.config[probe_start:local_start]
        self.assertIn("resource_class: windows.medium", probe_block)
        self.assertIn("store_artifacts:", probe_block)
        for forbidden in (
            "persist_to_workspace:",
            "save_cache:",
            "restore_cache:",
            "UE58Seed",
        ):
            self.assertNotIn(forbidden, probe_block)


if __name__ == "__main__":
    unittest.main()

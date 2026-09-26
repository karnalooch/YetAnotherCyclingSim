from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".circleci" / "config.yml"
PACKER = ROOT / "scripts" / "ci" / "Prepare-YacsUe58Seed.ps1"
RESTORE = ROOT / "scripts" / "ci" / "Restore-YacsUe58Seed.ps1"
VALIDATOR = ROOT / "scripts" / "ci" / "Test-YacsUe58SeedPayload.ps1"
CODE_ONLY = ROOT / "scripts" / "ci" / "Test-YacsCodeOnlyCheckout.ps1"
PREFLIGHT = ROOT / "scripts" / "ue" / "Preflight-YacsProof.ps1"


class CircleCiWindowsPhaseBContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = CONFIG.read_text(encoding="utf-8")
        cls.packer = PACKER.read_text(encoding="utf-8")
        cls.restore = RESTORE.read_text(encoding="utf-8")
        cls.validator = VALIDATOR.read_text(encoding="utf-8")
        cls.code_only = CODE_ONLY.read_text(encoding="utf-8")
        cls.preflight = PREFLIGHT.read_text(encoding="utf-8")
        cls.proof = (ROOT / "scripts" / "ue" / "Invoke-YacsProof.ps1").read_text(
            encoding="utf-8"
        )

    def test_expensive_phase_b_paths_are_disabled_by_default(self):
        for parameter in ("ue_cache_seed:", "ue_canary:"):
            self.assertIn(parameter, self.config)
        self.assertGreaterEqual(self.config.count("default: false"), 3)

    def test_seed_uses_self_hosted_resource_class(self):
        self.assertIn("ue_seed_resource_class:", self.config)
        self.assertIn('default: "karnalooch/yacs-ue58-seed"', self.config)
        self.assertIn("machine: true", self.config)
        self.assertIn(
            "resource_class: << pipeline.parameters.ue_seed_resource_class >>",
            self.config,
        )

    def test_seed_and_canary_share_explicit_cache_key(self):
        self.assertIn("ue_cache_key:", self.config)
        self.assertIn('default: "yacs-ue58-win64-v4"', self.config)
        self.assertIn("save_cache:", self.config)
        self.assertIn("restore_cache:", self.config)
        self.assertGreaterEqual(
            self.config.count("<< pipeline.parameters.ue_cache_key >>"),
            2,
        )

    def test_hosted_canary_runs_real_unreal_ci_entry_point(self):
        self.assertIn("windows-ue-hosted-canary:", self.config)
        self.assertIn("resource_class: windows.medium", self.config)
        self.assertIn("Invoke-YacsUnrealCi.ps1", self.config)
        self.assertIn("-ExpectedHead $env:CIRCLE_SHA1", self.config)

    def test_hosted_canary_allows_silent_unreal_build_and_automation(self):
        canary_start = self.config.index("  ue-hosted-canary:")
        workflows_start = self.config.index("workflows:")
        canary_block = self.config[canary_start:workflows_start]
        self.assertIn("name: Build YACS Editor and run scoped Automation", canary_block)
        self.assertIn("no_output_timeout: 45m", canary_block)

    def test_circleci_checkouts_are_blobless_and_skip_lfs_smudge(self):
        self.assertGreaterEqual(self.config.count("method: blobless"), 5)
        self.assertGreaterEqual(
            self.config.count('GIT_LFS_SKIP_SMUDGE: "1"'),
            5,
        )

    def test_hosted_canary_enforces_code_only_lfs_pointers(self):
        canary_start = self.config.index("  ue-hosted-canary:")
        workflows_start = self.config.index("workflows:")
        canary_block = self.config[canary_start:workflows_start]
        self.assertIn("name: Enforce code-only checkout", canary_block)
        self.assertIn("Test-YacsCodeOnlyCheckout.ps1", canary_block)
        for token in (
            "git lfs ls-files --name-only",
            "git lfs pointer --check",
            "Code-only checkout materialized Git LFS payload",
            "CODE-ONLY CHECKOUT PASS",
        ):
            self.assertIn(token, self.code_only)

    def test_unreal_proof_emits_phase_telemetry(self):
        for token in (
            "phase_status.json",
            "Write-YacsPhaseStatus",
            "YACS PHASE:",
            "-Phase 'preflight' -Status 'running'",
            "-Phase 'build' -Status 'running'",
            "-Phase 'automation' -Status 'running'",
            "-Phase 'tally' -Status 'running'",
        ):
            self.assertIn(token, self.proof)

    def test_long_unreal_processes_emit_heartbeats_and_log_tails(self):
        for token in (
            "Wait-YacsProcessWithHeartbeat",
            "HeartbeatSeconds = 30",
            "YACS HEARTBEAT",
            "YACS LOGTAIL",
            "Get-Content -LiteralPath $LogPath -Tail 5",
            "Get-Content -LiteralPath $LogPath -Tail 10",
        ):
            self.assertIn(token, self.proof)
        self.assertIn(
            "Wait-YacsProcessWithHeartbeat -Process $BuildProc",
            self.proof,
        )
        self.assertIn(
            "Wait-YacsProcessWithHeartbeat -Process $UATProc",
            self.proof,
        )

    def test_expensive_circleci_jobs_are_main_only(self):
        self.assertGreaterEqual(
            self.config.count('filters: pipeline.git.branch == "main"'),
            4,
        )

    def test_seed_keeps_engine_plugins_and_source_by_default(self):
        for forbidden_exclusion in (
            "Engine\\Plugins",
            "Engine\\Source",
            "Engine\\Content",
            "Engine\\Shaders",
            "Engine\\Binaries\\Win64",
        ):
            self.assertNotIn(f"'{forbidden_exclusion}'", self.packer)

    def test_restore_fails_closed_on_hash_disk_and_version(self):
        for token in (
            "SHA256 mismatch",
            "Not enough free disk",
            "^5\\.8\\.",
            "ArchiveIntegrityValidated",
            "Unsafe archive entry path",
            "Archive entry escapes destination root",
        ):
            self.assertIn(token, self.restore)

    def test_seed_has_long_no_output_timeout_and_progress(self):
        self.assertIn("no_output_timeout: 45m", self.config)
        for token in (
            "Scanning UE 5.8 tree",
            "Packing UE seed:",
            "Validating UE seed:",
        ):
            self.assertIn(token, self.packer)

    def test_seed_uses_partial_zip_and_full_integrity_validation(self):
        for token in (
            "ue58-win64.zip",
            "ue58-win64.partial.",
            "ZipArchiveMode]::Create",
            "ZipArchiveMode]::Read",
            "ArchiveIntegrityValidated",
            "ARCHIVE PASS",
        ):
            self.assertIn(token, self.packer)
        self.assertNotIn("tar.exe", self.packer)
        self.assertNotIn("tar.exe", self.restore)

    def test_seed_hash_is_powershell_version_independent_and_resumable(self):
        self.assertIn("[System.Security.Cryptography.SHA256]::Create()", self.packer)
        self.assertIn(
            "Reusing validated UE seed archive without repacking", self.packer
        )
        self.assertIn("postValidationHashFailure", self.packer)
        self.assertNotIn("$hash = Get-FileHash", self.packer)

    def test_seed_persists_archive_outside_ephemeral_workdir(self):
        for token in (
            "Persistent\\UE58Seed",
            "-OutputRoot $persistentSeedRoot",
            "New-Item -ItemType HardLink",
            "Staged persistent UE seed into CircleCI cache path via hardlink",
        ):
            self.assertIn(token, self.config)

    def test_seed_cache_path_is_drive_aligned_and_fails_closed(self):
        for token in (
            "ue_seed_working_directory:",
            "D:\\CircleCI\\YACS-Runner\\Workdir",
            "working_directory: << pipeline.parameters.ue_seed_working_directory >>",
            "CIRCLE_WORKING_DIRECTORY",
            "CircleCI working-directory mismatch",
            "Staged UE cache size mismatch",
            "implausibly small",
        ):
            self.assertIn(token, self.config)

    def test_self_hosted_seed_uses_workspace_not_cache_publish(self):
        seed_start = self.config.index("  ue-cache-seed:")
        publish_start = self.config.index("  ue-cache-publish:")
        seed_block = self.config[seed_start:publish_start]
        self.assertIn("persist_to_workspace:", seed_block)
        self.assertIn(
            "root: 'D:\\CircleCI\\YACS-Runner\\Workdir\\Saved\\RuntimeProof\\CI\\UE58Seed'",
            seed_block,
        )
        self.assertNotIn("save_cache:", seed_block)

    def test_self_hosted_seed_keeps_temp_and_tmp_on_d(self):
        seed_start = self.config.index("  ue-cache-seed:")
        publish_start = self.config.index("  ue-cache-publish:")
        seed_block = self.config[seed_start:publish_start]
        for token in (
            "TEMP: 'D:\\CircleCI\\YACS-Runner\\Temp'",
            "TMP: 'D:\\CircleCI\\YACS-Runner\\Temp'",
            "Self-hosted UE seed TEMP must stay on D:",
            "Self-hosted UE seed TMP must stay on D:",
        ):
            self.assertIn(token, seed_block)

    def test_self_hosted_seed_uses_git_for_windows_workspace_tools(self):
        seed_start = self.config.index("  ue-cache-seed:")
        publish_start = self.config.index("  ue-cache-publish:")
        seed_block = self.config[seed_start:publish_start]
        for token in (
            "C:\\Program Files\\Git\\usr\\bin",
            "Verify CircleCI workspace gzip prerequisite from Git for Windows",
            "Git for Windows gzip prerequisite is missing",
            "Git for Windows tar prerequisite is missing",
            "Get-Command gzip.exe",
            "Get-Command tar.exe",
        ):
            self.assertIn(token, seed_block)
        self.assertNotIn("sourceforge.net/projects/gnuwin32", seed_block)
        self.assertNotIn("gzip-1.3.12-1-bin.zip", seed_block)

    def test_self_hosted_seed_validates_foreground_runner_environment(self):
        seed_start = self.config.index("  ue-cache-seed:")
        publish_start = self.config.index("  ue-cache-publish:")
        seed_block = self.config[seed_start:publish_start]
        for token in (
            "Verify foreground machine-runner host contract",
            "D:\\CircleCI\\YACS-Runner\\Workdir",
            "Get-Command gzip.exe",
            "Get-Command tar.exe",
            "Foreground machine-runner host contract: PASS",
        ):
            self.assertIn(token, seed_block)
        self.assertNotIn(
            "PATH: 'C:\\Program Files\\Git\\usr\\bin",
            seed_block,
        )

    def test_hosted_job_publishes_workspace_to_cache(self):
        for token in (
            "ue-cache-publish:",
            "attach_workspace:",
            "Test-YacsUe58SeedPayload.ps1",
            "WORKSPACE SEED PASS",
            "save_cache:",
            "C:\\YacsUe58Seed\\ue58-win64.zip",
            "no_output_timeout: 45m",
        ):
            self.assertIn(token, self.config)

    def test_seed_workflow_verifies_restored_cache_on_hosted_windows(self):
        for token in (
            "ue-cache-verify:",
            "Test-YacsUe58SeedPayload.ps1",
            "CACHE RESTORE PASS",
            "requires:",
            "- ue-cache-publish",
        ):
            self.assertIn(token, self.config)

    def test_large_seed_hashing_emits_progress(self):
        for token in (
            "Hashing UE seed:",
            "Hashing UE seed complete:",
            "TransformBlock",
            "UE seed SHA256 mismatch",
        ):
            self.assertIn(token, self.validator)
        for token in (
            "Hashing cached UE seed:",
            "Hashing cached UE seed complete:",
            "Restoring UE seed:",
            "Restoring UE seed complete:",
        ):
            self.assertIn(token, self.restore)

    def test_hosted_canary_restores_from_hosted_cache_path(self):
        self.assertIn(
            "-SeedRoot 'C:\\YacsUe58Seed'",
            self.config,
        )

    def test_hosted_preflight_accepts_direct_restored_engine_root(self):
        self.assertIn("'C:\\UE_5.8'", self.preflight)
        direct_check = "Test-Path -LiteralPath $directUat -PathType Leaf"
        child_scan = "Get-ChildItem -LiteralPath $d -Directory"
        self.assertIn(direct_check, self.preflight)
        self.assertIn(
            "$EngineRoot = (Resolve-Path -LiteralPath $d).Path", self.preflight
        )
        self.assertLess(
            self.preflight.index(direct_check), self.preflight.index(child_scan)
        )

    def test_restore_handles_drive_root_destination_parent(self):
        self.assertIn(
            "if (-not (Test-Path -LiteralPath $destinationParent -PathType Container))",
            self.restore,
        )
        self.assertIn(
            "[System.IO.Directory]::CreateDirectory($destinationParent)",
            self.restore,
        )
        self.assertNotIn(
            "New-Item -ItemType Directory -Path $destinationParent -Force",
            self.restore,
        )

    def test_restore_hash_is_powershell_version_independent(self):
        self.assertIn("[System.Security.Cryptography.SHA256]::Create()", self.restore)
        self.assertNotIn("Get-FileHash", self.restore)


if __name__ == "__main__":
    unittest.main()

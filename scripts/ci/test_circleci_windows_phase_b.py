from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".circleci" / "config.yml"
PACKER = ROOT / "scripts" / "ci" / "Prepare-YacsUe58Seed.ps1"
RESTORE = ROOT / "scripts" / "ci" / "Restore-YacsUe58Seed.ps1"


class CircleCiWindowsPhaseBContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = CONFIG.read_text(encoding="utf-8")
        cls.packer = PACKER.read_text(encoding="utf-8")
        cls.restore = RESTORE.read_text(encoding="utf-8")

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

    def test_self_hosted_seed_bootstraps_workspace_gzip_on_d(self):
        seed_start = self.config.index("  ue-cache-seed:")
        publish_start = self.config.index("  ue-cache-publish:")
        seed_block = self.config[seed_start:publish_start]
        for token in (
            "D:\\CircleCI\\YACS-Runner\\Tools\\gzip-1.3.12-1\\bin",
            "Ensure CircleCI workspace gzip prerequisite on D",
            "gzip-1.3.12-1-bin.zip",
            "598BFC7DE80C616DBBF8E53ACBF8358C91C6D3A3E0DDEC094C0E05C465D0661B",
            "Get-Command gzip.exe",
            "Get-Command tar.exe",
        ):
            self.assertIn(token, seed_block)

    def test_hosted_job_publishes_workspace_to_cache(self):
        for token in (
            "ue-cache-publish:",
            "attach_workspace:",
            "WORKSPACE SEED PASS",
            "Workspace UE seed SHA256 mismatch",
            "save_cache:",
            "C:\\YacsUe58Seed\\ue58-win64.zip",
        ):
            self.assertIn(token, self.config)

    def test_seed_workflow_verifies_restored_cache_on_hosted_windows(self):
        for token in (
            "ue-cache-verify:",
            "CACHE RESTORE PASS",
            "Restored UE cache SHA256 mismatch",
            "requires:",
            "- ue-cache-publish",
        ):
            self.assertIn(token, self.config)

    def test_hosted_canary_restores_from_hosted_cache_path(self):
        self.assertIn(
            "-SeedRoot 'C:\\YacsUe58Seed'",
            self.config,
        )

    def test_restore_hash_is_powershell_version_independent(self):
        self.assertIn("[System.Security.Cryptography.SHA256]::Create()", self.restore)
        self.assertNotIn("Get-FileHash", self.restore)


if __name__ == "__main__":
    unittest.main()

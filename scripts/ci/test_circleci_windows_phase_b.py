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
        self.assertIn('default: "yacs-ue58-win64-v1"', self.config)
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


if __name__ == "__main__":
    unittest.main()

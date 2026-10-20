"""Static policy checks for the reviewed YACS storage auto-clean scripts."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
AUTO = ROOT / "scripts/runner/Invoke-YacsStorageAutoclean.ps1"
INSTALL = ROOT / "scripts/runner/Install-YacsStorageAutoclean.ps1"
DOC = ROOT / "docs/tooling/YACS_STORAGE_AUTOCLEAN.md"


class StorageAutoCleanContract(unittest.TestCase):
    def test_clean_requires_apply_and_has_strict_budget(self):
        s = AUTO.read_text(encoding="utf-8")
        for token in (
            "[switch]$Apply",
            "[switch]$WriteReceipt",
            "if ($Apply -and $selected -gt 0",
            "MinimumAgeDays = 14",
            "TargetFreeGiB = 50",
            "MaxReclaimGiB = 12",
            "Clear-YacsRunnerWorkspace.ps1",
            "Assert-NoReparse",
            "Get-BusyWorkloads",
        ):
            self.assertIn(token, s)

    def test_deletion_only_targets_individual_ddc_files(self):
        s = AUTO.read_text(encoding="utf-8")
        self.assertIn("Remove-Item -LiteralPath $f.Path", s)
        for token in (
            "Remove-Item -LiteralPath $ddcRoot",
            "Remove-Item -LiteralPath $root",
            "Remove-Item -LiteralPath $runnerRoot",
            "Remove-Item -LiteralPath $maintenanceRoot",
        ):
            self.assertNotIn(token, s)
        self.assertIn("zenserver", s.lower())
        self.assertIn("$protectedExtensions", s)
        self.assertIn("'.umap'", s)
        self.assertIn("'.hiplc'", s)
        self.assertIn("work\\lesson*", s)

    def test_install_is_opt_in_no_immediate_execute(self):
        s = INSTALL.read_text(encoding="utf-8")
        for token in (
            "[switch]$Install",
            "[switch]$EnableDeletion",
            "if (-not $Install)",
            "New-ScheduledTaskTrigger -AtLogOn",
            "New-ScheduledTaskTrigger -Daily",
            "-RunLevel Limited",
            "Get-FileHash",
        ):
            self.assertIn(token, s)
        self.assertNotIn("Start-ScheduledTask", s)

    def test_documentation_marks_zen_and_accepted_caches_protected(self):
        s = DOC.read_text(encoding="utf-8")
        self.assertIn("**NEVER**", s)
        self.assertIn("latest-autoclean.json", s)
        self.assertIn("runner-space-recovery", s)


if __name__ == "__main__":
    unittest.main()

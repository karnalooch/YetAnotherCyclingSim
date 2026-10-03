from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HOST_AUDIT = ROOT / "scripts" / "runner" / "Test-YacsWindowsHost.ps1"
RESTORE = ROOT / "scripts" / "assets" / "Restore-YacsSaCalobraWorldData.ps1"
CLEANUP = ROOT / "scripts" / "runner" / "Clear-YacsRunnerWorkspace.ps1"
RECEIPT = (
    ROOT
    / "worldgen"
    / "terrain"
    / "benchmarks"
    / "sa_calobra"
    / "world_data"
    / "manual_cnig_receipt_2026-10-03.json"
)


class WindowsHostRecoveryContractTests(unittest.TestCase):
    def test_scripts_parse_with_powershell(self) -> None:
        pwsh = shutil.which("pwsh")
        if pwsh is None:
            self.skipTest("pwsh is unavailable")
        for path in (HOST_AUDIT, RESTORE, CLEANUP):
            escaped = str(path).replace("'", "''")
            command = f"""
            $path = '{escaped}'
            $tokens = $null
            $errors = $null
            [System.Management.Automation.Language.Parser]::ParseFile(
              $path, [ref]$tokens, [ref]$errors
            ) | Out-Null
            if ($errors.Count -gt 0) {{
              $errors | ForEach-Object {{ Write-Error $_.Message }}
              exit 1
            }}
            """
            result = subprocess.run(
                [pwsh, "-NoProfile", "-Command", command],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_restore_contract_matches_admitted_receipt(self) -> None:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual(receipt["verification"]["file_count"], 17)
        self.assertEqual(receipt["verification"]["total_size_bytes"], 3_339_596_438)
        text = RESTORE.read_text(encoding="utf-8")
        self.assertIn("data-cnig-sa-calobra-working-v1-2026-10-03", text)
        self.assertIn("gh release download", text)
        self.assertIn("--skip-existing", text)
        self.assertIn("Get-FileHash", text)
        self.assertIn("unexpected remote raw file", text)
        self.assertNotIn("--clobber", text)

    def test_cleanup_contract_preserves_source_caches(self) -> None:
        text = CLEANUP.read_text(encoding="utf-8")
        for protected in (
            "_yacs-world-data",
            "_yacs-retained-lfs",
            "_yacs-sa-calobra-assets",
            "_terrain-recovery-worktree",
            "_unreal-ci-warm",
        ):
            self.assertIn(protected, text)
        self.assertIn("[switch] $Apply", text)
        self.assertIn("$ExpectedCandidateCount", text)
        self.assertIn("$ExpectedReclaimBytes", text)
        self.assertIn("Runner.Worker", text)
        self.assertIn("contains a reparse point", text)
        self.assertIn("changed during apply", text)
        self.assertIn("Remove-Item -LiteralPath", text)
        self.assertNotIn("git clean", text)

    def test_cleanup_preview_does_not_delete(self) -> None:
        pwsh = shutil.which("pwsh")
        if pwsh is None:
            self.skipTest("pwsh is unavailable")
        with tempfile.TemporaryDirectory() as temp:
            runner = Path(temp) / "actions-runner-yacs"
            workspace = (
                runner / "_work" / "YetAnotherCyclingSim" / "YetAnotherCyclingSim"
            )
            candidate = workspace / "_unreal-build-123-1"
            protected = workspace / "_yacs-retained-lfs"
            candidate.mkdir(parents=True)
            protected.mkdir()
            (candidate / "build.bin").write_bytes(b"x" * 1024)
            (protected / "keep.bin").write_bytes(b"y" * 1024)
            result = subprocess.run(
                [
                    pwsh,
                    "-NoProfile",
                    "-File",
                    str(CLEANUP),
                    "-RunnerRoot",
                    str(runner),
                    "-MinimumAgeHours",
                    "0",
                    "-Json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["apply"])
            self.assertEqual(payload["candidate_count"], 1)
            self.assertEqual(payload["estimated_reclaim_bytes"], 1024)
            self.assertTrue(candidate.exists())
            self.assertTrue(protected.exists())

    def test_cleanup_empty_preview_reports_zero(self) -> None:
        pwsh = shutil.which("pwsh")
        if pwsh is None:
            self.skipTest("pwsh is unavailable")
        with tempfile.TemporaryDirectory() as temp:
            runner = Path(temp) / "actions-runner-yacs"
            workspace = (
                runner / "_work" / "YetAnotherCyclingSim" / "YetAnotherCyclingSim"
            )
            workspace.mkdir(parents=True)
            result = subprocess.run(
                [
                    pwsh,
                    "-NoProfile",
                    "-File",
                    str(CLEANUP),
                    "-RunnerRoot",
                    str(runner),
                    "-MinimumAgeHours",
                    "0",
                    "-Json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["candidate_count"], 0)
            self.assertEqual(payload["estimated_reclaim_bytes"], 0)
            self.assertEqual(payload["deleted_bytes"], 0)

    @unittest.skipUnless(sys.platform == "win32", "cleanup apply is Windows-only")
    def test_cleanup_apply_deletes_only_reviewed_candidate(self) -> None:
        pwsh = shutil.which("pwsh")
        if pwsh is None:
            self.skipTest("pwsh is unavailable")
        with tempfile.TemporaryDirectory() as temp:
            runner = Path(temp) / "actions-runner-yacs"
            workspace = (
                runner / "_work" / "YetAnotherCyclingSim" / "YetAnotherCyclingSim"
            )
            candidate = workspace / "_unreal-build-123-1"
            protected = workspace / "_yacs-retained-lfs"
            candidate.mkdir(parents=True)
            protected.mkdir()
            (candidate / "build.bin").write_bytes(b"x" * 1024)
            (protected / "keep.bin").write_bytes(b"y" * 1024)
            result = subprocess.run(
                [
                    pwsh,
                    "-NoProfile",
                    "-File",
                    str(CLEANUP),
                    "-RunnerRoot",
                    str(runner),
                    "-MinimumAgeHours",
                    "0",
                    "-ExpectedCandidateCount",
                    "1",
                    "-ExpectedReclaimBytes",
                    "1024",
                    "-Apply",
                    "-Json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["apply"])
            self.assertEqual(payload["deleted_bytes"], 1024)
            self.assertFalse(candidate.exists())
            self.assertTrue(protected.exists())


if __name__ == "__main__":
    unittest.main()

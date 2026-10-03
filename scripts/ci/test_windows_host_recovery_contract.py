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
            (candidate / "Intermediate").mkdir()
            (candidate / "Intermediate" / "build.bin").write_bytes(b"x" * 1024)
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

    def test_cleanup_protects_active_build_and_blocks_invalid_pointer(self) -> None:
        pwsh = shutil.which("pwsh")
        if pwsh is None:
            self.skipTest("pwsh is unavailable")
        with tempfile.TemporaryDirectory() as temp:
            runner = Path(temp) / "actions-runner-yacs"
            workspace = runner / "_work/YetAnotherCyclingSim/YetAnotherCyclingSim"
            active = workspace / "_unreal-build-123-1"
            (active / ".git").mkdir(parents=True)
            (active / "Intermediate").mkdir()
            (active / "Intermediate/build.bin").write_bytes(b"verified")
            pointer = workspace / "_yacs-unreal-ci/active.json"
            pointer.parent.mkdir()
            command = [
                pwsh,
                "-NoProfile",
                "-File",
                str(CLEANUP),
                "-RunnerRoot",
                str(runner),
                "-MinimumAgeHours",
                "0",
                "-Json",
            ]
            for name, accepted in (
                (active.name, True),
                ("../outside", False),
                ("_unreal-build-999-1", False),
            ):
                with self.subTest(worktree=name):
                    pointer.write_text(
                        json.dumps({"schema_version": 1, "worktree": name})
                    )
                    result = subprocess.run(
                        command, capture_output=True, text=True, check=False
                    )
                    if accepted:
                        self.assertEqual(
                            result.returncode, 0, result.stdout + result.stderr
                        )
                        self.assertEqual(
                            json.loads(result.stdout)["candidate_count"], 0
                        )
                    else:
                        self.assertNotEqual(result.returncode, 0)
                    self.assertTrue((active / "Intermediate/build.bin").exists())

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
            (candidate / "Intermediate").mkdir()
            (candidate / "Intermediate" / "build.bin").write_bytes(b"x" * 1024)
            (candidate / "Source").mkdir()
            (candidate / "Source" / "keep.cpp").write_text("source", encoding="utf-8")
            (candidate / "Saved").mkdir()
            (candidate / "Saved" / "proof.txt").write_text("evidence", encoding="utf-8")
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
            self.assertTrue(candidate.exists())
            self.assertFalse((candidate / "Intermediate").exists())
            self.assertEqual((candidate / "Source" / "keep.cpp").read_text(), "source")
            self.assertEqual(
                (candidate / "Saved" / "proof.txt").read_text(), "evidence"
            )
            self.assertTrue(protected.exists())

    @unittest.skipUnless(sys.platform == "win32", "junction proof is Windows-only")
    def test_cleanup_rejects_a_junction_in_workspace_ancestry(self) -> None:
        pwsh = shutil.which("pwsh")
        if pwsh is None:
            self.skipTest("pwsh is unavailable")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            actual = root / "actual-runner"
            (actual / "_work/YetAnotherCyclingSim/YetAnotherCyclingSim").mkdir(
                parents=True
            )
            alias = root / "linked-runner"
            created = subprocess.run(
                [
                    pwsh,
                    "-NoProfile",
                    "-Command",
                    "New-Item -ItemType Junction -Path '"
                    + str(alias).replace("'", "''")
                    + "' -Target '"
                    + str(actual).replace("'", "''")
                    + "' | Out-Null",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            result = subprocess.run(
                [
                    pwsh,
                    "-NoProfile",
                    "-File",
                    str(CLEANUP),
                    "-RunnerRoot",
                    str(alias),
                    "-Json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("traverses a reparse point", result.stderr)
            self.assertTrue(actual.exists())


if __name__ == "__main__":
    unittest.main()

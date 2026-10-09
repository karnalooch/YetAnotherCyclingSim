"""Regression coverage for the owner-approved 5 GiB runner disk admission floor."""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts/runner/Assert-YacsDiskReserve.ps1"
HOOK = ROOT / "scripts/runner/Invoke-YacsJobStarted.ps1"
START = ROOT / "scripts/runner/Start-YacsRunner.ps1"
AUDIT = ROOT / "scripts/runner/Test-YacsWindowsHost.ps1"
TEXTURE = ROOT / ".github/workflows/texture-material-prep-remote-proof.yml"


class RunnerDiskReserveTests(unittest.TestCase):
    def test_shared_guard_preserves_fail_closed_comparison_and_five_gib_default(self):
        script = GUARD.read_text(encoding="utf-8")
        self.assertIn("[double]$MinimumFreeGiB = 5,", script)
        self.assertIn("[ValidateRange(1, 4096)]", script)
        self.assertIn("if ($free -lt $MinimumFreeGiB)", script)
        self.assertIn("$free = $AvailableBytes / 1GB", script)

    def test_job_started_hook_runs_before_checkout_with_shared_guard(self):
        script = HOOK.read_text(encoding="utf-8")
        launcher = START.read_text(encoding="utf-8")
        self.assertIn("Assert-YacsDiskReserve -Path $workspace", script)
        self.assertIn("Assert-YacsDiskReserve.ps1", script)
        self.assertIn("ACTIONS_RUNNER_HOOK_JOB_STARTED", launcher)
        self.assertIn("Invoke-YacsJobStarted.ps1", launcher)

    def test_host_audit_and_independent_texture_proof_match_five_gib(self):
        audit = AUDIT.read_text(encoding="utf-8")
        texture = TEXTURE.read_text(encoding="utf-8")
        self.assertIn("$MinimumFreeGiB = 5.0,", audit)
        self.assertIn("$FreeGiB -ge $MinimumFreeGiB", audit)
        self.assertIn("if ($drive.Free -lt 5GB)", texture)
        self.assertIn("repository 5 GiB reserve", texture)
        self.assertNotIn("$drive.Free -lt 50GB", texture)

    @unittest.skipUnless(
        shutil.which("pwsh"), "PowerShell 7 is needed to execute the guard"
    )
    def test_boundary_and_explicit_higher_override(self):
        cases = (
            (4.99, None, False),
            (5.0, None, True),
            (5.01, None, True),
            (5.0, 8, False),
            (8.0, 8, True),
        )
        guard_path = str(GUARD).replace("'", "''")
        for free_gib, override, expected in cases:
            with self.subTest(free_gib=free_gib, override=override):
                command = (
                    "$ErrorActionPreference = 'Stop'; "
                    f". '{guard_path}'; "
                    "Assert-YacsDiskReserve -Path '.' "
                    f"-AvailableBytes ([long]({free_gib} * 1GB))"
                )
                if override is not None:
                    command += f" -MinimumFreeGiB {override}"
                result = subprocess.run(
                    ["pwsh", "-NoProfile", "-NonInteractive", "-Command", command],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                self.assertEqual(
                    result.returncode == 0,
                    expected,
                    result.stdout + result.stderr,
                )


if __name__ == "__main__":
    unittest.main()

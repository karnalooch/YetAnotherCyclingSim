from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell is required")
class RunnerDiskReserveTests(unittest.TestCase):
    def run_guard(self, gib):
        script = Path(__file__).parents[1] / "runner/Assert-YacsDiskReserve.ps1"
        with tempfile.TemporaryDirectory() as root:
            return subprocess.run(
                [
                    "pwsh",
                    "-NoProfile",
                    "-Command",
                    f"$ErrorActionPreference='Stop'; . '{script}'; try {{ Assert-YacsDiskReserve -Path '{root}' -AvailableBytes {int(gib * 1024**3)} }} catch {{ [Console]::Error.WriteLine($_.Exception.Message); exit 1 }}",
                ],
                text=True,
                capture_output=True,
            )

    def test_below_reserve_rejects_job(self):
        result = self.run_guard(4.99)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Job stopped before heavy work", result.stderr)

    def test_reserve_boundary_accepts_job(self):
        result = self.run_guard(5)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_above_reserve_accepts_job(self):
        result = self.run_guard(5.01)
        self.assertEqual(result.returncode, 0, result.stderr)

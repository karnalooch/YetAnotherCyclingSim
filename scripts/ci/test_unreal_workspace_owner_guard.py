"""Execute cleanup with fake processes; never touch a native editor."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell unavailable")
class OwnerGuardTests(unittest.TestCase):
    def run_case(self, mode):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ci = root / "scripts/ci"
            runner = root / "scripts/runner"
            ci.mkdir(parents=True)
            runner.mkdir(parents=True)
            helper = ci / "Release-YacsUnrealWorkspaceLocks.ps1"
            shutil.copyfile(ROOT / "scripts/ci" / helper.name, helper)
            probe = runner / "Get-YacsUnrealHostState.ps1"
            if mode != "missing":
                shutil.copyfile(ROOT / "scripts/runner" / probe.name, probe)
            if mode == "error":
                probe.write_text("throw 'inspection failed'")
            if mode == "unknown":
                probe.write_text(
                    "[pscustomobject]@{status='UNKNOWN';local_or_unknown_count=0}"
                )
            workspace = root / "workspace"
            log = workspace / "Saved/Logs/YetAnotherCyclingSim.log"
            log.parent.mkdir(parents=True)
            log.write_text("owner log")
            script = root / "fixture.ps1"
            script.write_text(r"""param($Root, $Mode)
$ErrorActionPreference = 'Stop'
$global:killed = $false
$global:reads = 0
function global:Get-CimInstance {
    $global:reads++
    if ($global:killed) { return }
    $workspace = Join-Path $Root 'workspace'
    $command = '"D:\owner\World.uproject" -ExecutePythonScript="' + $workspace + '\preview\start.py"'
    if ($Mode -eq 'remote') { $command = $workspace + '\_unreal-ci-warm\World.uproject -Unattended' }
    if ($Mode -eq 'arrival' -and $global:reads -eq 1) { return }
    [pscustomobject]@{Name='UnrealEditor.exe'; ProcessId=123; ParentProcessId=1; ExecutablePath='fake-editor'; CommandLine=$command; CreationDate=[DateTime]::UtcNow}
}
function global:Get-Process {
    [pscustomobject]@{HasExited=$global:killed; SessionId=1}
}
function global:taskkill.exe {
    $global:killed = $true
    $global:LASTEXITCODE = 0
}
try {
    & (Join-Path $Root 'scripts/ci/Release-YacsUnrealWorkspaceLocks.ps1') -Workspace (Join-Path $Root 'workspace') -ProcessExitTimeoutSec 0 -LogReleaseTimeoutSec 0
    $accepted = $true
} catch { $accepted = $false }
'RESULT=' + (ConvertTo-Json -Compress @{accepted=$accepted;killed=$global:killed;log=(Test-Path -LiteralPath (Join-Path $Root 'workspace/Saved/Logs/YetAnotherCyclingSim.log'))})
""")
            if mode.startswith("final_"):
                bootstrap = workspace / "_bootstrap-cleanup"
                shutil.copytree(root / "scripts", bootstrap / "scripts")
                warm = workspace / "_unreal-ci-warm/scripts/ci"
                warm.mkdir(parents=True)
                (warm / helper.name).write_text(
                    "$global:killed = $true; throw 'STALE helper invoked'"
                )
                if mode == "final_missing":
                    (bootstrap / "scripts/ci" / helper.name).unlink()
                workflow = (ROOT / ".github/workflows/reusable-unreal.yml").read_text()
                step = workflow.split(
                    "- name: Clean current-run evidence and non-allow-listed residue", 1
                )[1]
                body = textwrap.dedent(step.split("run: |\n", 1)[1])
                final = root / "final.ps1"
                final.write_text(body)
                fixture = script.read_text().replace(
                    "& (Join-Path $Root 'scripts/ci/Release-YacsUnrealWorkspaceLocks.ps1') -Workspace (Join-Path $Root 'workspace') -ProcessExitTimeoutSec 0 -LogReleaseTimeoutSec 0",
                    "$env:GITHUB_WORKSPACE = Join-Path $Root 'workspace'; $env:YACS_UNREAL_WORKTREE = '_unreal-ci-warm'; & (Join-Path $Root 'final.ps1')",
                )
                script.write_text(fixture)
            result = subprocess.run(
                [
                    shutil.which("pwsh"),
                    "-NoProfile",
                    "-File",
                    str(script),
                    str(root),
                    mode,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(
                next(
                    line[7:]
                    for line in result.stdout.splitlines()
                    if line.startswith("RESULT=")
                )
            )

    def test_owner_launcher_inside_runner_is_preserved(self):
        self.assertEqual(
            self.run_case("local"), {"accepted": False, "killed": False, "log": True}
        )

    def test_owner_arriving_after_initial_probe_is_preserved(self):
        self.assertEqual(
            self.run_case("arrival"), {"accepted": False, "killed": False, "log": True}
        )

    def test_unverifiable_ownership_preserves_process_and_log(self):
        for mode in ("missing", "error", "unknown"):
            with self.subTest(mode=mode):
                self.assertEqual(
                    self.run_case(mode),
                    {"accepted": False, "killed": False, "log": True},
                )

    def test_stale_unattended_ci_cleanup_still_works(self):
        self.assertEqual(
            self.run_case("remote"), {"accepted": True, "killed": True, "log": False}
        )

    def test_final_cleanup_never_falls_back_to_old_warm_helper(self):
        for mode in ("final_local", "final_missing"):
            with self.subTest(mode=mode):
                self.assertEqual(
                    self.run_case(mode),
                    {"accepted": False, "killed": False, "log": True},
                )

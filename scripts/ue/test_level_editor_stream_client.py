"""Exercise the real PowerShell ownership functions without starting a browser."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

WRAPPER = Path(__file__).with_name("Test-YacsLevelEditorStreamClient.ps1")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
TICKS = 639273174838677317

RUNNER = r"""
param([string] $Wrapper, [string] $FixturePath)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$tokens = $null
$errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($Wrapper, [ref] $tokens, [ref] $errors)
if ($errors.Count) { throw ($errors | Out-String) }
foreach ($name in @(
    'Read-OwnedProcessIdentity', 'Format-OwnedProcessIdentityFailure',
    'Assert-OwnedProcessIdentity', 'Add-OwnedProcess', 'Observe-OwnedProcesses', 'Stop-OwnedProcesses'
)) {
    $nodes = @($ast.FindAll({ param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name
    }, $true))
    if ($nodes.Count -ne 1) { throw "Missing or duplicate function: $name" }
    . ([ScriptBlock]::Create($nodes[0].Extent.Text))
}
# An unassociated Process subclass supplies only controlled native I/O. It
# cannot name, start or terminate an OS process, even if a fixture goes wrong.
Add-Type -TypeDefinition @'
using System;
using System.Diagnostics;
public sealed class StreamProcessReadback {
    public int Pid;
    public bool Exited;
    public long StartTicks;
    public string Executable;
    public string ReadError;
}
public sealed class StreamProcessFixture : Process {
    public StreamProcessReadback[] Readbacks;
    public int ReadCount;
    public int HandleReadCount;
    public int KillCount;
    public int DisposeCount;
    public bool Stopped;
    public long ExitTicks;
    private StreamProcessReadback Current {
        get { return Readbacks[Math.Max(0, Math.Min(ReadCount - 1, Readbacks.Length - 1))]; }
    }
    public new IntPtr Handle { get { HandleReadCount++; return new IntPtr(42); } }
    public new int Id { get { return Current.Pid; } }
    public new bool HasExited { get { return Stopped || Current.Exited; } }
    public new DateTime StartTime { get { return new DateTime(Current.StartTicks, DateTimeKind.Utc); } }
    public new DateTime ExitTime { get { return new DateTime(ExitTicks, DateTimeKind.Utc); } }
    public new void Refresh() { ReadCount++; }
    public string ReadExecutable() {
        if (!String.IsNullOrEmpty(Current.ReadError)) { throw new InvalidOperationException(Current.ReadError); }
        return Current.Executable;
    }
    public new void Kill() { KillCount++; Stopped = true; }
    public new bool WaitForExit(int milliseconds) { return HasExited; }
    public new void Dispose() { DisposeCount++; }
}
'@
$fixture = Get-Content -LiteralPath $FixturePath -Raw | ConvertFrom-Json -AsHashtable
function New-FixtureProcess([object[]] $Readbacks) {
    $process = [StreamProcessFixture]::new()
    $process.Readbacks = @($Readbacks | ForEach-Object {
        $row = [StreamProcessReadback]::new()
        $row.Pid = $_.pid
        $row.Exited = $_.has_exited
        $row.StartTicks = $_.start_ticks
        if ($null -ne $_.executable) { $row.Executable = $_.executable }
        if ($null -ne $_.read_error) { $row.ReadError = $_.read_error }
        $row
    })
    $process.ExitTicks = $fixture.parent_exit_ticks
    return $process
}
$Browser = New-FixtureProcess $fixture.readbacks
$children = @{}
foreach ($child in $fixture.children) {
    $children[[string] $child.lookup_pid] = New-FixtureProcess $child.readbacks
}
# Process.Path is a PowerShell property; replace only this OS read boundary.
Update-TypeData -TypeName StreamProcessFixture -MemberType ScriptProperty -MemberName Path -Value { $this.ReadExecutable() } -Force
$unrelated = [StreamProcessFixture]::new()
$unrelated.Readbacks = @([StreamProcessReadback]@{ Pid = 9999; StartTicks = 639273174838677317 })
$Clock = [pscustomobject]@{ ElapsedMilliseconds = [long] $fixture.elapsed_ms }
$WorkLimitMilliseconds = 80000
$OwnedProcesses = @{}
$CleanupErrors = [Collections.Generic.List[string]]::new()
$receipt = [ordered]@{}
$script:Sleeps = [Collections.Generic.List[int]]::new()
$script:CimReadCount = 0
$script:ProcessLookups = [Collections.Generic.List[int]]::new()
function Start-Sleep([int] $Milliseconds) {
    $script:Sleeps.Add($Milliseconds)
    $Clock.ElapsedMilliseconds += $Milliseconds
}
function Get-CimInstance {
    [CmdletBinding()]
    param([string] $ClassName, [string[]] $Property, [int] $OperationTimeoutSec)
    if ($ClassName -ne 'Win32_Process' -or $OperationTimeoutSec -ne 2) { throw 'Unexpected native CIM call.' }
    $index = [Math]::Min($script:CimReadCount, $fixture.cim_snapshots.Count - 1)
    $script:CimReadCount++
    foreach ($row in $fixture.cim_snapshots[$index]) {
        [pscustomobject]@{
            ProcessId = $row.pid; ParentProcessId = $row.parent_pid
            CreationDate = [DateTime]::new($row.created_ticks, [DateTimeKind]::Utc)
        }
    }
}
function Get-Process {
    [CmdletBinding()]
    param([int] $Id)
    $script:ProcessLookups.Add($Id)
    if (-not $children.ContainsKey([string] $Id)) { throw 'Unexpected native process lookup.' }
    return $children[[string] $Id]
}
$admissionError = $null
$assertionError = $null
try { Add-OwnedProcess $Browser 26428 $fixture.expected_executable }
catch { $admissionError = $_.Exception.Message }
$admitted = $OwnedProcesses.Count -eq 1
if ($fixture.operation -eq 'assert' -and $admitted) {
    try {
        Assert-OwnedProcessIdentity $Browser $OwnedProcesses['3264'] 'DevTools listener process identity changed.'
    }
    catch { $assertionError = $_.Exception.Message }
}
if ($null -ne $fixture.cleanup_elapsed_ms) { $Clock.ElapsedMilliseconds = $fixture.cleanup_elapsed_ms }
if ($fixture.operation -eq 'cleanup') { Stop-OwnedProcesses }
if ($fixture.operation -eq 'observe') { Observe-OwnedProcesses }
$entries = @($OwnedProcesses.Values | ForEach-Object {
    @{ pid = $_.pid; parent_pid = $_.parent_pid; start_ticks = [string] $_.start_ticks; executable = $_.executable }
})
[ordered]@{
    admission_error = $admissionError; assertion_error = $assertionError
    admitted = $admitted; entries = $entries; cleanup_errors = @($CleanupErrors)
    kill_count = $Browser.KillCount; dispose_count = $Browser.DisposeCount
    unrelated_kill_count = $unrelated.KillCount
    read_count = $Browser.ReadCount; handle_read_count = $Browser.HandleReadCount
    elapsed_ms = $Clock.ElapsedMilliseconds; sleeps = @($script:Sleeps)
    cim_read_count = $script:CimReadCount; process_lookups = @($script:ProcessLookups)
    child_processes = @($children.GetEnumerator() | ForEach-Object {
        @{ lookup_pid = [int] $_.Key; kill_count = $_.Value.KillCount; dispose_count = $_.Value.DisposeCount }
    })
} | ConvertTo-Json -Depth 8 -Compress
"""


def readback(
    executable: str | None = EDGE,
    *,
    pid: int = 3264,
    ticks: int = TICKS,
    exited: bool = False,
    error: str | None = None,
) -> dict:
    return {
        "pid": pid,
        "has_exited": exited,
        "start_ticks": ticks,
        "executable": executable,
        "read_error": error,
    }


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is required")
class ProcessIdentityTests(unittest.TestCase):
    def run_fixture(
        self,
        readbacks: list[dict],
        *,
        operation: str = "admit",
        elapsed_ms: int = 0,
        expected_executable: str = EDGE,
        cleanup_elapsed_ms: int | None = None,
        children: list[dict] | None = None,
        cim_snapshots: list[list[dict]] | None = None,
        parent_exit_ticks: int = TICKS + 200000,
    ) -> dict:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner = root / "fixture.ps1"
            fixture = root / "fixture.json"
            runner.write_text(RUNNER, encoding="utf-8")
            fixture.write_text(
                json.dumps(
                    {
                        "readbacks": readbacks,
                        "operation": operation,
                        "elapsed_ms": elapsed_ms,
                        "expected_executable": expected_executable,
                        "cleanup_elapsed_ms": cleanup_elapsed_ms,
                        "children": children or [],
                        "cim_snapshots": cim_snapshots or [[]],
                        "parent_exit_ticks": parent_exit_ticks,
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    shutil.which("pwsh"),
                    "-NoProfile",
                    "-NonInteractive",
                    "-File",
                    str(runner),
                    str(WRAPPER),
                    str(fixture),
                ],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def assert_diagnostic(self, message: str) -> dict:
        self.assertIn("Identity readback: ", message)
        return json.loads(message.split("Identity readback: ", 1)[1])

    def test_null_path_becomes_actual_nonempty_path_before_admission(self):
        result = self.run_fixture([readback(None), readback()])
        self.assertIsNone(result["admission_error"])
        self.assertTrue(result["admitted"])
        self.assertEqual(result["read_count"], 2)
        self.assertEqual(result["handle_read_count"], 2)
        self.assertEqual(result["sleeps"], [50])
        self.assertEqual(
            result["entries"],
            [
                {
                    "pid": 3264,
                    "parent_pid": 26428,
                    "start_ticks": str(TICKS),
                    "executable": EDGE,
                }
            ],
        )
        self.assertEqual(result["kill_count"], 0)

    def test_root_mismatched_path_is_not_admitted_or_cleaned_up(self):
        other = r"C:\Other\msedge.exe"
        result = self.run_fixture([readback(other)], operation="cleanup")
        self.assertFalse(result["admitted"])
        self.assertEqual(result["entries"], [])
        self.assertEqual(result["kill_count"], 0)
        self.assertEqual(result["unrelated_kill_count"], 0)
        self.assertIn("cleanup cannot be confirmed", result["cleanup_errors"][0])
        diagnostic = self.assert_diagnostic(result["admission_error"])
        self.assertEqual(diagnostic["expected"]["executable"], EDGE)
        self.assertEqual(diagnostic["observed"]["executable"], other)

    def test_missing_path_times_out_without_admission_or_unverified_kill(self):
        result = self.run_fixture([readback(None)], operation="cleanup")
        self.assertFalse(result["admitted"])
        self.assertEqual(result["entries"], [])
        self.assertEqual(result["elapsed_ms"], 2000)
        self.assertEqual(result["read_count"], 41)
        self.assertEqual(result["kill_count"], 0)
        self.assertEqual(result["unrelated_kill_count"], 0)
        self.assertIn("cleanup cannot be confirmed", result["cleanup_errors"][0])
        diagnostic = self.assert_diagnostic(result["admission_error"])
        self.assertIsNone(diagnostic["observed"]["executable"])

    def test_path_wait_cannot_consume_reserved_cleanup_budget(self):
        result = self.run_fixture([readback(None)], elapsed_ms=79975)
        self.assertFalse(result["admitted"])
        self.assertEqual(result["elapsed_ms"], 80000)
        self.assertEqual(result["sleeps"], [25])
        self.assertEqual(result["read_count"], 2)

    def test_ready_path_at_deadline_cannot_be_admitted(self):
        for readbacks, elapsed_ms, deadline in (
            ([readback(None)] * 40 + [readback()], 0, 2000),
            ([readback(None), readback()], 79975, 80000),
        ):
            with self.subTest(elapsed_ms=elapsed_ms):
                result = self.run_fixture(readbacks, elapsed_ms=elapsed_ms)
                self.assertFalse(result["admitted"])
                self.assertEqual(result["entries"], [])
                self.assertEqual(result["elapsed_ms"], deadline)
                self.assertIn("Timed out", result["admission_error"])
                diagnostic = self.assert_diagnostic(result["admission_error"])
                self.assertEqual(diagnostic["observed"]["executable"], EDGE)

    def test_exit_while_waiting_never_admits_or_kills(self):
        result = self.run_fixture(
            [readback(None), readback(exited=True)], operation="cleanup"
        )
        self.assertFalse(result["admitted"])
        self.assertEqual(result["kill_count"], 0)
        self.assertEqual(result["cleanup_errors"], [])
        diagnostic = self.assert_diagnostic(result["admission_error"])
        self.assertTrue(diagnostic["observed"]["has_exited"])

    def test_pid_and_one_tick_change_during_path_wait_are_rejected(self):
        for changed in (readback(pid=3265), readback(ticks=TICKS + 1)):
            with self.subTest(changed=changed):
                result = self.run_fixture([readback(None), changed])
                self.assertFalse(result["admitted"])
                self.assertEqual(result["entries"], [])
                diagnostic = self.assert_diagnostic(result["admission_error"])
                self.assertEqual(diagnostic["expected"]["pid"], 3264)
                self.assertEqual(diagnostic["expected"]["start_ticks_utc"], str(TICKS))
                self.assertEqual(diagnostic["observed"]["pid"], changed["pid"])
                self.assertEqual(
                    diagnostic["observed"]["start_ticks_utc"],
                    str(changed["start_ticks"]),
                )

    def test_listener_refuses_changed_or_unreadable_identity_with_details(self):
        for changed in (
            readback(r"C:\Other\msedge.exe"),
            readback(ticks=TICKS + 1),
            readback(None),
            readback(error="Fixture path read refused"),
        ):
            with self.subTest(changed=changed):
                result = self.run_fixture([readback(), changed], operation="assert")
                self.assertTrue(result["admitted"])
                self.assertIn(
                    "DevTools listener process identity changed.",
                    result["assertion_error"],
                )
                diagnostic = self.assert_diagnostic(result["assertion_error"])
                self.assertEqual(diagnostic["expected"]["executable"], EDGE)
                self.assertEqual(diagnostic["expected"]["start_ticks_utc"], str(TICKS))
                self.assertEqual(
                    diagnostic["observed"]["start_ticks_utc"],
                    str(changed["start_ticks"]),
                )
                self.assertEqual(result["kill_count"], 0)

    def test_cleanup_stops_only_process_with_matching_admitted_identity(self):
        result = self.run_fixture([readback()], operation="cleanup")
        self.assertTrue(result["admitted"])
        self.assertEqual(result["kill_count"], 1)
        self.assertEqual(result["unrelated_kill_count"], 0)
        self.assertEqual(result["dispose_count"], 1)
        self.assertEqual(result["cleanup_errors"], [])

    def test_cleanup_never_kills_after_exact_identity_changes(self):
        for changed in (readback(ticks=TICKS + 1), readback(r"C:\Other\msedge.exe")):
            with self.subTest(changed=changed):
                result = self.run_fixture([readback(), changed], operation="cleanup")
                self.assertTrue(result["admitted"])
                self.assertEqual(result["kill_count"], 0)
                self.assertEqual(result["unrelated_kill_count"], 0)
                self.assertEqual(len(result["cleanup_errors"]), 3)
                diagnostic = self.assert_diagnostic(result["cleanup_errors"][0])
                self.assertEqual(diagnostic["expected"]["start_ticks_utc"], str(TICKS))
                self.assertEqual(
                    diagnostic["observed"]["start_ticks_utc"],
                    str(changed["start_ticks"]),
                )

    def test_cleanup_discovers_and_stops_pre_exit_child_after_80_seconds(self):
        created = TICKS + 100000
        result = self.run_fixture(
            [readback()],
            operation="cleanup",
            cleanup_elapsed_ms=81000,
            children=[
                {
                    "lookup_pid": 9608,
                    "readbacks": [
                        readback(None, pid=9608, ticks=created),
                        readback(pid=9608, ticks=created),
                    ],
                }
            ],
            # The child is first seen in the second cleanup pass, after its
            # held parent has been stopped. Its creation predates that exit.
            cim_snapshots=[
                [],
                [{"pid": 9608, "parent_pid": 3264, "created_ticks": created}],
            ],
        )
        self.assertEqual(result["cim_read_count"], 2)
        self.assertEqual(result["process_lookups"], [9608])
        self.assertEqual({entry["pid"] for entry in result["entries"]}, {3264, 9608})
        self.assertEqual(result["elapsed_ms"], 81050)
        self.assertEqual(result["sleeps"], [50])
        self.assertEqual(result["kill_count"], 1)
        self.assertEqual(result["child_processes"][0]["kill_count"], 1)
        self.assertEqual(result["unrelated_kill_count"], 0)
        self.assertEqual(result["cleanup_errors"], [])

    def test_normal_observation_does_not_adopt_child_after_80_seconds(self):
        created = TICKS + 100000
        result = self.run_fixture(
            [readback()],
            operation="observe",
            cleanup_elapsed_ms=81000,
            children=[
                {"lookup_pid": 9608, "readbacks": [readback(pid=9608, ticks=created)]}
            ],
            cim_snapshots=[
                [{"pid": 9608, "parent_pid": 3264, "created_ticks": created}]
            ],
        )
        self.assertEqual(result["process_lookups"], [9608])
        self.assertEqual([entry["pid"] for entry in result["entries"]], [3264])
        self.assertEqual(result["child_processes"][0]["kill_count"], 0)
        self.assertEqual(result["elapsed_ms"], 81000)

    def test_cleanup_never_adopts_child_created_after_held_parent_exit(self):
        parent_exit = TICKS + 200000
        created = parent_exit + 1
        result = self.run_fixture(
            [readback()],
            operation="cleanup",
            cleanup_elapsed_ms=81000,
            parent_exit_ticks=parent_exit,
            children=[
                {"lookup_pid": 9608, "readbacks": [readback(pid=9608, ticks=created)]}
            ],
            cim_snapshots=[
                [],
                [{"pid": 9608, "parent_pid": 3264, "created_ticks": created}],
            ],
        )
        self.assertEqual(result["cim_read_count"], 2)
        self.assertEqual(result["process_lookups"], [])
        self.assertEqual([entry["pid"] for entry in result["entries"]], [3264])
        self.assertEqual(result["kill_count"], 1)
        self.assertEqual(result["child_processes"][0]["kill_count"], 0)
        self.assertEqual(result["unrelated_kill_count"], 0)

    def test_cleanup_rejects_cim_child_with_wrong_native_pid_or_start(self):
        created = TICKS + 100000
        for observed in (
            readback(pid=9609, ticks=created),
            readback(pid=9608, ticks=created + 10001),
        ):
            with self.subTest(observed=observed):
                result = self.run_fixture(
                    [readback()],
                    operation="cleanup",
                    cleanup_elapsed_ms=81000,
                    children=[{"lookup_pid": 9608, "readbacks": [observed]}],
                    cim_snapshots=[
                        [],
                        [{"pid": 9608, "parent_pid": 3264, "created_ticks": created}],
                    ],
                )
                self.assertEqual(result["process_lookups"], [9608])
                self.assertEqual([entry["pid"] for entry in result["entries"]], [3264])
                self.assertEqual(result["child_processes"][0]["kill_count"], 0)
                self.assertEqual(result["child_processes"][0]["dispose_count"], 1)
                self.assertEqual(result["unrelated_kill_count"], 0)

    def test_cleanup_path_at_88_second_deadline_is_refused_and_reported(self):
        created = TICKS + 100000
        result = self.run_fixture(
            [readback()],
            operation="cleanup",
            cleanup_elapsed_ms=87975,
            children=[
                {
                    "lookup_pid": 9608,
                    "readbacks": [
                        readback(None, pid=9608, ticks=created),
                        readback(pid=9608, ticks=created),
                    ],
                }
            ],
            cim_snapshots=[
                [],
                [{"pid": 9608, "parent_pid": 3264, "created_ticks": created}],
            ],
        )
        self.assertEqual(result["elapsed_ms"], 88000)
        self.assertEqual(result["sleeps"], [25])
        self.assertEqual([entry["pid"] for entry in result["entries"]], [3264])
        self.assertEqual(result["child_processes"][0]["kill_count"], 0)
        self.assertEqual(result["unrelated_kill_count"], 0)
        self.assertEqual(len(result["cleanup_errors"]), 1)
        self.assertIn("Timed out", result["cleanup_errors"][0])
        diagnostic = self.assert_diagnostic(result["cleanup_errors"][0])
        self.assertEqual(diagnostic["observed"]["pid"], 9608)
        self.assertEqual(diagnostic["observed"]["executable"], EDGE)

    def test_long_diagnostic_path_has_explicit_truncation(self):
        other = "C:\\" + "x" * 1000
        result = self.run_fixture([readback(other)])
        diagnostic = self.assert_diagnostic(result["admission_error"])
        observed = diagnostic["observed"]
        self.assertEqual(observed["executable"], other[:512])
        self.assertEqual(observed["executable_length"], len(other))
        self.assertTrue(observed["executable_truncated"])


TARGET_RUNNER = r"""
param([string] $Wrapper, [string] $FixturePath)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$tokens = $null
$errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($Wrapper, [ref] $tokens, [ref] $errors)
if ($errors.Count) { throw ($errors | Out-String) }
$function = $ast.Find({ param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -ceq 'Select-BlankDevToolsTarget'
}, $true)
. ([ScriptBlock]::Create($function.Extent.Text))
# Reproduce Invoke-RestMethod's non-enumerated JSON-array output boundary.
function Invoke-RestMethod {
    Write-Output -NoEnumerate (Get-Content -LiteralPath $FixturePath -Raw | ConvertFrom-Json -NoEnumerate)
}
try {
    $targets = Invoke-RestMethod
    $target = Select-BlankDevToolsTarget $targets
    $uri = if ($null -ne $target) { ([Uri] $target.webSocketDebuggerUrl).AbsoluteUri } else { $null }
    @{ uri = $uri; error = $null } | ConvertTo-Json -Compress
}
catch { @{ uri = $null; error = $_.Exception.Message } | ConvertTo-Json -Compress }
"""


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is required")
class DevToolsTargetTests(unittest.TestCase):
    def select(self, targets):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner = root / "target.ps1"
            fixture = root / "targets.json"
            runner.write_text(TARGET_RUNNER, encoding="utf-8")
            fixture.write_text(json.dumps(targets), encoding="utf-8")
            result = subprocess.run(
                [
                    shutil.which("pwsh"),
                    "-NoProfile",
                    "-NonInteractive",
                    "-File",
                    str(runner),
                    str(WRAPPER),
                    str(fixture),
                ],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_multiple_targets_select_one_matching_page(self):
        url = "ws://127.0.0.1:9237/devtools/page/owned"
        result = self.select(
            [
                {
                    "type": "worker",
                    "url": "about:blank",
                    "webSocketDebuggerUrl": "ws://127.0.0.1:9237/devtools/page/worker",
                },
                {"type": "page", "url": "about:blank", "webSocketDebuggerUrl": url},
                {
                    "type": "page",
                    "url": "about:blank",
                    "webSocketDebuggerUrl": "ws://127.0.0.1:9237/devtools/page/other",
                },
            ]
        )
        self.assertEqual(result, {"uri": url, "error": None})

    def test_fields_from_different_targets_cannot_match(self):
        result = self.select(
            [
                {"type": "worker", "url": "about:blank"},
                {"type": "page", "url": "https://example.test/"},
            ]
        )
        self.assertEqual(result, {"uri": None, "error": None})

    def test_empty_and_single_target_arrays(self):
        self.assertEqual(self.select([]), {"uri": None, "error": None})
        url = "ws://127.0.0.1:9237/devtools/page/only"
        self.assertEqual(
            self.select(
                [{"type": "page", "url": "about:blank", "webSocketDebuggerUrl": url}]
            ),
            {"uri": url, "error": None},
        )

    def test_array_or_missing_debugger_url_is_rejected(self):
        missing = self.select([{"type": "page", "url": "about:blank"}])
        self.assertIn("one nonempty debugger URL string", missing["error"])
        for value in (None, [], ["ws://127.0.0.1:9237/devtools/page/one"], ""):
            with self.subTest(value=value):
                result = self.select(
                    [
                        {
                            "type": "page",
                            "url": "about:blank",
                            "webSocketDebuggerUrl": value,
                        }
                    ]
                )
                self.assertIsNone(result["uri"])
                self.assertIn("one nonempty debugger URL string", result["error"])


CDP_RUNNER = r"""
param([string] $Wrapper, [string] $Mode)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$tokens = $null
$errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($Wrapper, [ref] $tokens, [ref] $errors)
if ($errors.Count) { throw ($errors | Out-String) }
foreach ($name in @('Get-RemainingMilliseconds', 'Invoke-Cdp', 'Invoke-PageExpression')) {
    $node = $ast.Find({ param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name
    }, $true)
    . ([ScriptBlock]::Create($node.Extent.Text))
}
# The async methods really return Task/Task<T>; only socket I/O is replaced.
# PowerShell exposes Task<VoidTaskResult>'s completion unless it is suppressed.
Add-Type -TypeDefinition @'
using System;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
public sealed class CdpSocketFixture {
    public string Mode;
    public int Sends;
    public int Receives;
    public int Connects;
    private int commandId;
    public async Task ConnectAsync(Uri uri, CancellationToken token) {
        await Task.Yield();
        Connects++;
        token.ThrowIfCancellationRequested();
    }
    public async Task SendAsync(ArraySegment<byte> bytes, WebSocketMessageType type, bool final, CancellationToken token) {
        await Task.Yield();
        Sends++;
        if (Mode == "send-error") throw new InvalidOperationException("fixture send failed");
        commandId = JsonDocument.Parse(bytes.AsMemory()).RootElement.GetProperty("id").GetInt32();
    }
    public Task<WebSocketReceiveResult> ReceiveAsync(ArraySegment<byte> bytes, CancellationToken token) {
        Receives++;
        string result = Mode == "protocol-error" ? "\"error\":{\"message\":\"fixture protocol failed\"}" :
            "\"result\":{\"frameId\":\"owned-frame\",\"result\":{\"value\":17}}";
        byte[] data = Encoding.UTF8.GetBytes("{\"id\":" + commandId + "," + result + "}");
        data.CopyTo(bytes.Array, bytes.Offset);
        return Task.FromResult(new WebSocketReceiveResult(data.Length, WebSocketMessageType.Text, true));
    }
}
'@
$WebSocket = [CdpSocketFixture]::new()
$WebSocket.Mode = $Mode
$Clock = [pscustomobject]@{ElapsedMilliseconds=0}
$WorkLimitMilliseconds = 80000
$script:CdpMessageId = 0
$BrowserEvents = [Collections.Generic.List[string]]::new()
$errorText = $null
$result = $null
try {
    if ($Mode -eq 'connect') {
        $debugBuilder = [UriBuilder]::new('ws://127.0.0.1:9237/devtools/page/owned')
        $connectCancel = [Threading.CancellationTokenSource]::new(3000)
        $connect = $ast.Find({ param($node)
            $node -is [Management.Automation.Language.TryStatementAst] -and
            $node.Body.Extent.Text -match '^\{\s*(\$null\s*=\s*)?\$WebSocket.ConnectAsync'
        }, $true)
        if ($null -eq $connect) { throw 'Missing connection statement.' }
        $result = @(. ([ScriptBlock]::Create($connect.Extent.Text))).Count
    }
    elseif ($Mode -eq 'evaluate') { $result = Invoke-PageExpression '17' }
    else {
        $navigation = Invoke-Cdp 'Page.navigate' @{url='http://127.0.0.1/'}
        if ($navigation.ContainsKey('errorText')) { throw 'Unexpected navigation error.' }
        $result = $navigation.frameId
    }
}
catch { $errorText = $_.Exception.Message }
@{result=$result;error=$errorText;sends=$WebSocket.Sends;receives=$WebSocket.Receives;connects=$WebSocket.Connects} | ConvertTo-Json -Compress
"""


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is required")
class CdpTaskBoundaryTests(unittest.TestCase):
    def run_fixture(self, mode):
        with tempfile.TemporaryDirectory() as temporary:
            runner = Path(temporary) / "cdp.ps1"
            runner.write_text(CDP_RUNNER, encoding="utf-8")
            result = subprocess.run(
                [
                    shutil.which("pwsh"),
                    "-NoProfile",
                    "-NonInteractive",
                    "-File",
                    str(runner),
                    str(WRAPPER),
                    mode,
                ],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_navigation_returns_only_protocol_result(self):
        result = self.run_fixture("navigate")
        self.assertIsNone(result["error"])
        self.assertEqual(result["result"], "owned-frame")
        self.assertEqual((result["sends"], result["receives"]), (1, 1))

    def test_page_expression_returns_only_evidence_value(self):
        result = self.run_fixture("evaluate")
        self.assertIsNone(result["error"])
        self.assertEqual(result["result"], 17)

    def test_connection_completion_produces_no_pipeline_value(self):
        result = self.run_fixture("connect")
        self.assertIsNone(result["error"])
        self.assertEqual(result["result"], 0)
        self.assertEqual(result["connects"], 1)

    def test_protocol_failure_is_not_swallowed(self):
        result = self.run_fixture("protocol-error")
        self.assertIn("fixture protocol failed", result["error"])
        self.assertIsNone(result["result"])
        self.assertEqual((result["sends"], result["receives"]), (1, 1))

    def test_send_failure_does_not_receive_or_retry(self):
        result = self.run_fixture("send-error")
        self.assertIn("fixture send failed", result["error"])
        self.assertIsNone(result["result"])
        self.assertEqual((result["sends"], result["receives"]), (1, 0))


if __name__ == "__main__":
    unittest.main()

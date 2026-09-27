<#
.SYNOPSIS
    Releases stale Unreal processes and the canonical workspace log on the trusted Windows runner.

.DESCRIPTION
    The self-hosted Actions workspace persists between jobs. A cancelled or interrupted
    Unreal commandlet can therefore survive into the next job and keep Saved/Logs/
    YetAnotherCyclingSim.log open. This helper is deliberately scoped to Unreal-related
    processes whose command line references the exact GITHUB_WORKSPACE path.

    taskkill /T /F is used so child processes that inherited the log handle are terminated
    together with the stale editor/commandlet. The helper fails closed if a workspace-scoped
    Unreal process remains alive or the log stays locked after the bounded retry window.
#>
[CmdletBinding()]
param(
    [string] $Workspace = $env:GITHUB_WORKSPACE,
    [int] $ProcessExitTimeoutSec = 5,
    [int] $LogReleaseTimeoutSec = 10
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($Workspace)) {
    throw 'Workspace path is required.'
}

$Workspace = [System.IO.Path]::GetFullPath($Workspace).TrimEnd('\')
$Names = @(
    'UnrealEditor.exe',
    'UnrealEditor-Cmd.exe',
    'CrashReportClient.exe',
    'ShaderCompileWorker.exe',
    'UnrealCEFSubProcess.exe'
)

function Test-NativeProcessAlive {
    param([int] $ProcessId)

    try {
        $NativeProcess = Get-Process -Id $ProcessId -ErrorAction Stop
        return -not $NativeProcess.HasExited
    }
    catch {
        return $false
    }
}

function Get-WorkspaceUnrealProcesses {
    @(
        Get-CimInstance Win32_Process -ErrorAction Stop |
            Where-Object {
                $_.Name -in $Names -and
                $_.CommandLine -and
                $_.CommandLine.IndexOf(
                    $Workspace,
                    [System.StringComparison]::OrdinalIgnoreCase
                ) -ge 0 -and
                (Test-NativeProcessAlive -ProcessId ([int]$_.ProcessId))
            }
    )
}

function Get-FileLockingProcesses {
    param([Parameter(Mandatory = $true)][string] $Path)

    if (-not ('YacsFileLockProbe.RestartManager' -as [type])) {
        $RestartManagerSource = @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace YacsFileLockProbe
{
    public static class RestartManager
    {
        const int ErrorSuccess = 0;
        const int ErrorMoreData = 234;
        const int MaxAppName = 255;
        const int MaxServiceName = 63;

        [StructLayout(LayoutKind.Sequential)]
        struct RM_UNIQUE_PROCESS
        {
            public int dwProcessId;
            public System.Runtime.InteropServices.ComTypes.FILETIME ProcessStartTime;
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        struct RM_PROCESS_INFO
        {
            public RM_UNIQUE_PROCESS Process;

            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = MaxAppName + 1)]
            public string strAppName;

            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = MaxServiceName + 1)]
            public string strServiceShortName;

            public uint ApplicationType;
            public uint AppStatus;
            public uint TSSessionId;

            [MarshalAs(UnmanagedType.Bool)]
            public bool bRestartable;
        }

        [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)]
        static extern int RmStartSession(
            out uint pSessionHandle,
            int dwSessionFlags,
            string strSessionKey);

        [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)]
        static extern int RmRegisterResources(
            uint pSessionHandle,
            uint nFiles,
            string[] rgsFilenames,
            uint nApplications,
            [In] RM_UNIQUE_PROCESS[] rgApplications,
            uint nServices,
            string[] rgsServiceNames);

        [DllImport("rstrtmgr.dll")]
        static extern int RmGetList(
            uint dwSessionHandle,
            out uint pnProcInfoNeeded,
            ref uint pnProcInfo,
            [In, Out] RM_PROCESS_INFO[] rgAffectedApps,
            ref uint lpdwRebootReasons);

        [DllImport("rstrtmgr.dll")]
        static extern int RmEndSession(uint pSessionHandle);

        public static int[] GetLockingProcessIds(string path)
        {
            uint handle;
            var result = RmStartSession(out handle, 0, Guid.NewGuid().ToString());
            if (result != ErrorSuccess)
                throw new InvalidOperationException("RmStartSession failed: " + result);

            try
            {
                var resources = new[] { path };
                result = RmRegisterResources(handle, 1, resources, 0, null, 0, null);
                if (result != ErrorSuccess)
                    throw new InvalidOperationException("RmRegisterResources failed: " + result);

                for (var attempt = 0; attempt < 3; attempt++)
                {
                    uint needed = 0;
                    uint count = 0;
                    uint rebootReasons = 0;

                    result = RmGetList(handle, out needed, ref count, null, ref rebootReasons);
                    if (result == ErrorSuccess)
                        return Array.Empty<int>();
                    if (result != ErrorMoreData)
                        throw new InvalidOperationException("RmGetList(size) failed: " + result);

                    var info = new RM_PROCESS_INFO[needed];
                    count = needed;
                    result = RmGetList(handle, out needed, ref count, info, ref rebootReasons);
                    if (result == ErrorMoreData)
                        continue;
                    if (result != ErrorSuccess)
                        throw new InvalidOperationException("RmGetList(data) failed: " + result);

                    var pids = new List<int>((int)count);
                    for (var i = 0; i < count; i++)
                        pids.Add(info[i].Process.dwProcessId);
                    return pids.ToArray();
                }

                throw new InvalidOperationException("RmGetList remained unstable after 3 attempts.");
            }
            finally
            {
                RmEndSession(handle);
            }
        }
    }
}
'@
        Add-Type -TypeDefinition $RestartManagerSource -Language CSharp -ErrorAction Stop
    }

    $Results = [System.Collections.Generic.List[object]]::new()
    foreach ($ProcessId in @([YacsFileLockProbe.RestartManager]::GetLockingProcessIds($Path))) {
        $NativeProcess = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        $ProcessName = if ($NativeProcess) { $NativeProcess.ProcessName } else { '<exited>' }
        [void]$Results.Add([pscustomobject]@{
            ProcessId = [int]$ProcessId
            ProcessName = [string]$ProcessName
        })
    }
    return @($Results)
}

function Write-WorkspaceLockDiagnostics {
    try {
        $ProcessTable = @(Get-CimInstance Win32_Process -ErrorAction Stop)
        $RawWorkspaceUnreal = @(
            $ProcessTable |
                Where-Object {
                    $_.Name -in $Names -and
                    $_.CommandLine -and
                    $_.CommandLine.IndexOf(
                        $Workspace,
                        [System.StringComparison]::OrdinalIgnoreCase
                    ) -ge 0
                }
        )

        if ($RawWorkspaceUnreal.Count -eq 0) {
            Write-Warning 'Lock diagnostic: no raw workspace-scoped Unreal process remained in CIM.'
            return
        }

        foreach ($Process in $RawWorkspaceUnreal) {
            $Parent = $ProcessTable |
                Where-Object { [int]$_.ProcessId -eq [int]$Process.ParentProcessId } |
                Select-Object -First 1
            $ParentName = if ($Parent) { $Parent.Name } else { '<missing>' }
            $NativeAlive = Test-NativeProcessAlive -ProcessId ([int]$Process.ProcessId)
            Write-Warning (
                "Lock diagnostic candidate: {0} pid={1} parentPid={2} parentName={3} nativeAlive={4}" -f
                    $Process.Name,
                    $Process.ProcessId,
                    $Process.ParentProcessId,
                    $ParentName,
                    $NativeAlive
            )
        }
    }
    catch {
        Write-Warning ("Lock diagnostic failed: {0}" -f $_.Exception.Message)
    }
}

$Stale = @(Get-WorkspaceUnrealProcesses)
foreach ($Process in $Stale) {
    $TargetProcessId = [int]$Process.ProcessId
    Write-Host ("Stopping stale workspace process {0} pid={1} with child tree." -f $Process.Name, $TargetProcessId)

    & taskkill.exe /PID $TargetProcessId /T /F | Write-Host
    $TaskkillExit = $LASTEXITCODE
    if ($TaskkillExit -ne 0) {
        $StillPresent = @(
            Get-WorkspaceUnrealProcesses |
                Where-Object { [int]$_.ProcessId -eq $TargetProcessId }
        )
        if ($StillPresent.Count -gt 0) {
            Write-Warning "taskkill returned exit=$TaskkillExit for pid=$TargetProcessId; deferring failure to bounded workspace verification."
        }
        else {
            Write-Host "Stale workspace Unreal process pid=$TargetProcessId exited before taskkill completed."
        }
    }
}

$ProcessDeadline = [DateTime]::UtcNow.AddSeconds($ProcessExitTimeoutSec)
do {
    $Remaining = @(Get-WorkspaceUnrealProcesses)
    if ($Remaining.Count -eq 0) {
        break
    }
    Start-Sleep -Milliseconds 100
} while ([DateTime]::UtcNow -lt $ProcessDeadline)

if ($Remaining.Count -gt 0) {
    $Description = $Remaining |
        ForEach-Object { "{0} pid={1}" -f $_.Name, $_.ProcessId }
    throw ("Workspace-scoped Unreal process tree remained alive: {0}" -f ($Description -join ', '))
}

$LockedLog = Join-Path $Workspace 'Saved/Logs/YetAnotherCyclingSim.log'
if (Test-Path -LiteralPath $LockedLog -PathType Leaf) {
    $Attempts = [Math]::Max(1, $LogReleaseTimeoutSec * 4)
    $LastDeleteError = $null
    for ($Attempt = 1; $Attempt -le $Attempts; $Attempt++) {
        try {
            Remove-Item -LiteralPath $LockedLog -Force -ErrorAction Stop
            $LastDeleteError = $null
            break
        }
        catch {
            $LastDeleteError = $_
            Start-Sleep -Milliseconds 250
        }
    }

    if (Test-Path -LiteralPath $LockedLog -PathType Leaf) {
        $Lockers = @(Get-FileLockingProcesses -Path $LockedLog)
        $KnownUnrealProcessNames = @(
            $Names |
                ForEach-Object { [System.IO.Path]::GetFileNameWithoutExtension($_) }
        )
        $KilledKnownLocker = $false

        foreach ($Locker in $Lockers) {
            Write-Warning (
                "Restart Manager locker: name={0} pid={1}" -f
                    $Locker.ProcessName,
                    $Locker.ProcessId
            )

            if ($Locker.ProcessName -in $KnownUnrealProcessNames) {
                Write-Host (
                    "Stopping known Unreal locker {0} pid={1} for exact workspace log." -f
                        $Locker.ProcessName,
                        $Locker.ProcessId
                )
                & taskkill.exe /PID ([int]$Locker.ProcessId) /T /F | Write-Host
                $KilledKnownLocker = $true
            }
        }

        if ($KilledKnownLocker) {
            $PostKillAttempts = [Math]::Max(1, $LogReleaseTimeoutSec * 4)
            for ($Attempt = 1; $Attempt -le $PostKillAttempts; $Attempt++) {
                try {
                    Remove-Item -LiteralPath $LockedLog -Force -ErrorAction Stop
                    $LastDeleteError = $null
                    break
                }
                catch {
                    $LastDeleteError = $_
                    Start-Sleep -Milliseconds 250
                }
            }
        }

        if (Test-Path -LiteralPath $LockedLog -PathType Leaf) {
            $ExitedWorkspaceUnrealPids = @(
                Get-CimInstance Win32_Process -ErrorAction Stop |
                    Where-Object {
                        $_.Name -in $Names -and
                        $_.CommandLine -and
                        $_.CommandLine.IndexOf(
                            $Workspace,
                            [System.StringComparison]::OrdinalIgnoreCase
                        ) -ge 0 -and
                        -not (Test-NativeProcessAlive -ProcessId ([int]$_.ProcessId))
                    } |
                    ForEach-Object { [int]$_.ProcessId }
            )
            $OnlyExitedWorkspaceUnrealLockers = (
                $Lockers.Count -gt 0 -and
                @(
                    $Lockers |
                        Where-Object {
                            $_.ProcessName -ne '<exited>' -or
                            [int]$_.ProcessId -notin $ExitedWorkspaceUnrealPids
                        }
                ).Count -eq 0
            )

            if ($OnlyExitedWorkspaceUnrealLockers) {
                $LockerSummary = ($Lockers | ForEach-Object { "pid={0}" -f $_.ProcessId }) -join ', '
                Write-Warning (
                    "Preserving stale locked workspace log owned only by exited workspace Unreal record(s): {0}. " +
                    "CI must use per-run -AbsLog paths and exclude only this exact file from git clean." -f
                        $LockerSummary
                )
            }
            else {
                Write-WorkspaceLockDiagnostics
                $LockerSummary = if ($Lockers.Count -gt 0) {
                    ($Lockers | ForEach-Object { "{0} pid={1}" -f $_.ProcessName, $_.ProcessId }) -join ', '
                }
                else {
                    '<Restart Manager reported no locker>'
                }
                throw (
                    "Workspace log lock did not clear within {0} seconds; lockers: {1}; last error: {2}" -f
                        $LogReleaseTimeoutSec,
                        $LockerSummary,
                        $LastDeleteError.Exception.Message
                )
            }
        }
    }
}

Write-Host ("Workspace lock cleanup: PASS ({0} stale Unreal process candidate(s))." -f $Stale.Count)

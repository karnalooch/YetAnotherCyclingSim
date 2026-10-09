#requires -Version 7.4
<#
.SYNOPSIS
    Reports who currently owns the shared YACS Unreal host.

.DESCRIPTION
    Classifies live Unreal Editor processes on the home workstation as either
    repository-owned unattended CI processes or local/unknown interactive work.
    This helper is read-only and never terminates a process.
#>
[CmdletBinding()]
param([switch] $AsJson)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Names = @('UnrealEditor.exe', 'UnrealEditor-Cmd.exe')
$RemoteMarkers = @(
    '_unreal-ci-warm',
    '_stage3g-full-worktree',
    'texture-prep-plugin-',
    'Saved\RuntimeProof\CI\Unreal',
    'Saved/RuntimeProof/CI/Unreal'
)

$Remote = [System.Collections.Generic.List[object]]::new()
$Local = [System.Collections.Generic.List[object]]::new()
$StaleCim = [System.Collections.Generic.List[object]]::new()

foreach ($Candidate in @(
    Get-CimInstance Win32_Process -ErrorAction Stop |
        Where-Object { $_.Name -in $Names }
)) {
    $Native = Get-Process -Id ([int]$Candidate.ProcessId) -ErrorAction SilentlyContinue
    $Record = [pscustomobject]@{
        name = [string]$Candidate.Name
        process_id = [int]$Candidate.ProcessId
        parent_process_id = [int]$Candidate.ParentProcessId
        executable_path = [string]$Candidate.ExecutablePath
        command_line = [string]$Candidate.CommandLine
        creation_date = if ($Candidate.CreationDate) {
            ([DateTime]$Candidate.CreationDate).ToUniversalTime().ToString('o')
        } else {
            $null
        }
        session_id = if ($Native) { $Native.SessionId } else { $null }
        owner = $null
    }

    if (-not $Native -or $Native.HasExited) {
        $Record.owner = 'stale_cim'
        [void]$StaleCim.Add($Record)
        continue
    }

    $CommandLine = [string]$Candidate.CommandLine
    $IsUnattended = (
        $CommandLine -and
        $CommandLine.IndexOf('-Unattended', [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    )
    $HasRemoteMarker = $false
    if ($CommandLine) {
        foreach ($Marker in $RemoteMarkers) {
            if ($CommandLine.IndexOf($Marker, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
                $HasRemoteMarker = $true
                break
            }
        }
    }

    if ($IsUnattended -and $HasRemoteMarker) {
        $Record.owner = 'remote_ci'
        [void]$Remote.Add($Record)
    }
    else {
        # Unknown/no-command-line processes are deliberately treated as local
        # ownership so remote automation yields rather than guessing.
        $Record.owner = 'local_or_unknown'
        [void]$Local.Add($Record)
    }
}

$Status = if ($Remote.Count -eq 0 -and $Local.Count -eq 0) {
    'IDLE'
}
elseif ($Remote.Count -gt 0 -and $Local.Count -eq 0) {
    'REMOTE_BUSY'
}
elseif ($Remote.Count -eq 0 -and $Local.Count -gt 0) {
    'LOCAL_BUSY'
}
else {
    'MIXED_BUSY'
}

$Result = [pscustomobject]@{
    schema_version = 1
    status = $Status
    hostname = $env:COMPUTERNAME
    checked_at_utc = [DateTime]::UtcNow.ToString('o')
    remote_ci_count = $Remote.Count
    local_or_unknown_count = $Local.Count
    stale_cim_record_count = $StaleCim.Count
    remote_ci_processes = @($Remote)
    local_or_unknown_processes = @($Local)
    stale_cim_records = @($StaleCim)
}

if ($AsJson) {
    $Result | ConvertTo-Json -Depth 8
}
else {
    $Result
}

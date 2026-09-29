<#
.SYNOPSIS
    Execute one allowlisted YACS remote Unreal Editor command.

.DESCRIPTION
    This is the fail-closed execution boundary used by the GitHub remote editor
    command bridge. It accepts only named repository-owned commands. No command
    text, Python source, shell fragment, asset path, map path, or arbitrary
    parameter from a GitHub comment is ever executed.

    The initial spike exposes only smoke-cube. It starts UnrealEditor-Cmd with a
    fixed repository script, spawns a transient cube, destroys it, writes proof,
    and verifies that the Git worktree remains unchanged.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('smoke-cube')]
    [string] $Command,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string] $ExpectedHead
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$ProjectPath = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject'
$ProofRoot = Join-Path $RepoRoot 'Saved/RuntimeProof/RemoteEditor'
$ProofPath = Join-Path $ProofRoot 'remote_editor_smoke.json'
$SummaryPath = Join-Path $ProofRoot 'remote_editor_command_summary.json'
$UnrealLogPath = Join-Path $ProofRoot 'unreal_remote_editor.log'
$SmokeScript = Join-Path $PSScriptRoot 'remote_editor_smoke.py'
$PreflightScript = Join-Path $PSScriptRoot 'Preflight-YacsProof.ps1'

New-Item -ItemType Directory -Path $ProofRoot -Force | Out-Null

foreach ($required in @($ProjectPath, $SmokeScript, $PreflightScript)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required remote editor input is missing: $required"
    }
}

Push-Location -LiteralPath $RepoRoot
try {
    $ActualHead = (& git rev-parse HEAD).Trim()
    if ($ActualHead -ne $ExpectedHead) {
        throw "Remote editor checkout HEAD '$ActualHead' != expected '$ExpectedHead'."
    }

    if (git status --porcelain) {
        throw 'Remote editor requires a clean Git worktree before Unreal starts.'
    }
}
finally {
    Pop-Location
}

$Preflight = & $PreflightScript -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ExpectedBranch 'HEAD' -ExpectedHead $ExpectedHead -ArtifactRoot (Join-Path $ProofRoot 'Preflight')

if (-not $Preflight) {
    throw 'Unreal preflight did not return context.'
}

$UnrealEditorCmd = [string] $Preflight.UnrealEditorCmdPath
if (-not $UnrealEditorCmd -or -not (Test-Path -LiteralPath $UnrealEditorCmd -PathType Leaf)) {
    throw 'Preflight did not resolve UnrealEditor-Cmd.exe.'
}

if ($Preflight.EngineVersion.MajorVersion -ne 5 -or $Preflight.EngineVersion.MinorVersion -ne 8) {
    throw "Remote editor spike requires Unreal Engine 5.8.x; found $($Preflight.EngineVersion.MajorVersion).$($Preflight.EngineVersion.MinorVersion).$($Preflight.EngineVersion.PatchVersion)."
}

Remove-Item -LiteralPath $ProofPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $UnrealLogPath -Force -ErrorAction SilentlyContinue

switch ($Command) {
    'smoke-cube' {
        $env:YACS_REMOTE_PROOF_PATH = $ProofPath
        try {
            $Arguments = @(
                $ProjectPath,
                "-ExecutePythonScript=$SmokeScript",
                '-unattended',
                '-nop4',
                '-nosplash',
                '-NoSound',
                '-UTF8Output',
                "-abslog=$UnrealLogPath"
            )

            Write-Host "Launching trusted Unreal remote command '$Command' at $ExpectedHead."
            & $UnrealEditorCmd @Arguments
            $ExitCode = $LASTEXITCODE
        }
        finally {
            Remove-Item Env:YACS_REMOTE_PROOF_PATH -ErrorAction SilentlyContinue
        }

        if ($ExitCode -ne 0) {
            if (Test-Path -LiteralPath $UnrealLogPath -PathType Leaf) {
                Write-Host '===== Unreal remote editor log tail =====' -ForegroundColor Yellow
                Get-Content -LiteralPath $UnrealLogPath -Tail 220 | ForEach-Object { Write-Host $_ }
                Write-Host '===== End Unreal remote editor log tail =====' -ForegroundColor Yellow
            }
            throw "Unreal remote editor command exited with code $ExitCode. See $UnrealLogPath."
        }
    }
    default {
        throw "Unsupported remote editor command '$Command'."
    }
}

if (-not (Test-Path -LiteralPath $ProofPath -PathType Leaf)) {
    throw "Remote editor proof file was not created: $ProofPath"
}

$Proof = Get-Content -LiteralPath $ProofPath -Raw | ConvertFrom-Json
if ($Proof.command -ne 'smoke-cube') {
    throw "Unexpected proof command '$($Proof.command)'."
}
if ($Proof.actor_label -ne 'YACS_REMOTE_SMOKE_CUBE') {
    throw "Unexpected actor label '$($Proof.actor_label)'."
}
if (-not [bool] $Proof.transient -or -not [bool] $Proof.destroyed) {
    throw 'Remote editor smoke did not prove transient spawn + destruction.'
}
if ([bool] $Proof.map_saved -or [bool] $Proof.persistent_asset_created) {
    throw 'Remote editor smoke reported a forbidden persistent mutation.'
}

Push-Location -LiteralPath $RepoRoot
try {
    $DirtyAfter = @(git status --porcelain)
}
finally {
    Pop-Location
}
if ($DirtyAfter.Count -gt 0) {
    throw "Remote editor changed tracked/untracked repository state: $($DirtyAfter -join '; ')"
}

$Summary = [ordered]@{
    TimestampUtc = (Get-Date).ToUniversalTime().ToString('o')
    Command = $Command
    ExpectedHead = $ExpectedHead
    ActualHead = $ActualHead
    UnrealEditorCmd = $UnrealEditorCmd
    EngineVersion = $Preflight.EngineVersion
    ProofPath = $ProofPath
    UnrealLogPath = $UnrealLogPath
    WorktreeCleanAfter = $true
    PersistentMutationAllowed = $false
    Status = 'PASS'
}
$Summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $SummaryPath -Encoding UTF8

Write-Host 'YACS remote editor command: PASS' -ForegroundColor Green
Write-Host "  command : $Command"
Write-Host "  proof   : $ProofPath"
Write-Host "  log     : $UnrealLogPath"

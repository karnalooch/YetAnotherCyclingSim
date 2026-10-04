#requires -Version 7.4
<#
.SYNOPSIS
    Restores and verifies the admitted Sa Calobra CNIG raw source snapshot.

.DESCRIPTION
    Uses authenticated GitHub CLI access to read the unpublished draft release.
    Existing files are never overwritten. Every local and remote raw file must
    match the tracked receipt by delivered filename, byte size and SHA-256.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path,
    [string] $Destination = '',
    [string] $Repository = 'karnalooch/YetAnotherCyclingSim',
    [string] $ReleaseTag = 'data-cnig-sa-calobra-working-v1-2026-10-03',
    [switch] $Apply,
    [switch] $Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = [System.IO.Path]::GetFullPath($RepoRoot).TrimEnd('\')
if (-not $Destination) {
    $WorkspaceConfig = Join-Path (Split-Path -Parent $RepoRoot) 'workspace.json'
    if ($env:YACS_WORKSPACE_CONFIG) { $WorkspaceConfig = $env:YACS_WORKSPACE_CONFIG }
    if (-not (Test-Path -LiteralPath $WorkspaceConfig -PathType Leaf)) {
        throw 'Pass -Destination explicitly on CI, or configure the canonical local workspace.'
    }
    $Workspace = Get-Content -LiteralPath $WorkspaceConfig -Raw | ConvertFrom-Json
    $RelativeData = [string]$Workspace.data
    if ([int]$Workspace.schema_version -ne 1 -or [IO.Path]::IsPathRooted($RelativeData) -or $RelativeData -match '(^|[\\/])\.\.([\\/]|$)') {
        throw 'Invalid workspace data path.'
    }
    $Destination = Join-Path (Split-Path -Parent $WorkspaceConfig) "$RelativeData/world-data/sa-calobra-working-v1/manual-cnig"
}
$Destination = [System.IO.Path]::GetFullPath($Destination).TrimEnd('\')
$DestinationRoot = [System.IO.Path]::GetPathRoot($Destination).TrimEnd('\')
if ($Destination -eq $DestinationRoot -or $Destination.Length -le ($DestinationRoot.Length + 3)) {
    throw "Unsafe world-data destination: $Destination"
}

$ReceiptPath = Join-Path $RepoRoot 'worldgen/terrain/benchmarks/sa_calobra/world_data/manual_cnig_receipt_2026-10-03.json'
if (-not (Test-Path -LiteralPath $ReceiptPath -PathType Leaf)) {
    throw "Tracked CNIG receipt is missing: $ReceiptPath"
}
$Receipt = Get-Content -LiteralPath $ReceiptPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
if ([int]$Receipt.verification.file_count -ne 17 -or [int64]$Receipt.verification.total_size_bytes -ne 3339596438) {
    throw 'Tracked CNIG receipt does not contain the admitted 17-file / 3,339,596,438-byte snapshot.'
}

$Expected = @{}
foreach ($File in $Receipt.files) {
    if ($Expected.ContainsKey([string]$File.delivered_name)) {
        throw "Duplicate delivered name in receipt: $($File.delivered_name)"
    }
    $Expected[[string]$File.delivered_name] = $File
}

$Gh = Get-Command gh -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $Gh) { throw 'GitHub CLI is required. Install gh and run gh auth login.' }
& gh auth status --hostname github.com *> $null
if ($LASTEXITCODE -ne 0) { throw 'GitHub CLI is not authenticated to github.com.' }

$ReleaseJson = (& gh release view $ReleaseTag --repo $Repository --json tagName,isDraft,assets,url 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { throw "Cannot read draft release '$ReleaseTag': $ReleaseJson" }
$Release = $ReleaseJson | ConvertFrom-Json -ErrorAction Stop
if (-not $Release.isDraft) { throw "Release '$ReleaseTag' is not an unpublished draft; refusing the private-source restore path." }

$Remote = @{}
foreach ($Asset in $Release.assets) {
    if ($Remote.ContainsKey([string]$Asset.name)) { throw "Duplicate remote asset: $($Asset.name)" }
    $Remote[[string]$Asset.name] = $Asset
}
$RemoteProblems = [System.Collections.Generic.List[string]]::new()
$UnexpectedRemoteRaw = @(
    $Remote.Keys |
        Where-Object { $_ -match '\.(?:laz|tif)$' -and -not $Expected.ContainsKey($_) } |
        Sort-Object
)
foreach ($Name in $UnexpectedRemoteRaw) {
    [void]$RemoteProblems.Add("unexpected remote raw file $Name")
}
foreach ($Name in $Expected.Keys) {
    $File = $Expected[$Name]
    if (-not $Remote.ContainsKey($Name)) {
        [void]$RemoteProblems.Add("missing remote file $Name")
        continue
    }
    $Asset = $Remote[$Name]
    if ([int64]$Asset.size -ne [int64]$File.size_bytes) { [void]$RemoteProblems.Add("remote size mismatch $Name") }
    if ([string]$Asset.digest -ne ('sha256:' + [string]$File.sha256)) { [void]$RemoteProblems.Add("remote SHA-256 mismatch $Name") }
    if ([string]$Asset.state -ne 'uploaded') { [void]$RemoteProblems.Add("remote state $Name=$($Asset.state)") }
}
if ($RemoteProblems.Count -gt 0) {
    throw ('Draft release verification failed: ' + ($RemoteProblems -join '; '))
}

function Get-LocalState {
    $Problems = [System.Collections.Generic.List[string]]::new()
    $Verified = 0
    $VerifiedBytes = 0L
    $Missing = [System.Collections.Generic.List[string]]::new()

    if (Test-Path -LiteralPath $Destination -PathType Container) {
        $Unexpected = @(
            Get-ChildItem -LiteralPath $Destination -File -Force |
                Where-Object { -not $Expected.ContainsKey($_.Name) }
        )
        foreach ($Item in $Unexpected) { [void]$Problems.Add("unexpected local file $($Item.Name)") }
    }

    foreach ($Name in ($Expected.Keys | Sort-Object)) {
        $Pinned = $Expected[$Name]
        $Path = Join-Path $Destination $Name
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
            [void]$Missing.Add($Name)
            continue
        }
        $Item = Get-Item -LiteralPath $Path
        if ([int64]$Item.Length -ne [int64]$Pinned.size_bytes) {
            [void]$Problems.Add("local size mismatch $Name")
            continue
        }
        $Hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($Hash -ne [string]$Pinned.sha256) {
            [void]$Problems.Add("local SHA-256 mismatch $Name")
            continue
        }
        $Verified++
        $VerifiedBytes += [int64]$Item.Length
    }

    return [pscustomobject]@{
        Verified = $Verified
        VerifiedBytes = $VerifiedBytes
        Missing = @($Missing)
        Problems = @($Problems)
    }
}

$Before = Get-LocalState
if ($Before.Problems.Count -gt 0) {
    throw ('Existing destination failed closed; no file was overwritten: ' + ($Before.Problems -join '; '))
}

if ($Apply -and $Before.Missing.Count -gt 0) {
    [void][System.IO.Directory]::CreateDirectory($Destination)
    & gh release download $ReleaseTag --repo $Repository --dir $Destination --pattern '*.laz' --pattern '*.tif' --skip-existing
    if ($LASTEXITCODE -ne 0) { throw "GitHub release download failed with exit code $LASTEXITCODE." }
}

$After = Get-LocalState
if ($After.Problems.Count -gt 0) {
    throw ('Restored destination verification failed: ' + ($After.Problems -join '; '))
}
if ($Apply -and ($After.Missing.Count -ne 0 -or $After.Verified -ne 17 -or $After.VerifiedBytes -ne 3339596438)) {
    throw "Restore incomplete: verified=$($After.Verified), bytes=$($After.VerifiedBytes), missing=$($After.Missing.Count)."
}

$Payload = [ordered]@{
    schema_version = 1
    apply = [bool]$Apply
    release_tag = $ReleaseTag
    release_url = [string]$Release.url
    release_is_draft = [bool]$Release.isDraft
    destination = $Destination
    remote_file_count = 17
    remote_bytes = 3339596438
    local_verified_file_count = [int]$After.Verified
    local_verified_bytes = [int64]$After.VerifiedBytes
    missing_count = [int]$After.Missing.Count
    missing = @($After.Missing)
    status = $(if ($After.Verified -eq 17 -and $After.VerifiedBytes -eq 3339596438) { 'PASS' } elseif ($Apply) { 'FAIL' } else { 'PREVIEW' })
}

if ($Json) {
    $Payload | ConvertTo-Json -Depth 4
}
else {
    Write-Host ("CNIG restore: {0}" -f $Payload.status)
    Write-Host ("Draft release: {0}" -f $ReleaseTag)
    Write-Host ("Destination: {0}" -f $Destination)
    Write-Host ("Verified: {0}/17 files, {1}/3339596438 bytes" -f $After.Verified, $After.VerifiedBytes)
    if (-not $Apply -and $After.Missing.Count -gt 0) {
        Write-Host ("Preview only: {0} files would be downloaded. Re-run with -Apply." -f $After.Missing.Count)
    }
}

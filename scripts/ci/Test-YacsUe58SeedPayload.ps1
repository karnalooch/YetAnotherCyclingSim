<#
.SYNOPSIS
    Validate a staged/restored UE 5.8 seed payload with progress output.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string] $SeedRoot,
    [string] $SuccessLabel = 'UE SEED PAYLOAD PASS',
    [int] $ProgressSeconds = 30
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-FileSha256HexWithProgress {
    param(
        [Parameter(Mandatory=$true)][string] $Path,
        [int] $ProgressSeconds = 30
    )

    $file = Get-Item -LiteralPath $Path
    $totalBytes = [int64]$file.Length
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($Path)
    $buffer = New-Object byte[] (8MB)
    $processed = [int64]0
    $progress = [System.Diagnostics.Stopwatch]::StartNew()

    try {
        while (($read = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            [void]$sha256.TransformBlock($buffer, 0, $read, $buffer, 0)
            $processed += $read

            if ($progress.Elapsed.TotalSeconds -ge $ProgressSeconds) {
                Write-Host ("Hashing UE seed: {0:N3}/{1:N3} GiB ({2:N1}%)" -f ($processed / 1GB), ($totalBytes / 1GB), (($processed / [double]$totalBytes) * 100))
                $progress.Restart()
            }
        }

        [void]$sha256.TransformFinalBlock([byte[]]::new(0), 0, 0)
        Write-Host ("Hashing UE seed complete: {0:N3} GiB" -f ($processed / 1GB))
        return ([System.BitConverter]::ToString($sha256.Hash)).Replace('-', '').ToLowerInvariant()
    } finally {
        $stream.Dispose()
        $sha256.Dispose()
    }
}

$archive = Join-Path $SeedRoot 'ue58-win64.zip'
$manifestPath = Join-Path $SeedRoot 'ue58-win64-manifest.json'

if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) {
    throw "UE seed archive missing: $archive"
}
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "UE seed manifest missing: $manifestPath"
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$archiveBytes = (Get-Item -LiteralPath $archive).Length

if ($archiveBytes -lt 1GB) {
    throw ("UE seed archive is implausibly small: {0} bytes." -f $archiveBytes)
}
if ([int64]$manifest.ArchiveBytes -ne [int64]$archiveBytes) {
    throw ("UE seed size mismatch: manifest={0}, actual={1}." -f $manifest.ArchiveBytes, $archiveBytes)
}
if (-not [bool]$manifest.ArchiveCreated -or -not [bool]$manifest.ArchiveIntegrityValidated) {
    throw 'UE seed manifest is not integrity-validated.'
}

$actualHash = Get-FileSha256HexWithProgress -Path $archive -ProgressSeconds $ProgressSeconds
if ($actualHash -ne [string]$manifest.ArchiveSha256) {
    throw 'UE seed SHA256 mismatch.'
}

Write-Host ("{0}: {1:N3} GiB, SHA256={2}" -f $SuccessLabel, ($archiveBytes / 1GB), $actualHash)
